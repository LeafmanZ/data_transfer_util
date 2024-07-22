import yaml
import boto3
import json
from filelock import FileLock

# Function to read JSON file
def read_json(file_path):
    with open(file_path, 'r') as json_file:
        return json.load(json_file)

# Function to write JSON file
def write_json(file_path, data):
    with open(file_path, 'w') as json_file:
        json.dump(data, json_file, indent=4)

# Function to update JSON file with new data without overriding existing keys
def update_json(file_path, new_data):
    lock_path = file_path + ".lock"
    with FileLock(lock_path):
        data = read_json(file_path)
        for key, value in new_data.items():
            if key in data and isinstance(data[key], list):
                data[key].extend(value)
            else:
                data[key] = value
        write_json(file_path, data)

def read_config(filename="config.yaml"):
    with open(filename, 'r') as stream:
        try:
            return yaml.safe_load(stream)
        except yaml.YAMLError as exc:
            print(exc)
            return None

def list_objects(bucket_name, prefix, s3_client, isSnow=False):
    """List all objects in a given bucket with a specified prefix along with their size."""
    
    objects = {}
    if isSnow:
        # Get the bucket instance
        bucket = s3_client.Bucket(bucket_name)

        for obj in bucket.objects.filter(Prefix=prefix):
            if not obj.key.endswith('/'):
                key = obj.key.replace(prefix, '', 1).lstrip('/')
                objects[key] = obj.size
    else:
        paginator = s3_client.get_paginator('list_objects_v2')
        for page in paginator.paginate(Bucket=bucket_name, Prefix=prefix):
            if "Contents" in page:
                for obj in page["Contents"]:
                    if not obj["Key"].endswith('/'):
                        key = obj["Key"].replace(prefix, '', 1).lstrip('/')
                        objects[key] = obj['Size']
    return objects

def create_s3_client(access_key, secret_access_key, region, endpoint_url):
    
    if endpoint_url == 'no_endpoint':
        s3_client = boto3.client('s3', 
        aws_access_key_id=access_key, 
        aws_secret_access_key=secret_access_key, 
        region_name=region)
    elif 's3-accelerate' in endpoint_url and region != 'snow':
        s3_client = boto3.client('s3', 
        aws_access_key_id=access_key, 
        aws_secret_access_key=secret_access_key, 
        region_name=region)
    elif endpoint_url != 'no_endpoint' and region != 'snow': 
        s3_client = boto3.client('s3', 
        aws_access_key_id=access_key, 
        aws_secret_access_key=secret_access_key, 
        region_name=region, 
        endpoint_url=endpoint_url,
        verify=False)
    else:
        session = boto3.Session(
            aws_access_key_id=access_key, 
            aws_secret_access_key=secret_access_key
        )
        if 'https' in endpoint_url: # denotes new snowballs
            s3_client = session.resource('s3', endpoint_url=endpoint_url, verify=False)
        else:
            s3_client = session.resource('s3', endpoint_url=endpoint_url)
    return s3_client

def delete_object_version(bucket_name, s3_client, object_key, version_id):
    try:
        # Call delete_object with the Bucket, Key, and VersionId as keyword arguments
        response = s3_client.delete_object(
            Bucket=bucket_name,
            Key=object_key,
            VersionId=version_id
        )
        print(f"Deleted object with VersionId {version_id} from bucket {bucket_name} and key {object_key}")
    except Exception as e:
        print(f"Error deleting object: {e}")

def permanently_delete_subdir(bucket, prefix, access_key, secret_access_key, region, endpoint_url):
    # Initialize S3 client with optional credentials and region
    s3_client = create_s3_client(access_key, secret_access_key, region, endpoint_url)

    # Begin Delete Process
    try:
        files=0
        while True:
            # List object versions including delete markers with the specified prefix
            response = s3_client.list_object_versions(Bucket=bucket, Prefix=prefix)

            # Process delete markers and versions
            for version in response.get('Versions', []):
                key = version['Key']
                version_id = version['VersionId']
                delete_object_version(bucket, s3_client, key, version_id)
                files+=1

            for delete_marker in response.get('DeleteMarkers', []):
                key = delete_marker['Key']
                version_id = delete_marker['VersionId']
                delete_object_version(bucket, s3_client, key, version_id)
                files+=1
            
            #Check if there are more results to fetch
            if not response.get('IsTruncated', False):
                break  # Exit the loop if no more results are available
        print(f'Files Deleted: {files}')

    except Exception as e:
        print(f"Error listing or deleting object versions: {e}")