from utils import read_config, create_client, is_endpoint_healthy, write_json
import time
import os

###
# BEGIN: LOAD IN CONFIGURATIONS
###
config = read_config()

if not config:
    print("Failed to read the configuration.")

src_service = config['src']['service']
src_bucket = config["src"]["bucket"]
src_prefix = config["src"]["bucket_prefix"]
src_region = config["src"]["region"]
src_access_key = config['src']['access_key']
src_secret_access_key = config['src']['secret_access_key']
src_endpoint_urls = config['src']['endpoint_urls']

dst_service = config['dst']['service']
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
while True:
    if not os.path.exists(log_local_directory):
        os.makedirs(log_local_directory)

    network_status_data_json_dir = os.path.join(log_local_directory, f"network_status_data_{int(time.time())}.json")

    src_endpoint_urls_succeeded = []
    src_endpoint_urls_failed = []
    for src_endpoint_url in src_endpoint_urls:
        print(f'Checking source endpoint: {src_endpoint_url}')
        src_client = create_client(src_service, src_access_key, src_secret_access_key, src_region, src_endpoint_url)
        if is_endpoint_healthy(src_service, src_bucket, src_prefix, src_client, isSnow=(src_region=='snow')):
            src_endpoint_urls_succeeded.append(src_endpoint_url)
        else:
            src_endpoint_urls_failed.append(src_endpoint_url)
    
    src_endpoints_operational_status = ''
    if len(src_endpoint_urls_succeeded) == 0:
        src_endpoints_operational_status = 'critical'
    elif len(src_endpoint_urls_succeeded) == len(src_endpoint_urls):
        src_endpoints_operational_status = 'operational'
    else:
        src_endpoints_operational_status = 'degraded'
    
    dst_endpoint_urls_succeeded = []
    dst_endpoint_urls_failed = []
    for dst_endpoint_url in dst_endpoint_urls:
        print(f'Checking destination endpoint: {dst_endpoint_url}')
        dst_client = create_client(dst_service, dst_access_key, dst_secret_access_key, dst_region, dst_endpoint_url)
        if is_endpoint_healthy(dst_service, dst_bucket, dst_prefix, dst_client, isSnow=(dst_region=='snow')):
            dst_endpoint_urls_succeeded.append(dst_endpoint_url)
        else:
            dst_endpoint_urls_failed.append(dst_endpoint_url)
    
    dst_endpoints_operational_status = ''
    if len(dst_endpoint_urls_succeeded) == 0:
        dst_endpoints_operational_status = 'critical'
    elif len(dst_endpoint_urls_succeeded) == len(dst_endpoint_urls):
        dst_endpoints_operational_status = 'operational'
    else:
        dst_endpoints_operational_status = 'degraded'

    failed_endpoints_dict = {
        "src_endpoint_urls_failed": src_endpoint_urls_failed,
        "dst_endpoint_urls_failed": dst_endpoint_urls_failed,
        "src_endpoint_urls_succeeded": src_endpoint_urls_succeeded,
        "dst_endpoint_urls_succeeded": dst_endpoint_urls_succeeded,
        "src_endpoints_operational_status": src_endpoints_operational_status,
        "dst_endpoints_operational_status": dst_endpoints_operational_status
    }

    write_json(network_status_data_json_dir, failed_endpoints_dict)
    print(f"Configuration details saved to {network_status_data_json_dir}")
    time.sleep(10)