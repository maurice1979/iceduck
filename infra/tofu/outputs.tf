output "bucket_name" {
  description = "S3 bucket backing the lakehouse."
  value       = aws_s3_bucket.lakehouse.bucket
}

output "glue_database_names" {
  description = "Glue databases for each medallion layer."
  value = {
    bronze = aws_glue_catalog_database.bronze.name
    silver = aws_glue_catalog_database.silver.name
    gold   = aws_glue_catalog_database.gold.name
  }
}

output "athena_workgroup_name" {
  description = "Athena workgroup used for query verification."
  value       = aws_athena_workgroup.iceduck.name
}

output "athena_results_location" {
  description = "S3 location Athena writes query results to."
  value       = "s3://${aws_s3_bucket.lakehouse.bucket}/athena-results/"
}
