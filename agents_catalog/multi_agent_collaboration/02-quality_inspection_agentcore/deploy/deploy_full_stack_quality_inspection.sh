#!/bin/bash

# Quality Inspection System - Complete Deployment Script
# This script deploys infrastructure first, then deploys AgentCore agents
#
# COMPATIBILITY: Works on macOS and Windows (with Git Bash)
# PREREQUISITES: AWS CLI, CDK CLI, Python 3.x, AgentCore CLI

set -e  # Exit on any error

# Configuration
PROFILE="${AWS_PROFILE}"
REGION="${AWS_REGION:-us-east-1}"
STACK_NAME="AgenticQualityInspectionStack"

# Colors for output
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
NC='\033[0m' # No Color

# Logging functions
log_info() {
    echo -e "${BLUE}[INFO]${NC} $1"
}

log_success() {
    echo -e "${GREEN}[SUCCESS]${NC} $1"
}

log_warning() {
    echo -e "${YELLOW}[WARNING]${NC} $1"
}

log_error() {
    echo -e "${RED}[ERROR]${NC} $1"
}

# Cleanup function for rollback
cleanup() {
    local exit_code=$?
    if [ $exit_code -ne 0 ]; then
        log_error "Deployment failed. Starting rollback..."
        
        # Rollback infrastructure stack
        if [ "$INFRASTRUCTURE_DEPLOYED" = "true" ]; then
            log_warning "Rolling back infrastructure stack..."
            cd ../cdk
            cdk destroy --profile "$PROFILE" --force || true
            cd ../deploy
        fi
        
        log_error "Rollback completed. Please check AWS Console for any remaining resources."
        exit $exit_code
    fi
}

# Set trap for cleanup on exit
trap cleanup EXIT

# Check prerequisites
check_prerequisites() {
    log_info "Checking prerequisites..."
    
    # Check if AWS_PROFILE is provided
    if [ -z "$PROFILE" ]; then
        log_error "AWS_PROFILE environment variable is required"
        log_error "Usage: AWS_PROFILE=your-profile bash deploy_full_stack_quality_inspection.sh"
        exit 1
    fi
    
    # Check AWS CLI
    if ! command -v aws &> /dev/null; then
        log_error "AWS CLI is not installed"
        exit 1
    fi
    
    # Check CDK CLI
    if ! command -v cdk &> /dev/null; then
        log_error "CDK CLI is not installed. Run: npm install -g aws-cdk"
        exit 1
    fi
    
    # Detect Python command (python3 vs python)
    if command -v python3 &> /dev/null; then
        PYTHON_CMD="python3"
        PIP_CMD="pip3"
    elif command -v python &> /dev/null; then
        PYTHON_CMD="python"
        PIP_CMD="pip"
    else
        log_error "Python is not installed or not in PATH"
        exit 1
    fi
    
    # Check AgentCore CLI
    if ! command -v agentcore &> /dev/null; then
        log_info "AgentCore CLI not found. It will be installed during deployment."
    fi
    
    # Check AWS profile
    if ! aws sts get-caller-identity --profile "$PROFILE" &> /dev/null; then
        log_error "AWS profile '$PROFILE' is not configured or invalid"
        exit 1
    fi
    
    # Get account ID
    ACCOUNT_ID=$(aws sts get-caller-identity --profile "$PROFILE" --query Account --output text)
    
    log_info "Using AWS Account: $ACCOUNT_ID"
    log_info "Using AWS Profile: $PROFILE"
    log_info "Using Region: $REGION"
    
    log_success "Prerequisites check passed"
}

# Deploy infrastructure
deploy_infrastructure() {
    log_info "Deploying infrastructure stack..."
    
    cd ../cdk
    
    # Install CDK dependencies
    log_info "Installing CDK dependencies..."
    $PIP_CMD install -r requirements.txt
    
    # Bootstrap CDK if needed
    log_info "Bootstrapping CDK..."
    cdk bootstrap --profile "$PROFILE"
    
    # Deploy infrastructure stack
    log_info "Deploying infrastructure stack..."
    cdk deploy "$STACK_NAME" --profile "$PROFILE" --require-approval never
    
    cd ..
    INFRASTRUCTURE_DEPLOYED=true
    log_success "Infrastructure deployment completed"
}

# Deploy AgentCore agents
deploy_agentcore_agents() {
    log_info "Deploying AgentCore agents..."
    
    # Run the AgentCore deployment script
    if [ -f "./quality_inspection_agentcore_deploy.sh" ]; then
        log_info "Running AgentCore deployment script..."
        bash ./quality_inspection_agentcore_deploy.sh
        log_success "AgentCore agents deployed successfully"
    else
        log_error "AgentCore deployment script not found: ./quality_inspection_agentcore_deploy.sh"
        exit 1
    fi
}

# Verify deployment
verify_deployment() {
    log_info "Verifying deployment..."
    
    # Check S3 bucket
    BUCKET_NAME="machinepartimages-$ACCOUNT_ID"
    if aws s3 ls "s3://$BUCKET_NAME" --profile "$PROFILE" &> /dev/null; then
        log_success "S3 bucket verified: $BUCKET_NAME"
    else
        log_error "S3 bucket not found: $BUCKET_NAME"
        return 1
    fi
    
    # Check DynamoDB table
    if aws dynamodb describe-table --table-name "vision-inspection-data" --profile "$PROFILE" &> /dev/null; then
        log_success "DynamoDB table verified: vision-inspection-data"
    else
        log_error "DynamoDB table not found: vision-inspection-data"
        return 1
    fi
    
    log_success "Deployment verification completed"
}

# Print deployment summary
print_summary() {
    log_success "=== DEPLOYMENT COMPLETED SUCCESSFULLY ==="
    echo
    log_info "Key Resources Created:"
    echo "  • S3 Bucket: machinepartimages-$ACCOUNT_ID"
    echo "  • DynamoDB Tables: vision-inspection-data, sop-decisions, action-execution-log, etc."
    echo "  • AgentCore Agents: 6 agent runtimes deployed"
    echo "  • VPC: vpc-agentic-quality-inspection"
    echo "  • SNS Topic: quality-inspection-alerts"
    echo
    log_info "Next Steps:"
    echo "  1. Check agentcore_deployment_results.md for ECR repositories and Runtime ARNs"
    echo "  2. Upload test images to s3://machinepartimages-$ACCOUNT_ID/inputimages/"
    echo "  3. Monitor CloudWatch logs for agent execution"
    echo "  4. Check DynamoDB tables for inspection results"
    echo "  5. Review SNS notifications for quality alerts"
    echo
    log_info "To get stack outputs:"
    echo "  aws cloudformation describe-stacks --stack-name $STACK_NAME --profile $PROFILE --query 'Stacks[0].Outputs'"
}

# Main execution
main() {
    log_info "Starting Quality Inspection full stack deployment..."
    
    check_prerequisites
    deploy_infrastructure
    deploy_agentcore_agents
    verify_deployment
    print_summary
    
    log_success "Full stack deployment completed successfully!"
}

main "$@"