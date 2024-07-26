import sys
import os

# Add the parent directory to the sys.path
parent_dir = os.path.abspath(os.path.join(os.path.dirname(__file__), '..'))
sys.path.append(parent_dir)

import argparse
import urllib3
import time
from util_s3 import read_config, create_s3_client, update_json

# Suppress InsecureRequestWarning
urllib3.disable_warnings(urllib3.exceptions.InsecureRequestWarning)

parser = argparse.ArgumentParser(description='Copy a specific object from one S3 bucket to another.')
parser.add_argument('src_bucket', type=str, help='The source S3 bucket name.')
parser.add_argument('dst_bucket', type=str, help='The destination S3 bucket name.')

parser.add_argument('src_key', type=str, help='The source object key to copy.')
parser.add_argument('dst_key', type=str, help='The destination object key for the copied object.')
parser.add_argument('bytes', type=int, help='The total size of the object in bytes')

parser.add_argument('src_endpoint_url', type=str, help='The source endpoint url for the copied object.')
parser.add_argument('dst_endpoint_url', type=str, help='The destination endpoint url for the copied object.')

parser.add_argument('dt_data_json_dir', type=str, help='The data transfer json file that we are saving transfer statistics to.')

args = parser.parse_args()

###
# BEGIN: LOAD IN CONFIGURATIONS
###
config = read_config()

if not config:
    print("Failed to read the configuration.")
    quit()

src_region = config["src"]["region"]
src_access_key = config['src']['access_key']
src_secret_access_key = config['src']['secret_access_key']

dst_region = config["dst"]["region"]
dst_access_key = config['dst']['access_key']
dst_secret_access_key = config['dst']['secret_access_key']
###
# END: LOAD IN CONFIGURATIONS
###

# Record the start time
start_time = time.time()

# create our source and destination s3 clients so we can interact with our buckets
src_s3_client = create_s3_client(src_access_key, src_secret_access_key, src_region, args.src_endpoint_url)
dst_s3_client = create_s3_client(dst_access_key, dst_secret_access_key, dst_region, args.dst_endpoint_url)

# Stream the object directly directly
if src_region == 'snow': 
    s3_object = src_s3_client.meta.client.get_object(Bucket=args.src_bucket, Key=args.src_key)
else:
    s3_object = src_s3_client.get_object(Bucket=args.src_bucket, Key=args.src_key)
# Upload the streamed object to the destination
if dst_region == 'snow':
    dst_s3_client.meta.client.upload_fileobj(s3_object['Body'], args.dst_bucket, args.dst_key)
else:
    dst_s3_client.upload_fileobj(s3_object['Body'], args.dst_bucket, args.dst_key)

# Record the end time
end_time = time.time()

# Calculate and print the elapsed time
elapsed_time = end_time - start_time
print(f"Object '{args.src_key}' has been copied to '{args.dst_key}' in {elapsed_time:.2f} seconds using {args.src_endpoint_url} to {args.dst_endpoint_url}.")

###
# BEGIN: SAVE FINISHING COMPLETION INFORMATION TO JSON
###
new_dt_data_dict = {'objects_moved': [{'src_key': args.src_key,
                                    'dst_key': args.dst_key,
                                    'bytes': args.bytes,
                                    'epoch_time_start': int(start_time),
                                    'epoch_time_end': int(end_time),
                                    'total_time_seconds': elapsed_time}]}
update_json(args.dt_data_json_dir, new_dt_data_dict)
###
# END: SAVE FINISHING COMPLETION INFORMATION TO JSON
###
