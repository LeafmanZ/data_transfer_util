import argparse
import urllib3
import time
from utils import read_config, create_client, update_json

# Suppress InsecureRequestWarning
urllib3.disable_warnings(urllib3.exceptions.InsecureRequestWarning)

###
# BEGIN: LOAD IN CONFIGURATIONS
###

parser = argparse.ArgumentParser(description='Copy a specific object from one bucket to another.')
parser.add_argument('src_service', type=str, help='The source cloud service.')
parser.add_argument('dst_service', type=str, help='The destination cloud service.')

parser.add_argument('src_bucket', type=str, help='The source bucket name.')
parser.add_argument('dst_bucket', type=str, help='The destination bucket name.')

parser.add_argument('src_key', type=str, help='The source object key to copy.')
parser.add_argument('dst_key', type=str, help='The destination object key for the copied object.')
parser.add_argument('bytes', type=int, help='The total size of the object in bytes')

parser.add_argument('src_endpoint_url', type=str, help='The source endpoint url for the copied object.')
parser.add_argument('dst_endpoint_url', type=str, help='The destination endpoint url for the copied object.')

parser.add_argument('data_transfer_data_json_dir', type=str, help='The data transfer json file that we are saving transfer statistics to.')
parser.add_argument('config', type=str, help='The configuration file we are using in our transfer.')


args = parser.parse_args()

config = read_config(args.config)

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

# create our source and destination cloud clients so we can interact with our buckets
src_client = create_client(args.src_service, src_access_key, src_secret_access_key, src_region, args.src_endpoint_url)
dst_client = create_client(args.dst_service, dst_access_key, dst_secret_access_key, dst_region, args.dst_endpoint_url)

# Stream the object directly directly from the source
if src_region == 'snow': 
    object = src_client.meta.client.get_object(Bucket=args.src_bucket, Key=args.src_key)["Body"]
elif args.src_service == "AWS":
    object = src_client.get_object(Bucket=args.src_bucket, Key=args.src_key)["Body"]
elif args.src_service == "AZURE":
    object = src_client.get_blob_client(container = args.src_bucket, blob=args.src_key).download_blob()

# Upload the streamed object to the destination
if dst_region == 'snow':
    dst_client.meta.client.upload_fileobj(object, args.dst_bucket, args.dst_key)
elif args.dst_service == "AWS":
    dst_client.upload_fileobj(object, args.dst_bucket, args.dst_key)
elif args.dst_service == "AZURE":
    dst_client.get_blob_client(container=args.dst_bucket, blob=args.dst_key).upload_blob(object, overwrite=True)

# Record the end time
end_time = time.time()

# Calculate and print the elapsed time
elapsed_time = end_time - start_time
print(f"Object '{args.src_key}' has been copied to '{args.dst_key}' in {elapsed_time:.2f} seconds using {args.src_endpoint_url} to {args.dst_endpoint_url}.")

###
# BEGIN: SAVE FINISHING COMPLETION INFORMATION TO JSON
###
new_data_transfer_data_dict = {'objects_moved': [{'src_key': args.src_key,
                                    'dst_key': args.dst_key,
                                    'bytes': args.bytes,
                                    'equivalent_gigabytes': float(f"{(args.bytes/1073741824):.3f}"),
                                    'epoch_time_start': int(start_time),
                                    'epoch_time_end': int(end_time),
                                    'total_time_seconds': elapsed_time}]}
update_json(args.data_transfer_data_json_dir, new_data_transfer_data_dict)
###
# END: SAVE FINISHING COMPLETION INFORMATION TO JSON
###
