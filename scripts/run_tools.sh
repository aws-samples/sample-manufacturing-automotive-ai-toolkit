#!/bin/bash

# MA3T Development Tools Runner
# Runs various development and security tools

set -e

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PROJECT_ROOT="$(dirname "$SCRIPT_DIR")"

# Default configuration
TOOL=""
REGION="${AWS_DEFAULT_REGION:-us-west-2}"

# Parse command line arguments
while [[ $# -gt 0 ]]; do
  case $1 in
    --tool)
      TOOL="$2"
      shift 2
      ;;
    --region)
      REGION="$2"
      shift 2
      ;;
    -h|--help)
      echo "Usage: $0 --tool TOOL [--region REGION]"
      echo ""
      echo "Available tools:"
      echo "  cdk-nag     Run CDK-Nag security checks"
      echo "  all         Run all available tools"
      echo ""
      echo "Options:"
      echo "  --region    AWS region (default: us-west-2)"
      echo "  --help      Show this help message"
      exit 0
      ;;
    *)
      echo "Unknown option: $1"
      echo "Use --help for usage information"
      exit 1
      ;;
  esac
done

if [ -z "$TOOL" ]; then
  echo "Error: --tool is required"
  echo "Use --help for usage information"
  exit 1
fi

run_cdk_nag() {
  echo "🔍 Running CDK-Nag security checks..."
  
  cd "$PROJECT_ROOT/cdk"
  
  # Install dependencies
  echo "📦 Installing CDK dependencies..."
  pip install -r requirements.txt
  
  # Run CDK synth with nag checks
  echo "🔍 Running CDK synth with nag checks..."
  export CDK_DEFAULT_REGION="$REGION"
  cdk synth --all
  
  if [ $? -eq 0 ]; then
    echo "✅ CDK-Nag checks completed successfully!"
  else
    echo "❌ CDK-Nag checks found issues"
    exit 1
  fi
}

run_all_tools() {
  echo "🛠️  Running all development tools..."
  run_cdk_nag
  echo "✅ All tools completed successfully!"
}

# Main execution
case $TOOL in
  cdk-nag)
    run_cdk_nag
    ;;
  all)
    run_all_tools
    ;;
  *)
    echo "Unknown tool: $TOOL"
    echo "Use --help to see available tools"
    exit 1
    ;;
esac

echo "🎉 Tools execution completed!"
