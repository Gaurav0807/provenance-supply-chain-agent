# Ingest Lambda: when messages arrive from SQS, start a knowledge base sync.
# The zip is built by Terraform from lambda/ingest/handler.py, so there is no separate build step.

data "archive_file" "ingest" {
  type        = "zip"
  source_file = "${path.module}/../lambda/ingest/handler.py"
  output_path = "${path.module}/ingest.zip"
}

resource "aws_lambda_function" "ingest" {
  function_name    = "provenance-ingest"
  role             = aws_iam_role.ingest.arn
  runtime          = "python3.11"
  handler          = "handler.handler"
  filename         = data.archive_file.ingest.output_path
  source_code_hash = data.archive_file.ingest.output_base64sha256
  timeout          = 60

  environment {
    variables = {
      KNOWLEDGE_BASE_ID = aws_bedrockagent_knowledge_base.docs.id
      DATA_SOURCE_ID    = aws_bedrockagent_data_source.docs.data_source_id
    }
  }
}

resource "aws_lambda_event_source_mapping" "ingest" {
  event_source_arn        = aws_sqs_queue.documents.arn
  function_name           = aws_lambda_function.ingest.arn
  batch_size              = 5
  function_response_types = ["ReportBatchItemFailures"]
}
