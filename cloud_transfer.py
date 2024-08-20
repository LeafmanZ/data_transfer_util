import argparse
from utils import read_config, is_endpoint_healthy, list_objects, write_json, update_json, create_client
import subprocess
from concurrent.futures import ThreadPoolExecutor, wait
import time
import os

###
# BEGIN: LOAD IN CONFIGURATIONS
###
parser = argparse.ArgumentParser(description='Using a config.yaml move data between storage environments')
parser.add_argument('config', type=str, help='The config.yaml that specifies your data transfer.')
args = parser.parse_args()

config = read_config(args.config)

if not config:
    print("Failed to read the configuration.")

src_service = config["src"]["service"]
src_bucket = config["src"]["bucket"]
src_prefix = config["src"]["bucket_prefix"]
src_region = config["src"]["region"]
src_access_key = config['src']['access_key']
src_secret_access_key = config['src']['secret_access_key']
src_endpoint_urls = config['src']['endpoint_urls']

dst_service = config["dst"]["service"]
dst_bucket = config["dst"]["bucket"]
dst_prefix = config["dst"]["bucket_prefix"]
dst_region = config["dst"]["region"]
dst_access_key = config['dst']['access_key']
dst_secret_access_key = config['dst']['secret_access_key']
dst_endpoint_urls = config['dst']['endpoint_urls']

log_local_directory = config['log']['local_directory']

# Filter out unhealthy endpoints
tmp_endpoint_urls = []
for src_endpoint_url in src_endpoint_urls:
    print(f'Checking source endpoint: {src_endpoint_url}')
    src_client = create_client(src_service, src_access_key, src_secret_access_key, src_region, src_endpoint_url)
    if is_endpoint_healthy(src_service, src_bucket, src_prefix, src_client, isSnow=(src_region=='snow')):
        tmp_endpoint_urls.append(src_endpoint_url)
src_endpoint_urls = tmp_endpoint_urls
        
tmp_endpoint_urls = []
for dst_endpoint_url in dst_endpoint_urls:
    print(f'Checking destination endpoint: {dst_endpoint_url}')
    dst_client = create_client(dst_service, dst_access_key, dst_secret_access_key, dst_region, dst_endpoint_url)
    if is_endpoint_healthy(dst_service, dst_bucket, dst_prefix, dst_client, isSnow=(dst_region=='snow')):
        tmp_endpoint_urls.append(dst_endpoint_url)
dst_endpoint_urls = tmp_endpoint_urls

max_workers = os.cpu_count()//3
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

data_transfer_data_json_dir = os.path.join(log_local_directory, f"data_transfer_data_{int(start_time)}.json")
data_transfer_data_dict = {
    "src_service": src_service,
    "src_bucket": src_bucket,
    "src_prefix": src_prefix,
    "src_region": src_region,
    "src_endpoint_urls": src_endpoint_urls,
    "dst_service": dst_service,
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
    "total_equivalent_gigabytes_to_move": False,
    "bytes_transferred": False,
    "equivalent_gigabytes_transferred": False,
    "remaining_bytes": False,
    "equivalent_remaining_bytes": False,
    "failed_objects": {}
}

write_json(data_transfer_data_json_dir, data_transfer_data_dict)
print(f"Configuration details saved to {data_transfer_data_json_dir}")
###
# END: SAVE CONFIGURATION INFORMATION TO JSON 
###
try:
    # create our source and destination clients so we can interact with our buckets
    src_client = create_client(src_service, src_access_key, src_secret_access_key, src_region, src_endpoint_urls[0])
    dst_client = create_client(dst_service, dst_access_key, dst_secret_access_key, dst_region, dst_endpoint_urls[0])

    # Get the objects in our destination and source buckets to compare missing objects
    src_objects = list_objects(src_service, src_bucket, src_prefix, src_client, isSnow=(src_region=='snow'))
    dst_objects = list_objects(dst_service, dst_bucket, dst_prefix, dst_client, isSnow=(dst_region=='snow'))

    # Dictionary of objects that have been successfully moved and are identical in both source and destination
    objects_synced = {key: src_objects[key] for key in src_objects if (key in dst_objects and src_objects[key] == dst_objects[key])}
    # Dictionary of objects that have not been moved or differ from the source to destination
    objects_not_synced = {key: src_objects[key] for key in src_objects if (key not in dst_objects or src_objects[key] != dst_objects[key])}

    total_bytes_to_move = sum(objects_not_synced.values())
    total_objects_to_move = len(objects_not_synced)
    ###
    # BEGIN: UPDATE BUCKET OBJECT INFORMATION
    ###
    update_data_transfer_data_dict = {"initial_synced_objects": len(objects_synced),
                        "initial_unsynced_objects": len(objects_not_synced),
                        "final_synced_objects": len(objects_synced),
                        "final_unsynced_objects": len(objects_not_synced),
                        "completion_percentage": 100*len(objects_synced)/(len(objects_synced)+len(objects_not_synced)),
                        "total_bytes_to_move": total_bytes_to_move,
                        "total_equivalent_gigabytes_to_move": float(f"{(total_bytes_to_move/1073741824):.3f}")}
    update_json(data_transfer_data_json_dir, update_data_transfer_data_dict)
    ###
    # END: UPDATE BUCKET OBJECT INFORMATION
    ###

    # Distribute endpoint_urls evenly over the amount of objects we need to move
    endpoint_url_distribution = []
    for i in range(len(objects_not_synced)):
        inbound = src_endpoint_urls[i % len(src_endpoint_urls)]
        outbound = dst_endpoint_urls[i % len(dst_endpoint_urls)]
        endpoint_url_distribution.append((inbound, outbound))

    # Function to run the cloud_sync_obj.py script, this is necessary to avoid GIL bottleneck
    def cloud_sync_obj(src_service, dst_service, src_bucket, dst_bucket, src_key, dst_key, bytes, src_endpoint_url, dst_endpoint_url, data_transfer_data_json_dir, benchmark_progress):
        command = f'python cloud_sync_obj.py "{src_service}" "{dst_service}" "{src_bucket}" "{dst_bucket}" "{src_key}" "{dst_key}" "{bytes}" "{src_endpoint_url}" "{dst_endpoint_url}" "{data_transfer_data_json_dir}" "{args.config}"'
        subprocess.run(command, shell=True, check=True)
        if benchmark_progress:
            # Get the objects in our destination buckets to compare missing objects
            dst_objects = list_objects(dst_service, dst_bucket, dst_prefix, dst_client, isSnow=(dst_region=='snow'))

            # Dictionary of objects that have been successfully moved and are identical in both source and destination
            objects_synced = {key: src_objects[key] for key in src_objects if (key in dst_objects and src_objects[key] == dst_objects[key])}
            # Dictionary of objects that have not been moved or differ from the source to destination
            objects_not_synced = {key: src_objects[key] for key in src_objects if (key not in dst_objects or src_objects[key] != dst_objects[key])}

            ###
            # BEGIN: UPDATE BUCKET OBJECT INFORMATION
            ###
            update_data_transfer_data_dict = {"final_synced_objects": len(objects_synced),
                                "final_unsynced_objects": len(objects_not_synced),
                                "completion_percentage": 100 * len(objects_synced)/(len(objects_synced)+len(objects_not_synced)),
                                "bytes_transferred": min(sum(objects_synced.values()), total_bytes_to_move),
                                "equivalent_gigabytes_transferred": float(f"{(min(sum(objects_synced.values()), total_bytes_to_move)/1073741824):.3f}"),
                                "remaining_bytes": sum(objects_not_synced.values()),
                                "equivalent_remaining_bytes": float(f"{(sum(objects_not_synced.values())/1073741824):.3f}")}
            update_json(data_transfer_data_json_dir, update_data_transfer_data_dict)
            ###
            # END: UPDATE BUCKET OBJECT INFORMATION
            ###

    # Spawn individual cloud_sync_obj processes moving 1 object per process, in parallel up to the amount of max_workers at a time.
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
            futures.append(executor.submit(cloud_sync_obj, src_service, dst_service, src_bucket, dst_bucket, src_key, dst_key, objects_not_synced[obj_key],src_endpoint_url, dst_endpoint_url, data_transfer_data_json_dir, benchmark_progress))

        # Wait for all futures to complete
        wait(futures)

    end_time = time.time()
    total_time = end_time - start_time
    print(f"Total time taken: {total_time:.2f} seconds")

    ###
    # BEGIN: SAVE FINISHING COMPLETION INFORMATION TO JSON
    ###
    # Get the objects in our destination buckets to compare missing objects
    dst_objects = list_objects(dst_service, dst_bucket, dst_prefix, dst_client, isSnow=(dst_region=='snow'))

    # Dictionary of objects that have been successfully moved and are identical in both source and destination
    objects_synced = {key: src_objects[key] for key in src_objects if (key in dst_objects and src_objects[key] == dst_objects[key])}
    # Dictionary of objects that have not been moved or differ from the source to destination
    objects_not_synced = {key: src_objects[key] for key in src_objects if (key not in dst_objects or src_objects[key] != dst_objects[key])}

    new_data_transfer_data_dict = {'final_synced_objects': len(objects_synced),
                        'final_unsynced_objects': len(objects_not_synced),
                        "completion_percentage": 100 * len(objects_synced)/(len(objects_synced)+len(objects_not_synced)),
                        "bytes_transferred": min(sum(objects_synced.values()), total_bytes_to_move),
                        "equivalent_gigabytes_transferred": float(f"{(min(sum(objects_synced.values()), total_bytes_to_move)/1073741824):.3f}"),
                        "remaining_bytes": sum(objects_not_synced.values()),
                        "equivalent_remaining_bytes": float(f"{(sum(objects_not_synced.values())/1073741824):.3f}"),
                        'failed_objects': objects_not_synced,
                        'end_time_epoch': int(end_time),
                        'total_duration_seconds': total_time,
                        'speed_gbps': float(f"{((min(sum(objects_synced.values()), total_bytes_to_move)/1073741824)*8/total_time):.3f}"),
                        'status': 'Completed'}
    update_json(data_transfer_data_json_dir, new_data_transfer_data_dict)
except:
    new_data_transfer_data_dict = {
        'status': 'Failed'
    }
    update_json(data_transfer_data_json_dir, new_data_transfer_data_dict)
###
# END: SAVE FINISHING COMPLETION INFORMATION TO JSON
###
