variable "aws_region" {
  description = "AWS region to target (Floci accepts any syntactically valid region)."
  type        = string
  default     = "eu-west-1"
}

variable "floci_endpoint" {
  description = "Floci emulator endpoint used for every AWS service endpoint."
  type        = string
  default     = "http://localhost:4566"
}

variable "floci_access_key" {
  description = "Static access key for Floci (not a real AWS credential)."
  type        = string
  default     = "floci"
}

variable "floci_secret_key" {
  description = "Static secret key for Floci (not a real AWS credential)."
  type        = string
  default     = "floci"
  sensitive   = true
}

variable "bucket_name" {
  description = "S3 bucket backing the lakehouse (raw landing + Iceberg warehouse + Athena results)."
  type        = string
  default     = "iceduck-lakehouse"
}

variable "athena_workgroup_name" {
  description = "Athena workgroup used for all query engine verification."
  type        = string
  default     = "iceduck"
}
