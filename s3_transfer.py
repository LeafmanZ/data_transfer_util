from util_s3 import read_config, list_objects, create_s3_client, write_json, update_json
import subprocess
from concurrent.futures import ThreadPoolExecutor, wait
import time
import os

###
# BEGIN: LOAD IN CONFIGURATIONS
###
config = read_config()

if not config:
    print("Failed to read the configuration.")

src_bucket = config["src"]["bucket"]
src_prefix = config["src"]["bucket_prefix"]
src_region = config["src"]["region"]
src_access_key = config['src']['access_key']
src_secret_access_key = config['src']['secret_access_key']
src_endpoint_urls = config['src']['endpoint_urls']

dst_bucket = config["dst"]["bucket"]
dst_prefix = config["dst"]["bucket_prefix"]
dst_region = config["dst"]["region"]
dst_access_key = config['dst']['access_key']
dst_secret_access_key = config['dst']['secret_access_key']
dst_endpoint_urls = config['dst']['endpoint_urls']

log_local_directory = config['log']['local_directory']

max_workers = os.cpu_count()
start_time = time.time()
###
# END: LOAD IN CONFIGURATIONS
###

###
# BEGIN: SAVE CONFIGURATION INFORMATION TO JSON
###
# Create log_local_directory subdir if it doesn't already exist
if not os.path.exists(log_local_directory):
    os.makedirs(log_local_directory)

dt_data_json_dir = os.path.join(log_local_directory, f"dt_data_{int(start_time)}.json")
dt_data_dict = {
    "service": "AWS",
    "src_bucket": src_bucket,
    "src_prefix": src_prefix,
    "src_region": src_region,
    "src_endpoint_urls": src_endpoint_urls,
    "dst_bucket": dst_bucket,
    "dst_prefix": dst_prefix,
    "dst_region": dst_region,
    "dst_endpoint_urls": dst_endpoint_urls,
    "max_workers": max_workers,
    "start_time_epoch": int(start_time),
    "status": "Running",
    "objects_moved": [],
    "end_time_epoch": False,
    "total_duration_seconds": False,
    "initial_synced_objects": False,
    "initial_unsynced_objects": False,
    "final_synced_objects": False,
    "final_unsynced_objects": False,
    "completion_percentage": False,
    "total_bytes_to_move": False,
    "bytes_transferred": False,
    "remaining_bytes": False,
    "failed_objects": {}
}

write_json(dt_data_json_dir, dt_data_dict)
print(f"Configuration details saved to {dt_data_json_dir}")
###
# END: SAVE CONFIGURATION INFORMATION TO JSON 
###
try:
    # create our source and destination s3 clients so we can interact with our buckets
    src_s3_client = create_s3_client(src_access_key, src_secret_access_key, src_region, src_endpoint_urls[0])
    dst_s3_client = create_s3_client(dst_access_key, dst_secret_access_key, dst_region, dst_endpoint_urls[0])

    # Get the objects in our destination and source buckets to compare missing objects
    src_objects = list_objects(src_bucket, src_prefix, src_s3_client, isSnow=(src_region=='snow'))
    dst_objects = list_objects(dst_bucket, dst_prefix, dst_s3_client, isSnow=(dst_region=='snow'))

    # Dictionary of objects that have been successfully moved and are identical in both source and destination
    objects_synced = {key: src_objects[key] for key in src_objects if (key in dst_objects and src_objects[key] == dst_objects[key])}
    # Dictionary of objects that have not been moved or differ from the source to destination
    objects_not_synced = {key: src_objects[key] for key in src_objects if (key not in dst_objects or src_objects[key] != dst_objects[key])}

    total_bytes_to_move = sum(objects_not_synced.values())
    total_objects_to_move = len(objects_not_synced)
    ###
    # BEGIN: UPDATE BUCKET OBJECT INFORMATION
    ###
    update_dt_data_dict = {"initial_synced_objects": len(objects_synced),
                        "initial_unsynced_objects": len(objects_not_synced),
                        "final_synced_objects": len(objects_synced),
                        "final_unsynced_objects": len(objects_not_synced),
                        "completion_percentage": len(objects_synced)/(len(objects_synced)+len(objects_not_synced)),
                        "total_bytes_to_move": total_bytes_to_move}
    update_json(dt_data_json_dir, update_dt_data_dict)
    ###
    # END: UPDATE BUCKET OBJECT INFORMATION
    ###

    # Distribute endpoint_urls evenly over the amount of objects we need to move
    endpoint_url_distribution = []
    for i in range(len(objects_not_synced)):
        inbound = src_endpoint_urls[i % len(src_endpoint_urls)]
        outbound = dst_endpoint_urls[i % len(dst_endpoint_urls)]
        endpoint_url_distribution.append((inbound, outbound))

    # Function to run the sync_s3_obj.py script, this is necessary to avoid GIL bottleneck
    def sync_s3_obj(src_bucket, dst_bucket, src_key, dst_key, bytes, src_endpoint_url, dst_endpoint_url, dt_data_json_dir, benchmark_progress):
        command = f"python sync_s3_obj.py {src_bucket} {dst_bucket} {src_key} {dst_key} {bytes} {src_endpoint_url} {dst_endpoint_url} {dt_data_json_dir}"
        subprocess.run(command, shell=True, check=True)
        if benchmark_progress:
            # Get the objects in our destination buckets to compare missing objects
            dst_objects = list_objects(dst_bucket, dst_prefix, dst_s3_client, isSnow=(dst_region=='snow'))

            # Dictionary of objects that have been successfully moved and are identical in both source and destination
            objects_synced = {key: src_objects[key] for key in src_objects if (key in dst_objects and src_objects[key] == dst_objects[key])}
            # Dictionary of objects that have not been moved or differ from the source to destination
            objects_not_synced = {key: src_objects[key] for key in src_objects if (key not in dst_objects or src_objects[key] != dst_objects[key])}

            ###
            # BEGIN: UPDATE BUCKET OBJECT INFORMATION
            ###
            update_dt_data_dict = {"final_synced_objects": len(objects_synced),
                                "final_unsynced_objects": len(objects_not_synced),
                                "completion_percentage": len(objects_synced)/(len(objects_synced)+len(objects_not_synced)),
                                "bytes_transferred": min(sum(objects_synced.values()), total_bytes_to_move),
                                "remaining_bytes": sum(objects_not_synced.values()),}
            update_json(dt_data_json_dir, update_dt_data_dict)
            ###
            # END: UPDATE BUCKET OBJECT INFORMATION
            ###

    # Spawn individual sync_s3_obj processes moving 1 object per process, in parallel up to the amount of max_workers at a time.
    with ThreadPoolExecutor(max_workers=max_workers) as executor:
        futures = []
        for i, obj_key in enumerate(objects_not_synced.keys()):
            src_key = f"{src_prefix.rstrip('/')}/{obj_key}".lstrip('/')
            dst_key = f"{dst_prefix.rstrip('/')}/{obj_key}".lstrip('/')
            src_endpoint_url, dst_endpoint_url = endpoint_url_distribution[i]
            if i % max_workers == 0: # Every nth object sync we spawn, update our sync status every update_benchmark_interval 
                benchmark_progress = True
            else:
                benchmark_progress = False
            futures.append(executor.submit(sync_s3_obj, src_bucket, dst_bucket, src_key, dst_key, objects_not_synced[obj_key],src_endpoint_url, dst_endpoint_url, dt_data_json_dir, benchmark_progress))

        # Wait for all futures to complete
        wait(futures)

    end_time = time.time()
    total_time = end_time - start_time
    print(f"Total time taken: {total_time:.2f} seconds")

    ###
    # BEGIN: SAVE FINISHING COMPLETION INFORMATION TO JSON
    ###
    # Get the objects in our destination buckets to compare missing objects
    dst_objects = list_objects(dst_bucket, dst_prefix, dst_s3_client, isSnow=(dst_region=='snow'))

    # Dictionary of objects that have been successfully moved and are identical in both source and destination
    objects_synced = {key: src_objects[key] for key in src_objects if (key in dst_objects and src_objects[key] == dst_objects[key])}
    # Dictionary of objects that have not been moved or differ from the source to destination
    objects_not_synced = {key: src_objects[key] for key in src_objects if (key not in dst_objects or src_objects[key] != dst_objects[key])}

    new_dt_data_dict = {'final_synced_objects': len(objects_synced),
                        'final_unsynced_objects': len(objects_not_synced),
                        "completion_percentage": len(objects_synced)/(len(objects_synced)+len(objects_not_synced)),
                        "bytes_transferred": min(sum(objects_synced.values()), total_bytes_to_move),
                        "remaining_bytes": sum(objects_not_synced.values()),
                        'failed_objects': objects_not_synced,
                        'end_time_epoch': int(end_time),
                        'total_duration_seconds': total_time,
                        'status': 'Completed'}
    update_json(dt_data_json_dir, new_dt_data_dict)
except:
    new_dt_data_dict = {
        'status': 'Failed'
    }
    update_json(dt_data_json_dir, new_dt_data_dict)
###
# END: SAVE FINISHING COMPLETION INFORMATION TO JSON
###
