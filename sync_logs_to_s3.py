import os
import time
import boto3
from botocore.exceptions import NoCredentialsError, PartialCredentialsError
from util_s3 import read_config, create_s3_client

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
###
# END: LOAD IN CONFIGURATIONS
###

# Create our log S3 client so we can sync logs to the bucket
log_s3_client = create_s3_client(log_access_key, log_secret_access_key, log_region, log_endpoint_urls[0])

def sync_logs_to_s3():
    for root, dirs, files in os.walk(log_local_directory):
        for file in files:
            local_path = os.path.join(root, file)
            relative_path = os.path.relpath(local_path, log_local_directory)
            s3_path = os.path.join(log_prefix, relative_path)

            try:
                log_s3_client.upload_file(local_path, log_bucket, s3_path)
                print(f"Uploaded {local_path} to s3://{log_bucket}/{s3_path}")
            except FileNotFoundError:
                print(f"File not found: {local_path}")
            except NoCredentialsError:
                print("Credentials not available.")
            except PartialCredentialsError:
                print("Incomplete credentials provided.")

# Continuously sync logs to the S3 bucket
while True:
    sync_logs_to_s3()
    time.sleep(1)  # Wait for 60 seconds before the next sync

