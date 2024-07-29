
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
