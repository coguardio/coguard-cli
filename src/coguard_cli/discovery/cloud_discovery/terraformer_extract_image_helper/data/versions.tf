terraform {
  required_providers {
    google = {
      source = "hashicorp/google"
    }
    aws = {
      source = "hashicorp/aws"
    }
    azure = {
      source = "hashicorp/azurerm"
    }
  }
  required_version = ">= 1.2.6"
}
