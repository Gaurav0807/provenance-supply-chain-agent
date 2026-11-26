# Vector index: Bedrock needs this index to exist before it creates the knowledge base.
# Terraform cannot create OpenSearch indexes, so a small script creates it during apply.
# The script is safe to run again: it does nothing if the index already exists.

resource "terraform_data" "vector_index" {
  triggers_replace = [aws_opensearchserverless_collection.docs.collection_endpoint, local.index_name]

  depends_on = [aws_opensearchserverless_access_policy.data]

  provisioner "local-exec" {
    command = "python ../scripts/create_vector_index.py"
    environment = {
      AOSS_ENDPOINT = aws_opensearchserverless_collection.docs.collection_endpoint
      INDEX_NAME    = local.index_name
      AWS_REGION    = var.region
    }
  }
}
