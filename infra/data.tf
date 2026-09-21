# Case store mapping. The demo keeps one JSON or SQLite file per mailbox.
# Cosmos DB is the production store, partitioned by tenant.

resource "azurerm_cosmosdb_account" "cases" {
  count               = var.enable_production_mapping ? 1 : 0
  name                = substr(replace("${var.prefix}-cosmos", "-", ""), 0, 44)
  location            = azurerm_resource_group.main.location
  resource_group_name = azurerm_resource_group.main.name
  offer_type          = "Standard"
  kind                = "GlobalDocumentDB"

  consistency_policy {
    consistency_level = "Session"
  }

  geo_location {
    location          = azurerm_resource_group.main.location
    failover_priority = 0
  }

  tags = {
    product = "VeriFY"
    env     = "dev"
  }
}

resource "azurerm_cosmosdb_sql_database" "verify" {
  count               = var.enable_production_mapping ? 1 : 0
  name                = "verify"
  resource_group_name = azurerm_resource_group.main.name
  account_name        = azurerm_cosmosdb_account.cases[0].name
}

resource "azurerm_cosmosdb_sql_container" "cases" {
  count               = var.enable_production_mapping ? 1 : 0
  name                = "cases"
  resource_group_name = azurerm_resource_group.main.name
  account_name        = azurerm_cosmosdb_account.cases[0].name
  database_name       = azurerm_cosmosdb_sql_database.verify[0].name
  partition_key_paths = ["/tenant"]
}
