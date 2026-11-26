# Event path: a new document in S3 -> SNS topic -> SQS queue -> ingest Lambda.
# Messages that keep failing go to a dead-letter queue after 10 attempts.

resource "aws_sns_topic" "documents" {
  name = "provenance-documents"
}

# Only this bucket may publish to the topic
resource "aws_sns_topic_policy" "documents" {
  arn = aws_sns_topic.documents.arn
  policy = jsonencode({
    Version = "2012-10-17"
    Statement = [{
      Effect    = "Allow"
      Principal = { Service = "s3.amazonaws.com" }
      Action    = "SNS:Publish"
      Resource  = aws_sns_topic.documents.arn
      Condition = { ArnLike = { "aws:SourceArn" = data.aws_s3_bucket.data.arn } }
    }]
  })
}

# Every new .md file under documents/ publishes a message
resource "aws_s3_bucket_notification" "documents" {
  bucket = data.aws_s3_bucket.data.id

  topic {
    topic_arn     = aws_sns_topic.documents.arn
    events        = ["s3:ObjectCreated:*"]
    filter_prefix = "documents/"
    filter_suffix = ".md"
  }

  depends_on = [aws_sns_topic_policy.documents]
}

resource "aws_sqs_queue" "documents_dlq" {
  name                      = "provenance-documents-dlq"
  message_retention_seconds = 1209600 # 14 days, to inspect failures
}

resource "aws_sqs_queue" "documents" {
  name                       = "provenance-documents"
  visibility_timeout_seconds = 180 # at least the Lambda timeout
  redrive_policy = jsonencode({
    deadLetterTargetArn = aws_sqs_queue.documents_dlq.arn
    maxReceiveCount     = 10
  })
}

# Only this topic may send messages to the queue
resource "aws_sqs_queue_policy" "documents" {
  queue_url = aws_sqs_queue.documents.id
  policy = jsonencode({
    Version = "2012-10-17"
    Statement = [{
      Effect    = "Allow"
      Principal = { Service = "sns.amazonaws.com" }
      Action    = "sqs:SendMessage"
      Resource  = aws_sqs_queue.documents.arn
      Condition = { ArnEquals = { "aws:SourceArn" = aws_sns_topic.documents.arn } }
    }]
  })
}

resource "aws_sns_topic_subscription" "documents" {
  topic_arn = aws_sns_topic.documents.arn
  protocol  = "sqs"
  endpoint  = aws_sqs_queue.documents.arn
}
