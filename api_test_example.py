import requests
import json

API_URL = 'http://127.0.0.1:443'
API_TOKEN = 'your_secure_token_here'
HEADERS = {'Authorization': API_TOKEN}

def test_list_logs(start_time, end_time):
    print("Testing /logs endpoint...")
    response = requests.get(f"{API_URL}/logs", headers=HEADERS, params={'start': start_time, 'end': end_time}, verify=False)
    print(f"Status Code: {response.status_code}")
    print("Response:")
    print(json.dumps(response.json(), indent=4))

def test_get_log(epoch_time, retrieve_objects_moved=False):
    print(f"Testing /log/{epoch_time} endpoint...")
    response = requests.get(f"{API_URL}/log/{epoch_time}", headers=HEADERS, params={'retrieve_objects_moved': retrieve_objects_moved}, verify=False)
    print(f"Status Code: {response.status_code}")
    print("Response:")
    print(json.dumps(response.json(), indent=4))

def test_get_latest_log(retrieve_objects_moved=False):
    print("Testing /log/latest endpoint...")
    response = requests.get(f"{API_URL}/log/latest", headers=HEADERS, params={'retrieve_objects_moved': retrieve_objects_moved}, verify=False)
    print(f"Status Code: {response.status_code}")
    print("Response:")
    print(json.dumps(response.json(), indent=4))

if __name__ == '__main__':
    # Adjust these parameters according to your test data
    start_time = 1721835440  # Example start time epoch
    end_time = 1821835460    # Example end time epoch
    epoch_time = 1722011110  # Example epoch time

    line_separator = '\n##########################\n'
    print(line_separator)
    test_list_logs(start_time, end_time)
    print(line_separator)
    test_get_log(epoch_time, retrieve_objects_moved=False)
    print(line_separator)
    test_get_latest_log(retrieve_objects_moved=False)
