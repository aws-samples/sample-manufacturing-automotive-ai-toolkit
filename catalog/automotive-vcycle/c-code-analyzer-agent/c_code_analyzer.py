from strands import Agent, tool
from strands.models import BedrockModel
from strands.multiagent import GraphBuilder
from bedrock_agentcore.runtime import BedrockAgentCoreApp
import json
import re
from datetime import datetime

app = BedrockAgentCoreApp()

# Automotive coding standards compliance analyzer tool
@tool
def verify_automotive_coding_compliance(c_code: str) -> dict:
    """
    Analyze C code for custom automotive coding standards compliance.
    Returns a dictionary with violation severity and details.
    """
    violations = []
    severity_level = "LOW"
    
    # Custom automotive coding rules (safety-focused)
    automotive_rules = {
        "AUTO-SAFE-001": {
            "pattern": r"extern\s+\w+\s+\w+\s*\(",
            "description": "External function declarations must be visible at definition point for safety traceability",
            "severity": "MEDIUM"
        },
        "AUTO-MEM-001": {
            "pattern": r"\bmalloc\b|\bcalloc\b|\brealloc\b|\bfree\b",
            "description": "Dynamic memory allocation is prohibited in safety-critical automotive systems",
            "severity": "HIGH"
        },
        "AUTO-FUNC-001": {
            "pattern": r"^\s*\w+\s*\([^)]*\)\s*;",
            "description": "Function return values must be checked for error handling in automotive systems",
            "severity": "MEDIUM"
        },
        "AUTO-STYLE-001": {
            "pattern": r"//.*",
            "description": "Use C-style comments for better compiler compatibility across automotive toolchains",
            "severity": "LOW"
        }
    }
    
    for rule_id, rule_info in automotive_rules.items():
        matches = re.findall(rule_info["pattern"], c_code, re.MULTILINE)
        if matches:
            violations.append({
                "rule": rule_id,
                "description": rule_info["description"],
                "severity": rule_info["severity"],
                "occurrences": len(matches)
            })
            
            # Update overall severity
            if rule_info["severity"] == "HIGH":
                severity_level = "HIGH"
            elif rule_info["severity"] == "MEDIUM" and severity_level != "HIGH":
                severity_level = "MEDIUM"
    
    return {
        "overall_severity": severity_level,
        "violations": violations,
        "total_violations": len(violations),
        "compliant": len(violations) == 0
    }

# Create the model for all agents
model_id = "us.amazon.nova-2-lite-v1:0" #"us.anthropic.claude-haiku-4-5-20251001-v1:0" #"us.anthropic.claude-sonnet-4-5-20250929-v1:0"
model = BedrockModel(model_id=model_id)

# Create the automotive coding standards analyzer agent
automotive_analyzer_agent = Agent(
    name="automotive_analyzer",
    model=model,
    tools=[verify_automotive_coding_compliance],
    system_prompt="""You are an automotive coding standards analyzer for safety-critical software. Your job is to:
1. Analyze C code for custom automotive coding standards violations (AUTO-SAFE-001, AUTO-MEM-001, AUTO-FUNC-001, AUTO-STYLE-001)
2. Identify the severity of violations (LOW, MEDIUM, HIGH)
3. Provide detailed explanations of violations found
4. Pass your analysis results to the next stage in the workflow

IMPORTANT: Always use the verify_automotive_coding_compliance tool to analyze the code first, then provide your analysis.

In your response, clearly state:
- Overall Severity: [LOW/MEDIUM/HIGH]
- Compliance Status: [COMPLIANT/NON-COMPLIANT]
- Whether the code is suitable for unit test generation

Focus on automotive safety standards and provide clear, actionable feedback."""
)

# Create the unit test generator agent
unit_test_agent = Agent(
    name="unit_test_generator",
    model=model,
    #tools=[generate_unit_tests],
    system_prompt="""You are a unit test generator for C code in automotive applications. Your job is to:
1. Generate comprehensive unit tests for C functions
2. Include edge cases and boundary conditions
3. Follow automotive testing standards
4. Create tests that are suitable for safety-critical applications

Generate clean, well-documented test code that can be easily integrated into a test framework."""
)

# Define condition function to check if unit tests should be generated
def should_generate_tests(state):
    """
    Condition function to determine if unit tests should be generated
    based on automotive coding standards analysis results.
    """
    automotive_result = state.results.get("automotive_analyzer")
    if not automotive_result:
        print("DEBUG: No automotive analyzer result found")
        return False
    
    # Extract the analysis result from the agent's response
    # The automotive_result is an AgentResult object, we need to access its .result attribute
    if hasattr(automotive_result, 'result'):
        result_text = str(automotive_result.result).lower()
    else:
        result_text = str(automotive_result).lower()

    
    # Simple approach: Look for HIGH severity violations that should block unit test generation
    # Everything else (LOW, MEDIUM, or COMPLIANT) should allow unit test generation
    
    # Definitive blocking patterns (HIGH severity)
    blocking_patterns = [
        "overall severity**: high",
        "overall severity: high", 
        "**overall severity**: high",
        "severity: high"
    ]

    
    # Check for blocking patterns
    for pattern in blocking_patterns:
        if pattern in result_text:
            print(f"DEBUG: Found blocking pattern: {pattern}")
            return False
        
    # Default: if no blocking patterns found, allow unit test generation
    print("DEBUG: No blocking patterns found, allowing unit test generation")
    return True

# Build the multi-agent graph
def build_automotive_analyzer_graph():
    """
    Build the automotive C code analyzer graph with conditional workflow.
    """
    builder = GraphBuilder()
    
    # Add nodes to the graph
    builder.add_node(automotive_analyzer_agent, "automotive_analyzer")
    builder.add_node(unit_test_agent, "unit_test_generator")
    
    # Add conditional edge: only generate tests if no severe violations
    builder.add_edge("automotive_analyzer", "unit_test_generator", condition=should_generate_tests)
    
    # Set entry point
    builder.set_entry_point("automotive_analyzer")
    
    # Build and return the graph
    return builder.build()

# Create the graph instance
automotive_graph = build_automotive_analyzer_graph()

@app.entrypoint
def automotive_c_analyzer(payload):
    """
    Multi-step automotive C code analyzer using agent graph with custom coding standards check and conditional unit test generation.
    """
    c_code = payload.get("c_code", "")
    if not c_code:
        return {"error": "No C code provided"}
    
    print(f"Analyzing C code: {c_code[:100]}...")
    
    # Create the analysis prompt
    analysis_prompt = f"""Analyze this automotive C code for custom automotive coding standards violations and provide detailed feedback:

{c_code}

Please use the verify_automotive_coding_compliance tool to analyze the code and provide a comprehensive report on any violations found."""
    
    # Execute the multi-agent graph
    try:
        graph_result = automotive_graph(analysis_prompt)
        
        print(f"Graph execution completed. Nodes executed: {graph_result.completed_nodes}/{graph_result.total_nodes}")
        print(f"Execution order: {[node.node_id for node in graph_result.execution_order]}")
        
        # Build the response structure
        result = {
            "execution_time_ms": graph_result.execution_time,
            "step1_automotive_analysis": {
                "analysis": graph_result.results.get("automotive_analyzer", {}).result if graph_result.results.get("automotive_analyzer") else "No automotive standards analysis performed",
                "violations": "See analysis above for detailed violation information"
            }
        }
        
        # Check if unit tests were generated
        if "unit_test_generator" in graph_result.results:
            result["step2_unit_tests"] = {
                "generated": True,
                "tests": graph_result.results["unit_test_generator"].result
            }
            print("Unit tests generated successfully.")
        else:
            result["step2_unit_tests"] = {
                "generated": False,
                "reason": "Unit test generation was skipped due to severe automotive coding standards violations or analysis failure."
            }
            print("Unit test generation was skipped.")
        
        # Return the final result from the graph (last executed node)
        return result
        
    except Exception as e:
        print(f"Error during graph execution: {e}")
        return {
            "error": f"Graph execution failed: {str(e)}",
            "step1_automotive_analysis": {"analysis": "Analysis failed", "violations": []},
            "step2_unit_tests": {"generated": False, "reason": "Analysis failed"}
        }

if __name__ == "__main__":
    app.run()