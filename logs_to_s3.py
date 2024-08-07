import os
import time
import boto3
from botocore.exceptions import NoCredentialsError, PartialCredentialsError
from utils import read_config, file_abspath, create_s3_client

###
# BEGIN: LOAD IN CONFIGURATIONS
###
config = read_config()

if not config:
    print("Failed to read the configuration.")
    exit(1)

log_bucket = config["log"]["bucket"]
log_prefix = config["log"]["bucket_prefix"]
log_region = config["log"]["region"]
log_access_key = config['log']['access_key']
log_secret_access_key = config['log']['secret_access_key']
log_endpoint_urls = config['log']['endpoint_urls']
log_local_directory = config['log']['local_directory']

# Create log_local_directory subdir if it doesn't already exist
if not os.path.exists(log_local_directory):
    os.makedirs(log_local_directory)
###
# END: LOAD IN CONFIGURATIONS
###

# Create our log S3 client so we can sync logs to the bucket
log_s3_client = create_s3_client(log_access_key, log_secret_access_key, log_region, log_endpoint_urls[0])

def get_s3_file_last_modified(s3_client, bucket, key):
    try:
        response = s3_client.head_object(Bucket=bucket, Key=key)
        return response['LastModified']
    except s3_client.exceptions.ClientError as e:
        if e.response['Error']['Code'] == '404':
            return None
        else:
            raise

def sync_logs_to_s3():
    for root, dirs, files in os.walk(log_local_directory):
        for file in files:
            local_path = os.path.join(root, file)
            relative_path = os.path.relpath(local_path, log_local_directory)
            s3_path = os.path.join(log_prefix, relative_path)
            local_modified_time = os.path.getmtime(local_path)

            s3_last_modified = get_s3_file_last_modified(log_s3_client, log_bucket, s3_path)

            if s3_last_modified is None or local_modified_time > s3_last_modified.timestamp():
                try:
                    log_s3_client.upload_file(local_path, log_bucket, s3_path)
                    print(f"Uploaded {local_path} to s3://{log_bucket}/{s3_path}")
                except FileNotFoundError:
                    print(f"File not found: {local_path}")
                except NoCredentialsError:
                    print("Credentials not available.")
                except PartialCredentialsError:
                    print("Incomplete credentials provided.")
            else:
                print(f"No upload needed for {local_path} (local modified time: {local_modified_time}, s3 modified time: {s3_last_modified})")

# Continuously sync logs to the S3 bucket
while True:
    try:
        sync_logs_to_s3()
    except Exception as e:
        error_message = f"An error occurred while syncing logs to S3: {e}. It is possible this is just an MD5 mismatch and a resync is automatically happening."
        print(error_message)

    time.sleep(10)  # Wait for 60 seconds before the next sync
