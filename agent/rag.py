"""Document search through the Bedrock knowledge base.

The knowledge base handles chunking, embeddings and vector storage, so this only calls retrieve.
"""
import os

from agent.aws import session

_client = session().client("bedrock-agent-runtime")


def search_documents(query, k=5):
    kb_id = os.environ.get("KNOWLEDGE_BASE_ID")
    if not kb_id:
        raise RuntimeError("KNOWLEDGE_BASE_ID is not set")
    resp = _client.retrieve(
        knowledgeBaseId=kb_id,
        retrievalQuery={"text": query},
        retrievalConfiguration={"vectorSearchConfiguration": {"numberOfResults": k}},
    )
    return [
        {
            "doc": r["location"]["s3Location"]["uri"].split("/")[-1],
            "text": r["content"]["text"],
            "score": r.get("score"),
        }
        for r in resp["retrievalResults"]
    ]
