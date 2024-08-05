import subprocess
import argparse
import os
from util_sbe import read_config

parser = argparse.ArgumentParser(description='Copy a specific object from one S3 bucket to another.')
parser.add_argument('snowdir', type=str, help='The snowball profile folder --> will be used for profile name.')

args = parser.parse_args()
snow_folder = args.snowdir

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

# Read sbe_config.yaml to process the unlock key and endpoint url
config = read_config(os.path.join(snow_folder, "sbe_config.yaml"))
unlock_key = config["unlock_key"]
endpoint = config["endpoint_url"]

command = "snowballEdge configure"

try:
    # Start the subprocess
    with subprocess.Popen(command, shell=True, stdin=subprocess.PIPE, stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True) as process:
        
        # Send manifest file path and simulate Enter key press
        process.stdin.write(manifest_path + "\n")
        
        # Send unlock key and simulate Enter key press
        process.stdin.write(unlock_key + "\n")
        
        # Send endpoint and simulate Enter key press
        process.stdin.write(endpoint + "\n")
        
        # Flush stdin to ensure all input is sent before closing
        process.stdin.flush()
        
        # Read stdout and stderr (optional)
        stdout, stderr = process.communicate()
        
        # Check return code
        if process.returncode == 0:
            print("\nSnowball Edge device configured successfully!\n")
        else:
            print(f"Error configuring Snowball Edge device. Return code: {process.returncode}")
            print("Error message:")
            print(stderr)
except subprocess.CalledProcessError as e:
    print(f"Error: {e}")
except Exception as e:
    print(f"Unexpected error: {e}")
