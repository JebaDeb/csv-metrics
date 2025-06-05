import pandas as pd
from google.cloud import storage, firestore
import json
from io import StringIO

# Initialize GCS and Firestore clients
storage_client = storage.Client()
firestore_client = firestore.Client()

def is_already_processed(file_name: str) -> bool:
    doc_ref = firestore_client.collection("processed_files").document(file_name)
    return doc_ref.get().exists

def mark_as_processed(file_name: str):
    doc_ref = firestore_client.collection("processed_files").document(file_name)
    doc_ref.set({"status": "processed"})

def read_csv_from_gcs(bucket_name: str, file_name: str) -> pd.DataFrame:
    bucket = storage_client.bucket(bucket_name)
    blob = bucket.blob(file_name)
    data = blob.download_as_text()
    return pd.read_csv(StringIO(data))

def compute_metrics(df: pd.DataFrame) -> dict:
    return {
        "row_count": len(df),
        "null_counts": df.isnull().sum().to_dict()
    }

def write_metrics_to_gcs(bucket_name: str, file_name: str, metrics: dict):
    report_file_name = file_name.replace("raw-data/", "reports/").replace(".csv", ".json")
    bucket = storage_client.bucket(bucket_name)
    blob = bucket.blob(report_file_name)
    blob.upload_from_string(json.dumps(metrics, indent=2), content_type="application/json")
