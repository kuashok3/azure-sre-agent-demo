// Monthly cost budget for THIS project only (subscription scope, filtered by tag Project).
// A budget sends e-mails; it does NOT stop spending.
// Note: cost data arrives with a delay of up to ~24 hours, and only tagged resources are counted.

targetScope = 'subscription'

@description('Monthly amount in the billing currency')
param amount int = 50

@description('E-mail address that receives budget alerts')
param contactEmail string

@description('First day of the current month (budgets must start on the 1st)')
param startDate string = '${utcNow('yyyy-MM')}-01'

param projectTag string = 'AzureSREAgentDemo'

resource budget 'Microsoft.Consumption/budgets@2023-11-01' = {
  name: 'budget-sredemo'
  properties: {
    category: 'Cost'
    amount: amount
    timeGrain: 'Monthly'
    timePeriod: { startDate: startDate }
    filter: {
      tags: { name: 'Project', operator: 'In', values: [projectTag] }
    }
    notifications: {
      actual50: {
        enabled: true
        operator: 'GreaterThanOrEqualTo'
        threshold: 50
        thresholdType: 'Actual'
        contactEmails: [contactEmail]
      }
      actual80: {
        enabled: true
        operator: 'GreaterThanOrEqualTo'
        threshold: 80
        thresholdType: 'Actual'
        contactEmails: [contactEmail]
      }
      actual100: {
        enabled: true
        operator: 'GreaterThanOrEqualTo'
        threshold: 100
        thresholdType: 'Actual'
        contactEmails: [contactEmail]
      }
      forecast100: {
        enabled: true
        operator: 'GreaterThanOrEqualTo'
        threshold: 100
        thresholdType: 'Forecasted'
        contactEmails: [contactEmail]
      }
    }
  }
}
