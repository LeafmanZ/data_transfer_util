import os
import json
import yaml
import time
import argparse
from util_sbe import read_config, run_command

parser = argparse.ArgumentParser(description='Unlock a Snowball Edge device and retrieve AWS keys.')
parser.add_argument('snowdir', type=str, help='Directory containing sbe_config.yaml and manifest.bin')
args = parser.parse_args()
snow_folder = args.snowdir
config_path = os.path.join(snow_folder, "sbe_config.yaml")

# Find the manifest file
manifest_name = None
for root, dirs, files in os.walk(snow_folder):
    for file in files:
        if file.endswith('manifest.bin'):
            manifest_name = file
            break
    if manifest_name:
        break

if not manifest_name:
    print("No manifest file found.")
    exit()

manifest_path = os.path.join(snow_folder, manifest_name)
config = read_config(config_path)
unlock_key = config.get("unlock_key")
endpoint_url = config.get("endpoint_url")

# Unlock the device
unlock_command = f'snowballEdge unlock-device --endpoint {endpoint_url} --manifest-file "{manifest_path}" --unlock-code {unlock_key}'
return_code, stdout, stderr = run_command(unlock_command)
if return_code != 0:
    print(f"Error unlocking Snowball Edge device. Return code: {return_code}\nError message:\n{stderr}")
    exit()

# Check device status
describe_command = f'snowballEdge describe-device --endpoint {endpoint_url} --manifest-file "{manifest_path}" --unlock-code {unlock_key}'
while True:
    return_code, stdout, stderr = run_command(describe_command)
    if return_code == 0:
        status_info = json.loads(stdout)
        status = status_info.get('UnlockStatus', {}).get('State', 'UNKNOWN')
        if status == 'UNLOCKED':
            print("Device is unlocked.\n")
            break
        else:
            print(f"Device status: {status}...\n")
    else:
        print(f"Error describing device. Return code: {return_code}\nError message:\n{stderr}")
        exit()
    time.sleep(10)

# Retrieve access key ID
keycommand = f'snowballEdge list-access-keys --endpoint {endpoint_url} --manifest-file "{manifest_path}" --unlock-code {unlock_key}'
return_code, stdout, stderr = run_command(keycommand)
if return_code != 0:
    print(f"Error could not access keys. Return code: {return_code}\nError message:\n{stderr}")
    exit()
output_dict = json.loads(stdout)
accesskey = list(output_dict.values())[0][0]

# Retrieve secret access key
secretcommand = f'snowballEdge get-secret-access-key --access-key-id {accesskey} --endpoint {endpoint_url} --manifest-file "{manifest_path}" --unlock-code {unlock_key}'
return_code, stdout, stderr = run_command(secretcommand)
if return_code != 0:
    print(f"Error could not retrieve secret access keys. Return code: {return_code}\nError message:\n{stderr}")
    exit()
secretkey = stdout.split()[-1]

# Save keys to YAML
aws_keys = {"aws_access_key_id": accesskey, "aws_secret_access_key": secretkey}
keys_filename = os.path.join(snow_folder, "keys.yaml")
with open(keys_filename, "w") as file:
    yaml.dump(aws_keys, file)
print(f'Access keys saved as "keys.yaml" in: {snow_folder}\n')
