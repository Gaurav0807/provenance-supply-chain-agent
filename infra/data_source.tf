# Data source: which S3 files the knowledge base reads, and how it chunks them.

resource "aws_bedrockagent_data_source" "docs" {
  name                 = "provenance-documents"
  knowledge_base_id    = aws_bedrockagent_knowledge_base.docs.id
  data_deletion_policy = "RETAIN" # deleting a file keeps its vectors; a sync can still remove them

  data_source_configuration {
    type = "S3"
    s3_configuration {
      bucket_arn         = data.aws_s3_bucket.data.arn
      inclusion_prefixes = ["documents/"]
    }
  }

  vector_ingestion_configuration {
    chunking_configuration {
      chunking_strategy = "FIXED_SIZE"
      fixed_size_chunking_configuration {
        max_tokens         = var.chunk_tokens
        overlap_percentage = var.chunk_overlap_pct
      }
    }
  }
}
