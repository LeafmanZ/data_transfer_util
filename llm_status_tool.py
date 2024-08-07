import threading
import time
from utils import read_config, list_objects, create_s3_client, is_endpoint_healthy
import json
from queue import Queue
import ollama

###
# BEGIN: LOAD IN CONFIGURATIONS
###
# Load configurations
config = read_config()

if not config:
    print("Failed to read the configuration.")
    exit(1)
    
log_service = config["log"]["service"]
log_bucket = config["log"]["bucket"]
log_prefix = config["log"]["bucket_prefix"]
log_region = config["log"]["region"]
log_access_key = config['log']['access_key']
log_secret_access_key = config['log']['secret_access_key']
log_endpoint_urls = config['log']['endpoint_urls']

tmp_endpoint_urls = []
for log_endpoint_url in log_endpoint_urls:
    print(f'Checking destination endpoint: {log_endpoint_url}')
    log_client = create_s3_client(log_service, log_access_key, log_secret_access_key, log_region, log_endpoint_url)
    if is_endpoint_healthy(log_service, log_bucket, log_prefix, log_client, isSnow=(log_region=='snow')):
        tmp_endpoint_urls.append(log_endpoint_url)
log_endpoint_urls = tmp_endpoint_urls
###
# END: LOAD IN CONFIGURATIONS
###

# Initialize S3 client and log objects
log_s3_client = create_s3_client(log_access_key, log_secret_access_key, log_region, log_endpoint_urls[0])

# Shared variables with threading lock
lock = threading.Lock()
data_transfer_logs = {}
network_status_logs = {}
latest_data_transfer_data = {}
latest_network_status_data = {}
data_transfer_logs_wdtime = {}
network_status_logs_wdtime = {}
latest_objects_moved = {}
latest_data_transfer_log = ''
latest_network_status_log = ''

def load_json_from_s3(s3_client, bucket, key):
    response = s3_client.get_object(Bucket=bucket, Key=key)
    content = response['Body'].read().decode('utf-8')
    return json.loads(content)

def background_task():
    global data_transfer_logs, network_status_logs, latest_data_transfer_data, latest_network_status_data, data_transfer_logs_wdtime, network_status_logs_wdtime, latest_objects_moved, latest_data_transfer_log, latest_network_status_log
    while True:
        with lock:
            log_objects = list_objects(log_service, log_bucket, log_prefix, log_s3_client, isSnow=(log_region=='snow'))

            data_transfer_logs = {k: v for k, v in log_objects.items() if k.startswith('data_transfer') and 'lock' not in k}
            network_status_logs = {k: v for k, v in log_objects.items() if k.startswith('network_status') and 'lock' not in k}

            def convert_log_keys_to_datetime(log_data):
                result = {}
                for log_key in log_data.keys():
                    epoch_time = int(log_key.split('_')[-1].split('.')[0])
                    date_time = time.strftime('%B %d, %Y %H:%M', time.localtime(epoch_time))
                    result[log_key] = date_time
                return result

            data_transfer_logs_wdtime = convert_log_keys_to_datetime(data_transfer_logs)
            network_status_logs_wdtime = convert_log_keys_to_datetime(network_status_logs)

            latest_data_transfer_log = max(data_transfer_logs.keys(), key=lambda x: int(x.split('_')[-1].split('.')[0]))
            latest_network_status_log = max(network_status_logs.keys(), key=lambda x: int(x.split('_')[-1].split('.')[0]))

            latest_data_transfer_data = load_json_from_s3(log_s3_client, log_bucket, f'{log_prefix}/{latest_data_transfer_log}')
            latest_network_status_data = load_json_from_s3(log_s3_client, log_bucket, f'{log_prefix}/{latest_network_status_log}')
            latest_objects_moved = latest_data_transfer_data.pop('objects_moved')
        
        time.sleep(10)

# Create and start the background task thread
background_thread = threading.Thread(target=background_task)
background_thread.daemon = True  # This ensures the thread will close when the main program exits
background_thread.start()

def get_latest_data_transfer_status():
    with lock:
        return latest_data_transfer_data, data_transfer_logs_wdtime[latest_data_transfer_log]

def get_latest_objects_moved():
    with lock:
        return latest_objects_moved, data_transfer_logs_wdtime[latest_data_transfer_log]

def get_current_network_status():
    with lock:
        return latest_network_status_data, network_status_logs_wdtime[latest_network_status_log]

def filter_recent_logs(logs_dict, hours=24):
    """
    Filters logs from a dictionary where keys contain epoch time, returning only the logs from the last specified number of hours.

    :param logs_dict: Dictionary containing logs where keys have epoch time embedded.
    :param hours: Number of hours to look back for recent logs (default is 24 hours).
    :return: Filtered dictionary containing only recent logs.
    """
    current_time = int(time.time())
    threshold_time = current_time - (hours * 3600)  # Convert hours to seconds
    
    def extract_epoch_from_filename(filename):
        return int(filename.split('_')[-1].split('.')[0])
    
    return {k: v for k, v in logs_dict.items() if extract_epoch_from_filename(k) >= threshold_time}

def summarize_recent_data_transfer_activity(timeframe_hours=24):
    with lock:
        recent_data_transfer_logs = filter_recent_logs(data_transfer_logs, hours=timeframe_hours)
        failed_transfers = 0
        successful_transfers = 0
        bytes_transferred = 0
        final_synced_objects = 0
        for recent_data_transfer_log in recent_data_transfer_logs.keys():
            recent_data_transfer_log_data = load_json_from_s3(log_s3_client, log_bucket, f'{log_prefix}/{recent_data_transfer_log}')
            if recent_data_transfer_log_data['status'] == 'Failed':
                failed_transfers += 1
            elif recent_data_transfer_log_data['status'] == 'Completed':
                successful_transfers += 1
            bytes_transferred += recent_data_transfer_log_data['bytes_transferred']
            final_synced_objects += recent_data_transfer_log_data['final_synced_objects']
        
        return {'time_period': f'Last {timeframe_hours} hours',
                'total_failed_transfers':failed_transfers, 
                'total_successful_transfers': successful_transfers, 
                'total_bytes_transferred': bytes_transferred, 
                'total_synced_objects': final_synced_objects}
    
def get_summary_of_available_knowledge():
    summary_of_available_knowledge = """
    You can respond with information related to network and data transfer management, specifically:

    1. **Current network status** - Information about the network setup including source and destination endpoints regarding where the data is transferring to and from.

    2. **Latest data transfer status** - Details on the most recent data transfer, including any pertinent statistics or status updates.

    3. **Summary of recent data transfer activities** - A summary report of data transfer activities over a specified period (default is 24 hours), including metrics on failed and successful transfers, total bytes transferred, and total synced objects.
    """
    return summary_of_available_knowledge

def filter_agent_outputs(agent_function):
    new_agent_function = agent_function.replace('<|eom_id|>', '')
    return new_agent_function

available_function_information = """
You are a highly efficient function-executing agent. Your task is to analyze user prompts and select the most appropriate function from the following options to retrieve the necessary data:

get_current_network_status(): Returns the current health of the network infrastructure, which includes endpoint connectivity. There is no information on the health of a data transfer.

get_latest_data_transfer_status(): Provides detailed information about the most recent data transfer/sync. It goes over the bytes needed to move, if its status is Running, Completed, or Failed.

summarize_recent_data_transfer_activity(timeframe_hours=24): Generates a summary of data transfer statistics, including the total failed transfers, total successful transfers, total bytes transferred, and total synced objects over a specified time period (default is 24 hours).

get_summary_of_available_knowledge(): Generates are summary of all available knowledge and functionality we are able to provide.

Given a user prompt, select and execute the most relevant function from the list above to obtain the necessary data. Respond only with the function name. Do not explain yourself.
"""


while True:
    user_prompt = input("USER: ")
    if user_prompt.lower() == "exit":
        print("Exiting...")
        break

    agent_function_raw = ollama.chat(
        model='myllama3:latest',
        messages=[{'role': 'tool', 'name': 'get_available_function_information', 'content': available_function_information},
                    {'role': 'user', 'content': user_prompt}],
        stream=False,
    )

    agent_function = filter_agent_outputs(agent_function_raw['message']['content'])
    agent_function_output = eval(agent_function)  # Use eval carefully, potential security risk.
    print(f'\nFUNC: {agent_function}')

    stream = ollama.chat(
        model='myllama3:latest',
        messages=[{'role': 'tool', 'name': f'{agent_function}', 'content': f'{agent_function_output}'},
                    {'role': 'user', 'content': f'{user_prompt}. Do not calculate math. Only answer based on knowledge you have. No hypotheticals.'}],
        stream=True,
    )
    print('AGENT: ', end = '')
    for chunk in stream:
        print(chunk['message']['content'], end='', flush=True)
    
    print('\n')