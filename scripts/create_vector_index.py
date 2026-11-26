"""Create the vector index in the OpenSearch Serverless collection.

Called by infra/index.tf during terraform apply. Safe to run again.
The field names must match field_mapping in infra/knowledge_base.tf.
"""
import hashlib
import json
import os
import sys

import boto3
import requests
from botocore.auth import SigV4Auth
from botocore.awsrequest import AWSRequest

ENDPOINT = os.environ["AOSS_ENDPOINT"].rstrip("/")
INDEX = os.environ.get("INDEX_NAME", "provenance-index")
REGION = os.environ.get("AWS_REGION", "us-east-1")
DIMS = 1024  # Titan Embed v2 default

INDEX_BODY = {
    "settings": {"index": {"knn": True}},
    "mappings": {
        "properties": {
            "AMAZON_BEDROCK_VECTOR": {
                "type": "knn_vector",
                "dimension": DIMS,
                "method": {"name": "hnsw", "engine": "faiss", "space_type": "l2"},
            },
            "AMAZON_BEDROCK_TEXT": {"type": "text"},
            "AMAZON_BEDROCK_METADATA": {"type": "text", "index": False},
        }
    },
}


def signed(method, path, body=None):
    """Send a request to OpenSearch Serverless, signed with the caller's AWS credentials.

    The body hash must be sent as a header. Without it, requests with a body are refused with 403.
    """
    url = ENDPOINT + path
    data = json.dumps(body).encode() if body is not None else b""
    headers = {"Content-Type": "application/json", "x-amz-content-sha256": hashlib.sha256(data).hexdigest()}
    req = AWSRequest(method=method, url=url, data=data, headers=headers)
    credentials = boto3.Session(region_name=REGION).get_credentials().get_frozen_credentials()
    SigV4Auth(credentials, "aoss", REGION).add_auth(req)
    return requests.request(method, url, data=data, headers=dict(req.headers), timeout=60)


def main():
    if signed("GET", f"/{INDEX}").status_code == 200:
        print(f"index {INDEX} already exists")
        return
    r = signed("PUT", f"/{INDEX}", INDEX_BODY)
    if r.status_code >= 300:
        print(r.status_code, r.text)
        sys.exit(1)
    print(f"created index {INDEX}")


if __name__ == "__main__":
    main()
