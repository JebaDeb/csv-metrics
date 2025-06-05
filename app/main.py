import os
import json
import pandas as pd
from flask import Flask, request
from google.cloud import storage, firestore
from datetime import datetime

app = Flask(__name__)
storage_client = storage.Client()
firestore_client = firestore.Client()

BUCKET_NAME = os.environ.get("BUCKET_NAME", "my-csv-ingestion-bucket")


@app.route("/", methods=["POST"])
def handle_pubsub():
    envelope = request.get_json()
    if not envelope or "message" not in envelope:
        return "Invalid Pub/Sub message", 400

    pubsub_message = envelope["message"]
    data = json.loads(base64.b64decode(pubsub_message["data"]).decode("utf-8"))

    file_name = data.get("name", "")
    if not file_name.endswith(".csv") or not file_name.startswith("raw_data/"):
        return f"Skipping non-CSV or non-raw_data file: {file_name}", 400

    # Check Firestore for idempotency
    doc_ref = firestore_client.collection("processed_files").document(file_name)
    if doc_ref.get().exists:
        return f"File already processed: {file_name}", 200

    try:
        bucket = storage_client.bucket(BUCKET_NAME)
        blob = bucket.blob(file_name)
        content = blob.download_as_text()

        # Read CSV using pandas
        df = pd.read_csv(pd.compat.StringIO(content))

        # Compute metrics
        row_count = len(df)
        null_counts = df.isnull().sum().to_dict()

        metrics = {
            "file": file_name,
            "processed_at": datetime.utcnow().isoformat(),
            "row_count": row_count,
            "null_counts": null_counts
        }

        # Save to reports/ as JSON
        report_blob = bucket.blob("reports/" + file_name.replace(".csv", ".json"))
        report_blob.upload_from_string(json.dumps(metrics), content_type="application/json")

        # Mark file as processed
        doc_ref.set({
            "processed": True,
            "timestamp": datetime.utcnow().isoformat()
        })

        return f"Processed {file_name}", 200

    except Exception as e:
        return f"Error processing file: {str(e)}", 500

