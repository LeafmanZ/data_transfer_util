from concurrent.futures import ThreadPoolExecutor
import boto3
import random
import io
from botocore.exceptions import NoCredentialsError, ClientError
from utils import read_config, create_client, list_objects, is_endpoint_healthy

###
# BEGIN: LOAD IN CONFIGURATIONS
###
### Takes the source of the good data transfer
# Read config.yaml file... ensure that the bucket and prefix in the yaml file dont end in a slash "/"
src_config = read_config()

# Configure your source AWS credentials from the config.yaml
src_service = src_config["src"]["service"]
src_access_key = src_config['src']["access_key"]
src_secret_access_key = src_config['src']["secret_access_key"]
src_region = src_config['src']["region"] # set to 'snow' if it is a snowball
src_endpoint_urls = src_config['src']['endpoint_urls']
# Source bucket and source prefix you want to corrupt... from config.yaml
src_bucket = src_config['src']['bucket']
src_prefix = src_config['src']['bucket_prefix']

### Sets destination as the source of the corrupt data transfer
# Read config_corrupt.yaml... ensure that the bucket and prefix in the yaml file dont end in a slash "/"
dst_config = read_config("config_corrupt.yaml")

# Configure your destination AWS credentials from the config_corrupt.yaml
dst_service = dst_config["src"]["service"]
dst_access_key = dst_config['src']["access_key"]
dst_secret_access_key = dst_config['src']["secret_access_key"]
dst_region = dst_config['src']["region"] # set to 'snow' if it is a snowball
dst_endpoint_urls = dst_config['src']['endpoint_urls']
# Destination bucket and prefix for the corrupted files... from corrupted_config.yaml
dst_bucket = dst_config['src']['bucket']
dst_prefix = dst_config['src']['bucket_prefix']

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
###
# END: LOAD IN CONFIGURATIONS
###

# Create a source and destination cloud client
src_client = create_client(src_service, src_access_key, src_secret_access_key, src_region, src_endpoint_urls[0])
dst_client = create_client(dst_service, dst_access_key, dst_secret_access_key, dst_region, dst_endpoint_urls[0])

### Begin Upload
# Query files/objects within the target bucket prefix
obj_dict = list_objects(src_service, src_bucket, src_prefix, src_client, isSnow=(src_region=='snow'))

# Take the queried object dictionary and create a list of object keys up to a maximum byte size (sample_size)
sample_size = 100000000000 # 100gb--> 100*E9

# Creates a list of obj keys (key_list) to a certain size limit
total_size = 0
key_list = []

for key, size in obj_dict.items():
    if total_size + size <= sample_size:
        key_list.append(key)
        total_size += size
    else:
        break

def process_object(obj_key):
    """
    Retrieves an object from a specified source, randomly corrupts its bytes, and then uploads the corrupted
    version to a destination. Handles different source and destination services like AWS, Azure, or a custom 'snow' service.
    """
    try:
        # Construct the source key with prefix
        src_key = f"{src_prefix}/{obj_key}"

        # Retrieve the object based on the source service type
        if src_region == 'snow': 
            object = src_client.meta.client.get_object(Bucket=src_bucket, Key=src_key)["Body"]
        elif src_service == "AWS":
            object = src_client.get_object(Bucket=src_bucket, Key=src_key)["Body"]
        elif src_service == "AZURE":
            object = src_client.get_blob_client(container=src_bucket, blob=src_key).download_blob()
        bytedata = bytearray(object.read() if src_service != "AZURE" else object.readall())

        # Corrupt random bytes in the object
        size = len(bytedata)
        for _ in range(500):  # Number of bytes to corrupt
            if size == 0:
                break
            pos = random.randint(0, size - 1)
            bytedata[pos] = random.randint(0, 255)
        corrupted_stream = io.BytesIO(bytedata)

        # Construct the destination key with prefix
        dst_key = f"{dst_prefix.rstrip('/')}/{obj_key}".lstrip('/')

        # Upload the corrupted object based on the destination service type
        if dst_region == 'snow':
            dst_client.meta.client.upload_fileobj(corrupted_stream, dst_bucket, dst_key)
        elif dst_service == "AWS":
            dst_client.upload_fileobj(corrupted_stream, dst_bucket, dst_key)
        elif dst_service == "AZURE":
            dst_client.get_blob_client(container=dst_bucket, blob=dst_key).upload_blob(corrupted_stream, overwrite=True)

        print(f"Corrupted and uploaded {obj_key} to {dst_key}")
    except (NoCredentialsError, ClientError) as e:
        print(f"Error processing {obj_key}: {e}")

# Use ThreadPoolExecutor to execute corruption in parallel
with ThreadPoolExecutor(max_workers=3) as executor:
    executor.map(process_object, key_list)