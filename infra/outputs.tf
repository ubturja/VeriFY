output "resource_group" {
  value = one(azurerm_resource_group.main[*].name)
}

output "location" {
  value = one(azurerm_resource_group.main[*].location)
}
