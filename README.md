from utils import read_config, create_client, create_s3_client, list_objects, is_endpoint_healthy
import time
import threading
import json
import yaml
import io
import os
import subprocess
import concurrent.futures

###
# BEGIN: LOAD IN CONFIGURATIONS
###
# Load configurations
config = read_config()

if not config:
    print("Failed to read the configuration.")
    exit(1)
    
log_service = config["log"]["service"]
log_bucket = config["log"]["bucket"]
log_prefix = config["log"]["bucket_prefix"]
log_region = config["log"]["region"]
log_access_key = config['log']['access_key']
log_secret_access_key = config['log']['secret_access_key']
log_endpoint_urls = config['log']['endpoint_urls']
deployment_location = config['deployment_location']

retry_attempts = 5  # Number of attempts to retry

# Initialize the list for healthy endpoints
tmp_endpoint_urls = []

for log_endpoint_url in log_endpoint_urls:
    print(f'Checking destination endpoint: {log_endpoint_url}')
    log_client = create_s3_client(log_access_key, log_secret_access_key, log_region, log_endpoint_url)
    
    # Retry mechanism if the endpoint is not healthy
    attempts = 0
    while attempts < retry_attempts:
        if is_endpoint_healthy(log_service, log_bucket, log_prefix, log_client, isSnow=(log_region == 'snow')):
            tmp_endpoint_urls.append(log_endpoint_url)
            break  # Exit the loop if the endpoint is healthy
        attempts += 1
        print(f'Retrying ({attempts}/{retry_attempts}) for endpoint: {log_endpoint_url}')
    
log_endpoint_urls = tmp_endpoint_urls
###
# END: LOAD IN CONFIGURATIONS
###

# Initialize S3 client and log objects
log_s3_client = create_s3_client(log_access_key, log_secret_access_key, log_region, log_endpoint_urls[0])

def load_yaml_from_s3(s3_client, bucket, key):
    response = s3_client.get_object(Bucket=bucket, Key=key)
    content = response['Body'].read().decode('utf-8')
    return yaml.safe_load(content)

# Locks for thread safety
e_lock = threading.Lock()
v_lock = threading.Lock()

def validation_manager():
    global log_service, log_bucket, log_prefix, log_region, log_access_key, log_secret_access_key, log_endpoint_urls
    while True:
        with v_lock:
            try:
                validation_results = {
                    "src": False,
                    "dst": False,
                    "log": False
                }
                validation_keys = {
                    "src": [],
                    "dst": [],
                    "log": []
                }

                api_logs = list_objects(log_service, log_bucket, "api", log_s3_client, isSnow=(log_region=='snow'))

                for key, value in list(api_logs.items()):
                    if 'validate' in key and deployment_location in key and 'validated' not in key:
                        # Procure and save the yaml data
                        config = load_yaml_from_s3(log_s3_client, log_bucket, f'api/{key}')
                        

                        # Delete that yaml file as soon as possible
                        try:
                            log_s3_client.delete_object(Bucket=log_bucket, Key=f'api/{key}')
                            print(f"Deleted object api/{key} from: {log_bucket}")
                        except Exception as e:
                            print(f"Error deleting object from S3: {e}")
                        
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

                        log_service = config["log"]["service"]
                        log_bucket = config["log"]["bucket"]
                        log_prefix = config["log"]["bucket_prefix"]
                        log_region = config["log"]["region"]
                        log_access_key = config['log']['access_key']
                        log_secret_access_key = config['log']['secret_access_key']
                        log_endpoint_urls = config['log']['endpoint_urls']

                        try:
                            # Check source endpoints
                            for src_endpoint_url in src_endpoint_urls:
                                src_client = create_client(src_service, src_access_key, src_secret_access_key, src_region, src_endpoint_url)
                                endpoint_health = is_endpoint_healthy(src_service, src_bucket, src_prefix, src_client, isSnow=(src_region=='snow'))
                                if endpoint_health:
                                    validation_results['src'] = True
                                    if isinstance(endpoint_health, dict):
                                        validation_keys['src'] = list(endpoint_health.keys())[:5]
                                    break
                        except :
                            pass
                        
                        try:
                            # Check destination endpoints
                            for dst_endpoint_url in dst_endpoint_urls:
                                dst_client = create_client(dst_service, dst_access_key, dst_secret_access_key, dst_region, dst_endpoint_url)
                                endpoint_health = is_endpoint_healthy(dst_service, dst_bucket, dst_prefix, dst_client, isSnow=(dst_region=='snow'))
                                if endpoint_health:
                                    validation_results['dst'] = True
                                    if isinstance(endpoint_health, dict):
                                        validation_keys['dst'] = list(endpoint_health.keys())[:5]
                                    break
                        except:
                            pass
                    
                        try:
                            # Check log endpoints
                            for log_endpoint_url in log_endpoint_urls:
                                log_client = create_client(log_service, log_access_key, log_secret_access_key, log_region, log_endpoint_url)
                                endpoint_health = is_endpoint_healthy(log_service, log_bucket, log_prefix, log_client, isSnow=(log_region=='snow'))
                                if endpoint_health:
                                    validation_results['log'] = True
                                    if isinstance(endpoint_health, dict):
                                        validation_keys['log'] = list(endpoint_health.keys())[:5]
                                    break
                        except:
                            pass
                        
                        try:
                            json_data = json.dumps({"validation_results": validation_results,
                                                     "validation_keys": validation_keys})
                            json_file_like = io.BytesIO(json_data.encode('utf-8'))
                            # Define S3 bucket and object key
                            new_key= key.replace('validate', 'validated').replace(".yaml",".json")
                            # Upload the file-like object to S3
                            log_s3_client.upload_fileobj(json_file_like, log_bucket, f'api/{new_key}')
                            print(f'Validation has been uploaded to S3 as: s3://{log_bucket}/api/{new_key}')
                        except Exception as e:
                            print(f"Error uploading validation results to S3: {e}")

            except Exception as e:
                print(f"Error Validating Config: {e}")
        time.sleep(1)

def execution_manager():
    global log_service, log_bucket, log_prefix, log_region, log_access_key, log_secret_access_key, log_endpoint_urls
    while True:
        with e_lock:
            try:
                api_logs = list_objects(log_service, log_bucket, "api", log_s3_client, isSnow=(log_region=='snow'))
                for key, value in list(api_logs.items()):
                    if 'run' in key and deployment_location in key:
                        print(f'Initializing Transfer with Config!')  # Print the data to the console (for debugging purposes)
                        # Procure and save the yaml data
                        config = load_yaml_from_s3(log_s3_client, log_bucket, f'api/{key}')

                        # Delete that run.yaml object as soon as possible
                        try: 
                            log_s3_client.delete_object(
                                    Bucket=log_bucket,
                                    Key=f'api/{key}'
                              )
                            print(f"Deleted object api/{key} from: {log_bucket}")
                        except Exception as e:
                            print(f"error deleting run config from S3: {e}")

                        ### Save the config yaml ###

                        try:
                            filename = os.path.join("run_configs", key)
                            directory = os.path.dirname(filename)
                            if not os.path.exists(directory):
                                os.makedirs(directory)
                            with open(filename, 'w') as file:
                                yaml.dump(config, file, default_flow_style=False)
                            print(f'Config saved to: {filename}')
                        except Exception as e:
                            print(f"Error saving config YAML: {e}")

                        ### Save the config yaml ###


                        # # Run the cloud_transfer.py script as a detached process
                        subprocess.Popen(
                            ['/home/ec2-user/anaconda3/bin/python', 'cloud_transfer.py', f'{filename}'],
                            stdout=subprocess.DEVNULL,
                            stderr=subprocess.DEVNULL,
                            start_new_session=True
                            )
            except Exception as e:
                print(f"Error Executing Run Config: {e}")
        time.sleep(1)

vm_thread = threading.Thread(target=validation_manager)
vm_thread.daemon = True  # This ensures the thread will close when the main program exits
vm_thread.start()

em_thread = threading.Thread(target=execution_manager)
em_thread.daemon = True  # This ensures the thread will close when the main program exits
em_thread.start()

# os.system('python logs_to_s3.py')
# os.system('python logs_network_status.py')


# List of scripts to run
scripts = [
    ['/home/ec2-user/anaconda3/bin/python', 'logs_to_s3.py'],
    ['/home/ec2-user/anaconda3/bin/python', 'logs_network_status.py']
]

# Create a ThreadPoolExecutor
with concurrent.futures.ThreadPoolExecutor() as executor:
    # Use executor.submit to run the scripts concurrently
    futures = [executor.submit(subprocess.run, script) for script in scripts]

# Wait for all scripts to finish
for future in futures:
    future.result()  # This will raise an exception if the script fails

try:
    while True:
        time.sleep(10)
except KeyboardInterrupt:
    print("Shutting down gracefully...")
