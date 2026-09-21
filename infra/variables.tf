variable "enable_production_mapping" {
  type        = bool
  default     = false
  description = "Create the Averis production resources (Service Bus, Cosmos, Key Vault). Leave false for the hackathon; Render hosts the demo."
}
