// Contoso Orders: Azure infrastructure (resource-group scope).
//
// Two-phase deployment (see docs/DEPLOYMENT.md):
//   Phase 1 (deployApps=false): monitoring, identity, registry, Key Vault, PostgreSQL, Container Apps env
//   Phase 2 (deployApps=true):  the two container apps, once the image is pushed, the Key Vault secret
//                               exists and database permissions are granted
// Re-running either phase is safe (idempotent).

targetScope = 'resourceGroup'

@description('Azure region for all resources, e.g. eastus2 or centralindia')
param location string

@description('Short prefix used in resource names')
@maxLength(10)
param namePrefix string = 'sredemo'

@description('Tags applied to every resource (cost tracking + cleanup)')
param tags object = {
  Project: 'AzureSREAgentDemo'
  Environment: 'NonProduction'
  Owner: 'Team'
  AutoCleanup: 'ReviewRequired'
}

@description('Object ID of the person deploying (becomes PostgreSQL Entra admin and Key Vault secrets officer)')
param deployerObjectId string

@description('UPN of the person deploying, e.g. someone@contoso.com (PostgreSQL Entra admin name)')
param deployerPrincipalName string

@description('Public IP of the deployer machine, allowed through the PostgreSQL firewall to run migrations')
param clientIpAddress string

@description('Phase 2 switch: deploy the container apps')
param deployApps bool = false

@description('Container image tag in ACR, required when deployApps=true')
param imageTag string = ''

@description('Git commit of the deployed image (shown in /info)')
param gitSha string = 'unknown'

@description('PostgreSQL compute size (Burstable tier). B1ms is cheapest; B2s if B1ms is not offered to the subscription')
@allowed(['Standard_B1ms', 'Standard_B2s'])
param postgresSkuName string = 'Standard_B1ms'

// ---------------------------------------------------------------------------------------------
// Names
// ---------------------------------------------------------------------------------------------
var suffix = take(uniqueString(resourceGroup().id), 5)
var names = {
  logAnalytics: 'log-${namePrefix}'
  appInsights: 'appi-${namePrefix}'
  identity: 'id-orders-api'
  registry: 'cr${namePrefix}${suffix}'
  keyVault: 'kv-${namePrefix}-${suffix}'
  postgres: 'psql-${namePrefix}-${suffix}'
  environment: 'cae-${namePrefix}'
  ordersApp: 'ca-orders-api'
  paymentApp: 'ca-payment-stub'
}
var databaseName = 'orders'
var faultSecretName = 'fault-admin-token'

// Built-in role definition IDs
var roles = {
  acrPull: '7f951dda-4ed3-4680-a7ca-43fe172d538d'
  keyVaultSecretsUser: '4633458b-17de-408a-b874-0445c86b69e6'
  keyVaultSecretsOfficer: 'b86a8fe4-44ce-4948-aee5-eccb2c155cd7'
}

// ---------------------------------------------------------------------------------------------
// Monitoring: Log Analytics (daily cap) + workspace-based Application Insights
// ---------------------------------------------------------------------------------------------
resource logAnalytics 'Microsoft.OperationalInsights/workspaces@2023-09-01' = {
  name: names.logAnalytics
  location: location
  tags: tags
  properties: {
    sku: { name: 'PerGB2018' }
    retentionInDays: 30
    workspaceCapping: { dailyQuotaGb: json('0.5') } // cost guard: ingestion stops for the day at 0.5 GB
  }
}

resource appInsights 'Microsoft.Insights/components@2020-02-02' = {
  name: names.appInsights
  location: location
  tags: tags
  kind: 'web'
  properties: {
    Application_Type: 'web'
    WorkspaceResourceId: logAnalytics.id
    IngestionMode: 'LogAnalytics'
  }
}

// ---------------------------------------------------------------------------------------------
// Identity used by both container apps (no passwords anywhere)
// ---------------------------------------------------------------------------------------------
resource appIdentity 'Microsoft.ManagedIdentity/userAssignedIdentities@2023-01-31' = {
  name: names.identity
  location: location
  tags: tags
}

// ---------------------------------------------------------------------------------------------
// Container registry: images pulled by the managed identity (admin user disabled)
// ---------------------------------------------------------------------------------------------
resource registry 'Microsoft.ContainerRegistry/registries@2023-07-01' = {
  name: names.registry
  location: location
  tags: tags
  sku: { name: 'Basic' }
  properties: { adminUserEnabled: false }
}

resource acrPull 'Microsoft.Authorization/roleAssignments@2022-04-01' = {
  name: guid(registry.id, appIdentity.id, roles.acrPull)
  scope: registry
  properties: {
    roleDefinitionId: subscriptionResourceId('Microsoft.Authorization/roleDefinitions', roles.acrPull)
    principalId: appIdentity.properties.principalId
    principalType: 'ServicePrincipal'
  }
}

// ---------------------------------------------------------------------------------------------
// Key Vault (RBAC mode): holds only the fault-injection admin token
// ---------------------------------------------------------------------------------------------
resource keyVault 'Microsoft.KeyVault/vaults@2023-07-01' = {
  name: names.keyVault
  location: location
  tags: tags
  properties: {
    tenantId: tenant().tenantId
    sku: { family: 'A', name: 'standard' }
    enableRbacAuthorization: true
    enableSoftDelete: true
    softDeleteRetentionInDays: 7 // shortest allowed, eases cleanup
    publicNetworkAccess: 'Enabled'
  }
}

resource kvSecretsUser 'Microsoft.Authorization/roleAssignments@2022-04-01' = {
  name: guid(keyVault.id, appIdentity.id, roles.keyVaultSecretsUser)
  scope: keyVault
  properties: {
    roleDefinitionId: subscriptionResourceId('Microsoft.Authorization/roleDefinitions', roles.keyVaultSecretsUser)
    principalId: appIdentity.properties.principalId
    principalType: 'ServicePrincipal'
  }
}

resource kvSecretsOfficerDeployer 'Microsoft.Authorization/roleAssignments@2022-04-01' = {
  name: guid(keyVault.id, deployerObjectId, roles.keyVaultSecretsOfficer)
  scope: keyVault
  properties: {
    roleDefinitionId: subscriptionResourceId('Microsoft.Authorization/roleDefinitions', roles.keyVaultSecretsOfficer)
    principalId: deployerObjectId
    principalType: 'User'
  }
}

// ---------------------------------------------------------------------------------------------
// PostgreSQL Flexible Server: Entra-only authentication (password auth disabled)
// Child resources are chained with dependsOn because the server accepts one change at a time.
// ---------------------------------------------------------------------------------------------
resource postgres 'Microsoft.DBforPostgreSQL/flexibleServers@2024-08-01' = {
  name: names.postgres
  location: location
  tags: tags
  sku: { name: postgresSkuName, tier: 'Burstable' }
  properties: {
    version: '16'
    storage: { storageSizeGB: 32, autoGrow: 'Disabled' }
    backup: { backupRetentionDays: 7, geoRedundantBackup: 'Disabled' }
    highAvailability: { mode: 'Disabled' }
    network: { publicNetworkAccess: 'Enabled' }
    authConfig: {
      activeDirectoryAuth: 'Enabled'
      passwordAuth: 'Disabled'
      tenantId: tenant().tenantId
    }
  }
}

resource postgresAdmin 'Microsoft.DBforPostgreSQL/flexibleServers/administrators@2024-08-01' = {
  parent: postgres
  name: deployerObjectId
  properties: {
    principalType: 'User'
    principalName: deployerPrincipalName
    tenantId: tenant().tenantId
  }
}

resource postgresDatabase 'Microsoft.DBforPostgreSQL/flexibleServers/databases@2024-08-01' = {
  parent: postgres
  name: databaseName
  properties: { charset: 'UTF8', collation: 'en_US.utf8' }
  dependsOn: [postgresAdmin]
}

// 0.0.0.0 rule = "allow Azure services" (lets Container Apps connect; accepted demo trade-off)
resource fwAzure 'Microsoft.DBforPostgreSQL/flexibleServers/firewallRules@2024-08-01' = {
  parent: postgres
  name: 'AllowAzureServices'
  properties: { startIpAddress: '0.0.0.0', endIpAddress: '0.0.0.0' }
  dependsOn: [postgresDatabase]
}

resource fwDeployer 'Microsoft.DBforPostgreSQL/flexibleServers/firewallRules@2024-08-01' = {
  parent: postgres
  name: 'AllowDeployerIp'
  properties: { startIpAddress: clientIpAddress, endIpAddress: clientIpAddress }
  dependsOn: [fwAzure]
}

// ---------------------------------------------------------------------------------------------
// Container Apps environment (Consumption), platform + console logs to Log Analytics
// ---------------------------------------------------------------------------------------------
resource environment 'Microsoft.App/managedEnvironments@2024-03-01' = {
  name: names.environment
  location: location
  tags: tags
  properties: {
    appLogsConfiguration: {
      destination: 'log-analytics'
      logAnalyticsConfiguration: {
        customerId: logAnalytics.properties.customerId
        sharedKey: logAnalytics.listKeys().primarySharedKey
      }
    }
  }
}

// ---------------------------------------------------------------------------------------------
// Phase 2: container apps
// ---------------------------------------------------------------------------------------------
var image = '${registry.properties.loginServer}/sre-demo-app:${imageTag}'
var faultSecretUri = '${keyVault.properties.vaultUri}secrets/${faultSecretName}'
var commonEnv = [
  { name: 'ENVIRONMENT', value: 'azure' }
  { name: 'DEPLOYMENT_REGION', value: location }
  { name: 'APP_VERSION', value: imageTag }
  { name: 'GIT_SHA', value: gitSha }
  { name: 'LOG_LEVEL', value: 'INFO' }
  { name: 'APPLICATIONINSIGHTS_CONNECTION_STRING', secretRef: 'appinsights-connection-string' }
  { name: 'FAULTS_ENABLED', value: 'true' }
  { name: 'FAULT_ADMIN_TOKEN', secretRef: 'fault-admin-token' }
]
var commonSecrets = [
  { name: 'appinsights-connection-string', value: appInsights.properties.ConnectionString }
  { name: 'fault-admin-token', keyVaultUrl: faultSecretUri, identity: appIdentity.id }
]

module paymentApp 'modules/container-app.bicep' = if (deployApps) {
  name: 'deploy-${names.paymentApp}'
  params: {
    name: names.paymentApp
    location: location
    tags: tags
    environmentId: environment.id
    image: image
    identityId: appIdentity.id
    registryServer: registry.properties.loginServer
    targetPort: 8001
    externalIngress: false
    allowInsecure: true // internal-only HTTP inside the environment (avoids HTTP->HTTPS redirect on POST)
    command: ['python', '-m', 'app.payment_stub']
    secrets: commonSecrets
    env: concat(commonEnv, [
      { name: 'PORT', value: '8001' }
      { name: 'OTEL_SERVICE_NAME', value: 'payment-stub' }
    ])
  }
  dependsOn: [acrPull, kvSecretsUser]
}

module ordersApp 'modules/container-app.bicep' = if (deployApps) {
  name: 'deploy-${names.ordersApp}'
  params: {
    name: names.ordersApp
    location: location
    tags: tags
    environmentId: environment.id
    image: image
    identityId: appIdentity.id
    registryServer: registry.properties.loginServer
    targetPort: 8000
    externalIngress: true
    allowInsecure: false
    command: []
    secrets: commonSecrets
    env: concat(commonEnv, [
      { name: 'PORT', value: '8000' }
      { name: 'OTEL_SERVICE_NAME', value: 'orders-api' }
      { name: 'DB_HOST', value: postgres.properties.fullyQualifiedDomainName }
      { name: 'DB_PORT', value: '5432' }
      { name: 'DB_NAME', value: databaseName }
      { name: 'DB_USER', value: names.identity }
      { name: 'DB_AUTH_MODE', value: 'entra' }
      { name: 'DB_SSLMODE', value: 'require' }
      { name: 'AZURE_CLIENT_ID', value: appIdentity.properties.clientId }
      { name: 'PAYMENT_BASE_URL', value: 'http://${names.paymentApp}' }
      { name: 'PAYMENT_TIMEOUT_SECONDS', value: '2' }
    ])
  }
  dependsOn: [acrPull, kvSecretsUser, paymentApp]
}

// ---------------------------------------------------------------------------------------------
// Outputs (no secrets)
// ---------------------------------------------------------------------------------------------
output registryName string = registry.name
output registryLoginServer string = registry.properties.loginServer
output keyVaultName string = keyVault.name
output faultSecretName string = faultSecretName
output postgresServerName string = postgres.name
output postgresFqdn string = postgres.properties.fullyQualifiedDomainName
output databaseName string = databaseName
output appIdentityName string = appIdentity.name
output appIdentityClientId string = appIdentity.properties.clientId
output appInsightsName string = appInsights.name
output logAnalyticsName string = logAnalytics.name
output environmentName string = environment.name
output ordersAppFqdn string = deployApps ? ordersApp!.outputs.fqdn : ''
