from concurrent.futures import ThreadPoolExecutor
import boto3
import random
import io
from botocore.exceptions import NoCredentialsError, ClientError
from util_s3 import read_config, create_s3_client, list_objects

# Process stream object and upload its corrupted version by manipulating bytes
def process_object(obj_key):
    try:
        s3_stream = src_s3.get_object(Bucket=src_bucket, Key=f"{src_prefix}/{obj_key}")
        bytedata = bytearray(s3_stream['Body'].read())
        size = len(bytedata)
        for _ in range(500):
            if size == 0:
                break
            pos = random.randint(0, size - 1)
            bytedata[pos] = random.randint(0,255)
        corrupted_stream = io.BytesIO(bytedata)
        new_key = f"{dst_prefix.rstrip('/')}/{obj_key}".lstrip('/')
        dst_s3.upload_fileobj(corrupted_stream, dst_bucket, new_key)
        print(f"Corrupted and uploaded {obj_key} to {new_key}")
    except (NoCredentialsError, ClientError) as e:
        print(f"Error processing {obj_key}: {e}")


### Takes the source of the good data transfer
# Read config.yaml file... ensure that the bucket and prefix in the yaml file dont end in a slash "/"
config = read_config()

# Configure your source AWS credentials from the config.yaml
src_access_key = config['src']["access_key"]
src_secret_access_key = config['src']["secret_access_key"]
src_region = config['src']["region"] # set to 'snow' if it is a snowball
src_endpoints = config['src']['endpoint_urls']
# Source bucket and source prefix you want to corrupt... from config.yaml
src_bucket = config['src']['bucket']
src_prefix = config['src']['bucket_prefix']


### Sets destination as the source of the corrupt data transfer
# Read corrupt_config.yaml... ensure that the bucket and prefix in the yaml file dont end in a slash "/"
dst_config = read_config("corrupt_config.yaml")

# Configure your destination AWS credentials from the corrupt_config.yaml
dst_access_key = dst_config['src']["access_key"]
dst_secret_access_key = dst_config['src']["secret_access_key"]
dst_region = dst_config['src']["region"] # set to 'snow' if it is a snowball
dst_endpoints = dst_config['src']['endpoint_urls']

# Destination bucket and prefix for the corrupted files... from corrupted_config.yaml
dst_bucket = dst_config['src']['bucket']
dst_prefix = dst_config['src']['bucket_prefix']

# Create a source and destination S3 client
src_s3 = create_s3_client(src_access_key, src_secret_access_key, src_region, src_endpoints[0])
dst_s3 = create_s3_client(dst_access_key, dst_secret_access_key, dst_region, dst_endpoints[0])


### Begin Upload
# Query files/objects within the target bucket prefix
obj_dict = list_objects(src_bucket, src_prefix, src_s3, isSnow=(src_region=='snow'))
key_list = obj_dict.keys()

# Use ThreadPoolExecutor to execute corruption in parallel
with ThreadPoolExecutor(max_workers=10) as executor:
    executor.map(process_object, key_list)
