from util_s3 import read_config, list_objects, create_s3_client
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
###
# END: LOAD IN CONFIGURATIONS
###

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

# Distribute endpoint_urls evenly over the amount of objects we need to move
endpoint_url_distribution = []
for i in range(len(objects_not_synced)):
    inbound = src_endpoint_urls[i % len(src_endpoint_urls)]
    outbound = dst_endpoint_urls[i % len(dst_endpoint_urls)]
    endpoint_url_distribution.append((inbound, outbound))

# Function to run the sync_s3_obj.py script, this is necessary to avoid GIL bottleneck
def sync_s3_obj(src_bucket, dst_bucket, src_key, dst_key, src_endpoint_url, dst_endpoint_url):
    command = f"python sync_s3_obj.py {src_bucket} {dst_bucket} {src_key} {dst_key} {src_endpoint_url} {dst_endpoint_url}"
    subprocess.run(command, shell=True, check=True)

# Measure the time taken to execute the concurrent futures
start_time = time.time()

# Check if objects_not_synced contains any objects
with ThreadPoolExecutor(max_workers=(os.cpu_count()//2)) as executor:
    futures = []
    for i, obj_key in enumerate(objects_not_synced.keys()):
        src_key = f"{src_prefix.rstrip('/')}/{obj_key}".lstrip('/')
        dst_key = f"{dst_prefix.rstrip('/')}/{obj_key}".lstrip('/')
        src_endpoint_url, dst_endpoint_url = endpoint_url_distribution[i]
        futures.append(executor.submit(sync_s3_obj, src_bucket, dst_bucket, src_key, dst_key, src_endpoint_url, dst_endpoint_url))

    # Wait for all futures to complete
    wait(futures)

end_time = time.time()
total_time = end_time - start_time

print(f"Total time taken: {total_time:.2f} seconds")
