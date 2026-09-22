# Production mapping for the local job queue.
# The running demo uses verify/services/jobqueue.py. These resources are the
# Azure equivalents and are created only when enable_production_mapping = true.

resource "azurerm_servicebus_namespace" "main" {
  count               = var.enable_production_mapping ? 1 : 0
  name                = substr(replace("${var.prefix}-sb", "-", ""), 0, 50)
  location            = azurerm_resource_group.main[0].location
  resource_group_name = azurerm_resource_group.main[0].name
  sku                 = "Standard"
  tags = {
    product = "VeriFY"
    env     = "dev"
  }
}

resource "azurerm_servicebus_queue" "process" {
  count        = var.enable_production_mapping ? 1 : 0
  name         = "process"
  namespace_id = azurerm_servicebus_namespace.main[0].id

  dead_lettering_on_message_expiration = true
  max_delivery_count                   = 3
  lock_duration                        = "PT1M"
}
