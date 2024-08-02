import yaml
import os
import boto3
import json
import subprocess
from filelock import FileLock
import signal
from azure.storage.blob import BlobServiceClient

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

# Finds the absolute path of a file from the current directory
def file_abspath(ending, dir_path = "."):
    for root, dirs, files in os.walk(dir_path):
        for file in files:
            if file.endswith(ending):
                file_path = os.path.join(root, file)
                if os.path.isfile(file_path):
                    return os.path.abspath(file_path)

# Reads into the sbe_config.yaml file
def read_config(filename='config.yaml', dir_path = "."):
    with open(filename, 'r') as stream:
        try:
            return yaml.safe_load(stream)
        except yaml.YAMLError as exc:
            print(exc)
            return None

# Runs subprocess commands and waits for command to finish
def run_command(command):
    try:
        with subprocess.Popen(command, shell=True, stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True) as process:
            stdout, stderr = process.communicate()
            return process.returncode, stdout, stderr
    except subprocess.CalledProcessError as e:
        print(f"Error running command: {e}")
        return e.returncode, '', str(e)
    except Exception as e:
        print(f"Unexpected error: {e}")
        return 1, '', str(e)

def list_objects(service, bucket_name, prefix, client, isSnow=False):
    if service == "AWS":
        objects = list_s3_objects(bucket_name, prefix, client, isSnow)
        return objects
    if service == "AZURE":
        objects = list_blob_objects(bucket_name, prefix, client)
        return objects
    
def list_s3_objects(bucket_name, prefix, s3_client, isSnow=False):
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

def list_blob_objects(bucket_name, prefix, az_client):
    objects = {}
    container_client = az_client.get_container_client(bucket_name)
    blob_list = container_client.list_blobs(name_starts_with=prefix)
    for blob in blob_list:
        if not blob.name.endswith('/'):
                        key = blob.name.replace(prefix, '', 1).lstrip('/')
                        objects[key] = blob.size
    return objects

def create_client(service, access_key = None, secret_access_key = None, region=None, endpoint_url=None):
    if service == 'AWS':
        return create_s3_client(access_key, secret_access_key, region, endpoint_url)
    elif service == 'AZURE':
        return create_az_client(access_key)
    
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

def create_az_client(access_key):
    connection_string = access_key
    az_client = BlobServiceClient.from_connection_string(connection_string)
    return az_client

class TimeoutException(Exception):
    pass

def timeout_handler(signum, frame):
    raise TimeoutException

def is_endpoint_healthy(bucket_name, prefix, s3_client, isSnow=False, timeout=2):
    """List all objects in a given bucket with a specified prefix along with their size, with a timeout."""
    """Returns True if endpoint is good, Returns False if endpoint is bad."""
    def inner():
        objects = {}
        if isSnow:
            # Get the bucket instance
            bucket = s3_client.Bucket(bucket_name)

            for obj in bucket.objects.filter(Prefix=prefix):
                if not obj.key.endswith('/'):
                    key = obj.key.replace(prefix, '', 1).lstrip('/')
                    objects[key] = obj.size
                break
            return True
        else:
            paginator = s3_client.get_paginator('list_objects_v2')
            for page in paginator.paginate(Bucket=bucket_name, Prefix=prefix):
                if "Contents" in page:
                    for obj in page["Contents"]:
                        if not obj["Key"].endswith('/'):
                            key = obj["Key"].replace(prefix, '', 1).lstrip('/')
                            objects[key] = obj['Size']
                break
        return True

    signal.signal(signal.SIGALRM, timeout_handler)
    signal.alarm(timeout)  # Set the timeout
    try:
        result = inner()
    except Exception as e:
        return False
    finally:
        signal.alarm(0)  # Disable the alarm
    return result

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