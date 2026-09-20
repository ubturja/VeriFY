resource "azurerm_storage_account" "docs" {
  name                     = substr(replace("${var.prefix}docsdev", "-", ""), 0, 24)
  resource_group_name      = azurerm_resource_group.main.name
  location                 = azurerm_resource_group.main.location
  account_tier             = "Standard"
  account_replication_type = "LRS"
  min_tls_version          = "TLS1_2"
}

resource "azurerm_storage_container" "raw" {
  name                  = "raw-mail"
  storage_account_id    = azurerm_storage_account.docs.id
  container_access_type = "private"
}

resource "azurerm_storage_container" "evidence" {
  name                  = "evidence"
  storage_account_id    = azurerm_storage_account.docs.id
  container_access_type = "private"
}
