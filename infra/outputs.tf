output "knowledge_base_id" {
  value = aws_bedrockagent_knowledge_base.docs.id
}

output "data_source_id" {
  value = aws_bedrockagent_data_source.docs.data_source_id
}

output "collection_endpoint" {
  value = aws_opensearchserverless_collection.docs.collection_endpoint
}

output "documents_queue_url" {
  value = aws_sqs_queue.documents.url
}

output "guardrail_id" {
  value = aws_bedrock_guardrail.agent.guardrail_id
}

output "guardrail_version" {
  value = aws_bedrock_guardrail_version.agent.version
}
