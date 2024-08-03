import subprocess
import argparse
from util_sbe import read_config, file_abspath
"""
Script Description:
-------------------
This script automates the process of configuring a Snowball Edge device to streamline snowball edge CLI.
This will allow commands to be run without needing to input the manifest file, unlock key, and endpoint each time.

Steps:
1. Ensure manifest file ends in manifest.bin
2. Ensure existense of sbe_config.yaml file with unlock key and endpoint information
--> unlock_key: "4a859-ce942-73077-9cd73-d5d9c"
--> endpoint_url: "https://192.168.75.124"
3. Run the script on command line:
--> python ./path/to/sbe_configure.py <snowdir>
1. Wait for SBE to procure its own ip address
2. Create a directory for the snowball and include the manifest file, and sbe_config.yaml
--> unlock_key: "4a859-ce942-73077-9cd73-d5d9c"
--> endpoint_url: "https://192.168.75.124"
3. Run the program on command line:
--> python ./path/to/unlock.py <snowdir>
4. The program will run and used the name of the snowdir as the profile name

Helper Functions Used:
----------------------
- read_config(dir_path): Reads configuration data from 'sbe_config.yaml' located in the specified directory.
- file_abspath(file_name, snow_folder): Retrieves the absolute path of a specified file ('manifest.bin') within the specified directory.
- run_command(command): Runs subprocess commands and waits for command to finish

Command Line Argument:
----------------------
- snowdir: The directory path of the Snowball Edge folder containing necessary configuration files. 
Can be given as folder name or path

Usage Example:
--------------
python ./path/to/sbe_configure.py <snowdir>

"""

parser = argparse.ArgumentParser(description='Copy a specific object from one S3 bucket to another.')
parser.add_argument('snowdir', type=str, help='The snowball profile folder --> will be used for profile name.')

args = parser.parse_args()

# Takes the parsed argument and process it 
snow_folder = (rf"{args.snowdir}".replace("\\", "/")).split("/")[-1]

# Iterate through current working directory for the .bin file, and save it as the manifest
manifest = file_abspath("manifest.bin", snow_folder)

# Read sbe_config.yaml to process the unlock key and endpoint url
config = read_config("sbe_config.yaml", snow_folder)
unlock_key = config["unlock_key"]
endpoint = config["endpoint_url"]

command = "snowballEdge configure"

try:
    # Start the subprocess
    with subprocess.Popen(command, shell=True, stdin=subprocess.PIPE, stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True) as process:
        
        # Send manifest file path and simulate Enter key press
        process.stdin.write(manifest + "\n")
        
        # Send unlock key and simulate Enter key press
        process.stdin.write(unlock_key + "\n")
        
        # Send endpoint and simulate Enter key press
        process.stdin.write(endpoint + "\n")
        
        # Close stdin to indicate end of input
        process.stdin.close()
        
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

