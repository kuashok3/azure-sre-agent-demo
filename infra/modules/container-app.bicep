// One Container App. Used for both orders-api and payment-stub.
//
// Probes: liveness AND readiness both use /health/live on purpose. If readiness used /health/ready,
// a database outage would mark every replica "not ready", the platform would stop sending traffic,
// and the app would go silent in telemetry. Instead the app keeps answering with clear 503s, which
// is better for users and gives investigators evidence. /health/ready stays available for people,
// smoke tests and the SRE Agent. (Decision for CHECKPOINTS open issue 8.)
//
// Scale: exactly 1 replica, because fault-injection state lives in memory per replica
// (CHECKPOINTS open issue 7). Single revision mode: rollback = redeploy the previous image tag.

param name string
param location string
param tags object
param environmentId string
param image string
param identityId string
param registryServer string
param targetPort int
param externalIngress bool
param allowInsecure bool
param command array
param secrets array
param env array
param minReplicas int = 1
param maxReplicas int = 1

resource app 'Microsoft.App/containerApps@2024-03-01' = {
  name: name
  location: location
  tags: tags
  identity: {
    type: 'UserAssigned'
    userAssignedIdentities: { '${identityId}': {} }
  }
  properties: {
    managedEnvironmentId: environmentId
    configuration: {
      activeRevisionsMode: 'Single'
      ingress: {
        external: externalIngress
        targetPort: targetPort
        transport: 'auto'
        allowInsecure: allowInsecure
      }
      registries: [
        { server: registryServer, identity: identityId }
      ]
      secrets: secrets
    }
    template: {
      containers: [
        {
          name: name
          image: image
          command: empty(command) ? null : command
          resources: { cpu: json('0.25'), memory: '0.5Gi' }
          env: env
          probes: [
            {
              type: 'Liveness'
              httpGet: { path: '/health/live', port: targetPort }
              periodSeconds: 10
              failureThreshold: 3
            }
            {
              type: 'Readiness'
              httpGet: { path: '/health/live', port: targetPort }
              periodSeconds: 10
              failureThreshold: 3
            }
          ]
        }
      ]
      scale: { minReplicas: minReplicas, maxReplicas: maxReplicas }
    }
  }
}

output fqdn string = app.properties.configuration.ingress.fqdn
output latestRevisionName string = app.properties.latestRevisionName
