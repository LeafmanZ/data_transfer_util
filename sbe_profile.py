import subprocess
import argparse
from util_s3 import read_config, file_abspath, run_command

"""
Script Description:
-------------------
This script automates the configuration of AWS CLI profiles using AWS access keys retrieved from a 'keys.yaml' file.
It sets up AWS CLI configurations for a specified profile using the access keys stored in the YAML file.

Steps:
1. Parse the directory path of the Snowball profile folder from the command line argument.
2. Extract the profile name from the provided Snowball profile directory path.
3. Locate the manifest file ('manifest.bin') within the specified Snowball profile directory.
4. Read AWS access keys ('aws_access_key_id' and 'aws_secret_access_key') from 'keys.yaml' located in the Snowball profile directory.
5. Create AWS CLI commands to set AWS configurations (access key, secret key, region, output format) for the specified profile.
6. Execute each AWS configuration command using subprocess to configure AWS CLI settings for the profile.
7. Display success or error messages for each configuration command executed.

Helper Functions Used:
----------------------
- read_config(file_name, folder_name): Reads configuration data (AWS access keys) from 'keys.yaml' located in the specified folder.
- file_abspath(file_name, folder_name): Retrieves the absolute path of a specified file ('manifest.bin') within the specified directory.

Command Line Argument:
----------------------
- snowdir: The directory path of the Snowball profile folder containing 'keys.yaml' and 'manifest.bin'. 
Can be given as folder name or path. 

Usage Example:
--------------
python ./path/to/sbe_profile.py <snowdir>

Notes:
------
- Ensure that the AWS CLI is properly installed and configured on the system where this script runs.
- Replace placeholders like 'read_config' and 'file_abspath' with actual functions or imports as per your implementation.
- After running the script, verify AWS configurations in '~/.aws/config' and '~/.aws/credentials' for the specified profile.
"""

parser = argparse.ArgumentParser(description='Copy a specific object from one S3 bucket to another.')
parser.add_argument('snowdir', type=str, help='The snowball profile folder --> will be used for profile name.')

args = parser.parse_args()

# Takes the parsed argument and process it to create the profile name
profile_name = (rf"{args.snowdir}".replace("\\", "/")).split("/")[-1]

# Iterate through current working directory for the .bin file, and save it as the manifest
manifest = file_abspath("manifest.bin", profile_name)

# Read keys.yaml to get access keys
config = read_config("keys.yaml", profile_name)
accesskey = config["aws_access_key_id"]
secretkey = config["aws_secret_access_key"]

# Create commands for setting AWS configurations using folder name argument and access keys
commands = [
    f'aws configure --profile {profile_name} set aws_access_key_id {accesskey}',
    f'aws configure --profile {profile_name} set aws_secret_access_key {secretkey}',
    f'aws configure --profile {profile_name} set region snow',
    f'aws configure --profile {profile_name} set output json'
]

# Executes each AWS configuration command individually
for command in commands:
    try:
        return_code, stdout, stderr = run_command(command)
        if return_code == 0:
            print(f"\nCommand: '{command}' executed successfully.")
    except subprocess.CalledProcessError as e:
        print(f"Error executing command '{command}':")
        print("Return code:", e.returncode)
        print("STDERR:\n", e.stderr)

print("\nAWS configuration complete!\nCheck '~/.aws/config' and '~/.aws/credentials' for confirmation. \n\n")