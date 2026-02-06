#!/usr/bin/env python3
"""
Fleet Safety Validation Agent - AgentCore Runtime Version

CHANGES FROM ECS VERSION:
1. Uses BedrockAgentCoreApp instead of FastAPI
2. @app.entrypoint decorator instead of @app.post("/invocations")
3. Direct dict payload instead of HTTP request parsing
4. Uses REAL GenAI with Strands Agent (NO hardcoded data)
5. Handles exact Phase 4-5 output format + ALL previous agent results (behavioral, intelligence, fleet)
"""

import os
import json
import logging
import asyncio
from datetime import datetime
from typing import Dict, Any, Optional
from dataclasses import dataclass

# Heavy imports moved to lazy initialization to avoid 30s timeout
from bedrock_agentcore.runtime import BedrockAgentCoreApp

# S3 Vectors tools import moved to lazy initialization to avoid 30s timeout

# Configure logging
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)

# AgentCore Application
app = BedrockAgentCoreApp()

@dataclass
class AnomalyDetectionResult:
    """Structured result from anomaly detection analysis"""
    anomaly_findings: Dict[str, Any]
    statistical_outliers: Dict[str, Any]
    pattern_deviations: Dict[str, Any]
    anomaly_classification: Dict[str, Any]
    anomaly_recommendations: Dict[str, Any]

# Global agent - initialized on startup
anomaly_detection_agent: Optional["Agent"] = None

def initialize_anomaly_detection_agent():
    """Initialize the Strands agent for anomaly detection analysis"""
    global anomaly_detection_agent

    system_prompt = """You are Fleet's expert Anomaly Detection Agent in the HIL (Hardware-in-the-Loop) multi-agent system, specifically designed to DISCOVER HIGH-VALUE EDGE CASES and unusual patterns that traditional rule-based systems miss. Your mission is to be SENSITIVE to detecting anomalies rather than proving scenes are normal.

CRITICAL BUSINESS OBJECTIVE: The customer pays significant DTO costs for data transfer and wants to identify scenarios like "a pedestrian hesitating at a crosswalk in an unusual way" that doesn't trigger existing rules but represents potential edge cases for model training. Your job is to find reasons WHY scenes might be valuable, not to dismiss them as normal.

## ANOMALY-FOCUSED DETECTION APPROACH:

**Smart Anomaly Detection**: Focus on unusual patterns that rule-based systems would miss, but distinguish between normal driving variations vs genuinely unusual scenarios that could challenge ML models.

**Intelligent HIL Value Assessment**: Your core mission is intelligent cost-benefit analysis for HIL testing investment. Consider these business principles:

**Business Objective**: Identify scenarios where HIL testing investment will yield the highest ROI for autonomous driving model improvement. Balance discovery sensitivity with resource optimization.

**Key Decision Factors** (use your intelligence to weigh these):
- **Training Value**: Could this scenario help improve model capabilities in ways current training data cannot?
- **Performance Signals**: Are there indicators this scenario challenges the current system?
- **Rarity vs Impact**: Common scenarios may still have high value if they reveal systematic issues
- **Cost of Missing vs Cost of Testing**: What's the business risk of not capturing this edge case?

**Scoring Philosophy**:
- **0.0-0.2**: Routine scenarios well-covered by existing training - resource allocation elsewhere is more valuable
- **0.2-0.4**: Moderate training value - scenarios with some unique characteristics worth considering
- **0.4-0.7**: High training value - clear gaps or challenges that HIL testing could address
- **0.7-1.0**: Critical scenarios - rare, high-impact situations requiring immediate attention

**Your Intelligence**: Use your reasoning to assess the holistic value of each scenario. Don't follow rigid rules - make intelligent judgments about training gaps, business value, and resource allocation.

**HIL-Focused Capabilities**:
- **Cross-Scene Anomaly Patterns**: You can compare anomaly patterns across similar scenes using S3 Vectors similarity data
- **Statistical Baseline Comparison**: You establish what's "normal" vs "anomalous" based on fleet-wide data patterns
- **Training Data Prioritization**: You focus on anomalies that provide maximum value for autonomous driving model training
- **Cost-Optimization Focus**: You identify which unusual scenarios justify HIL testing investment

## CRITICAL: Use Statistical Tools Instead of Qualitative Reasoning

You have access to fleet-wide statistical baseline tools that provide QUANTITATIVE anomaly detection:

**MANDATORY TOOL USAGE**:
1. **query_fleet_statistics_tool**: Use this FIRST to get statistical baselines from available fleet scenes
   - Provides percentiles, means, and distributions for risk scores, safety scores, environments
   - Enables quantitative comparison: "This scene's risk score is in the 95th percentile"
   - Returns statistical context: fleet size, distributions, anomaly assessments

2. **detect_statistical_anomaly_tool**: Use this to get vector-based anomaly scores
   - Provides statistical anomaly score based on embedding similarity to fleet
   - Returns anomaly severity (0.0-1.0) based on distance to nearest neighbors
   - Gives quantitative reasoning: "Closest fleet match has 0.72 similarity"

**Replace qualitative reasoning with statistical facts**:
- OLD: "This seems like unusual pedestrian behavior"
- NEW: "Pedestrian behavior deviates from 87% of fleet scenes (95th percentile risk)"
- OLD: "Lane positioning appears problematic"
- NEW: "Lane positioning quality 0.45 is below fleet mean of 0.78 (25th percentile)"

**Always call these tools with the scene's embeddings_data before making anomaly assessments.**

## Your HIL Anomaly Detection Framework:

When analyzing the Scene Understanding agent results, you MUST provide comprehensive anomaly analysis with:

1. **Anomaly Findings**: Detailed anomaly identification
   - unusual_patterns: Behavioral or environmental patterns that deviate from norms
   - statistical_outliers: Quantified deviations from fleet-wide baselines
   - edge_case_elements: Rare or complex scenario components
   - anomaly_severity: Scoring of how unusual each anomaly is (0.0-1.0)

2. **Statistical Outliers**: Quantitative anomaly analysis
   - behavioral_deviations: Driving behaviors significantly different from fleet averages
   - environmental_anomalies: Weather, lighting, or road conditions that are unusual
   - interaction_outliers: Unusual vehicle-to-vehicle or vehicle-to-pedestrian interactions
   - complexity_outliers: Scenarios with unusually high complexity scores

3. **Pattern Deviations**: Comparative pattern analysis
   - fleet_baseline_comparison: How this scene compares to similar scenes in the fleet
   - expected_vs_actual: Differences between expected and observed patterns
   - cross_scene_anomaly_patterns: Anomaly patterns identified across multiple scenes
   - deviation_significance: Statistical significance of identified deviations

4. **Anomaly Classification**: HIL testing prioritization with BIAS TOWARD DISCOVERY
   - anomaly_type: Classification of anomaly (behavioral, environmental, interaction, complexity)
   - hil_testing_value: DEFAULT to "Medium" or higher unless truly routine - err on side of inclusion
   - investment_priority: Consider customer DTO costs - extracting potentially valuable data is cheaper than missing edge cases
   - training_gap_addressed: ANY scenario that could improve model robustness has value

5. **Anomaly Recommendations**: HIL testing recommendations with DISCOVERY FOCUS
   - hil_testing_priority: Be generous - scenarios with 0.1+ anomaly scores deserve consideration
   - recommended_testing_scenarios: Always suggest complementary scenarios to expand edge case coverage
   - data_augmentation_suggestions: Focus on extracting maximum training value from unusual patterns
   - cost_benefit_analysis: Factor in the cost of MISSING an edge case vs extracting potentially valuable data

## Intelligent HIL Assessment Principles:

- **Value-First Reasoning**: Focus on business value and training ROI rather than following rigid criteria
- **Pattern Recognition**: Use your intelligence to identify novel patterns that could improve model robustness
- **Systematic vs Isolated**: Consider whether issues represent systematic gaps or isolated edge cases
- **Performance Context**: Weigh scenario characteristics against actual system performance indicators
- **Resource Optimization**: Balance the cost of testing versus the potential value of missing edge cases
- **Holistic Assessment**: Combine multiple factors intelligently rather than using checklist-based scoring

**Sequential HIL Workflow**:
- **Build on Scene Understanding**: Use the comprehensive scene analysis from the Scene Understanding agent as your foundation
- **Statistical Comparison**: Compare scene characteristics against fleet-wide baselines to identify outliers
- **Training Value Focus**: Assess which anomalies would provide maximum value for autonomous driving model training
- **Cost-Benefit Analysis**: Evaluate the ROI of HIL testing investment for each identified anomaly
- **Pattern Recognition Support**: Provide anomaly insights that enable the Similarity Search agent to find related high-value scenarios

## Available Analysis Tools:

You have access to the `http_request` tool to fetch real-time fleet data and statistical baselines:

**Fleet Behavior Baselines:**
- Autonomous Vehicle Performance Data: https://www.nhtsa.gov/research-data/research-testing-databases/
- SAE Automation Levels: https://www.sae.org/blog/sae-j3016-update

**Statistical Analysis Resources:**
- Traffic Pattern Analysis: https://www.fhwa.dot.gov/policyinformation/statistics/2023/
- Behavioral Analytics: https://www.iihs.org/topics/advanced-driver-assistance

Example usage: `http_request(url="https://www.nhtsa.gov/research-data/research-testing-databases/", method="GET")`

## Output Format:

CRITICAL: You MUST provide meaningful, detailed analysis for ALL fields. DO NOT return empty objects {} or placeholder text "...". Every field must contain substantial, specific analysis based on the scene data provided.

CRITICAL: Return a structured response object (NOT a JSON string) with these exact fields populated based on your anomaly detection analysis:

Required response structure - return the actual object with these fields:
- anomaly_findings: dict containing unusual_patterns, statistical_outliers, edge_case_elements, anomaly_severity (float 0.0-1.0)
- statistical_outliers: dict containing behavioral_deviations, environmental_anomalies, interaction_outliers, complexity_outliers
- pattern_deviations: dict containing fleet_baseline_comparison, expected_vs_actual, cross_scene_anomaly_patterns, deviation_significance (float 0.0-1.0)
- anomaly_classification: dict containing anomaly_type, hil_testing_value, investment_priority, training_gap_addressed
- anomaly_recommendations: dict containing hil_testing_priority, recommended_testing_scenarios, data_augmentation_suggestions, cost_benefit_analysis

IMPORTANT: Do NOT wrap your response in JSON markdown blocks or return it as a string. Return the structured object directly with complete analysis for each field.
    "recommended_testing_scenarios": "[REQUIRED: Additional specific scenarios that complement this anomaly for comprehensive testing.]",
    "data_augmentation_suggestions": "[REQUIRED: Specific methods to expand training data around this anomaly pattern.]",
    "cost_benefit_analysis": "[REQUIRED: Detailed ROI assessment showing expected value from HIL testing this scenario.]"
  }
}

## ENFORCEMENT RULES:
1. NO EMPTY OBJECTS: Every object must contain meaningful key-value pairs
2. NO PLACEHOLDER TEXT: Replace all "..." with actual analysis
3. SPECIFIC METRICS: Include quantitative data wherever possible
4. SCENE-SPECIFIC: All analysis must relate directly to the provided scene data
5. BUSINESS VALUE: Focus on HIL testing value and training data optimization
6. COMPLETE ANALYSIS: Each field must contain substantive analysis, not generic statements

IF YOU CANNOT PERFORM MEANINGFUL ANOMALY ANALYSIS DUE TO INSUFFICIENT DATA, you must state this explicitly in each field rather than returning empty content, but you must still attempt analysis based on whatever scene understanding data is available.

WARNING: CRITICAL: ANTI-HALLUCINATION PROTOCOL WARNING
- ONLY use provided scene data and previous agent results
- NO fabricated URLs, internal references, or statistics
- Use S3 Vectors tool results for statistical claims
- Ground all analysis in actual behavioral metrics"""

    try:
        # Import heavy dependencies at runtime to avoid 30s init timeout
        import boto3
        from strands import Agent
        from strands_tools import http_request
        from .s3_vectors_tools import (
            query_fleet_statistics_tool,
            detect_statistical_anomaly_tool
        )

        anomaly_detection_agent = Agent(
            name="anomaly_detector",
            system_prompt=system_prompt,
            model="us.anthropic.claude-sonnet-4-20250514-v1:0",
            tools=[
                http_request,
                query_fleet_statistics_tool,
                detect_statistical_anomaly_tool
            ]
        )
        logger.info("Anomaly Detection agent initialized successfully")
        return True
    except Exception as e:
        logger.error(f"Failed to initialize Anomaly Detection agent: {str(e)}")
        return False

# Agent will be initialized lazily on first invoke (30s timeout fix)

@app.entrypoint
def invoke(payload: Dict[str, Any]) -> Dict[str, Any]:
    """
    Main AgentCore entrypoint - performs safety validation using real GenAI
    """
    global anomaly_detection_agent  # Access the global variable

    try:
        # --- LAZY INITIALIZATION FIX ---
        if anomaly_detection_agent is None:
            logger.info("Agent not initialized. Initializing now (Lazy Loading)...")
            success = initialize_anomaly_detection_agent()
            if not success:
                raise RuntimeError("Failed to lazily initialize Anomaly Detection agent")
        # -------------------------------

        # Extract payload data (dict instead of typed model)
        scene_id = payload.get("scene_id", "unknown")
        task_context = payload.get("task_context", "context_aware_worker")
        embeddings_data = payload.get("embeddings_data", [])
        behavioral_metrics = payload.get("behavioral_metrics", {})
        behavioral_analysis = payload.get("behavioral_analysis", {})
        intelligence_analysis = payload.get("intelligence_analysis", {})
        fleet_optimization = payload.get("fleet_optimization", {})
        timestamp = payload.get("timestamp", datetime.utcnow().isoformat())

        logger.info(f"Starting safety validation for {scene_id} (context: {task_context})")

        # Prepare safety validation context for GenAI
        validation_context = prepare_safety_context(payload)

        # Perform anomaly detection analysis using Strands agent (REAL GenAI)
        validation_result = asyncio.run(perform_anomaly_detection_analysis(validation_context))

        # Return dict response (same format as before for Phase 6 compatibility)
        response = {
            "scene_id": scene_id,
            "agent_type": "anomaly_detection",
            "status": "success",
            "analysis": {
                "anomaly_findings": validation_result.anomaly_findings,
                "statistical_outliers": validation_result.statistical_outliers,
                "pattern_deviations": validation_result.pattern_deviations,
                "anomaly_classification": validation_result.anomaly_classification,
                "anomaly_recommendations": validation_result.anomaly_recommendations,
                "analysis_timestamp": timestamp
            },
            "metadata": {
                "validation_timestamp": datetime.utcnow().isoformat(),
                "agent_version": "1.0.0",
                "model_used": "us.anthropic.claude-sonnet-4-20250514-v1:0",
                "behavioral_analysis_consumed": bool(behavioral_analysis),
                "intelligence_analysis_consumed": bool(intelligence_analysis),
                "fleet_optimization_consumed": bool(fleet_optimization),
                "deployment_type": "agentcore_runtime"
            }
        }

        logger.info(f"Safety validation completed for {scene_id}")
        return response

    except Exception as e:
        logger.error(f"Safety validation failed for {scene_id}: {str(e)}")
        return {
            "scene_id": payload.get("scene_id", "unknown"),
            "agent_type": "safety_validation",
            "status": "error",
            "error": f"Safety validation failed: {str(e)}",
            "analysis": {},
            "metadata": {
                "error_timestamp": datetime.utcnow().isoformat(),
                "agent_version": "1.0.0",
                "deployment_type": "agentcore_runtime"
            }
        }

def prepare_safety_context(payload: Dict[str, Any]) -> str:
    """Prepare safety validation context for GenAI with Enhanced Phase 6 multi-cycle support"""
    scene_id = payload.get("scene_id", "unknown")
    task_context = payload.get("task_context", "context_aware_worker")
    embeddings_data = payload.get("embeddings_data", [])
    behavioral_metrics = payload.get("behavioral_metrics", {})
    behavioral_analysis = payload.get("behavioral_analysis", {})
    intelligence_analysis = payload.get("intelligence_analysis", {})
    fleet_optimization = payload.get("fleet_optimization", {})

    # Extract previous agent results for agent-to-agent communication
    previous_agent_results = payload.get("previous_agent_results", {})

    # Handle both possible agent type names for scene understanding results
    scene_understanding = (previous_agent_results.get("scene_understanding", {}) or
                          previous_agent_results.get("behavioral_gap_analysis", {}))

    # Build scene understanding context for safety analysis
    scene_understanding_context = ""
    if scene_understanding:
        analysis = scene_understanding.get("analysis", {})
        insights = scene_understanding.get("insights", [])
        recommendations = scene_understanding.get("recommendations", [])

        scene_understanding_context += "\n**SCENE UNDERSTANDING ANALYSIS:**\n"
        if isinstance(analysis, str):
            # Handle malformed JSON string from agent response
            scene_understanding_context += f"{analysis}\n"
        else:
            scene_understanding_context += f"{json.dumps(analysis, indent=2)}\n"

        if insights:
            scene_understanding_context += f"**Key Insights:** {insights}\n"
        if recommendations:
            scene_understanding_context += f"**Recommendations:** {recommendations}\n"

    # Extract formatted behavioral metrics from orchestrator
    key_behavioral_metrics = payload.get("key_behavioral_metrics", {})
    metrics_summary = key_behavioral_metrics.get("metrics_summary", "No behavioral metrics available")
    detailed_metrics = key_behavioral_metrics.get("detailed_metrics", {})

    # Enhanced Phase 6: New multi-cycle context fields
    cross_scene_intelligence = payload.get("cross_scene_intelligence", {})
    iterative_context = payload.get("iterative_context", {})

    # Extract Anomaly Context (Essential for Discovery Mode)
    anomaly_context = payload.get("anomaly_context", {})
    is_anomaly = anomaly_context.get("is_anomaly", False)
    anomaly_score = anomaly_context.get("anomaly_score", 0.0)
    anomaly_reason = anomaly_context.get("reason", "No anomaly data available")

    # Enhanced Phase 6: Multi-cycle context processing
    is_iterative_mode = bool(iterative_context)
    current_cycle = iterative_context.get('current_cycle', 1) if is_iterative_mode else 1
    max_cycles = iterative_context.get('max_cycles', 1) if is_iterative_mode else 1
    workflow_params = iterative_context.get('workflow_params', {}) if is_iterative_mode else {}

    # Cross-scene intelligence processing
    similar_scenes = cross_scene_intelligence.get('similar_scenes', [])
    pattern_insights = cross_scene_intelligence.get('pattern_insights', [])
    cross_scene_context = cross_scene_intelligence.get('cycle_context', '')

    # Extract behavioral analysis results
    behavioral_patterns = behavioral_analysis.get("behavioral_patterns", {})
    identified_gaps = behavioral_analysis.get("identified_gaps", {})
    behavioral_risk_assessment = behavioral_analysis.get("risk_assessment", {})
    behavioral_recommendations = behavioral_analysis.get("recommendations", {})

    # Extract intelligence research results
    regulatory_context = intelligence_analysis.get("regulatory_context", {})
    compliance_status = regulatory_context.get("compliance_status", "unknown")
    applicable_regulations = regulatory_context.get("applicable_regulations", [])
    safety_requirements = regulatory_context.get("safety_requirements", [])

    # Extract fleet optimization results
    optimization_strategies = fleet_optimization.get("optimization_strategies", {})
    performance_metrics = fleet_optimization.get("performance_metrics", {})
    implementation_plan = fleet_optimization.get("implementation_plan", {})

    context = f"""## Enhanced Phase 6 Safety Validation Request - Final Agent

## PREVIOUS AGENT ANALYSIS RESULTS:
{scene_understanding_context if scene_understanding_context else "No scene understanding analysis available from previous agent."}

**Scene ID**: {scene_id}
**Task Context**: {task_context}
**Analysis Mode**: {'Iterative Multi-Cycle Safety Validation' if is_iterative_mode else 'Standard Safety Validation'}
**Current Cycle**: {current_cycle} of {max_cycles}
**Analysis Type**: Comprehensive safety validation using ALL previous agent results

## ANOMALY DETECTION VALIDATION:
**ANOMALY STATUS**: {"ANOMALY DETECTED - REQUIRES SAFETY VALIDATION" if is_anomaly else "NORMAL SCENE - STANDARD VALIDATION"}
**Anomaly Score**: {anomaly_score:.3f} (0.0=normal, 1.0=highly anomalous)
**Detection Reason**: {anomaly_reason}
**Safety Validation Priority**: {"CRITICAL - Anomalous behavior requires thorough safety analysis" if is_anomaly else "Standard - routine safety validation"}

**Your Safety Validation Task**: {'Explicitly validate why this anomalous scene is safe or unsafe for autonomous driving. Focus on whether the detected anomaly represents a safety risk or acceptable operational variation.' if is_anomaly else 'Validate safety compliance based on standard behavioral analysis.'}

## Behavioral Analysis Results:
### Behavioral Patterns:
{json.dumps(behavioral_patterns, indent=2)}

### Identified Performance Gaps:
{json.dumps(identified_gaps, indent=2)}

### Behavioral Risk Assessment:
{json.dumps(behavioral_risk_assessment, indent=2)}

### Behavioral Recommendations:
{json.dumps(behavioral_recommendations, indent=2)}

## Intelligence Research Results:
### Regulatory Context:
- Compliance Status: {compliance_status}
- Applicable Regulations: {applicable_regulations}
- Safety Requirements: {safety_requirements}

### Full Regulatory Context:
{json.dumps(regulatory_context, indent=2)}

## Fleet Optimization Results:
### Optimization Strategies:
{json.dumps(optimization_strategies, indent=2)}

### Performance Metrics:
{json.dumps(performance_metrics, indent=2)}

### Implementation Plan:
{json.dumps(implementation_plan, indent=2)}

## Phase 4-5 Behavioral Metrics:
{json.dumps(behavioral_metrics, indent=2)}

## KEY QUANTIFIED METRICS (VALIDATED):
{json.dumps(key_behavioral_metrics, indent=2)}

## CRITICAL ANALYSIS REQUIREMENTS:
{metrics_summary}

## Enhanced Phase 6: Cross-Scene Safety Intelligence
{f'''
**Similar Scenes Found**: {len(similar_scenes)}
**Cross-Scene Context**: {cross_scene_context}

**Fleet Safety Pattern Insights**:
{json.dumps(pattern_insights[:5], indent=2) if pattern_insights else "None available"}

**Similar Scene Safety Context** (Top 3):
{json.dumps(similar_scenes[:3], indent=2) if similar_scenes else "None available"}
''' if is_iterative_mode and (similar_scenes or pattern_insights) else 'Cross-scene intelligence not available for this cycle.'}

## Enhanced Phase 6: Iterative Safety Context
{f'''
**Business Objective**: {workflow_params.get('business_objective_canonical', 'Standard safety validation')}
**Workflow Priority**: {workflow_params.get('workflow_priority', 'standard')}
**Target Metrics**: {workflow_params.get('target_metrics', [])}
**Required Safety Focus**: {workflow_params.get('required_analysis', [])}

**Previous Cycles Summary**:
{json.dumps(iterative_context.get('previous_cycles_summary', {}), indent=2)}
''' if is_iterative_mode else 'Single-pass validation mode - no iterative context.'}

## Your HIL Anomaly Detection Task:
As the HIL Anomaly Detection Agent, analyze the Scene Understanding results and identify statistical outliers, pattern deviations, and unusual behaviors for cost-optimized HIL testing:

1. **Anomaly Findings**: Identify unusual behavioral or environmental patterns that deviate from fleet norms
2. **Statistical Outliers**: Detect quantified deviations from fleet-wide baselines with specific metrics
3. **Pattern Deviations**: Compare this scene against fleet baselines to identify significant deviations
4. **Anomaly Classification**: Classify anomalies by type, HIL testing value, and investment priority
5. **Anomaly Recommendations**: Provide HIL testing recommendations and cost-benefit analysis

## HIL Anomaly Detection Requirements:
- Focus on cost-optimized HIL data discovery by flagging high-value anomalous scenarios
- Identify behavioral patterns, edge cases, and statistical outliers that indicate training value
- Assess training data gaps that each anomaly could help address
- Prioritize scenarios based on HIL testing ROI and autonomous driving model improvement potential
- Structure response as comprehensive JSON matching the EXACT expected anomaly detection format

## Expected Output Fields (CRITICAL - Use EXACT field names):
- anomaly_findings: Dict with unusual_patterns, statistical_outliers, edge_case_elements, anomaly_severity
- statistical_outliers: Dict with behavioral_deviations, environmental_anomalies, interaction_outliers, complexity_outliers
- pattern_deviations: Dict with fleet_baseline_comparison, expected_vs_actual, cross_scene_anomaly_patterns, deviation_significance
- anomaly_classification: Dict with anomaly_type, hil_testing_value, investment_priority, training_gap_addressed
- anomaly_recommendations: Dict with hil_testing_priority, recommended_testing_scenarios, data_augmentation_suggestions, cost_benefit_analysis

Please perform comprehensive safety validation and return detailed results in JSON format."""

    return context

async def perform_anomaly_detection_analysis(validation_context: str) -> AnomalyDetectionResult:
    """
    Perform safety validation using Strands agent (REAL GenAI - NO hardcoded data)
    """
    try:
        # Use the Strands agent to perform validation
        agent_response = await anomaly_detection_agent.invoke_async(validation_context)

        # Extract the response text - handle both dict and object formats
        if hasattr(agent_response, 'message') and hasattr(agent_response.message, 'content'):
            # Object format
            response_text = str(agent_response.message.content[0].text)
        elif hasattr(agent_response, 'message'):
            # Dictionary format - message is dict
            response_text = str(agent_response.message['content'][0]['text'])
        else:
            # Full dictionary format
            response_text = str(agent_response['message']['content'][0]['text'])

        # Parse structured response from agent
        parsed_result = parse_anomaly_response(response_text)

        return parsed_result

    except Exception as e:
        logger.error(f"Anomaly detection analysis failed: {str(e)}")
        # Return fallback result (still no hardcoded analysis data)
        return AnomalyDetectionResult(
            anomaly_findings={"error": f"Analysis failed: {str(e)}"},
            statistical_outliers={"error": f"Analysis failed: {str(e)}"},
            pattern_deviations={"error": f"Analysis failed: {str(e)}"},
            anomaly_classification={"error": f"Analysis failed: {str(e)}"},
            anomaly_recommendations={"error": f"Analysis failed: {str(e)}"}
        )

def parse_anomaly_response(response_text: str) -> AnomalyDetectionResult:
    """Parse agent response into structured anomaly detection result with robust markdown handling"""
    import ast
    import re

    def extract_and_clean_json(text: str) -> str:
        """Extract JSON from text and clean markdown formatting"""
        # First, try to find markdown-wrapped JSON
        if "```json" in text and "```" in text:
            json_start = text.find("```json") + 7
            json_end = text.find("```", json_start)
            if json_end != -1:
                json_content = text[json_start:json_end].strip()
                logger.info("Anomaly Agent: Extracted JSON from markdown wrapper")
                return json_content

        # Fallback: extract JSON by finding first { to last }
        if '{' in text and '}' in text:
            json_start = text.find('{')
            json_end = text.rfind('}') + 1
            json_content = text[json_start:json_end]
            logger.info("Anomaly Agent: Extracted JSON using bracket matching")
            return json_content

        return text

    def fix_escaped_json(json_str: str) -> str:
        """Fix common JSON escaping issues"""
        # Handle escaped newlines and quotes that might break JSON parsing
        json_str = json_str.replace('\\n', '\n')
        json_str = json_str.replace('\\"', '"')
        json_str = json_str.replace('\\\\', '\\')
        return json_str

    try:
        # Step 1: Extract and clean JSON content
        json_content = extract_and_clean_json(response_text)

        # Step 2: Fix common escaping issues
        json_content = fix_escaped_json(json_content)

        # Step 3: Try multiple parsing strategies
        parsed_json = None

        # Try JSON parsing first
        try:
            parsed_json = json.loads(json_content)
            logger.info("Anomaly Agent: Successfully parsed JSON response")
        except json.JSONDecodeError:
            # Try Python literal evaluation for dict strings with single quotes
            try:
                parsed_json = ast.literal_eval(json_content)
                logger.info("Anomaly Agent: Successfully parsed using ast.literal_eval")
            except (ValueError, SyntaxError):
                # Try fixing common quote issues
                try:
                    fixed_json = json_content.replace("'", '"')
                    parsed_json = json.loads(fixed_json)
                    logger.info("Anomaly Agent: Successfully parsed after quote fixing")
                except json.JSONDecodeError:
                    # Try regex extraction as last resort
                    json_pattern = r'\{.*\}'
                    matches = re.findall(json_pattern, response_text, re.DOTALL)
                    if matches:
                        longest_match = max(matches, key=len)
                        parsed_json = json.loads(longest_match)
                        logger.info("Anomaly Agent: Successfully parsed using regex fallback")

        if parsed_json:
            return AnomalyDetectionResult(
                anomaly_findings=parsed_json.get('anomaly_findings', {}),
                statistical_outliers=parsed_json.get('statistical_outliers', {}),
                pattern_deviations=parsed_json.get('pattern_deviations', {}),
                anomaly_classification=parsed_json.get('anomaly_classification', {}),
                anomaly_recommendations=parsed_json.get('anomaly_recommendations', {})
            )

    except Exception as e:
        logger.error(f"Anomaly Agent: Unexpected error during JSON parsing: {str(e)}")

    # Final fallback: create result from text response
    logger.warning("Anomaly Agent: Using error fallback due to parsing failure")
    return AnomalyDetectionResult(
        anomaly_findings={"error": "parsing_failed", "raw": response_text[:200]},
        statistical_outliers={},
        pattern_deviations={},
        anomaly_classification={},
        anomaly_recommendations={}
    )

if __name__ == "__main__":
    logger.info("Starting Anomaly Detection Agent with AgentCore Runtime")
    app.run()