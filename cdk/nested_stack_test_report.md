# Nested Stack Auto-Discovery and Deployment Test Report

**Test Date**: 2025-09-22 20:22:41

## Summary
- **Total Tests**: 8
- **Passed**: 8
- **Failed**: 0
- **Success Rate**: 100.0%

## Setup
✅ **Status**: PASSED

## Agent Discovery
✅ **Status**: PASSED

**Cdk Stacks Count**: 1

**Agentcore Agents Count**: 1

**Cdk Stacks**:
```json
[
  {
    "name": "00-vista-agents",
    "category": "multi_agent_collaboration",
    "stack_class": "VistaServiceStack",
    "path": "/Users/agweber/code/old-amazon-bedrock-agents-healthcare-lifesciences/agents_catalog/multi_agent_collaboration/00-vista-agents/cdk"
  }
]
```

**Agentcore Agents**:
```json
[
  {
    "name": "00-products-agent",
    "category": "standalone_agents",
    "path": "/Users/agweber/code/old-amazon-bedrock-agents-healthcare-lifesciences/agents_catalog/standalone_agents/00-products-agent"
  }
]
```

**Issues**:
```json
[]
```

## Vista Agents Discovery
✅ **Status**: PASSED

**Checks**:
```json
{
  "vista_directory_exists": true,
  "cdk_directory_exists": true,
  "app_py_exists": true,
  "stack_file_exists": true,
  "stack_class_extraction": true,
  "cdk_config_creation": true
}
```

**Vista Path**: /Users/agweber/code/old-amazon-bedrock-agents-healthcare-lifesciences/agents_catalog/multi_agent_collaboration/00-vista-agents

**Cdk Path**: /Users/agweber/code/old-amazon-bedrock-agents-healthcare-lifesciences/agents_catalog/multi_agent_collaboration/00-vista-agents/cdk

## Agentcore Discovery
✅ **Status**: PASSED

**Checks**:
```json
{
  "products_directory_exists": true,
  "agentcore_config_exists": true,
  "manifest_exists": true,
  "dockerfile_exists": true,
  "requirements_exists": true,
  "agentcore_config_creation": true
}
```

**Products Path**: /Users/agweber/code/old-amazon-bedrock-agents-healthcare-lifesciences/agents_catalog/standalone_agents/00-products-agent

## Shared Resource Passing
✅ **Status**: PASSED

**Available Resources**:
```json
[
  "bedrock_model_id",
  "deploy_application",
  "use_local_code",
  "github_url",
  "git_branch",
  "s3_bucket_name",
  "deploy_vista_agents",
  "stack_name",
  "region",
  "account",
  "resource_bucket",
  "resource_bucket_name",
  "resource_bucket_arn",
  "tables",
  "agent_role",
  "agent_role_arn",
  "lambda_execution_role",
  "lambda_execution_role_arn",
  "codebuild_service_role",
  "lambda_functions",
  "business_functions",
  "data_functions",
  "codebuild_projects",
  "cdk_synthesis_project",
  "agentcore_deployment_project",
  "storage_construct",
  "iam_construct",
  "compute_construct",
  "codebuild_construct"
]
```

**Missing Resources**:
```json
[]
```

**Resource Access Tests**:
```json
{
  "s3_bucket_access": true,
  "iam_role_access": true,
  "dynamodb_tables_access": true,
  "lambda_functions_access": true
}
```

**Total Resources**: 29

## Nested Stack Registration
✅ **Status**: PASSED

**Method**: already_registered

**Stack Type**: VistaServiceStack

**Stack Id**: NestedStack00vistaagents

## Codebuild Project Creation
✅ **Status**: PASSED

**Method**: already_created

**Project Type**: Project

**Project Id**: AgentProject00productsagent

## Main Stack Integration
✅ **Status**: PASSED

**Nested Stacks Count**: 1

**Agentcore Projects Count**: 1

**Agent Summary**:
```json
{
  "cdk_nested_stacks": [
    {
      "name": "00-vista-agents",
      "path": "/Users/agweber/code/old-amazon-bedrock-agents-healthcare-lifesciences/agents_catalog/multi_agent_collaboration/00-vista-agents/cdk",
      "stack_class": "VistaServiceStack",
      "category": "multi_agent_collaboration"
    }
  ],
  "agentcore_agents": [
    {
      "name": "00-products-agent",
      "path": "/Users/agweber/code/old-amazon-bedrock-agents-healthcare-lifesciences/agents_catalog/standalone_agents/00-products-agent",
      "category": "standalone_agents",
      "has_dockerfile": true,
      "has_requirements": true
    }
  ],
  "total_agents": 2
}
```

**Resource Summary**:
```json
{
  "storage": {
    "bucket_name": "${Token[TOKEN.40]}",
    "tables_count": 7,
    "table_names": [
      "dealer-data",
      "dealer-appointment-data",
      "customer-user-profile",
      "dtc-parts-lookup",
      "dealer-parts-stock",
      "dealer-parts-order",
      "warranty-info"
    ]
  },
  "compute": {
    "lambda_functions_count": 12,
    "function_names": [
      "get-dealer-data",
      "get-dealer-appointment-slots",
      "BookAppointment",
      "BookAppointmentStar",
      "get-parts-for-dtc",
      "place-parts-order",
      "get-dealer-stock",
      "GetWarrantyData",
      "SampleDataFunction",
      "InsertCustomerProfiles",
      "dtc-parts-data-loader",
      "InsertWarrantyInfo"
    ]
  },
  "codebuild": {
    "projects_count": 3,
    "project_names": [
      "cdk_synthesis",
      "agentcore_deployment",
      "agentcore_00-products-agent"
    ]
  },
  "agents": {
    "cdk_nested_stacks": [
      {
        "name": "00-vista-agents",
        "path": "/Users/agweber/code/old-amazon-bedrock-agents-healthcare-lifesciences/agents_catalog/multi_agent_collaboration/00-vista-agents/cdk",
        "stack_class": "VistaServiceStack",
        "category": "multi_agent_collaboration"
      }
    ],
    "agentcore_agents": [
      {
        "name": "00-products-agent",
        "path": "/Users/agweber/code/old-amazon-bedrock-agents-healthcare-lifesciences/agents_catalog/standalone_agents/00-products-agent",
        "category": "standalone_agents",
        "has_dockerfile": true,
        "has_requirements": true
      }
    ],
    "total_agents": 2
  }
}
```

