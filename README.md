
---
---

# S3 Data Transfer Scripts

This document provides a detailed overview of two Python scripts designed for managing data transfers between AWS S3 buckets. The scripts facilitate data synchronization, particularly useful in environments involving AWS Snowball or similar services.

## s3_transfer.py

### Usage

This script orchestrates the transfer of data between two S3 buckets. To use the script, configure the `config.yaml` file with the necessary details about the source and destination buckets, including access keys, region, and endpoint URLs. Then run the script using the following command:

```
python s3_transfer.py
```

**Configuration Parameters:**
- `bucket`: The name of the bucket.
- `bucket_prefix`: Directory path within the bucket where data resides.
- `region`: Set to 'snow' if using AWS Snowball.
- `access_key` and `secret_access_key`: Credentials for S3 access.
- `endpoint_urls`: List of endpoint URLs to manage high availability and load balancing.

### For Developers

The `s3_transfer.py` script automates the process of comparing objects between the source and destination buckets, and performing the data transfer. It utilizes multi-threading to enhance the transfer efficiency, distributing tasks across available CPU cores. Key functions include:

- **Configuration Loading**: Reads the settings from `config.yaml` and initializes the environment.
- **JSON Logging**: Tracks the transfer status, including details about the data moved, the duration of the transfer, and any errors encountered.
- **S3 Client Management**: Handles connections to AWS S3, accommodating different regions and special configurations like Snowball.
- **Concurrency**: Uses `ThreadPoolExecutor` for parallel processing to optimize transfer times.

## s3_sync_obj.py

### Usage

This helper script is invoked by `s3_transfer.py` to handle the transfer of individual objects. It is not intended to be run independently. A typical invocation by the main script looks like this:

```
python s3_sync_obj.py {src_bucket} {dst_bucket} {src_key} {dst_key} {bytes} {src_endpoint_url} {dst_endpoint_url} {dt_data_json_dir}
```

### For Developers

`s3_sync_obj.py` is designed for robust and efficient object transfer, including error handling and performance tracking. Key features include:

- **Argument Parsing**: Collects all necessary details for the transfer via command-line arguments.
- **Secure S3 Client Setup**: Establishes secure connections to the S3 buckets, with special consideration for regions and custom endpoint URLs.
- **Data Streaming and Uploading**: Optimizes data transfers by streaming objects directly between buckets to minimize local resource utilization.
- **Performance Logging**: Records the transfer time and updates a JSON log with the completion details for each object moved.

---
---

# API Service and Testing

This document provides detailed information on how to set up and interact with the API services, as well as how to run tests on the API endpoints using provided example scripts.

## api_service.py

### Usage

To set up the API service on a Linux system, follow these steps:

1. **Navigate to the current directory where `api_service.py` is located.**
2. **Install OpenSSL if not already installed:**
   ```
   sudo apt-get install openssl
   ```
3. **Generate SSL certificates:**
   ```
   openssl req -newkey rsa:2048 -nodes -keyout key.pem -x509 -days 365 -out cert.pem
   ```
   Follow the prompts to complete the form for the certificate.
4. **Find the Python path:**
   ```
   type which python
   ```
   Use the output path to run the script as shown below.
5. **Run the API service:**
   ```
   sudo /home/ubuntu/anaconda3/bin/python api_service.py
   ```

### Developer Documentation

This script initializes a Flask application to serve an API that interacts with AWS S3 for logging purposes. Key components:

- **Environment Setup:** The script requires SSL certificates (`key.pem` and `cert.pem`) for HTTPS.
- **Configuration:** It reads configuration from a JSON file using `util_s3` helper functions and sets up an S3 client for log retrieval.
- **Endpoints:**
  - `GET /`: Lists all available routes and their descriptions.
  - `GET /logs`: Lists log files within a specified time range.
  - `GET /log/<epoch_time>`: Retrieves a specific log file by epoch time.
  - `GET /log/latest`: Retrieves the most recent log file.

## api_test_example.py

### Usage

This script is used to test the endpoints of the API deployed by `api_service.py`. It can be run in a Jupyter notebook or directly in its folder.

1. **Ensure the API URL and port number are correctly configured:**
   ```
   API_URL = 'http://127.0.0.1:5000'
   ```
2. **Set the same authorization token as in `api_service.py`:**
   ```
   API_TOKEN = 'your_secure_token_here'
   ```
3. **Run the script:**
   Execute the script to test various endpoints using predefined epoch times.

### Developer Documentation

The script uses the `requests` library to send HTTP requests to the API:

- **Testing Functions:**
  - `test_list_logs(start_time, end_time)`: Tests the listing of logs between two epoch times.
  - `test_get_log(epoch_time, retrieve_objects_moved)`: Tests retrieval of a specific log by its epoch time.
  - `test_get_latest_log(retrieve_objects_moved)`: Tests retrieval of the latest log.

Each function prints the status code and JSON response for its respective API call, facilitating easy debugging and verification of API behavior.

---
---
# Setting up Snowball Edge
This will include steps to ensuring proper automated set up of your SBE. All scripts starting with sbe_ and ending with .py will be used for the set up. They are and will be used in this respective order:
1. sbe_unlock.py
2. sbe_profile.py
3. sbe_config.py

**Before you begin:**

1. **Wait for the Snowball Edge (SBE) to procure its own IP address.**
2. **Prepare the Directory**: Create a directory for the Snowball Edge and include the manifest file ending with (`manifest.bin`) and `sbe_config.yaml` with the following configuration:
   ```yaml
   unlock_key: "unlock-key-numbers-go-here"
   endpoint_url: "https://you.rnu.mbe.rs"
   ```

## sbe_unlock.py

### Usage

This script automates the process of unlocking a Snowball Edge device, retrieving AWS access keys, and saving them to a YAML file located in the snowball directory as `keys.yaml`. This will be used in the later scripts in this process.

**Run the Script**: Execute the script from the command line with the directory path of the Snowball Edge folder (snowdir) as an argument:
   ```bash
   python ./path/to/sbe_unlock.py <full/path/to/snowdir>
   ```

### Developer Documentation
This script, `sbe_unlock.py`, is the first step of the automated process of unlocking and using your AWS Snowball Edge device.  
Key features of this script include:
- **Argument Parsing**: The script retrieves the path of the Snowball Edge directory from the command line argument.
- **Unlocking the Device**: It enters the Snowball directory and accesses the endpoint URL and unlock code from the `sbe_config.yaml` file and `manifest.bin` file to unlock the Snowball Edge device.
- **Check and Wait**: Program continuously checks and waits for unlock process to complete.
- **Retrieve Access Keys**: Obtains AWS access and secret keys and writes to the Snowball directory as `keys.yaml`.


## sbe_profile.py

### Usage

This script configures AWS CLI profiles using the credentials obtained from the Snowball Edge device. It reads the credentials from the `keys.yaml` file created by `sbe_unlock.py` and sets up the AWS CLI profile accordingly. The profile name used for this configuration will be the same as the Snowball directory.

**Run the Script**: Execute the script from the command line with the directory path of the Snowball Edge folder (snowdir) as an argument:
   ```bash
   python ./path/to/sbe_profile.py <full/path/to/snowdir>
   ```

### Developer Documentation

The `sbe_profile.py` script is the second step in the automated setup process of configuring AWS CLI profiles for your Snowball Edge device.  
Key features of this script include:
- **Argument Parsing**: Retrieves the path of the Snowball Edge directory from the command line argument and processes it to create the profile name.
- **AWS Configuration**: Reads the `keys.yaml` file to obtain AWS access and secret keys. It then creates and sets up an AWS CLI profile using these credentials.
- **Command Execution**: Executes necessary AWS CLI commands to configure the profile with the access keys, secret keys, region, and output format.

## sbe_config.py

### Usage

This script configures the Snowball Edge device by providing it with the necessary details such as the manifest file path, unlock key, and endpoint URL. This will allow the user to configure the default Snowball profile to allow for usage of the SnowballEdge CLI.  

**Run the Script**: Execute the script from the command line with the directory path of the Snowball Edge folder (snowdir) as an argument:
   ```bash
   python ./path/to/sbe_config.py <path/to/snowdir>
   ```

### Developer Documentation

The `sbe_config.py` script is the final step in the automated setup process of configuring your Snowball Edge device.  
Key features of this script include:

- **Argument Parsing**: Retrieves the Snowball Edge directory path from the command line argument and processes it to determine the configuration.
- **Device Configuration**: Iteratively configures each of the prompts given by the `snowballEdge configure` command using the provided manifest file, unlock key, and endpoint URL.


This configuration will ultimately allow the user to run commands such as:
   ```bash
   snowballEdge describe-device
   ```
Instead of:
   ```bash
   snowballEdge describe-device --endpoint https://123.456.78.900 --manifest-file "C:PATH/TO/manifest.bin" --unlock-code really-big-unlock-code-#
   ```
---
