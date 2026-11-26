# Knowledge base: Bedrock reads the documents, splits them into chunks, embeds them with Titan,
# and stores the vectors in the collection. Queries go through its retrieve API.

resource "aws_bedrockagent_knowledge_base" "docs" {
  name     = "provenance-docs"
  role_arn = aws_iam_role.kb.arn

  knowledge_base_configuration {
    type = "VECTOR"
    vector_knowledge_base_configuration {
      embedding_model_arn = "arn:aws:bedrock:${var.region}::foundation-model/${var.embedding_model}"
    }
  }

  storage_configuration {
    type = "OPENSEARCH_SERVERLESS"
    opensearch_serverless_configuration {
      collection_arn    = aws_opensearchserverless_collection.docs.arn
      vector_index_name = local.index_name
      field_mapping {
        vector_field   = "AMAZON_BEDROCK_VECTOR"
        text_field     = "AMAZON_BEDROCK_TEXT"
        metadata_field = "AMAZON_BEDROCK_METADATA"
      }
    }
  }

  depends_on = [terraform_data.vector_index, aws_iam_role_policy.kb]
}
