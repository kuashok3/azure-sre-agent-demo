// Alerting for Contoso Orders: one action group (e-mail) + four log-search alert rules.
// Deployed separately from main.bicep so thresholds can be tuned without touching the app.
//
// Thresholds are ILLUSTRATIVE for a low-traffic demo (see docs/SERVICE_LEVELS.md):
// each rate rule needs a minimum number of requests so a single failed request at 3 a.m. doesn't page.
// All queries count with sum(ItemCount) (sampling-aware; see docs/OBSERVABILITY.md §4b).
// autoMitigate=true: an alert resolves by itself once the condition clears, so a "fired" alert that
// stays open means the problem is still there.

targetScope = 'resourceGroup'

param location string = resourceGroup().location
param workspaceName string = 'log-sredemo'

@description('Who receives alert e-mails')
param alertEmail string

param tags object = {
  Project: 'AzureSREAgentDemo'
  Environment: 'NonProduction'
  Owner: 'Team'
  AutoCleanup: 'ReviewRequired'
}

resource workspace 'Microsoft.OperationalInsights/workspaces@2023-09-01' existing = {
  name: workspaceName
}

resource actionGroup 'Microsoft.Insights/actionGroups@2023-01-01' = {
  name: 'ag-sredemo'
  location: 'global'
  tags: tags
  properties: {
    groupShortName: 'sredemo'
    enabled: true
    emailReceivers: [
      { name: 'architect', emailAddress: alertEmail, useCommonAlertSchema: true }
    ]
  }
}

var rules = [
  {
    name: 'alert-sredemo-5xx-rate'
    displayName: 'orders-api: 5xx error rate above 5%'
    description: 'Share of /api/* requests failing with 5xx over 5 minutes (min 5 requests). Runbook: runbooks/HTTP_5XX_ERRORS.md'
    severity: 2
    window: 'PT5M'
    measure: 'error_rate_pct'
    threshold: 5
    query: '''
AppRequests
| where AppRoleName == 'orders-api' and Url has '/api/'
| summarize total = sum(ItemCount), bad = sumif(ItemCount, toint(ResultCode) >= 500)
| where total >= 5
| extend error_rate_pct = 100.0 * bad / total
'''
  }
  {
    name: 'alert-sredemo-latency-p95'
    displayName: 'orders-api: p95 latency above 1000 ms'
    description: 'p95 duration of successful /api/* requests over 10 minutes (min 5 requests). Runbook: runbooks/HIGH_LATENCY.md'
    severity: 3
    window: 'PT10M'
    measure: 'p95_ms'
    threshold: 1000
    query: '''
AppRequests
| where AppRoleName == 'orders-api' and Url has '/api/' and toint(ResultCode) < 500
| summarize total = sum(ItemCount), p95_ms = percentile(DurationMs, 95)
| where total >= 5
'''
  }
  {
    name: 'alert-sredemo-dependency-failures'
    displayName: 'orders-api: dependency calls failing'
    description: 'Failed PostgreSQL or payment-stub calls from orders-api over 5 minutes. Runbooks: DATABASE_FAILURE.md, DEPENDENCY_TIMEOUT.md'
    severity: 2
    window: 'PT5M'
    measure: 'failed'
    threshold: 3
    query: '''
AppDependencies
| where AppRoleName == 'orders-api' and Success == false and Target != 'settings.sdk.monitor.azure.com'
| summarize failed = sum(ItemCount)
'''
  }
  {
    name: 'alert-sredemo-database-unavailable'
    displayName: 'orders-api: database unavailable'
    description: 'orders-api reported database_unavailable (real outage or injected fault). Runbook: runbooks/DATABASE_FAILURE.md'
    severity: 1
    window: 'PT5M'
    measure: 'errors'
    threshold: 0
    query: '''
AppTraces
| where AppRoleName == 'orders-api' and tostring(Properties.error_code) == 'database_unavailable'
| summarize errors = sum(ItemCount)
'''
  }
]

resource alertRules 'Microsoft.Insights/scheduledQueryRules@2023-12-01' = [
  for rule in rules: {
    name: rule.name
    location: location
    tags: tags
    properties: {
      displayName: rule.displayName
      description: rule.description
      severity: rule.severity
      enabled: true
      scopes: [workspace.id]
      evaluationFrequency: 'PT5M'
      windowSize: rule.window
      autoMitigate: true
      criteria: {
        allOf: [
          {
            query: rule.query
            timeAggregation: 'Maximum'
            metricMeasureColumn: rule.measure
            operator: 'GreaterThan'
            threshold: rule.threshold
            failingPeriods: { numberOfEvaluationPeriods: 1, minFailingPeriodsToAlert: 1 }
          }
        ]
      }
      actions: { actionGroups: [actionGroup.id] }
    }
  }
]

output actionGroupId string = actionGroup.id
output alertRuleNames array = [for rule in rules: rule.name]
