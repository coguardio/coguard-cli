terraform {
  required_providers {
    google = {
      source = "hashicorp/google"
      version = "4.59.0"
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
