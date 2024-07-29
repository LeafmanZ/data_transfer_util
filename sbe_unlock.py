import os
import json
import yaml
import time
import argparse
from util_s3 import read_config, file_abspath, run_command
"""
Script Description:
-------------------
This script automates the process of unlocking a Snowball Edge device, retrieving AWS access keys,
and saving them to a YAML file located in a specified directory associated with the Snowball Edge device.

Steps:
1. Wait for SBE to procure its own ip address
2. Create a directory for the snowball and include the manifest file, and sbe_config.yaml
--> unlock_key: "4a859-ce942-73077-9cd73-d5d9c"
--> endpoint_url: "https://192.168.75.124"
3. Run the program on command line:
--> python ./path/to/unlock.py <snowdir>
4. Parse the directory path of the Snowball Edge folder from the command line argument.
5. Read necessary configuration data from a 'sbe_config.yaml' file located in the specified Snowball Edge folder.
6. Unlock the Snowball Edge device using its endpoint URL, manifest file ('manifest.bin'), and unlock code retrieved from the configuration.
7. Retrieve AWS access keys using the unlocked Snowball Edge device and parse the output JSON to obtain the access key ID.
8. Retrieve the AWS secret access key corresponding to the obtained access key ID.
9. Save the AWS access key ID and secret access key to a YAML file named 'keys.yaml' within the same Snowball Edge folder.

Helper Functions Used:
----------------------
- read_config(dir_path): Reads configuration data from 'sbe_config.yaml' located in the specified directory.
- write_yaml(data, snow_folder): Writes provided data (AWS keys) to a YAML file ('keys.yaml') in the specified directory.
- file_abspath(file_name, snow_folder): Retrieves the absolute path of a specified file ('manifest.bin') within the specified directory.

Command Line Argument:
----------------------
- snowdir: The directory path of the Snowball Edge folder containing necessary configuration files. 
Can be given as folder name or path

Usage Example:
--------------
python ./path/to/unlock.py <snowdir>

Note:
- Ensure that the Snowball Edge CLI commands ('snowballEdge unlock-device', 'list-access-keys', 'get-secret-access-key') 
  are properly configured and available on the system where this script runs.
- Replace placeholders like 'read_config', 'write_yaml', and 'file_abspath' with actual functions or imports as per your implementation.
"""

parser = argparse.ArgumentParser(description='Copy a specific object from one S3 bucket to another.')
parser.add_argument('snowdir', type=str, help='The source snowball folder.')

args = parser.parse_args()

# Takes the parsed argument and process it to unlock the snowball and output the access key information
snow_folder = (rf"{args.snowdir}".replace("\\", "/")).split("/")[-1]

# Read in config data from sbe_config.yaml
config = read_config("sbe_config.yaml", dir_path = snow_folder)

# Save necessary data
unlock_key = config["unlock_key"]
endpoint_url = config["endpoint_url"]

# Iterate through current working directory for the .bin file, and save it as the manifest
manifest = file_abspath("manifest.bin", snow_folder)

# Creates the command to unlock the snowball device
unlockcommand = f'snowballEdge unlock-device --endpoint {endpoint_url} --manifest-file "{manifest}" --unlock-code {unlock_key}'

# Create execute script for unlocking sbe
return_code, stdout, stderr = run_command(unlockcommand)

if return_code == 0:
    print(f"\nSuccessfully pushed unlock command.\n")
    print(f'{stdout}')
    
else:
    print(f"Error unlocking Snowball Edge device. Return code: {return_code}")
    print("Error message:")
    print(stderr)
    quit()

# # Checks to see if device is still unlocking
describe_command = f'snowballEdge describe-device --endpoint {endpoint_url} --manifest-file "{manifest}" --unlock-code {unlock_key}'

while True:
    return_code, stdout, stderr = run_command(describe_command)
    
    if return_code == 0:
        # Check the device status from stdout
        try:
            status_info = json.loads(stdout)
            # Example check (modify based on actual output)
            status = status_info.get('UnlockStatus', {}).get('State', 'UNKNOWN')
            
            if status == 'UNLOCKED':  # Replace 'UNLOCKED' with the actual status indicating completion
                print("Device is unlocked.\n")
                break
            else:
                print(f"Device status: {status}...\n")
        except json.JSONDecodeError:
            print("Failed to decode JSON from describe-device output.")
            print(stderr)
            
    else:
        print(f"Error describing device. Return code: {return_code}")
        print("Error message:")
        print(stderr)
    
    time.sleep(10)  # Wait n seconds before checking again

# Create and execute script for getting AWS access key --> takes the access key value of the returned dictionary
keycommand = f'snowballEdge list-access-keys --endpoint {endpoint_url} --manifest-file "{manifest}" --unlock-code {unlock_key}'

print(f'Getting access key...\n')
return_code, stdout, stderr = run_command(keycommand)
if return_code == 0:
    output_dict = json.loads(stdout)
    accesskey = list(output_dict.values())[0][0]
    print(f'Access key: {accesskey}\n')
else:
    print(f"Error could not access keys. Return code: {return_code}")
    print("Error message:")
    print(stderr)

# Create and execute script for getting AWS secret key--> takes the secret key value of the returned list
secretcommand = f'snowballEdge  get-secret-access-key --access-key-id {accesskey} --endpoint {endpoint_url} --manifest-file "{manifest}" --unlock-code {unlock_key}'

print(f'Getting secret access key...\n')
return_code, stdout, stderr = run_command(secretcommand)
if return_code == 0:
    secretkey = stdout.split()[-1]
    print(f'Secret key: {secretkey}\n')
else:
    print(f"Error could not secret access keys. Return code: {return_code}")
    print("Error message:")
    print(stderr)

# Create a keys.yaml file with the access and secret keys
aws_keys = {
    "aws_access_key_id": accesskey,
    "aws_secret_access_key": secretkey     
    }

filename = os.path.abspath(snow_folder)
filename = os.path.join(filename, "keys.yaml")
with open(filename, "w") as file:
    yaml.dump(aws_keys, file)
print(f'Acess keys returned as "keys.yaml" to: {snow_folder}\n\n')
