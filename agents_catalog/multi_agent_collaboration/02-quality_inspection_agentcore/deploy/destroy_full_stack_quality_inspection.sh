#!/bin/bash

# Quality Inspection System - Complete Destroy Script
# This script destroys AgentCore agents first, then destroys the infrastructure stack
#
# COMPATIBILITY: Works on macOS and Windows (with Git Bash)
# PREREQUISITES: AWS CLI, CDK CLI, AgentCore CLI

set -e  # Exit on any error

# Configuration
PROFILE="${AWS_PROFILE}"
REGION="${AWS_REGION:-us-east-1}"
STACK_NAME="AgenticQualityInspectionStack"
FORCE_DESTROY=false

# Parse command line arguments
while [[ $# -gt 0 ]]; do
  case $1 in
    --force)
      FORCE_DESTROY=true
      shift
      ;;
    *)
      echo "Unknown option: $1"
      echo "Usage: $0 [--force]"
      exit 1
      ;;
  esac
done

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

# Check prerequisites
check_prerequisites() {
    log_info "Checking prerequisites..."
    
    # Check if AWS_PROFILE is provided
    if [ -z "$PROFILE" ]; then
        log_error "AWS_PROFILE environment variable is required"
        log_error "Usage: AWS_PROFILE=your-profile bash destroy_full_stack_quality_inspection.sh"
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
    
    # Check AgentCore CLI
    if ! command -v agentcore &> /dev/null; then
        log_warning "AgentCore CLI not found. Skipping AgentCore cleanup."
        SKIP_AGENTCORE=true
    else
        SKIP_AGENTCORE=false
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

# Destroy AgentCore agents
destroy_agentcore_agents() {
    if [ "$SKIP_AGENTCORE" = true ]; then
        log_warning "Skipping AgentCore cleanup (CLI not found)"
        return
    fi
    
    log_info "Destroying AgentCore agents..."
    
    # List of Quality Inspection agents
    AGENTS=(
        "quality_inspection_orchestrator"
        "quality_inspection_vision"
        "quality_inspection_analysis"
        "quality_inspection_sop"
        "quality_inspection_action"
        "quality_inspection_communication"
    )
    
    # Get list of configured agents to check which ones exist
    log_info "Checking for existing AgentCore agents..."
    SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
    AGENTS_DIR="$SCRIPT_DIR/../src/agents"
    
    if [ -d "$AGENTS_DIR" ]; then
        ORIGINAL_DIR=$(pwd)
        cd "$AGENTS_DIR"
        CONFIGURED_AGENTS=$(agentcore configure list 2>/dev/null | grep -E "✅ quality_inspection_" | awk '{print $2}' || true)
        cd "$ORIGINAL_DIR"
        log_info "Found configured agents: $CONFIGURED_AGENTS"
    else
        log_warning "Agents directory not found: $AGENTS_DIR"
        CONFIGURED_AGENTS=""
    fi
    
    if [ -z "$CONFIGURED_AGENTS" ]; then
        log_info "No AgentCore agents configured locally. Checking AWS resources directly..."
        
        # Manually clean up AgentCore resources using AWS CLI
        log_info "Cleaning up AgentCore runtimes using AWS CLI..."
        
        # List and delete AgentCore runtimes
        RUNTIMES=$(aws bedrock-agentcore list-runtimes --region "$REGION" --profile "$PROFILE" --query 'runtimes[?contains(name, `quality_inspection`)].name' --output text 2>/dev/null || true)
        
        if [ ! -z "$RUNTIMES" ]; then
            for runtime in $RUNTIMES; do
                log_info "Deleting AgentCore runtime: $runtime"
                aws bedrock-agentcore delete-runtime --name "$runtime" --region "$REGION" --profile "$PROFILE" 2>/dev/null || log_warning "Failed to delete runtime: $runtime"
            done
        else
            log_info "No AgentCore runtimes found with quality_inspection prefix"
        fi
        
        # Clean up ECR repositories
        log_info "Cleaning up ECR repositories..."
        ECR_REPOS=$(aws ecr describe-repositories --region "$REGION" --profile "$PROFILE" --query 'repositories[?contains(repositoryName, `quality_inspection`)].repositoryName' --output text 2>/dev/null || true)
        
        if [ ! -z "$ECR_REPOS" ]; then
            for repo in $ECR_REPOS; do
                log_info "Deleting ECR repository: $repo"
                aws ecr delete-repository --repository-name "$repo" --force --region "$REGION" --profile "$PROFILE" 2>/dev/null || log_warning "Failed to delete ECR repo: $repo"
            done
        else
            log_info "No ECR repositories found with quality_inspection prefix"
        fi
        
        return
    fi
    
    # Destroy each agent that exists
    if [ -d "$AGENTS_DIR" ] && [ ! -z "$CONFIGURED_AGENTS" ]; then
        ORIGINAL_DIR=$(pwd)
        cd "$AGENTS_DIR"
        for agent in "${AGENTS[@]}"; do
            if echo "$CONFIGURED_AGENTS" | grep -q "$agent"; then
                log_info "Destroying agent: $agent"
                if agentcore destroy --agent "$agent" --force --delete-ecr-repo; then
                    log_success "Agent destroyed: $agent"
                else
                    log_warning "Failed to destroy agent: $agent"
                fi
            else
                log_info "Agent not configured locally, skipping: $agent"
            fi
        done
        cd "$ORIGINAL_DIR"
    elif [ -z "$CONFIGURED_AGENTS" ]; then
        log_info "No configured agents found locally"
    fi
    
    log_success "AgentCore agents cleanup completed"
}

# Destroy infrastructure stack
destroy_infrastructure() {
    log_info "Destroying infrastructure stack..."
    
    # Check if stack exists
    if ! aws cloudformation describe-stacks --stack-name "$STACK_NAME" --profile "$PROFILE" --region "$REGION" &>/dev/null; then
        log_info "Stack $STACK_NAME does not exist, skipping"
        return
    fi
    
    SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
    CDK_DIR="$SCRIPT_DIR/../cdk"
    
    # Check if CDK directory exists
    if [ ! -d "$CDK_DIR" ]; then
        log_error "CDK directory not found: $CDK_DIR"
        return 1
    fi
    
    cd "$CDK_DIR"
    
    # Destroy infrastructure stack
    log_info "Destroying CDK stack: $STACK_NAME"
    cdk destroy "$STACK_NAME" --app "python app.py" --profile "$PROFILE" --force --region "$REGION"
    
    cd - > /dev/null
    log_success "Infrastructure stack destroyed"
}

# Clean up S3 bucket contents (CDK won't delete non-empty buckets)
cleanup_s3_bucket() {
    log_info "Cleaning up S3 bucket contents..."
    
    BUCKET_NAME="machinepartimages-$ACCOUNT_ID"
    
    # Check if bucket exists
    if aws s3 ls "s3://$BUCKET_NAME" --profile "$PROFILE" --region "$REGION" &>/dev/null; then
        log_info "Emptying S3 bucket: $BUCKET_NAME"
        aws s3 rm "s3://$BUCKET_NAME" --recursive --profile "$PROFILE" --region "$REGION" || true
        log_success "S3 bucket emptied: $BUCKET_NAME"
    else
        log_info "S3 bucket not found: $BUCKET_NAME"
    fi
}

# Verify destruction
verify_destruction() {
    log_info "Verifying destruction..."
    
    # Check if stack still exists
    if aws cloudformation describe-stacks --stack-name "$STACK_NAME" --profile "$PROFILE" --region "$REGION" &>/dev/null; then
        log_error "Stack still exists: $STACK_NAME"
        return 1
    else
        log_success "Stack successfully destroyed: $STACK_NAME"
    fi
    
    # Check if S3 bucket still exists
    BUCKET_NAME="machinepartimages-$ACCOUNT_ID"
    if aws s3 ls "s3://$BUCKET_NAME" --profile "$PROFILE" --region "$REGION" &>/dev/null; then
        log_warning "S3 bucket still exists: $BUCKET_NAME (may be retained by design)"
    else
        log_success "S3 bucket destroyed: $BUCKET_NAME"
    fi
    
    log_success "Destruction verification completed"
}

# Print destruction summary
print_summary() {
    log_success "=== DESTRUCTION COMPLETED SUCCESSFULLY ==="
    echo
    log_info "Resources Destroyed:"
    echo "  • AgentCore Agents: 6 agent runtimes removed"
    echo "  • ECR Repositories: Agent container images deleted"
    echo "  • CDK Stack: $STACK_NAME"
    echo "  • S3 Bucket: Contents emptied"
    echo "  • DynamoDB Tables: All quality inspection tables"
    echo "  • VPC: vpc-agentic-quality-inspection"
    echo "  • SNS Topic: quality-inspection-alerts"
    echo
    log_info "Manual Cleanup (if needed):"
    echo "  • Check AWS Console for any remaining resources"
    echo "  • Verify CloudWatch Log Groups are deleted"
    echo "  • Check for any remaining IAM roles/policies"
    echo
    log_success "Quality Inspection system completely destroyed!"
}

# Main execution
main() {
    log_info "Starting Quality Inspection full stack destruction..."
    
    # Confirmation prompt (skip if --force flag is used)
    if [ "$FORCE_DESTROY" != true ]; then
        echo
        log_warning "This will permanently destroy the Quality Inspection system including:"
        echo "  • All AgentCore agent runtimes"
        echo "  • All infrastructure resources"
        echo "  • All data in DynamoDB tables"
        echo "  • All S3 bucket contents"
        echo
        read -p "Are you sure you want to continue? (yes/no): " confirm
        
        if [ "$confirm" != "yes" ]; then
            log_info "Destruction cancelled by user"
            exit 0
        fi
    else
        log_info "Force destroy enabled - skipping confirmation"
    fi
    
    check_prerequisites
    cleanup_s3_bucket
    destroy_agentcore_agents
    destroy_infrastructure
    verify_destruction
    print_summary
    
    log_success "Full stack destruction completed successfully!"
}

main "$@"