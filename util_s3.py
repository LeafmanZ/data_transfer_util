import yaml
import boto3

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