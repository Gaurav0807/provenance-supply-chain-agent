variable "region" {
  type    = string
  default = "us-east-1"
}

variable "bucket_name" {
  type    = string
  default = "provenance-data-4102a6"
}

variable "embedding_model" {
  type    = string
  default = "amazon.titan-embed-text-v2:0"
}

variable "admin_user_name" {
  type    = string
  default = "User_Gaurav" # the IAM user that runs terraform apply and the index script
}

variable "chunk_tokens" {
  type    = number
  default = 512
}

variable "chunk_overlap_pct" {
  type    = number
  default = 10
}

locals {
  collection_name = "provenance-docs"
  index_name      = "provenance-index"
  account_id      = data.aws_caller_identity.me.account_id
  root_arn        = "arn:aws:iam::${local.account_id}:root"
}
