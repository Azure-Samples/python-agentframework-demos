targetScope = 'subscription'

@minLength(1)
@maxLength(64)
@description('Name of the the environment which is used to generate a short unique hash used in all resources.')
param environmentName string

@minLength(1)
@description('Location for the OpenAI resource')
// https://learn.microsoft.com/azure/ai-services/openai/concepts/models?tabs=python-secure%2Cglobal-standard%2Cstandard-chat-completions#models-by-deployment-type
@allowed([
  'australiaeast'
  'brazilsouth'
  'canadaeast'
  'eastus'
  'eastus2'
  'francecentral'
  'germanywestcentral'
  'japaneast'
  'koreacentral'
  'northcentralus'
  'norwayeast'
  'polandcentral'
  'southafricanorth'
  'southcentralus'
  'southindia'
  'spaincentral'
  'swedencentral'
  'switzerlandnorth'
  'uaenorth'
  'uksouth'
  'westeurope'
  'westus'
  'westus3'
])
@metadata({
  azd: {
    type: 'location'
  }
})
param location string

@description('Name of the GPT model to deploy')
param azureOpenaiChatModel string = 'gpt-5-mini'

@description('Version of the GPT model to deploy')
// See version availability in this table:
// https://learn.microsoft.com/azure/ai-foundry/foundry-models/concepts/models-sold-directly-by-azure?pivots=azure-openai#models-by-deployment-type
param azureOpenaiChatModelVersion string = '2025-08-07'

@description('Name of the model deployment (can be different from the model name)')
param azureOpenaiChatDeployment string = 'gpt-5-mini'

@description('Capacity of the GPT deployment')
// You can increase this, but capacity is limited per model/region, so you will get errors if you go over
// https://learn.microsoft.com/en-us/azure/ai-services/openai/quotas-limits
param azureOpenaiChatDeploymentCapacity int = 30


@description('Name of the text embedding model to deploy')
param azureOpenaiEmbeddingModel string = 'text-embedding-3-large'

@description('Version of the text embedding model to deploy')
// See version availability in this table:
// https://learn.microsoft.com/azure/ai-services/openai/concepts/models?tabs=python-secure%2Cglobal-standard%2Cstandard-chat-completions#models-by-deployment-type
param azureOpenaiEmbeddingModelVersion string = '1'

@description('Name of the model deployment (can be different from the model name)')
param azureOpenaiEmbeddingDeployment string = 'text-embedding-3-large'

@description('Capacity of the text embedding deployment')
// You can increase this, but capacity is limited per model/region, so you will get errors if you go over
// https://learn.microsoft.com/en-us/azure/ai-services/openai/quotas-limits
param azureOpenaiEmbeddingDeploymentCapacity int = 30

@description('Id of the user or app to assign application roles')
param principalId string = ''

@description('Non-empty if the deployment is running on GitHub Actions')
param runningOnGitHub string = ''

var principalType = empty(runningOnGitHub) ? 'User' : 'ServicePrincipal'

var resourceToken = toLower(uniqueString(subscription().id, environmentName, location))
var prefix = '${environmentName}${resourceToken}'
var tags = { 'azd-env-name': environmentName }

// Organize resources in a resource group
resource resourceGroup 'Microsoft.Resources/resourceGroups@2021-04-01' = {
    name: '${prefix}-rg'
    location: location
    tags: tags
}

var openAiServiceName = '${prefix}-openai'
module openAi 'br/public:avm/res/cognitive-services/account:0.7.1' = {
  name: 'openai'
  scope: resourceGroup
  params: {
    name: openAiServiceName
    location: location
    tags: tags
    kind: 'OpenAI'
    sku: 'S0'
    customSubDomainName: openAiServiceName
    disableLocalAuth: true
    networkAcls: {
      defaultAction: 'Allow'
      bypass: 'AzureServices'
    }
    deployments: [
      {
        name: azureOpenaiChatDeployment
        model: {
          format: 'OpenAI'
          name: azureOpenaiChatModel
          version: azureOpenaiChatModelVersion
        }
        sku: {
          name: 'GlobalStandard'
          capacity: azureOpenaiChatDeploymentCapacity
        }
      }
      {
        name: azureOpenaiEmbeddingDeployment
        model: {
          format: 'OpenAI'
          name: azureOpenaiEmbeddingModel
          version: azureOpenaiEmbeddingModelVersion
        }
        sku: {
          name: 'GlobalStandard'
          capacity: azureOpenaiEmbeddingDeploymentCapacity
        }
      }
    ]
    roleAssignments: [
      {
        principalId: principalId
        roleDefinitionIdOrName: 'Cognitive Services OpenAI User'
        principalType: principalType
      }
    ]
  }
}

output AZURE_LOCATION string = location
output AZURE_TENANT_ID string = tenant().tenantId
output AZURE_RESOURCE_GROUP string = resourceGroup.name

// Specific to Azure OpenAI
output AZURE_OPENAI_ENDPOINT string = openAi.outputs.endpoint
output AZURE_OPENAI_CHAT_MODEL string = azureOpenaiChatModel
output AZURE_OPENAI_CHAT_DEPLOYMENT string = azureOpenaiChatDeployment
output AZURE_OPENAI_EMBEDDING_MODEL string = azureOpenaiEmbeddingModel
output AZURE_OPENAI_EMBEDDING_DEPLOYMENT string = azureOpenaiEmbeddingDeployment
