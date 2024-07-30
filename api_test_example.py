import requests
import json

API_URL = 'https://3.88.35.127'
API_TOKEN = 'your_secure_token_here'
HEADERS = {'Authorization': API_TOKEN}

def test_list_logs(file_type, start_time, end_time):
    print(f"Testing /logs endpoint for {file_type}...")
    response = requests.get(f"{API_URL}/logs", headers=HEADERS, params={'file_type': file_type, 'start': start_time, 'end': end_time}, verify=False)
    print(f"Status Code: {response.status_code}")
    print("Response:")
    try:
        print(json.dumps(response.json(), indent=4))
    except json.JSONDecodeError:
        print(response.text)

def test_get_log(file_type, epoch_time, retrieve_objects_moved=False):
    print(f"Testing /log/{file_type}/{epoch_time} endpoint...")
    response = requests.get(f"{API_URL}/log/{file_type}/{epoch_time}", headers=HEADERS, params={'retrieve_objects_moved': retrieve_objects_moved}, verify=False)
    print(f"Status Code: {response.status_code}")
    print("Response:")
    try:
        print(json.dumps(response.json(), indent=4))
    except json.JSONDecodeError:
        print(response.text)

def test_get_latest_log(file_type, retrieve_objects_moved=False):
    print(f"Testing /log/latest/{file_type} endpoint...")
    response = requests.get(f"{API_URL}/log/latest/{file_type}", headers=HEADERS, params={'retrieve_objects_moved': retrieve_objects_moved}, verify=False)
    print(f"Status Code: {response.status_code}")
    print("Response:")
    try:
        print(json.dumps(response.json(), indent=4))
    except json.JSONDecodeError:
        print(response.text)

if __name__ == '__main__':
    # Adjust these parameters according to your test data
    start_time = 1721835440  # Example start time epoch
    end_time = 1821835460    # Example end time epoch

    file_types = ['hs', 'dt']
    
    for file_type in file_types:
        line_separator = '\n##########################\n'
        print(line_separator)
        test_list_logs(file_type, start_time, end_time)
        print(line_separator)
        if file_type == 'hs':
            test_get_log(file_type, 1722366185, retrieve_objects_moved=False)
        else:
            test_get_log(file_type, 1722011110, retrieve_objects_moved=False)
        print(line_separator)
        test_get_latest_log(file_type, retrieve_objects_moved=False)
        print(line_separator)
