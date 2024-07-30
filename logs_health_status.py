from util_s3 import read_config, create_s3_client, is_endpoint_healthy, write_json
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

###
# END: LOAD IN CONFIGURATIONS
###
# Create log_local_directory subdir if it doesn't already exist
if not os.path.exists(log_local_directory):
    os.makedirs(log_local_directory)

hs_data_json_dir = os.path.join(log_local_directory, f"hs_data_{int(time.time())}.json")

src_endpoint_urls_failed = []
for src_endpoint_url in src_endpoint_urls:
    print(f'Checking source endpoint: {src_endpoint_url}')
    src_s3_client = create_s3_client(src_access_key, src_secret_access_key, src_region, src_endpoint_url)
    if not is_endpoint_healthy(src_bucket, src_prefix, src_s3_client, isSnow=(src_region=='snow')):
        src_endpoint_urls_failed.append(src_endpoint_url)
        
dst_endpoint_urls_failed = []
for dst_endpoint_url in dst_endpoint_urls:
    print(f'Checking destination endpoint: {dst_endpoint_url}')
    dst_s3_client = create_s3_client(dst_access_key, dst_secret_access_key, dst_region, dst_endpoint_url)
    if not is_endpoint_healthy(dst_bucket, dst_prefix, dst_s3_client, isSnow=(dst_region=='snow')):
        dst_endpoint_urls_failed.append(dst_endpoint_url)

failed_endpoints_dict = {
    "src_endpoint_urls_failed": src_endpoint_urls_failed,
    "dst_endpoint_urls_failed": dst_endpoint_urls_failed
}

write_json(hs_data_json_dir, failed_endpoints_dict)