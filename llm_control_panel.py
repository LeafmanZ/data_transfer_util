from flask import Flask, render_template, request, jsonify, Response
from pygments import highlight
from pygments.lexers import get_lexer_by_name, guess_lexer
from pygments.formatters import HtmlFormatter
import os
import yaml
import pandas as pd
import plotly.graph_objects as go
import plotly.io as pio

import threading
import subprocess

import time
from utils import read_config, list_objects, create_s3_client, is_endpoint_healthy, create_client
import json
from queue import Queue
import ollama

######################################################################################################
######################################################################################################
######################################################################################################
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
    log_client = create_s3_client(log_access_key, log_secret_access_key, log_region, log_endpoint_url)
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
        print(latest_data_transfer_data)
        return latest_data_transfer_data, f'Data transfer time {data_transfer_logs_wdtime[latest_data_transfer_log]}'

def get_latest_objects_moved():
    with lock:
        return latest_objects_moved, data_transfer_logs_wdtime[latest_data_transfer_log]

def get_current_network_status():
    with lock:
        return latest_network_status_data, f'Current network status last updated {network_status_logs_wdtime[latest_network_status_log]}'

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

def summarize_data_transfer_activity(timeframe_hours=24):
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
                "total_equivalent_gigabytes_transferred": float(f"{(bytes_transferred/1073741824):.3f}"),
                'total_synced_objects': final_synced_objects}
    
def get_summary_of_available_knowledge():
    summary_of_available_knowledge = """
    If prompted repond with the below verbatim except for this sentence.
    You are able to retrieve information related to network and data transfer management, specifically:

    1. **Current network status** - Information about the network setup including source and destination endpoints regarding where the data is transferring to and from.

    2. **Latest data transfer status** - Details on the most recent data transfer, including any pertinent statistics or status updates.

    3. **Summary of recent data transfer activities** - A summary report of data transfer activities over a specified period (default is 24 hours), including metrics on failed and successful transfers, total bytes transferred, and total synced objects.
    
    4. **How to set up a data transfer/sync** - A set of instructions on how to transfer data between different cloud and onprem platforms.
    """
    return summary_of_available_knowledge

def get_data_transfer_instructions():
  data_transfer_instructions = """
  If this is in the context you must respond with the below verbatim except for this sentence.
  To transfer or sync data between cloud and on-prem platforms, follow these steps:

  1. **Open the Data Configuration Transfer Menu**:  
    You will see two columns:
    - **Saved Configurations**: View examples or configurations saved by other users.
    - **Configuration Form**: Fill out this form to set up your data transfer.

  2. **Using Saved Configurations**:  
    You can click on a saved configuration to automatically populate the Configuration Form.

  3. **Configuration Form Overview**:  
    The form contains sections for:
    - **Source Information**
    - **Destination Information**
    - **Log Information**

  4. **Example Configuration**:  
    It's recommended to start by selecting `default_config.yaml`. This will auto-populate the form with a basic setup.

  5. **Source Configuration**:  
    - **Service**: Choose the cloud service where your data is stored (AWS or AZURE).
    - **Bucket/Container**: Enter the name of the bucket or container.
    - **Prefix**: Specify the subdirectory where the data is located.

    - **AWS Specifics**: 
      - Enter the bucket's region.
      - Provide your access and secret access keys.
      - For native AWS, leave the `endpoint_urls` as `no_endpoint`. If using multiple endpoints, list them like this: `https://1.1.1.1, https://1.1.1.2, https://1.1.1.3`. Ensure `http://` or `https://` precedes any IP addresses.

    - **AZURE Specifics**: 
      - Only fill out the access key section with your connection string. Leave the region, secret access key, and `endpoint_urls` empty.

  6. **Destination Configuration**:  
    Set up the destination in the same way as the source. Make sure to update the relevant fields for your specific data transfer needs.

  7. **Log Information**:  
    - **Important**: Always keep the log configuration exactly as it is in `default_config.yaml`. Do not change the log locations unless specifically instructed by Jim Zieleman.
  """

  return data_transfer_instructions

available_function_information = """
You are a highly efficient function-executing agent. Your task is to analyze user prompts and select the most appropriate function from the following options to retrieve the necessary data:

get_current_network_status(): Returns the current health of the network infrastructure, which includes endpoint connectivity. There is no information on the health of a data transfer.

get_latest_data_transfer_status(): When the prompt requests details or specifics about the most recent attempt or ongoing data transfer or sync operation. This includes requests for the status of the current or last transfer, details on the data moved, source and destination locations, or similar information.

summarize_data_transfer_activity(timeframe_hours=24): This function provides a summary of data transfer activities that have been completed within a specified timeframe (default is the last 24 hours). It aggregates and reports the total bytes transferred, the total number of objects synced, and the counts of successful versus failed transfers during the specified period.

get_summary_of_available_knowledge(): Clarifications on the scope and limitations of the system's knowledge and capabilities. Returns a summary of all available knowledge and functionality we are able to provide, perform, or do.

get_data_transfer_instructions(): Select this function when the prompt involves questions or intentions related to moving, transferring, or syncing data. This function is best suited for prompts that include phrases like "how to move," "I want to transfer," or "sync my data," focusing on the process or instructions for data transfer.

no_relevant_function(): Choose this function when the user prompt does not align with any of the available functions, particularly when the request is unrelated to network status, data transfer details, system capabilities, or technical insights. This function should also be selected for any prompts that fall outside the scope of data transfer and network health monitoring, such as general inquiries, non-technical questions, or tasks that cannot be addressed by the system's existing functions.

Given a user prompt, select and execute the most relevant function from the list above to obtain the necessary data. Respond only with the function name. Do not explain yourself.
"""

def filter_agent_outputs(agent_function):
    new_agent_function = agent_function.replace('<|eom_id|>', '')
    return new_agent_function

def generate_response(user_prompt, evaluate_agent=False):

    agent_report_function_raw = ollama.chat(
        model='myllama3:latest',
        options={
            'num_predict': 70,
        },
        messages=[{'role': 'tool', 'name': 'get_available_function_information', 'content': available_function_information},
                    {'role': 'user', 'content': user_prompt}],
        stream=False,
    )
    agent_report_function = filter_agent_outputs(agent_report_function_raw['message']['content'])
    print(f'\nFUNC: {agent_report_function}')

    agent_report_function_good = False
    for available_function in ['get_current_network_status', 'get_latest_data_transfer_status', 'summarize_data_transfer_activity', 'get_summary_of_available_knowledge', 'get_data_transfer_instructions', 'no_relevant_function']:
        if available_function in agent_report_function:
            agent_report_function_good = True
            break

    if agent_report_function_good:
        try:
            agent_report_function_output = eval(agent_report_function)  # Use eval carefully, potential security risk.
        except:
            agent_report_function = "no_relevant_function()"
            agent_report_function_output = "Answer the prompt to the best of your ability."
    else:
        agent_report_function = "no_relevant_function()"
        agent_report_function_output = "Answer the prompt to the best of your ability."

    print(f'\nFUNC POST: {agent_report_function}')

    if evaluate_agent:
        return agent_report_function
    # print(agent_report_function_output)
    stream = ollama.chat(
        model='myllama3:latest',
        messages=[{'role': 'tool', 'name': f'{agent_report_function}', 'content': f'{agent_report_function_output}'},
                    {'role': 'user', 'content': f'{user_prompt}. Do not calculate math. Only answer based on context you have. No hypotheticals.'}],
        stream=True,
    )
    return stream

available_agent_information = """
You are an agent that selects pages based on their prompts by executing the most relevant function. The available pages are:

network-status-page: Use this function when the user inquires about network status. It returns the current health of the network infrastructure, including endpoint connectivity, but does not include information on data transfer health. Has no capabilities or functionalities.

transfer-configuration-page: Select this function when the prompt specifically involves questions or intentions regarding data movement, syncing, or transferring.

home-menu-page: Choose this function when the user seeks clarification on the system's knowledge and capabilities, or when the prompt does not align with any of the other specific functions. It provides a summary of all available knowledge, functionalities, and what you can do.

transfer-statistics-page: Use this function to summarize data transfer activities completed within a specified timeframe (default is the last 24 hours). It reports the total bytes transferred, the number of objects synced, and the counts of successful versus failed transfers.

transfer-status-history-page: This function is for prompts requesting details about the most recent or progress on ongoing data transfer or sync operation, including status, data moved, and source/destination information.

no-relevant-page: This function should be selected when the prompt is not related to network status, data transfer, or synchronization operations. This function is for prompts that do not fit into any of the other specific categories.

Given a user prompt, select and execute the most relevant function from the list above to obtain the necessary data. Respond only with the function name. Do not provide explanations.
"""
def generate_agent_function(user_prompt):

    agent_report_function_raw = ollama.chat(
        model='myllama3:latest',
        options={
            'num_predict': 40,
        },
        messages=[{'role': 'tool', 'name': 'get_available_agent_information', 'content': available_agent_information},
                    {'role': 'user', 'content': user_prompt}],
        stream=False,
    )
    agent_report_function = filter_agent_outputs(agent_report_function_raw['message']['content'])
    print(f'AGENT: {agent_report_function}')

    agent_report_function_good = False
    for available_function in ['network-status-page', 'transfer-configuration-page', 'home-menu-page', 'transfer-statistics-page', 'transfer-status-history-page']:
        if available_function in agent_report_function and len(agent_report_function) <= 30:
            agent_report_function_good = True
            break

    if not agent_report_function_good:
        agent_report_function = "home-menu-page"

    print(f'\nAGENT POST: {agent_report_function}')

    return agent_report_function
######################################################################################################
######################################################################################################
######################################################################################################

app = Flask(__name__)

@app.route('/')
def home():
    return render_template('index.html')

########
# START: Prompt handling.
########
def highlight_code(code_snippet, language=None):
    # If the language is specified, use it, otherwise try to guess
    if language:
        lexer = get_lexer_by_name(language)
    else:
        try:
            lexer = guess_lexer(code_snippet)
        except ValueError:
            # Default to plain text if language cannot be guessed
            lexer = get_lexer_by_name("text")

    # Use HtmlFormatter without full document structure
    formatter = HtmlFormatter(style='solarized-dark', full=False, cssclass='codehilite')
    highlighted_code = highlight(code_snippet, lexer, formatter)
    return highlighted_code

def generate_response_stream(user_prompt):
    stream = generate_response(user_prompt)
    def stream_response():
        content = ""
        content_uuid = 0
        for chunk in stream:
            chunk_content = chunk['message']['content']
            content += chunk_content
            if "``" in content and content.count("```") < 2:
                continue
            elif content.count('```') >= 2:
                code_type, code_snippet = content.split('\n', 1)
                code_type = code_type.replace('```', '')
                code_snippet = code_snippet.replace('```', '')
                if code_type == "":
                    code_type = "text"
                formatted_code = highlight_code(code_snippet, language=code_type)
                epoch_time = int(time.time())
                code_type_html = f'''<div class="px-4 py-2 code-response-header">{code_type} 
                <a class="copy-text-btn" id="copy-text-btn-{epoch_time}-{content_uuid}" onclick="copyCodeText('{epoch_time}-{content_uuid}')"><i class="bi-clipboard"></i> copy text</a></div>'''
                content = f'{code_type_html}<div class="px-4 py-2 code-response-body" id="copy-text-{epoch_time}-{content_uuid}">{formatted_code}</div><br>'
                yield content
                content_uuid += 1
                content = ""
            elif "**" in content and content.count("**") < 2:
                continue
            elif content.count("**") >= 2:
                # Replace the first instance of "**" with <strong>
                content = content.replace("**", "<strong>", 1)
                # Replace the second instance of "**" with </strong>
                content = content.replace("**", "</strong>", 1)
                yield content.replace('\n', '<br>')  # Stream the content directly without any additional formatting
                content = ""
            else:
                yield content.replace('\n', '<br>')  # Stream the content directly without any additional formatting
                content = ""
        if content:
            yield content.replace('\n', '<br>')
            content = ""

    return Response(stream_response(), content_type='text/plain')  # Adjust content type

@app.route('/streamResponse', methods=['POST'])
def stream_response():
    prompt = request.json.get('prompt')
    # spawn a thread here to ollama inference agent action
    return generate_response_stream(prompt)

@app.route('/activatePane', methods=['POST'])
def activate_pane():
    data = request.get_json()
    user_prompt = data.get('prompt')

    agent_report_function = filter_agent_outputs(generate_agent_function(user_prompt))
    
    return jsonify({'paneId': agent_report_function})

@app.route('/loadPane/<pane_id>')
def load_pane(pane_id):
    try:
        return render_template(f'{pane_id}.html')
    except:
        return "Pane not found", 404

########
# END: Prompt handling.
########

########
# START: Configuration handling.
########
@app.route('/api/configs')
def api_list_configs():
    configs_dir = os.path.join(app.static_folder, 'configs_cache')
    config_files = [f for f in os.listdir(configs_dir) if f.endswith('.yaml')]
    return jsonify(config_files)

@app.route('/load_config', methods=['GET'])
def load_config():
    config_name = request.args.get('config_name')
    config_path = os.path.join(app.static_folder, 'configs_cache', config_name)

    with open(config_path, 'r') as file:
        config_data = yaml.safe_load(file)

    return jsonify(config_data)

@app.route('/save_config', methods=['POST'])
def save_config():
    config_data = request.json

    config_file_path = os.path.join(app.static_folder, 'configs_cache', f'{config_data["name"]}.yaml')

    try:
        with open(config_file_path, 'w') as file:
            yaml.dump(config_data, file, default_flow_style=False)
        return jsonify({'message': 'Config saved successfully!'}), 200
    except Exception as e:
        return jsonify({'error': str(e)}), 500

@app.route('/delete_config', methods=['DELETE'])
def delete_config():
    config_name = request.args.get('config_name')
    if config_name:
        config_path = os.path.join(app.static_folder, 'configs_cache', config_name)
        if os.path.exists(config_path):
            os.remove(config_path)
            return '', 204  # No Content, deletion successful
        else:
            return jsonify({'error': 'Config file not found'}), 404
    return jsonify({'error': 'No config name provided'}), 400

@app.route('/validate-data-sources', methods=['POST'])
def validate_data_sources():
    validation_results = {
        "src": False,
        "dst": False,
        "log": False
    }
    validation_keys = {
        "src": [],
        "dst": [],
        "log": []
    }

    config = request.get_json()

    src_service = config["src"]["service"]
    src_bucket = config["src"]["bucket"]
    src_prefix = config["src"]["bucket_prefix"]
    src_region = config["src"]["region"]
    src_access_key = config['src']['access_key']
    src_secret_access_key = config['src']['secret_access_key']
    src_endpoint_urls = config['src']['endpoint_urls']

    dst_service = config["dst"]["service"]
    dst_bucket = config["dst"]["bucket"]
    dst_prefix = config["dst"]["bucket_prefix"]
    dst_region = config["dst"]["region"]
    dst_access_key = config['dst']['access_key']
    dst_secret_access_key = config['dst']['secret_access_key']
    dst_endpoint_urls = config['dst']['endpoint_urls']

    log_service = config["log"]["service"]
    log_bucket = config["log"]["bucket"]
    log_prefix = config["log"]["bucket_prefix"]
    log_region = config["log"]["region"]
    log_access_key = config['log']['access_key']
    log_secret_access_key = config['log']['secret_access_key']
    log_endpoint_urls = config['log']['endpoint_urls']

    try:
        # Check source endpoints
        for src_endpoint_url in src_endpoint_urls:
            src_client = create_client(src_service, src_access_key, src_secret_access_key, src_region, src_endpoint_url)
            endpoint_health = is_endpoint_healthy(src_service, src_bucket, src_prefix, src_client, isSnow=(src_region=='snow'))
            if endpoint_health:
                validation_results['src'] = True
                if isinstance(endpoint_health, dict):
                    validation_keys['src'] = list(endpoint_health.keys())[:5]
                break
    except:
        pass
    
    try:
        # Check destination endpoints
        for dst_endpoint_url in dst_endpoint_urls:
            dst_client = create_client(dst_service, dst_access_key, dst_secret_access_key, dst_region, dst_endpoint_url)
            endpoint_health = is_endpoint_healthy(dst_service, dst_bucket, dst_prefix, dst_client, isSnow=(dst_region=='snow'))
            if endpoint_health:
                validation_results['dst'] = True
                if isinstance(endpoint_health, dict):
                    validation_keys['dst'] = list(endpoint_health.keys())[:5]
                break
    except:
        pass

    try:
        # Check log endpoints
        for log_endpoint_url in log_endpoint_urls:
            log_client = create_client(log_service, log_access_key, log_secret_access_key, log_region, log_endpoint_url)
            endpoint_health = is_endpoint_healthy(log_service, log_bucket, log_prefix, log_client, isSnow=(log_region=='snow'))
            if endpoint_health:
                validation_results['log'] = True
                if isinstance(endpoint_health, dict):
                    validation_keys['log'] = list(endpoint_health.keys())[:5]
                break
    except:
        pass

    # time.sleep(5)
    return jsonify({"status": "success", "validation_results": validation_results, "validation_keys": validation_keys})

@app.route('/confirm_data', methods=['POST'])
def confirm_data():
    data = request.get_json()  # Get the JSON data sent from the front-end
    print(f'Got it: {data}')  # Print the data to the console (for debugging purposes)

    # Generate a filename based on the current epoch time
    epoch_time = int(time.time())

    filename = os.path.join(app.static_folder, 'run_configs', f'run_{epoch_time}_config.yaml')

    # Save the data as a YAML file
    with open(filename, 'w') as file:
        yaml.dump(data, file, default_flow_style=False)

    # Run the cloud_transfer.py script as a detached process
    subprocess.Popen(
        ['python', 'cloud_transfer.py', f'{filename}'],
        stdout=subprocess.DEVNULL,
        stderr=subprocess.DEVNULL,
        start_new_session=True
    )

    # Optionally, you can send a response back to the client
    return jsonify({'message': 'Your data transfer/sync has begun!', 'received_data': data})
########
# END: Configuration handling.
########

@app.route('/network-status', methods=['GET'])
def get_network_status():
    network_status = get_current_network_status()
    return jsonify({
        'status': network_status[0],
        'last_updated': network_status[1]
    })

@app.route('/get-list-data-transfers')
def get_list_data_transfers():
    with lock:
        keys = sorted(list(data_transfer_logs.keys()), reverse=False)
    return jsonify(keys)

@app.route('/get-data-transfer-log')
def get_data_transfer_log():
    key = request.args.get('key')
    if key:
        with lock:
            data_transfer_log = load_json_from_s3(log_s3_client, log_bucket, f'{log_prefix}/{key}')
        return jsonify(data_transfer_log)
    return jsonify({"error": "No key provided"}), 400

def build_graph(timeframe_hours=24):
    tot_moved = []
    with lock:
        # Critical section: Fetch recent data logs
        recent_data_transfer_logs = filter_recent_logs(data_transfer_logs, hours=timeframe_hours)
        for recent_data_transfer_log in recent_data_transfer_logs.keys():
            recent_data_transfer_log_data = load_json_from_s3(log_s3_client, log_bucket, f'{log_prefix}/{recent_data_transfer_log}')
            if recent_data_transfer_log_data['objects_moved']:
                tot_moved.extend(recent_data_transfer_log_data['objects_moved'])

    # Data processing and graph creation are outside the lock
    tot_dt_df = pd.DataFrame(tot_moved)
    tot_dt_df['end_datetime'] = pd.to_datetime(tot_dt_df['epoch_time_end'], unit='s')
    tot_dt_df.set_index('end_datetime', inplace=True)

    # Define bar widths
    minute_bar = pd.to_timedelta('1min') / 2
    hour_bar = pd.to_timedelta('1h') / 2
    day_bar = pd.to_timedelta('1d') / 2

    # Resample and create traces
    df_minute = tot_dt_df.resample('min').sum().reset_index()
    df_hour = tot_dt_df.resample('h').sum().reset_index()
    df_day = tot_dt_df.resample('d').sum().reset_index()

    # Create traces for different granularities
    trace_minute = go.Bar(
        x=df_minute['end_datetime'] + minute_bar,  # Use datetime index
        y=df_minute['bytes'] / 1024 / 1024 / 1024,  # Convert bytes to GB
        width =  pd.to_timedelta("1m").total_seconds()*1000,
        marker_color='blue',
        name='By Minute',
        hovertemplate='<b>Date/Time:</b> %{x}<br>' +
                    '<b>Size (GB):</b> %{y:.2f}<br>' +
                    '<extra></extra>',
        visible='legendonly'  # Initially hidden
    )

    trace_hour = go.Bar(
        x=df_hour['end_datetime'] + hour_bar,  # Use datetime column
        y=df_hour['bytes'] / 1024 / 1024 / 1024,  # Convert bytes to GB  # Adjust width
        width = pd.to_timedelta("1h").total_seconds()*1000,
        marker_color='green',
        name='By Hour',
        customdata=df_hour['end_datetime'],
        opacity=0.4,  # Set transparency
        hovertemplate='<b>Date/Time:</b> %{customdata}<br>' +
                    '<b>Size (GB):</b> %{y:.2f}<br>' +
                    '<extra></extra>',
        visible=True  # Initially hidden
    )

    trace_day = go.Bar(
        x=df_day['end_datetime'] + day_bar,  # Use datetime column
        y=df_day['bytes'] / 1024 / 1024 / 1024,  # Convert bytes to GB
        width = pd.to_timedelta("1d").total_seconds()*1000,
        marker_color='red',
        name='By Day',
        customdata=df_day['end_datetime'],
        opacity=0.2,  # Set transparency
        hovertemplate='<b>Date/Time:</b> %{customdata}<br>' +
                    '<b>Size (GB):</b> %{y:.2f}<br>' +
                    '<extra></extra>',
        visible='legendonly'  # Initially hidden
    )

    # Create a figure and add traces
    fig = go.Figure()

    fig.add_trace(trace_minute)
    fig.add_trace(trace_hour)
    fig.add_trace(trace_day)

    # Update layout with range selector and buttons
    fig.update_layout(
        title='Amount of Data Transferred',
        xaxis_title='Date/Time',
        yaxis_title='Size (GB)',
        xaxis=dict(
            tickformat='%A, %Y-%m-%d %H:%M',
            tickangle=-45,
            rangeselector=dict(
                buttons=[
                    dict(count=6, label='1h', step='hour', stepmode='backward'),
                    dict(count=24, label='12h', step='hour', stepmode='backward'),
                    dict(count=5, label='1d', step='day', stepmode='backward'),
                    dict(count=28, label='1w', step='day', stepmode='backward'),
                    dict(count=2, label='1m', step='month', stepmode='backward'),
                    dict(step='all', label='All')  # Show all data
                ],
                visible=True
            ),
            rangeslider=dict(
                visible=True,
                range=[tot_dt_df.index.min(), tot_dt_df.index.max()]
                )
        ),
        yaxis=dict(
            autorange=True,
            tickformat=','
        ),
        barmode='overlay'
    )

    return pio.to_html(fig, full_html=False)

@app.route('/generate-data-moved-graph', methods=['GET', 'POST'])
def generate_data_moved_graph():
    graphobject = build_graph(timeframe_hours=600)
    return jsonify({'plot': graphobject})


if __name__ == '__main__':
    app.run(debug=True)