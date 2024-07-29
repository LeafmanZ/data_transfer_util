
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
Here's a README template that you can use for your project. It includes sections for each script (`api_service.py` and `api_test_example.py`), detailing both usage instructions for users and explanations for developers on how the code functions.

---

# Project API Service and Testing

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

This README provides a comprehensive guide for both users needing to set up and run the API service and developers looking to understand and test the API functionality.
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

Here's a README template that you can use for your project. It includes sections for each script (`api_service.py` and `api_test_example.py`), detailing both usage instructions for users and explanations for developers on how the code functions.

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
