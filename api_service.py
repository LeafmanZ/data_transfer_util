import json
import os
from datetime import datetime
from flask import Flask, request, jsonify, abort
from util_s3 import read_config, list_objects, create_s3_client

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

def get_object(epoch_time, retrieve_objects_moved):
    key = f"{log_prefix}/dt_data_{epoch_time}.json"
    try:
        response = log_s3_client.get_object(Bucket=log_bucket, Key=key)
        log_data = json.loads(response['Body'].read().decode('utf-8'))
        if not retrieve_objects_moved:
            log_data.pop('objects_moved', None)
        return log_data
    except log_s3_client.exceptions.NoSuchKey:
        return None

def get_latest_object(retrieve_objects_moved):
    objects = list_objects(log_bucket, log_prefix, log_s3_client, isSnow=(log_region == 'snow'))
    if not objects:
        return None
    latest_key = max(objects.keys(), key=lambda key: int(key.split('_')[-1].split('.')[0]))
    return get_object(int(latest_key.split('_')[-1].split('.')[0]), retrieve_objects_moved)

@app.route('/', methods=['GET'])
def list_routes():
    token = request.headers.get('Authorization')
    if token != TOKEN:
        abort(403)
    
    route_list = []
    for rule in app.url_map.iter_rules():
        if rule.endpoint != 'static':
            route_info = {
                'route': rule.rule,
                'methods': list(rule.methods),
                'description': app.view_functions[rule.endpoint].__doc__
            }
            route_list.append(route_info)
    return jsonify(route_list)

@app.route('/logs', methods=['GET'])
def list_logs():
    """List all log files within a specified time range.
    Parameters:
    - start: Start time (epoch) (required)
    - end: End time (epoch) (required)
    """
    token = request.headers.get('Authorization')
    if token != TOKEN:
        abort(403)
    
    try:
        start_time = int(request.args.get('start'))
        end_time = int(request.args.get('end'))
    except (TypeError, ValueError):
        abort(400, "Invalid start or end time")

    logs = list_objects(log_bucket, log_prefix, log_s3_client, isSnow=(log_region=='snow')).keys()
    
    # Filter logs based on start_time and end_time
    filtered_logs = [log for log in logs if start_time <= int(log.split('_')[-1].split('.')[0]) <= end_time]
    
    return jsonify(filtered_logs)

@app.route('/log/<int:epoch_time>', methods=['GET'])
def get_log(epoch_time):
    """Retrieve a specific log file by its epoch time.
    Parameters:
    - epoch_time: Epoch time of the log file (required)
    - retrieve_objects_moved: Boolean flag to retrieve 'objects_moved' data (optional)
    """
    token = request.headers.get('Authorization')
    if token != TOKEN:
        abort(403)
    
    retrieve_objects_moved = request.args.get('retrieve_objects_moved', 'false').lower() == 'true'
    log = get_object(epoch_time, retrieve_objects_moved)
    if log is None:
        abort(404)
    return jsonify(log)

@app.route('/log/latest', methods=['GET'])
def get_latest_log():
    """Retrieve the latest log file.
    Parameters:
    - retrieve_objects_moved: Boolean flag to retrieve 'objects_moved' data (optional)
    """
    token = request.headers.get('Authorization')
    if token != TOKEN:
        abort(403)
    
    retrieve_objects_moved = request.args.get('retrieve_objects_moved', 'false').lower() == 'true'
    log = get_latest_object(retrieve_objects_moved)
    if log is None:
        abort(404)
    return jsonify(log)

if __name__ == '__main__':
    app.run(debug=False)
