"""Start a Bedrock knowledge base sync when documents arrive. Triggered by SQS.

The knowledge base reads documents/ from S3, chunks them, embeds them with Titan,
and stores the vectors. One sync scans the whole data source, so one sync per batch is enough.
"""
import os

import boto3

client = boto3.client("bedrock-agent")


def handler(event, context):
    try:
        job = client.start_ingestion_job(
            knowledgeBaseId=os.environ["KNOWLEDGE_BASE_ID"],
            dataSourceId=os.environ["DATA_SOURCE_ID"],
        )
        print("started ingestion job", job["ingestionJob"]["ingestionJobId"])
        return {"batchItemFailures": []}
    except client.exceptions.ConflictException:
        # A sync is already running. Mark the messages failed so SQS retries them later.
        print("ingestion already running; retrying batch later")
        return {"batchItemFailures": [{"itemIdentifier": r["messageId"]} for r in event["Records"]]}
