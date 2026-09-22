resource "azurerm_storage_account" "docs" {
  count                    = var.enable_production_mapping ? 1 : 0
  name                     = substr(replace("${var.prefix}docsdev", "-", ""), 0, 24)
  resource_group_name      = azurerm_resource_group.main[0].name
  location                 = azurerm_resource_group.main[0].location
  account_tier             = "Standard"
  account_replication_type = "LRS"
  min_tls_version          = "TLS1_2"
}

resource "azurerm_storage_container" "raw" {
  count                 = var.enable_production_mapping ? 1 : 0
  name                  = "raw-mail"
  storage_account_id    = azurerm_storage_account.docs[0].id
  container_access_type = "private"
}

resource "azurerm_storage_container" "evidence" {
  count                 = var.enable_production_mapping ? 1 : 0
  name                  = "evidence"
  storage_account_id    = azurerm_storage_account.docs[0].id
  container_access_type = "private"
}
