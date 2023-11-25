terraform {
  required_providers {
    google = {
      source = "hashicorp/google"
      # This is a temporary fixing of the version, until https://github.com/GoogleCloudPlatform/terraformer/issues/1695 is fixed
      version = "4.59.0"
    }
    aws = {
      source = "hashicorp/aws"
      version = "5.23.0"
    }
    azure = {
      source = "hashicorp/azurerm"
      version = "3.82.0"
    }
  }
  required_version = ">= 1.2.6"
}
