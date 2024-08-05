import subprocess
import os
import argparse
from util_sbe import read_config, run_command

parser = argparse.ArgumentParser(description='Copy a specific object from one S3 bucket to another.')
parser.add_argument('snowdir', type=str, help='The snowball profile folder --> will be used for profile name.')

args = parser.parse_args()
snow_folder = args.snowdir
profile_name = os.path.basename(snow_folder)

access_keys_config_path = os.path.join(snow_folder, 'keys.yaml')

# Read keys.yaml to get access keys
config = read_config(access_keys_config_path)
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