#!/bin/bash

# Quality Inspection AgentCore Deployment Script
# Deploys agents to AgentCore for the first time using agentcore launch
# Outputs ECR repositories and Bedrock AgentCore Runtime ARNs

set -e

# Configuration
PROFILE="${AWS_PROFILE}"
REGION="${AWS_REGION:-us-east-1}"

# Colors for output
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
NC='\033[0m'

log_info() {
    echo -e "${BLUE}[INFO]${NC} $1"
}

log_success() {
    echo -e "${GREEN}[SUCCESS]${NC} $1"
}

log_error() {
    echo -e "${RED}[ERROR]${NC} $1"
}

# Check prerequisites
check_prerequisites() {
    log_info "Checking AgentCore deployment prerequisites..."
    
    if [ -z "$PROFILE" ]; then
        log_error "AWS_PROFILE environment variable is required"
        exit 1
    fi
    
    # Install AgentCore CLI if not available
    if ! command -v agentcore &> /dev/null; then
        log_info "Installing AgentCore CLI..."
        pip install bedrock-agentcore-starter-toolkit
    fi
    
    # Verify AgentCore CLI installation
    if ! command -v agentcore &> /dev/null; then
        log_error "Failed to install AgentCore CLI"
        exit 1
    fi
    
    # Get account ID
    ACCOUNT_ID=$(aws sts get-caller-identity --profile "$PROFILE" --query Account --output text)
    log_info "Using AWS Account: $ACCOUNT_ID"
    log_info "Using AWS Profile: $PROFILE"
    log_info "Using Region: $REGION"
    
    # Get AgentCore execution role ARN from CloudFormation stack
    AGENTCORE_ROLE_ARN=$(aws cloudformation describe-stacks \
        --stack-name "AgenticQualityInspectionStack" \
        --profile "$PROFILE" \
        --query "Stacks[0].Outputs[?OutputKey=='AgentCoreExecutionRoleArn'].OutputValue" \
        --output text 2>/dev/null)
    
    if [ -z "$AGENTCORE_ROLE_ARN" ] || [ "$AGENTCORE_ROLE_ARN" = "None" ]; then
        log_error "Could not retrieve AgentCore execution role ARN from CloudFormation stack"
        log_error "Make sure the infrastructure stack 'AgenticQualityInspectionStack' is deployed"
        exit 1
    fi
    
    log_info "Using AgentCore Execution Role: $AGENTCORE_ROLE_ARN"
}

# Deploy agents to AgentCore
deploy_agents() {
    log_info "Deploying agents to AgentCore..."
    
    cd src/agents
    
    # Create account-specific AgentCore config
    log_info "Creating account-specific AgentCore configuration..."
    rm -rf .bedrock_agentcore/
    
    cat > .bedrock_agentcore.yaml << EOF
default_agent: quality_inspection_orchestrator
agents:
  quality_inspection_orchestrator:
    name: quality_inspection_orchestrator
    entrypoint: quality_inspection_orchestrator.py
    platform: linux/arm64
    aws:
      execution_role: $AGENTCORE_ROLE_ARN
      account: '$ACCOUNT_ID'
      region: $REGION
      network_configuration:
        network_mode: PUBLIC
    observability:
      enabled: true
EOF
    
    log_success "AgentCore config created for account $ACCOUNT_ID"
    
    # Agent configurations with their Python files
    agent_names=("quality_inspection_orchestrator" "quality_inspection_vision" "quality_inspection_analysis" "quality_inspection_sop" "quality_inspection_action" "quality_inspection_communication")
    agent_files=("quality_inspection_orchestrator.py" "vision_agent.py" "analysis_agent.py" "sop_agent.py" "action_agent.py" "communication_agent.py")
    
    # Create output file for deployment results
    echo "# Quality Inspection AgentCore Deployment Results" > ../../agentcore_deployment_results.md
    echo "Generated on: $(date)" >> ../../agentcore_deployment_results.md
    echo "" >> ../../agentcore_deployment_results.md
    
    for i in "${!agent_names[@]}"; do
        agent_name="${agent_names[$i]}"
        agent_file="${agent_files[$i]}"
        log_info "Configuring and deploying $agent_name..."
        
        # Step 1: Configure the agent
        log_info "Configuring $agent_name with entrypoint $agent_file..."
        agentcore configure \
            --entrypoint "$agent_file" \
            --name "$agent_name" \
            --region "$REGION" \
            --execution-role "$AGENTCORE_ROLE_ARN" \
            --disable-memory \
            --non-interactive
        
        if [ $? -ne 0 ]; then
            log_error "Failed to configure $agent_name"
            continue
        fi
        
        # Step 2: Launch the agent
        log_info "Launching $agent_name to AgentCore..."
        agentcore launch --agent "$agent_name" --auto-update-on-conflict > launch_output.txt 2>&1
        
        if [ $? -eq 0 ]; then
            log_success "$agent_name deployed successfully"
            
            # Get runtime ARN using AWS CLI (more reliable than parsing agentcore status)
            RUNTIME_ARN=$(aws bedrock-agentcore-control list-agent-runtimes \
                --profile "$PROFILE" \
                --query "agentRuntimes[?agentRuntimeName=='$agent_name'].agentRuntimeArn" \
                --output text 2>/dev/null || echo "Not found")
            
            # Get ECR repository from agentcore status
            agentcore status --agent "$agent_name" --verbose > status_output.txt 2>&1
            ECR_REPO=$(grep -o "[0-9]\+\.dkr\.ecr\.[^[:space:]]\+\.amazonaws\.com/[^[:space:]]*" status_output.txt | head -1 || echo "Not found")
            
            # Log results
            echo "Runtime ARN: $RUNTIME_ARN"
            echo "ECR Repository: $ECR_REPO"
            echo ""
            
            # Update SSM parameter with runtime ARN
            case "$agent_name" in
                "quality_inspection_orchestrator")
                    SSM_PARAM="/quality-inspection/agentcore-runtime/orchestrator"
                    ;;
                "quality_inspection_vision")
                    SSM_PARAM="/quality-inspection/agentcore-runtime/vision"
                    ;;
                "quality_inspection_analysis")
                    SSM_PARAM="/quality-inspection/agentcore-runtime/analysis"
                    ;;
                "quality_inspection_sop")
                    SSM_PARAM="/quality-inspection/agentcore-runtime/sop"
                    ;;
                "quality_inspection_action")
                    SSM_PARAM="/quality-inspection/agentcore-runtime/action"
                    ;;
                "quality_inspection_communication")
                    SSM_PARAM="/quality-inspection/agentcore-runtime/communication"
                    ;;
            esac
            
            if [ -n "$SSM_PARAM" ] && [ "$RUNTIME_ARN" != "Not found" ]; then
                log_info "Updating SSM parameter $SSM_PARAM with runtime ARN..."
                aws ssm put-parameter \
                    --name "$SSM_PARAM" \
                    --value "$RUNTIME_ARN" \
                    --overwrite \
                    --profile "$PROFILE" > /dev/null 2>&1
                
                if [ $? -eq 0 ]; then
                    log_success "SSM parameter $SSM_PARAM updated successfully"
                else
                    log_error "Failed to update SSM parameter $SSM_PARAM"
                fi
            fi
            
            # Add to results file
            echo "## $agent_name" >> ../../agentcore_deployment_results.md
            echo "- **Runtime ARN**: \`$RUNTIME_ARN\`" >> ../../agentcore_deployment_results.md
            echo "- **ECR Repository**: \`$ECR_REPO\`" >> ../../agentcore_deployment_results.md
            echo "- **SSM Parameter**: \`$SSM_PARAM\`" >> ../../agentcore_deployment_results.md
            echo "" >> ../../agentcore_deployment_results.md
            
            # Clean up
            rm -f launch_output.txt status_output.txt
        else
            log_error "Failed to deploy $agent_name"
            cat launch_output.txt
            rm -f launch_output.txt
        fi
    done
    
    cd ../..
    log_success "All agents processed"
    log_info "Deployment results saved to: agentcore_deployment_results.md"
}

# Main execution
main() {
    log_info "Starting Quality Inspection AgentCore deployment..."
    
    check_prerequisites
    deploy_agents
    
    log_success "AgentCore deployment completed successfully!"
    echo ""
    echo "Next steps:"
    echo "1. Check agentcore_deployment_results.md for ECR repositories and Runtime ARNs"
    echo "2. Update your application configuration with the new Runtime ARNs"
    echo "3. Test agent invocations using the Runtime ARNs"
}

main "$@"