# Bedrock Agents Functionality Test Report

## Summary
- **Total Tests**: 5
- **Passed**: 5
- **Failed**: 0

## Agent Discovery
✅ **Status**: PASSED

**Stack Outputs**: {}

**Discovered Agents**: 7

**Discovered Aliases**: 14

**Agents**: [
  {
    "agentId": "1BBDXDKVXG",
    "agentName": "SAM-agent-analyze_vehiclesymptom",
    "agentStatus": "PREPARED",
    "description": "Analyze vehicle symptom and recommend an action / next steps based on severity",
    "latestAgentVersion": "1",
    "updatedAt": "2025-07-17 19:56:17.478819+00:00"
  },
  {
    "agentId": "GN7ZOZ71Y9",
    "agentName": "SAM-agent-bookdealerappt",
    "agentStatus": "PREPARED",
    "description": "Customer books appointment with the selected dealership to analyze vehicle symptom",
    "latestAgentVersion": "1",
    "updatedAt": "2025-07-17 19:56:47.293537+00:00"
  },
  {
    "agentId": "GRNHIZYSSB",
    "agentName": "SAM-agent-find-nearestdealership",
    "agentStatus": "PREPARED",
    "description": "Find nearest automotive dealership",
    "latestAgentVersion": "1",
    "updatedAt": "2025-07-17 19:56:58.547348+00:00"
  },
  {
    "agentId": "PTIVLGNHFO",
    "agentName": "SAM-agent-finddealeravailability",
    "agentStatus": "PREPARED",
    "description": "Find dealership availability that will help customer to book appt",
    "latestAgentVersion": "1",
    "updatedAt": "2025-07-17 19:56:48.345663+00:00"
  },
  {
    "agentId": "PB1WPWWP2P",
    "agentName": "SAM-agent-orchestrater",
    "agentStatus": "PREPARED",
    "description": "Multiagent service agent orchestration with end to end flow",
    "latestAgentVersion": "1",
    "updatedAt": "2025-07-17 19:57:39.343303+00:00"
  },
  {
    "agentId": "GDGDNT8P4J",
    "agentName": "SAM-agent-parts-availability",
    "agentStatus": "PREPARED",
    "description": "Check for available parts based on DTC",
    "latestAgentVersion": "1",
    "updatedAt": "2025-07-17 19:56:53.416088+00:00"
  },
  {
    "agentId": "OJA93ADU95",
    "agentName": "SAM-agent-warrantyandrecalls",
    "agentStatus": "PREPARED",
    "description": "Agent on warranties and recalls",
    "latestAgentVersion": "1",
    "updatedAt": "2025-07-17 19:56:46.748025+00:00"
  }
]

**Aliases**: [
  {
    "agent_id": "1BBDXDKVXG",
    "agent_name": "SAM-agent-analyze_vehiclesymptom",
    "alias_id": "KIOZALLTB9",
    "alias_name": "analyze-vehiclesymptom-alias"
  },
  {
    "agent_id": "1BBDXDKVXG",
    "agent_name": "SAM-agent-analyze_vehiclesymptom",
    "alias_id": "TSTALIASID",
    "alias_name": "AgentTestAlias"
  },
  {
    "agent_id": "GN7ZOZ71Y9",
    "agent_name": "SAM-agent-bookdealerappt",
    "alias_id": "TSTALIASID",
    "alias_name": "AgentTestAlias"
  },
  {
    "agent_id": "GN7ZOZ71Y9",
    "agent_name": "SAM-agent-bookdealerappt",
    "alias_id": "ZLAWGQVCLW",
    "alias_name": "bookdealerappt-alias"
  },
  {
    "agent_id": "GRNHIZYSSB",
    "agent_name": "SAM-agent-find-nearestdealership",
    "alias_id": "ELHG8N3TMO",
    "alias_name": "find-nearestdealership-alias"
  },
  {
    "agent_id": "GRNHIZYSSB",
    "agent_name": "SAM-agent-find-nearestdealership",
    "alias_id": "TSTALIASID",
    "alias_name": "AgentTestAlias"
  },
  {
    "agent_id": "PTIVLGNHFO",
    "agent_name": "SAM-agent-finddealeravailability",
    "alias_id": "TSTALIASID",
    "alias_name": "AgentTestAlias"
  },
  {
    "agent_id": "PTIVLGNHFO",
    "agent_name": "SAM-agent-finddealeravailability",
    "alias_id": "ZQMR6WICKM",
    "alias_name": "finddealeravailability-alias"
  },
  {
    "agent_id": "PB1WPWWP2P",
    "agent_name": "SAM-agent-orchestrater",
    "alias_id": "KZRORFD3P3",
    "alias_name": "orchestrater-alias"
  },
  {
    "agent_id": "PB1WPWWP2P",
    "agent_name": "SAM-agent-orchestrater",
    "alias_id": "TSTALIASID",
    "alias_name": "AgentTestAlias"
  },
  {
    "agent_id": "GDGDNT8P4J",
    "agent_name": "SAM-agent-parts-availability",
    "alias_id": "7RTCE236L6",
    "alias_name": "parts-availability-alias"
  },
  {
    "agent_id": "GDGDNT8P4J",
    "agent_name": "SAM-agent-parts-availability",
    "alias_id": "TSTALIASID",
    "alias_name": "AgentTestAlias"
  },
  {
    "agent_id": "OJA93ADU95",
    "agent_name": "SAM-agent-warrantyandrecalls",
    "alias_id": "DKHBBSW63W",
    "alias_name": "warrantyandrecalls-alias"
  },
  {
    "agent_id": "OJA93ADU95",
    "agent_name": "SAM-agent-warrantyandrecalls",
    "alias_id": "TSTALIASID",
    "alias_name": "AgentTestAlias"
  }
]

## Agent Configurations
✅ **Status**: PASSED

**Agent Details**: {
  "1BBDXDKVXG": {
    "name": "SAM-agent-analyze_vehiclesymptom",
    "status": "PREPARED",
    "foundation_model": "anthropic.claude-3-haiku-20240307-v1:0",
    "role_arn": "arn:aws:iam::149536462911:role/ma3t-toolkit-stack-3-Vista-BedrockAgentRole7C982E0C-35kEocbhs9fF",
    "action_groups_count": 0,
    "missing_fields": [],
    "configuration_valid": true
  },
  "GN7ZOZ71Y9": {
    "name": "SAM-agent-bookdealerappt",
    "status": "PREPARED",
    "foundation_model": "anthropic.claude-3-haiku-20240307-v1:0",
    "role_arn": "arn:aws:iam::149536462911:role/ma3t-toolkit-stack-3-Vista-BedrockAgentRole7C982E0C-35kEocbhs9fF",
    "action_groups_count": 0,
    "missing_fields": [],
    "configuration_valid": true
  },
  "GRNHIZYSSB": {
    "name": "SAM-agent-find-nearestdealership",
    "status": "PREPARED",
    "foundation_model": "anthropic.claude-3-haiku-20240307-v1:0",
    "role_arn": "arn:aws:iam::149536462911:role/ma3t-toolkit-stack-3-Vista-BedrockAgentRole7C982E0C-35kEocbhs9fF",
    "action_groups_count": 0,
    "missing_fields": [],
    "configuration_valid": true
  },
  "PTIVLGNHFO": {
    "name": "SAM-agent-finddealeravailability",
    "status": "PREPARED",
    "foundation_model": "anthropic.claude-3-haiku-20240307-v1:0",
    "role_arn": "arn:aws:iam::149536462911:role/ma3t-toolkit-stack-3-Vista-BedrockAgentRole7C982E0C-35kEocbhs9fF",
    "action_groups_count": 0,
    "missing_fields": [],
    "configuration_valid": true
  },
  "PB1WPWWP2P": {
    "name": "SAM-agent-orchestrater",
    "status": "PREPARED",
    "foundation_model": "anthropic.claude-3-haiku-20240307-v1:0",
    "role_arn": "arn:aws:iam::149536462911:role/ma3t-toolkit-stack-3-Vista-BedrockAgentRole7C982E0C-35kEocbhs9fF",
    "action_groups_count": 0,
    "missing_fields": [],
    "configuration_valid": true
  },
  "GDGDNT8P4J": {
    "name": "SAM-agent-parts-availability",
    "status": "PREPARED",
    "foundation_model": "anthropic.claude-3-haiku-20240307-v1:0",
    "role_arn": "arn:aws:iam::149536462911:role/ma3t-toolkit-stack-3-Vista-BedrockAgentRole7C982E0C-35kEocbhs9fF",
    "action_groups_count": 0,
    "missing_fields": [],
    "configuration_valid": true
  },
  "OJA93ADU95": {
    "name": "SAM-agent-warrantyandrecalls",
    "status": "PREPARED",
    "foundation_model": "anthropic.claude-3-haiku-20240307-v1:0",
    "role_arn": "arn:aws:iam::149536462911:role/ma3t-toolkit-stack-3-Vista-BedrockAgentRole7C982E0C-35kEocbhs9fF",
    "action_groups_count": 0,
    "missing_fields": [],
    "configuration_valid": true
  }
}

**Total Agents**: 7

**Valid Agents**: 7

## Agent Aliases
✅ **Status**: PASSED

**Alias Details**: {
  "1BBDXDKVXG:KIOZALLTB9": {
    "agent_name": "SAM-agent-analyze_vehiclesymptom",
    "alias_name": "analyze-vehiclesymptom-alias",
    "status": "PREPARED",
    "routing_entries": 1,
    "alias_valid": true
  },
  "1BBDXDKVXG:TSTALIASID": {
    "agent_name": "SAM-agent-analyze_vehiclesymptom",
    "alias_name": "AgentTestAlias",
    "status": "PREPARED",
    "routing_entries": 1,
    "alias_valid": true
  },
  "GN7ZOZ71Y9:TSTALIASID": {
    "agent_name": "SAM-agent-bookdealerappt",
    "alias_name": "AgentTestAlias",
    "status": "PREPARED",
    "routing_entries": 1,
    "alias_valid": true
  },
  "GN7ZOZ71Y9:ZLAWGQVCLW": {
    "agent_name": "SAM-agent-bookdealerappt",
    "alias_name": "bookdealerappt-alias",
    "status": "PREPARED",
    "routing_entries": 1,
    "alias_valid": true
  },
  "GRNHIZYSSB:ELHG8N3TMO": {
    "agent_name": "SAM-agent-find-nearestdealership",
    "alias_name": "find-nearestdealership-alias",
    "status": "PREPARED",
    "routing_entries": 1,
    "alias_valid": true
  },
  "GRNHIZYSSB:TSTALIASID": {
    "agent_name": "SAM-agent-find-nearestdealership",
    "alias_name": "AgentTestAlias",
    "status": "PREPARED",
    "routing_entries": 1,
    "alias_valid": true
  },
  "PTIVLGNHFO:TSTALIASID": {
    "agent_name": "SAM-agent-finddealeravailability",
    "alias_name": "AgentTestAlias",
    "status": "PREPARED",
    "routing_entries": 1,
    "alias_valid": true
  },
  "PTIVLGNHFO:ZQMR6WICKM": {
    "agent_name": "SAM-agent-finddealeravailability",
    "alias_name": "finddealeravailability-alias",
    "status": "PREPARED",
    "routing_entries": 1,
    "alias_valid": true
  },
  "PB1WPWWP2P:KZRORFD3P3": {
    "agent_name": "SAM-agent-orchestrater",
    "alias_name": "orchestrater-alias",
    "status": "PREPARED",
    "routing_entries": 1,
    "alias_valid": true
  },
  "PB1WPWWP2P:TSTALIASID": {
    "agent_name": "SAM-agent-orchestrater",
    "alias_name": "AgentTestAlias",
    "status": "PREPARED",
    "routing_entries": 1,
    "alias_valid": true
  },
  "GDGDNT8P4J:7RTCE236L6": {
    "agent_name": "SAM-agent-parts-availability",
    "alias_name": "parts-availability-alias",
    "status": "PREPARED",
    "routing_entries": 1,
    "alias_valid": true
  },
  "GDGDNT8P4J:TSTALIASID": {
    "agent_name": "SAM-agent-parts-availability",
    "alias_name": "AgentTestAlias",
    "status": "PREPARED",
    "routing_entries": 1,
    "alias_valid": true
  },
  "OJA93ADU95:DKHBBSW63W": {
    "agent_name": "SAM-agent-warrantyandrecalls",
    "alias_name": "warrantyandrecalls-alias",
    "status": "PREPARED",
    "routing_entries": 1,
    "alias_valid": true
  },
  "OJA93ADU95:TSTALIASID": {
    "agent_name": "SAM-agent-warrantyandrecalls",
    "alias_name": "AgentTestAlias",
    "status": "PREPARED",
    "routing_entries": 1,
    "alias_valid": true
  }
}

**Total Aliases**: 14

**Valid Aliases**: 14

## Agent Invocation
✅ **Status**: PASSED

**Invocation Results**: {
  "1BBDXDKVXG:KIOZALLTB9": {
    "agent_name": "SAM-agent-analyze_vehiclesymptom",
    "alias_name": "analyze-vehiclesymptom-alias",
    "test_prompt": "My car is making a strange noise when I brake. What could be wrong?",
    "response_length": 1028,
    "response_preview": "Based on the information provided, there are a few potential issues that could be causing the strange noise when braking:\n\n1. Potential Issues:\n- Worn or damaged brake pads\n- Warped or damaged brake r...",
    "invocation_successful": true
  },
  "1BBDXDKVXG:TSTALIASID": {
    "agent_name": "SAM-agent-analyze_vehiclesymptom",
    "alias_name": "AgentTestAlias",
    "test_prompt": "My car is making a strange noise when I brake. What could be wrong?",
    "response_length": 1012,
    "response_preview": "Based on the information provided, a strange noise when braking could be caused by a few potential issues:\n\n1. Potential Issues:\n- Worn or damaged brake pads\n- Warped or damaged brake rotors\n- Loose o...",
    "invocation_successful": true
  },
  "GN7ZOZ71Y9:TSTALIASID": {
    "agent_name": "SAM-agent-bookdealerappt",
    "alias_name": "AgentTestAlias",
    "test_prompt": "Hello, I'd like to know about booking an appointment",
    "response_length": 471,
    "response_preview": "Looks like I'm missing some key information to book the appointment. Let me ask you for the details I need:\n\n- What is the dealer name you would like to book the appointment with?\n- What is the date y...",
    "invocation_successful": true
  }
}

**Total Tested**: 3

**Successful Invocations**: 3

**Skipped Invocations**: 0

## Supervisor Collaboration
✅ **Status**: PASSED

**Supervisor Agent**: SAM-agent-orchestrater

**Collaboration Mode**: SUPERVISOR_ROUTER

**Collaborators Count**: 0

**Collaborator Details**: []

**Collaboration Test Successful**: True

**Test Response Length**: 207

