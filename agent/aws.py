"""AWS session shared by the agent, the judge and the evals.

Locally: export AWS_PROFILE=provenance-new
In CI or Lambda: no profile is set, so the default credentials are used.
"""
import os

import boto3
from botocore.config import Config


def session():
    return boto3.Session(
        profile_name=os.environ.get("AWS_PROFILE") or None,
        region_name=os.environ.get("AWS_REGION", "us-east-1"),
    )


def bedrock_client():
    """Bedrock runtime client. Retries throttled calls with backoff, so a busy model slows the run instead of stopping it."""
    return session().client(
        "bedrock-runtime",
        config=Config(retries={"max_attempts": 12, "mode": "adaptive"}, read_timeout=120),
    )
