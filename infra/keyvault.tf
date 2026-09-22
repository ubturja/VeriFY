# Secrets mapping. The demo reads VERIFY_SECRET_KEY from the environment.
# Key Vault is where that key, the LLM keys, and the webhook URL live in production.

data "azurerm_client_config" "current" {}

resource "azurerm_key_vault" "main" {
  count                      = var.enable_production_mapping ? 1 : 0
  name                       = substr(replace("${var.prefix}kv", "-", ""), 0, 24)
  location                   = azurerm_resource_group.main[0].location
  resource_group_name        = azurerm_resource_group.main[0].name
  tenant_id                  = data.azurerm_client_config.current.tenant_id
  sku_name                   = "standard"
  soft_delete_retention_days = 7
  purge_protection_enabled   = false

  tags = {
    product = "VeriFY"
    env     = "dev"
  }
}
