// Durable Task Scheduler + Task Hub
param schedulerName string
param taskHubName string
param location string
param tags object = {}
param principalId string
param principalType string

resource dts 'Microsoft.DurableTask/schedulers@2025-11-01' = {
  name: schedulerName
  location: location
  tags: tags
  properties: {
    ipAllowlist: ['0.0.0.0/0']
    sku: {
      name: 'Consumption'
    }
  }
}

resource taskHub 'Microsoft.DurableTask/schedulers/taskHubs@2025-11-01' = {
  parent: dts
  name: taskHubName
  properties: {}
}

// Durable Task Data Contributor
resource roleAssignment 'Microsoft.Authorization/roleAssignments@2022-04-01' = {
  scope: dts
  name: guid(dts.id, principalId, '0ad04412-c4d5-4796-b79c-f76d14c8d402')
  properties: {
    principalId: principalId
    roleDefinitionId: subscriptionResourceId(
      'Microsoft.Authorization/roleDefinitions',
      '0ad04412-c4d5-4796-b79c-f76d14c8d402'
    )
    principalType: principalType
  }
}

output endpoint string = dts.properties.endpoint
output taskHubName string = taskHub.name
