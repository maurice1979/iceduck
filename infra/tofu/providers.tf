terraform {
  required_version = ">= 1.6.0"

  required_providers {
    aws = {
      source  = "hashicorp/aws"
      version = "~> 5.0"
    }
  }

  # Local state only — single-developer learning project. Floci does support
  # an S3 backend (per its own compat-test fixtures), but that adds a
  # bootstrapping chicken-and-egg problem (the state bucket would need to
  # exist before it can be created) that isn't worth solving here.
}

provider "aws" {
  region     = var.aws_region
  access_key = var.floci_access_key
  secret_key = var.floci_secret_key

  # Floci is not real AWS — skip checks that would otherwise fail or slow
  # down every plan/apply against it.
  skip_credentials_validation = true
  skip_metadata_api_check     = true
  skip_requesting_account_id  = true
  s3_use_path_style           = true

  endpoints {
    s3     = var.floci_endpoint
    iam    = var.floci_endpoint
    sts    = var.floci_endpoint
    glue   = var.floci_endpoint
    athena = var.floci_endpoint
  }
}
