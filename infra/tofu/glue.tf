resource "aws_glue_catalog_database" "bronze" {
  name         = "iceduck_bronze"
  location_uri = "s3://${aws_s3_bucket.lakehouse.bucket}/warehouse/bronze/"
}

resource "aws_glue_catalog_database" "silver" {
  name         = "iceduck_silver"
  location_uri = "s3://${aws_s3_bucket.lakehouse.bucket}/warehouse/silver/"
}

resource "aws_glue_catalog_database" "gold" {
  name         = "iceduck_gold"
  location_uri = "s3://${aws_s3_bucket.lakehouse.bucket}/warehouse/gold/"
}

# No crawler: bronze/silver/gold schemas are created explicitly by
# pyiceberg (bronze) and dbt-duckdb[glue] (silver/gold) at write time,
# so there's nothing for a crawler to discover.
