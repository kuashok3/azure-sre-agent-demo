// Probe: can this subscription create a Burstable PostgreSQL Flexible Server in a region?
// Deploy into a throwaway resource group, check the result, then delete the group.
// Same auth settings as the real server (Entra only, no password is ever generated).
// Background: B1ms and B2s both failed with SkuNotAvailable in eastus2 on 2026-10-13, even though
// `az postgres flexible-server list-skus` listed them.

param location string

@allowed(['Standard_B1ms', 'Standard_B2s'])
param skuName string = 'Standard_B1ms'

resource probe 'Microsoft.DBforPostgreSQL/flexibleServers@2024-08-01' = {
  name: 'psql-probe-${take(uniqueString(resourceGroup().id), 6)}'
  location: location
  tags: { Project: 'AzureSREAgentDemo', Purpose: 'region-probe', AutoCleanup: 'DeleteAfterTest' }
  sku: { name: skuName, tier: 'Burstable' }
  properties: {
    version: '16'
    storage: { storageSizeGB: 32, autoGrow: 'Disabled' }
    backup: { backupRetentionDays: 7, geoRedundantBackup: 'Disabled' }
    highAvailability: { mode: 'Disabled' }
    network: { publicNetworkAccess: 'Disabled' }
    authConfig: { activeDirectoryAuth: 'Enabled', passwordAuth: 'Disabled', tenantId: tenant().tenantId }
  }
}

output serverName string = probe.name
output state string = probe.properties.state
