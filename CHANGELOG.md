# Changelog

All notable changes to this project will be documented in this file.

The format is based on [Keep a Changelog](https://keepachangelog.com/en/1.0.0/),
and this project adheres to [Semantic Versioning](https://semver.org/spec/v2.0.0.html).

---

## [1.1.0] - 2025-10-17

### Added
- Auto-grant permission system that automatically grants IAM permissions to agent resources via resource-based policies, eliminating manual permission management and enabling scalable deployment of 100+ agents without role modification
- Developer documentation with 9 new guides covering agent creation, testing, deployment, and troubleshooting
- `destroy_cdk.sh` script for easy cleanup of deployed resources
- Agent grouping support in UI for better organization

### Changed
- Upgraded Lambda runtime from Python 3.9 to Python 3.11
- Improved AgentCore response parsing in UI to handle multiple JSON formats
- Updated agent discovery and registration system

### Fixed
- Bedrock Agent collaboration dependency issues causing deployment failures
- DynamoDB permission errors for AgentCore agents
- UI not parsing AgentCore responses correctly

### Removed
- Unused Strands agent files

---
