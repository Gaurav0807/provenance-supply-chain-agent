"""AWS session shared by the agent, the judge and the evals.

Locally: export AWS_PROFILE=provenance-new
In CI or Lambda: no profile is set, so the default credentials are used.
"""
import os

import boto3


def session():
    return boto3.Session(
        profile_name=os.environ.get("AWS_PROFILE") or None,
        region_name=os.environ.get("AWS_REGION", "us-east-1"),
    )
