# Entry point: Terraform version, providers, remote state, and shared data.
# Each component is in its own file: see the list in README or the file names.

terraform {
  required_version = ">= 1.6"

  required_providers {
    aws = {
      source  = "hashicorp/aws"
      version = "~> 5.0"
    }
    archive = {
      source  = "hashicorp/archive"
      version = "~> 2.4"
    }
  }

  backend "s3" {
    bucket  = "provenance-tfstate-4102a6"
    key     = "provenance/terraform.tfstate"
    region  = "us-east-1"
    encrypt = true
  }
}

provider "aws" {
  region = var.region
}

data "aws_caller_identity" "me" {}

# The documents bucket was created before Terraform, so Terraform reads it rather than creating it.
data "aws_s3_bucket" "data" {
  bucket = var.bucket_name
}
