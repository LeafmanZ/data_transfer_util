from flask import Flask, request, jsonify, abort
from util_s3 import read_config, list_objects, create_s3_client
import json
import os
from datetime import datetime

app = Flask(__name__)

TOKEN = os.getenv("API_TOKEN", "your_secure_token_here")

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

log_s3_client = create_s3_client(log_access_key, log_secret_access_key, log_region, log_endpoint_urls[0])

def get_object(epoch_time):
    key = f"{log_prefix}dt_data_{epoch_time}.json"
    try:
        response = log_s3_client.get_object(Bucket=log_bucket, Key=key)
        return json.loads(response['Body'].read().decode('utf-8'))
    except log_s3_client.exceptions.NoSuchKey:
        return None

def get_latest_object():
    objects = list_objects(log_bucket, log_prefix, log_s3_client)
    if not objects:
        return None
    latest_key = max(objects.keys(), key=lambda key: int(key.split('_')[-1].split('.')[0]))
    return get_object(int(latest_key.split('_')[-1].split('.')[0]))

@app.route('/logs', methods=['GET'])
def get_logs():
    token = request.headers.get('Authorization')
    if token != TOKEN:
        abort(403)
    
    start_time = int(request.args.get('start'))
    end_time = int(request.args.get('end'))
    logs = list_objects(log_bucket, f"{log_prefix}{start_time}_{end_time}/", log_s3_client)
    return jsonify(logs)

@app.route('/log/<int:epoch_time>', methods=['GET'])
def get_log(epoch_time):
    token = request.headers.get('Authorization')
    if token != TOKEN:
        abort(403)
    
    log = get_object(epoch_time)
    if log is None:
        abort(404)
    return jsonify(log)

@app.route('/log/latest', methods=['GET'])
def get_latest_log():
    token = request.headers.get('Authorization')
    if token != TOKEN:
        abort(403)
    
    log = get_latest_object()
    if log is None:
        abort(404)
    return jsonify(log)

if __name__ == '__main__':
    app.run(debug=True)
