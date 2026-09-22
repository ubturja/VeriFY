terraform {
  required_version = ">= 1.7.0"
  required_providers {
    azurerm = {
      source  = "hashicorp/azurerm"
      version = "~> 4.0"
    }
  }

  # Uncomment after the student subscription and storage account exist.
  # backend "azurerm" {
  #   resource_group_name  = "rg-verify-tfstate"
  #   storage_account_name = "stverifytfstate"
  #   container_name       = "tfstate"
  #   key                  = "verify.tfstate"
  # }
}

provider "azurerm" {
  features {}
}

variable "location" {
  type        = string
  default     = "southeastasia"
  description = "Azure region. Southeast Asia matches Averis residency needs."
}

variable "prefix" {
  type    = string
  default = "verify"
}

resource "azurerm_resource_group" "main" {
  count    = var.enable_production_mapping ? 1 : 0
  name     = "rg-${var.prefix}-dev"
  location = var.location
  tags = {
    product = "VeriFY"
    env     = "dev"
  }
}
