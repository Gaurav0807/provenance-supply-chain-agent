# Vector store: an OpenSearch Serverless collection that holds the document vectors.
# The three policies below must exist before the collection can be used.

# 1. Encryption: AWS-owned key
resource "aws_opensearchserverless_security_policy" "encryption" {
  name = "${local.collection_name}-enc"
  type = "encryption"
  policy = jsonencode({
    Rules       = [{ ResourceType = "collection", Resource = ["collection/${local.collection_name}"] }]
    AWSOwnedKey = true
  })
}

# 2. Network: public endpoint (fine for a demo; use a VPC endpoint for production)
resource "aws_opensearchserverless_security_policy" "network" {
  name = "${local.collection_name}-net"
  type = "network"
  policy = jsonencode([{
    Rules = [
      { ResourceType = "collection", Resource = ["collection/${local.collection_name}"] },
      { ResourceType = "dashboard", Resource = ["collection/${local.collection_name}"] },
    ]
    AllowFromPublic = true
  }])
}

# 3. Data access: who may create the index and read or write vectors
resource "aws_opensearchserverless_access_policy" "data" {
  name = "${local.collection_name}-data"
  type = "data"
  policy = jsonencode([{
    Rules = [
      {
        ResourceType = "collection"
        Resource     = ["collection/${local.collection_name}"]
        Permission   = ["aoss:CreateCollectionItems", "aoss:DescribeCollectionItems", "aoss:UpdateCollectionItems", "aoss:DeleteCollectionItems"]
      },
      {
        ResourceType = "index"
        Resource     = ["index/${local.collection_name}/*"]
        Permission   = ["aoss:CreateIndex", "aoss:DescribeIndex", "aoss:UpdateIndex", "aoss:DeleteIndex", "aoss:ReadDocument", "aoss:WriteDocument"]
      },
    ]
    Principal = [local.root_arn, aws_iam_role.kb.arn, "arn:aws:iam::${local.account_id}:user/${var.admin_user_name}"]
  }])
}

resource "aws_opensearchserverless_collection" "docs" {
  name = local.collection_name
  type = "VECTORSEARCH"

  depends_on = [
    aws_opensearchserverless_security_policy.encryption,
    aws_opensearchserverless_security_policy.network,
  ]
}
