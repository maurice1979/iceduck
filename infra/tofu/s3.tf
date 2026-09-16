resource "aws_s3_bucket" "lakehouse" {
  bucket = var.bucket_name
}

# Prefixes (raw/, warehouse/, athena-results/) are logical S3 key prefixes —
# they come into existence the moment the first object is written under
# them (by pyiceberg, dbt, or Athena's query-results writer) and need no
# placeholder objects here.
