# NOTE: this role/policy is provisioned for OpenTofu/IAM-practice and
# real-AWS parity — it is NOT what actually authorizes access in this
# project today. Floci does not enforce IAM for the CLI/dbt/pyiceberg
# clients, which authenticate directly with the static floci_access_key/
# floci_secret_key credentials (see providers.tf). If this stack is later
# pointed at real AWS, actual assume-role wiring would need to be added
# for this role to do anything — right now it exists purely as IaC practice.

resource "aws_iam_role" "lakehouse_access" {
  name = "iceduck-lakehouse-access"

  assume_role_policy = jsonencode({
    Version = "2012-10-17"
    Statement = [
      {
        Effect = "Allow"
        Principal = {
          Service = "athena.amazonaws.com"
        }
        Action = "sts:AssumeRole"
      }
    ]
  })
}

resource "aws_iam_policy" "lakehouse_access" {
  name = "iceduck-lakehouse-access-policy"

  policy = jsonencode({
    Version = "2012-10-17"
    Statement = [
      {
        Sid    = "S3LakehouseAccess"
        Effect = "Allow"
        Action = [
          "s3:GetObject",
          "s3:PutObject",
          "s3:DeleteObject",
          "s3:ListBucket",
        ]
        Resource = [
          aws_s3_bucket.lakehouse.arn,
          "${aws_s3_bucket.lakehouse.arn}/*",
        ]
      },
      {
        Sid    = "GlueCatalogAccess"
        Effect = "Allow"
        Action = [
          "glue:GetDatabase",
          "glue:GetDatabases",
          "glue:GetTable",
          "glue:GetTables",
          "glue:CreateTable",
          "glue:UpdateTable",
          "glue:DeleteTable",
        ]
        Resource = "*"
      },
      {
        Sid    = "AthenaQueryAccess"
        Effect = "Allow"
        Action = [
          "athena:StartQueryExecution",
          "athena:GetQueryExecution",
          "athena:GetQueryResults",
          "athena:GetWorkGroup",
        ]
        Resource = "*"
      },
    ]
  })
}

resource "aws_iam_role_policy_attachment" "lakehouse_access" {
  role       = aws_iam_role.lakehouse_access.name
  policy_arn = aws_iam_policy.lakehouse_access.arn
}
