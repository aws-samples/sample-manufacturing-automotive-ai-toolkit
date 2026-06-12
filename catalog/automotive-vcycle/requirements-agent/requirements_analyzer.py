"""
Automotive Requirements Analyzer Agent Graph

This module implements a multi-agent system for automotive requirements analysis using Strands agents.
The system analyzes requirements documents for consistency and generates user acceptance tests if no severe issues are found.

Architecture:
- Agent 1: Requirements Consistency Analyzer
- Agent 2: User Acceptance Test Generator (conditional execution)
- Conditional edge based on consistency analysis results
"""

from strands import Agent, tool
from strands.models import BedrockModel
from strands.multiagent import GraphBuilder
from bedrock_agentcore.runtime import BedrockAgentCoreApp
import json
import re
import traceback
from datetime import datetime
from typing import Dict, Any

app = BedrockAgentCoreApp()

# Requirements analysis tool
@tool
def check_for_incomplete_requirements(requirements_doc_content: str) -> dict:
    """
    Analyzes business requirements documents for consistency, completeness, and quality.
    
    Args:
        requirements_doc_content: The FULL TEXT CONTENT of the requirements document(s) to analyze.
    
    Returns:
        A dictionary with issue severity and details including:
        - issues: List of identified issues with type, description, severity, and occurrences
        - total_issues: Total count of issues found
        - ready_for_development: Boolean indicating if requirements are ready
        - severity_counts: Breakdown of issues by severity level (high, medium, low)
    """
    issues = []
    
    # Automotive requirements analysis checks based on BRD structure
    analysis_patterns = {
        "Missing Functional Requirements IDs": {
            "pattern": r"(?i)(?:functional requirement|FR)(?!.*\bFR-\d+\b)",
            "description": "Functional requirements should have unique identifiers (e.g., FR-100, FR-110)",
            "severity": "MEDIUM"
        },
        "Missing Non-Functional Requirements IDs": {
            "pattern": r"(?i)(?:non-functional requirement|NFR)(?!.*\bNFR-\d+\b)",
            "description": "Non-functional requirements should have unique identifiers (e.g., NFR-100, NFR-110)",
            "severity": "MEDIUM"
        },
        "Incomplete Requirements": {
            "pattern": r"\b(TODO|ToDo|TBD|To be determined|PLACEHOLDER|XXX)\b",
            "description": "Requirements contain incomplete or placeholder items",
            "severity": "HIGH"
        }
    }
    
    for issue_type, pattern_info in analysis_patterns.items():
        matches = re.findall(pattern_info["pattern"], requirements_doc_content, re.MULTILINE | re.IGNORECASE)
        if matches:
            issues.append({
                "issue_type": issue_type,
                "description": pattern_info["description"],
                "severity": pattern_info["severity"],
                "occurrences": len(matches)
            })
    
    # Count severity levels
    high_count = sum(1 for issue in issues if issue["severity"] == "HIGH")
    medium_count = sum(1 for issue in issues if issue["severity"] == "MEDIUM")
    low_count = sum(1 for issue in issues if issue["severity"] == "LOW")
    
    return {
        "issues": issues,
        "total_issues": len(issues),
        "ready_for_development": high_count == 0,
        "severity_counts": {
            "high": high_count,
            "medium": medium_count,
            "low": low_count
        }
    }


# Create the model for all agents
model_id = "us.amazon.nova-2-lite-v1:0" #"us.anthropic.claude-haiku-4-5-20251001-v1:0"
model = BedrockModel(
    model_id=model_id, max_tokens=40000
)

# Create the requirements analyzer agent
requirements_analyzer_agent = Agent(
    name="requirements_analyzer",
    model=model,
    tools=[check_for_incomplete_requirements],
    system_prompt="""You are an automotive requirements analyst specializing in vehicle infotainment and safety systems. Your job is to:

1. Analyze automotive requirements documents (BRDs) for consistency, completeness, and quality
2. Evaluate requirements against automotive industry standards (ISO 26262, UNECE WP.29, Android Auto guidelines)
3. Identify issues with severity levels (LOW, MEDIUM, HIGH) based on safety and development impact
4. Assess requirements structure including:
   - Functional Requirements (FR-XXX) with acceptance criteria
   - Non-Functional Requirements (NFR-XXX) with measurable targets
   - Use cases with triggers, flows, and success criteria
   - Business drivers with success metrics
   - Safety and security considerations

IMPORTANT: Always use the check_for_incomplete_requirements tool to check if there are any missing content. Then use your expert knowledge to provide an overall assessment.

In your response, clearly state:
- **Overall Severity**: [LOW/MEDIUM/HIGH]
- **Ready for Development**: [YES/NO] 
- **Safety Assessment**: Any driver distraction or safety concerns
- **Completeness Score**: Percentage of required sections present.

Focus on automotive safety standards, driver distraction guidelines, and development readiness. Provide specific, actionable feedback for improvement."""
)

#2. Include business objective validation scenarios, 4. Create tests that are suitable for safety-critical applications
#using a minimal set of... to reduce response time.
# Create the user acceptance test generator agent
uat_generator_agent = Agent(
    name="uat_generator",
    model=model,
    system_prompt="""You are a user acceptance test generator for automotive applications. Your job is to:
1. Generate user acceptance tests based on requirements
2. Follow automotive testing standards

Generate clean, well-documented test specifications that can be easily executed by test teams."""
)

# No conditional logic - always generate UATs

# Build the multi-agent graph
def build_requirements_analyzer_graph():
    """
    Build the requirements analyzer graph with conditional workflow.
    """
    builder = GraphBuilder()
    
    # Add nodes to the graph
    builder.add_node(requirements_analyzer_agent, "requirements_analyzer")
    builder.add_node(uat_generator_agent, "uat_generator")
    
    # Add unconditional edge: always generate UATs
    builder.add_edge("requirements_analyzer", "uat_generator")
    
    # Set entry point
    builder.set_entry_point("requirements_analyzer")
    
    # Build and return the graph
    return builder.build()

# Create the graph instance
requirements_graph = build_requirements_analyzer_graph()


@app.entrypoint
def automotive_requirements_analyzer(payload):
    """
    Multi-step automotive requirements analyzer using agent graph with consistency check and conditional UAT generation.
    """
    requirements_docs = payload.get("requirements_docs", "")
    if not requirements_docs:
        return {"error": "No requirements documents provided"}
    
    print(f"Analyzing requirements documents: {requirements_docs[:100]}...")
    
    # Create the analysis prompt
    analysis_prompt = f"""Analyze these automotive requirements documents for consistency, completeness, and quality issues:

{requirements_docs}

Use the check_for_incomplete_requirements tool to analyze the requirements and provide a comprehensive report on any issues found."""
    
    # Execute the multi-agent graph
    try:
        graph_result = requirements_graph(analysis_prompt)
        
        print(f"Graph execution completed. Nodes executed: {graph_result.completed_nodes}/{graph_result.total_nodes}")
        print(f"Execution order: {[node.node_id for node in graph_result.execution_order]}")
        
        # Build the response structure
        result = {
            "execution_time_ms": graph_result.execution_time,
            "step1_requirements_analysis": {
                "analysis": graph_result.results.get("requirements_analyzer", {}).result if graph_result.results.get("requirements_analyzer") else "No requirements analysis performed",
                "issues": "See analysis above for detailed issue information"
            }
        }
        
        # User acceptance tests are always generated
        if "uat_generator" in graph_result.results:
            result["step2_user_acceptance_tests"] = {
                "generated": True,
                "tests": graph_result.results["uat_generator"].result
            }
            print("User acceptance tests generated successfully.")
        else:
            result["step2_user_acceptance_tests"] = {
                "generated": False,
                "reason": "User acceptance test generation failed unexpectedly."
            }
            print("User acceptance test generation failed.")
        
        # Return the final result from the graph
        return result
        
    except Exception as e:
        print(f"Error during graph execution: {e}")
        print("Full stack trace:")
        traceback.print_exc()
        return {
            "error": f"Graph execution failed: {str(e)}",
            "step1_requirements_analysis": {"analysis": "Analysis failed", "issues": []},
            "step2_user_acceptance_tests": {"generated": False, "reason": "Graph execution failed"}
        }

if __name__ == "__main__":
    app.run()