import yaml
import subprocess

def read_config(config_path):
    with open(config_path, 'r') as stream:
        try:
            return yaml.safe_load(stream)
        except yaml.YAMLError as exc:
            print(exc)
            return None

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
