import yaml
import os
import subprocess

# Finds the absolute path of a file from the current directory
def file_abspath(ending, dir_path = "."):
    for root, dirs, files in os.walk(dir_path):
        for file in files:
            if file.endswith(ending):
                file_path = os.path.join(root, file)
                if os.path.isfile(file_path):
                    return os.path.abspath(file_path)

# Reads into the sbe_config.yaml file
def read_config(filename='config.yaml', dir_path = "."):
    filename = file_abspath(filename , dir_path)
    with open(filename, 'r') as stream:
        try:
            return yaml.safe_load(stream)
        except yaml.YAMLError as exc:
            print(exc)
            return None

# Runs subprocess commands and waits for command to finish
def run_command(command):
    try:
        with subprocess.Popen(command, shell=True, stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True) as process:
            stdout, stderr = process.communicate()
            return process.returncode, stdout, stderr
    except subprocess.CalledProcessError as e:
        print(f"Error running command: {e}")
        return e.returncode, '', str(e)
    except Exception as e:
        print(f"Unexpected error: {e}")
        return 1, '', str(e)