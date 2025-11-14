#!/bin/bash

# List of AgentCore runtime roles to delete
RUNTIME_ROLES=(
    "AmazonBedrockAgentCoreSDKRuntime-us-east-1-9c56b3cf05"
    "AmazonBedrockAgentCoreSDKRuntime-us-east-1-b1d064f266"
    "AmazonBedrockAgentCoreSDKRuntime-us-east-1-d86e38a8f5"
    "AmazonBedrockAgentCoreSDKRuntime-us-east-1-e83eb3798d"
    "AmazonBedrockAgentCoreSDKRuntime-us-east-1-f2edfcb9e6"
    "AmazonBedrockAgentCoreSDKRuntime-us-east-1-f7f6ce1f61"
)

echo "🧹 Cleaning up AgentCore runtime roles..."

for role in "${RUNTIME_ROLES[@]}"; do
    echo "Processing role: $role"
    
    # Detach managed policies
    echo "  Detaching managed policies..."
    aws iam list-attached-role-policies --role-name "$role" --profile grantaws --query 'AttachedPolicies[].PolicyArn' --output text | while read policy_arn; do
        if [ ! -z "$policy_arn" ]; then
            echo "    Detaching: $policy_arn"
            aws iam detach-role-policy --role-name "$role" --policy-arn "$policy_arn" --profile grantaws
        fi
    done
    
    # Delete inline policies
    echo "  Deleting inline policies..."
    aws iam list-role-policies --role-name "$role" --profile grantaws --query 'PolicyNames[]' --output text | while read policy_name; do
        if [ ! -z "$policy_name" ]; then
            echo "    Deleting: $policy_name"
            aws iam delete-role-policy --role-name "$role" --policy-name "$policy_name" --profile grantaws
        fi
    done
    
    # Delete the role
    echo "  Deleting role: $role"
    aws iam delete-role --role-name "$role" --profile grantaws
    
    echo "  ✅ Role $role deleted"
    echo ""
done

echo "🎉 All AgentCore runtime roles cleaned up!"