#!/bin/bash

# Simple script to destroy only AgentCore agents
# Use this when CDK stack is already destroyed

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

log_warning() {
    echo -e "${YELLOW}[WARNING]${NC} $1"
}

log_error() {
    echo -e "${RED}[ERROR]${NC} $1"
}

# Check prerequisites
if [ -z "$PROFILE" ]; then
    log_error "AWS_PROFILE environment variable is required"
    exit 1
fi

if ! command -v agentcore &> /dev/null; then
    log_error "AgentCore CLI not found"
    exit 1
fi

log_info "Destroying AgentCore agents only..."

# List of Quality Inspection agents
AGENTS=(
    "quality_inspection_orchestrator"
    "quality_inspection_vision"
    "quality_inspection_analysis"
    "quality_inspection_sop"
    "quality_inspection_action"
    "quality_inspection_communication"
)

# Get script directory and navigate to agents directory
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
AGENTS_DIR="$SCRIPT_DIR/../src/agents"

if [ ! -d "$AGENTS_DIR" ]; then
    log_error "Agents directory not found: $AGENTS_DIR"
    exit 1
fi

ORIGINAL_DIR=$(pwd)
cd "$AGENTS_DIR"

# Get list of configured agents
log_info "Checking for existing AgentCore agents..."
CONFIGURED_AGENTS=$(agentcore configure list 2>/dev/null | grep -E "✅ quality_inspection_" | awk '{print $2}' || true)

if [ -z "$CONFIGURED_AGENTS" ]; then
    log_info "No Quality Inspection AgentCore agents found"
    cd "$ORIGINAL_DIR"
    exit 0
fi

log_info "Found agents: $CONFIGURED_AGENTS"

# Destroy each agent that exists
for agent in "${AGENTS[@]}"; do
    if echo "$CONFIGURED_AGENTS" | grep -q "$agent"; then
        log_info "Destroying agent: $agent"
        if agentcore destroy --agent "$agent" --force --delete-ecr-repo; then
            log_success "Agent destroyed: $agent"
        else
            log_warning "Failed to destroy agent: $agent"
        fi
    else
        log_info "Agent not found, skipping: $agent"
    fi
done

cd "$ORIGINAL_DIR"

log_success "AgentCore agents cleanup completed!"