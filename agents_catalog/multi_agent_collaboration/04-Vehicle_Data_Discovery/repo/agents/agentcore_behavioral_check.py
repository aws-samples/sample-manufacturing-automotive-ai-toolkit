#!/usr/bin/env python3
"""
Fleet Behavioral Gap Analysis Agent - AgentCore Runtime Version (UNUSED PROTOTYPE)

CHANGES FROM ECS VERSION:
1. Uses BedrockAgentCoreApp instead of FastAPI
2. @app.entrypoint decorator instead of @app.post("/invocations")
3. Direct dict payload instead of HTTP request parsing
4. Uses REAL GenAI with Strands Agent (NO hardcoded data)

NOTE: This file is not integrated into the production pipeline.
Production uses behavioral_gap_analysis_agent.py via AgentCore runtime ARNs.
"""

import os
import json
import logging
import asyncio
import re
from datetime import datetime
from typing import Dict, Any, Optional
from dataclasses import dataclass

import boto3
from strands import Agent
from strands_tools import http_request
from bedrock_agentcore.runtime import BedrockAgentCoreApp

# Configure logging
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)

# AgentCore Application
app = BedrockAgentCoreApp()

@dataclass
class SceneUnderstandingResult:
    """Structured result from scene understanding analysis"""
    scene_analysis: Dict[str, Any]
    scene_characteristics: Dict[str, Any]
    behavioral_insights: Dict[str, Any]
    recommendations: Dict[str, Any]
    confidence_metrics: Dict[str, Any]

# Global agent - initialized on startup
scene_understanding_agent: Optional[Agent] = None

def initialize_scene_understanding_agent():
    """Initialize the Strands agent for scene understanding analysis"""
    global scene_understanding_agent

    system_prompt = """You are Fleet's expert Scene Understanding Agent in the HIL (Hardware-in-the-Loop) multi-agent system, the first agent in a sequential 3-agent topology focused on cost-optimized scenario discovery and HIL training data curation.

Your core mission is to provide comprehensive, detailed analysis of autonomous driving scenes for HIL data discovery and cost-optimized training data curation. You serve as the foundation scene analyzer that enables subsequent agents (Anomaly Detection and Similarity Search) to perform specialized pattern analysis.

## Your HIL Expertise Areas:

**Comprehensive Scene Analysis**: You understand vehicle dynamics, environmental context, traffic patterns, and can decompose complex driving scenarios into detailed behavioral components for HIL testing scenarios.

**Contextual Understanding**: You excel at identifying scene characteristics, environmental conditions, traffic complexity, and interaction patterns that are valuable for HIL scenario selection.

**Risk and Complexity Scoring**: You evaluate scene complexity, safety criticality, and training value to help optimize HIL testing investments.

**Scenario Characterization**: You provide structured scene descriptions that enable other agents to identify patterns, anomalies, and high-value training scenarios.

**HIL-Focused Capabilities**:
- **Scene Decomposition**: Break down complex driving scenarios into analyzable components
- **Environmental Context**: Identify weather, lighting, traffic, and infrastructure factors
- **Interaction Analysis**: Catalog vehicle-to-vehicle, vehicle-to-pedestrian, and vehicle-to-infrastructure interactions
- **Training Value Assessment**: Score scenes for their potential value in HIL testing and model training
- **Cross-Scene Pattern Foundation**: Provide consistent scene descriptions that enable pattern recognition across the fleet

## Your HIL Analysis Framework:

When analyzing scene data with ROS bag information, you MUST provide comprehensive analysis with:

1. **Scene Analysis**: Detailed breakdown of the driving scenario
   - environmental_conditions: Weather, lighting, road conditions
   - traffic_complexity: Vehicle density, pedestrian activity, intersection complexity
   - vehicle_behavior: Ego-vehicle actions, maneuvers, decision points
   - interaction_patterns: How ego-vehicle interacts with other road users
   - infrastructure_context: Road type, signage, traffic control devices

2. **Scene Characteristics**: Structured categorization for HIL scenarios
   - scenario_type: Highway, urban, suburban, parking, etc.
   - complexity_level: Simple, moderate, complex, edge_case
   - safety_criticality: Low, medium, high risk scenarios
   - training_relevance: Value for autonomous driving model training

3. **Behavioral Insights**: Key observations for HIL testing
   - critical_decisions: Important autonomous driving decisions made
   - edge_case_elements: Unusual or rare scenario components
   - performance_indicators: How well the system handled the scenario
   - learning_opportunities: What this scenario could teach an AI system

4. **Recommendations**: HIL-focused suggestions
   - hil_testing_priority: How important this scenario is for HIL testing
   - similar_scenario_needs: What related scenarios should be tested
   - model_training_focus: Specific aspects that need training attention
   - regulatory_considerations: Safety standards or compliance factors

## HIL Analysis Guidelines:

- Focus on scene understanding that enables cost-optimized HIL testing
- Provide detailed, consistent scene descriptions for pattern matching
- Identify unique or valuable scenarios for training data curation
- Score scenes for HIL testing priority and training value
- Enable other agents to perform anomaly detection and similarity search

**Sequential HIL Workflow**:
- **Foundation Role**: You provide the comprehensive scene analysis that feeds into anomaly detection and similarity search
- **Consistency Focus**: Use consistent terminology and categorization to enable cross-scene pattern recognition
- **HIL Optimization**: Emphasize scenario characteristics that impact HIL testing effectiveness
- **Training Data Quality**: Assess scenes for their value in creating high-quality training datasets

## Available Analysis Tools:

You have access to the `http_request` tool to fetch real-time traffic and safety data:

**Traffic Safety Data:**
- NHTSA Crash Data: https://www.nhtsa.gov/research-data/fatality-analysis-reporting-system-fars
- IIHS Safety Research: https://www.iihs.org/topics/autonomous-vehicles

**Best Practices:**
- SAE Automation Levels: https://www.sae.org/news/2019/01/sae-updates-j3016-automated-driving-graphic
- ISO 26262 Functional Safety: https://www.iso.org/standard/68383.html

Example usage: `http_request(url="https://www.nhtsa.gov/research-data/fatality-analysis-reporting-system-fars", method="GET")`

## Output Format:

Always structure your response as comprehensive JSON with all required fields populated based on the scene understanding analysis of the provided scene data. Use this exact structure:

{
  "scene_analysis": {
    "environmental_conditions": "...",
    "traffic_complexity": "...",
    "vehicle_behavior": "...",
    "interaction_patterns": "...",
    "infrastructure_context": "..."
  },
  "scene_characteristics": {
    "scenario_type": "...",
    "complexity_level": "...",
    "safety_criticality": "...",
    "training_relevance": "..."
  },
  "behavioral_insights": {
    "critical_decisions": "...",
    "edge_case_elements": "...",
    "performance_indicators": "...",
    "learning_opportunities": "..."
  },
  "recommendations": {
    "hil_testing_priority": "...",
    "similar_scenario_needs": "...",
    "model_training_focus": "...",
    "regulatory_considerations": "..."
  },
  "confidence_metrics": {
    "overall_confidence": 0.85,
    "analysis_depth": "comprehensive"
  }
}"""

    try:
        scene_understanding_agent = Agent(
            name="scene_understanding_analyzer",
            system_prompt=system_prompt,
            model="us.anthropic.claude-sonnet-4-20250514-v1:0",
            tools=[http_request]
        )
        logger.info("Scene Understanding agent initialized successfully")
        return True
    except Exception as e:
        logger.error(f"Failed to initialize Scene Understanding agent: {str(e)}")
        return False

# Initialize agent on startup
initialize_scene_understanding_agent()

@app.entrypoint
async def invoke(payload: Dict[str, Any]) -> Dict[str, Any]:
    """
    Main AgentCore entrypoint - performs scene understanding analysis using real GenAI
    """
    try:
        # Extract payload data (dict instead of typed model)
        scene_id = payload.get("scene_id", "unknown")
        ros_bag_data = payload.get("ros_bag_data", {})
        processed_data = payload.get("processed_data", {})
        embeddings_data = payload.get("embeddings_data", [])
        behavioral_metrics = payload.get("behavioral_metrics", {})
        timestamp = payload.get("timestamp", datetime.utcnow().isoformat())

        logger.info(f"Starting scene understanding analysis for {scene_id}")

        if not scene_understanding_agent:
            raise Exception("Scene Understanding agent not initialized")

        # Prepare analysis context for GenAI
        analysis_context = prepare_scene_understanding_context(payload)

        # Perform scene understanding analysis using Strands agent (REAL GenAI)
        analysis_result = await perform_scene_understanding_analysis(analysis_context)

        # Return dict response (same format as before for Phase 6 compatibility)
        response = {
            "scene_id": scene_id,
            "agent_type": "scene_understanding",
            "status": "success",
            "analysis": {
                "scene_analysis": analysis_result.scene_analysis,
                "scene_characteristics": analysis_result.scene_characteristics,
                "behavioral_insights": analysis_result.behavioral_insights,
                "recommendations": analysis_result.recommendations,
                "confidence_score": analysis_result.confidence_metrics.get("overall_confidence", 0.85),
                "analysis_timestamp": timestamp
            },
            "metadata": {
                "analysis_timestamp": datetime.utcnow().isoformat(),
                "agent_version": "1.0.0",
                "model_used": "us.anthropic.claude-sonnet-4-20250514-v1:0",
                "deployment_type": "agentcore_runtime"
            }
        }

        logger.info(f"Scene understanding analysis completed for {scene_id}")
        return response

    except Exception as e:
        logger.error(f"Scene understanding analysis failed for {scene_id}: {str(e)}")
        return {
            "scene_id": payload.get("scene_id", "unknown"),
            "agent_type": "scene_understanding",
            "status": "error",
            "error": f"Scene understanding analysis failed: {str(e)}",
            "analysis": {},
            "metadata": {
                "error_timestamp": datetime.utcnow().isoformat(),
                "agent_version": "1.0.0",
                "deployment_type": "agentcore_runtime"
            }
        }

def prepare_scene_understanding_context(payload: Dict[str, Any]) -> str:
    """Prepare scene understanding analysis context for GenAI using HIL-focused format"""
    scene_id = payload.get("scene_id", "unknown")
    task_context = payload.get("task_context", "entry_level_worker")
    embeddings_data = payload.get("embeddings_data", [])
    behavioral_metrics = payload.get("behavioral_metrics", {})
    vector_metadata = payload.get("vector_metadata", {})
    processing_context = payload.get("processing_context", {})
    shared_state = payload.get("shared_state", {})

    # Enhanced Phase 6: New multi-cycle context fields
    cross_scene_intelligence = payload.get("cross_scene_intelligence", {})
    iterative_context = payload.get("iterative_context", {})

    # --- CRITICAL: Extract Anomaly Context (Essential for Discovery Mode) ---
    anomaly_context = payload.get("anomaly_context", {})
    is_anomaly = anomaly_context.get("is_anomaly", False)
    anomaly_score = anomaly_context.get("anomaly_score", 0.0)
    anomaly_reason = anomaly_context.get("reason", "No anomaly data available")
    # -----------------------------------------------------------------------

    # DISCOVERY-BASED FIX: Extract behavioral insights from dense scene descriptions
    # No hardcoded metric field lookups - use dynamic analysis from actual content
    scene_descriptions = [emb.get("text_content", emb.get("text", "")) for emb in embeddings_data if isinstance(emb, dict)]
    behavioral_insights = [desc for desc in scene_descriptions if any(keyword in desc.lower()
                          for keyword in ['driving', 'vehicle', 'lane', 'speed', 'distance', 'braking', 'steering'])]

    # Dynamic complexity analysis from content length and keywords
    total_descriptions = len(scene_descriptions)
    complexity_score = len([desc for desc in scene_descriptions if len(desc) > 100]) / max(total_descriptions, 1)
    safety_score = len([desc for desc in scene_descriptions if any(word in desc.lower()
                       for word in ['safety', 'safe', 'secure'])]) / max(total_descriptions, 1)

    # Define variables to prevent NameErrors in prompt template (Variable Safety)
    vector_similarity = behavioral_metrics.get("vector_similarity_score", 0.0)  # Keep for backward compatibility
    total_vectors = len(embeddings_data)  # Dynamic calculation from actual data
    embedding_types = list(set([emb.get("input_type", "unknown") for emb in embeddings_data if isinstance(emb, dict)]))  # Dynamic extraction

    # Prepare embedding summaries for analysis
    embedding_summaries = []
    for emb in embeddings_data[:5]:  # First 5 for context
        embedding_summaries.append({
            "type": emb.get("input_type", "unknown"),
            "text": emb.get("text", "")[:200] + "..." if len(emb.get("text", "")) > 200 else emb.get("text", ""),
            "vector_length": len(emb.get("vector", []))
        })

    # Enhanced Phase 6: Multi-cycle context processing
    is_iterative_mode = bool(iterative_context)
    current_cycle = iterative_context.get('current_cycle', 1) if is_iterative_mode else 1
    max_cycles = iterative_context.get('max_cycles', 1) if is_iterative_mode else 1
    workflow_params = iterative_context.get('workflow_params', {}) if is_iterative_mode else {}

    # Cross-scene intelligence processing
    similar_scenes = cross_scene_intelligence.get('similar_scenes', [])
    pattern_insights = cross_scene_intelligence.get('pattern_insights', [])
    cross_scene_context = cross_scene_intelligence.get('cycle_context', '')

    context = f"""## Enhanced Phase 6 Behavioral Gap Analysis Request

**Scene ID**: {scene_id}
**Task Context**: {task_context}
**Analysis Mode**: {'Iterative Multi-Cycle Analysis' if is_iterative_mode else 'Standard Single-Pass Analysis'}
**Current Cycle**: {current_cycle} of {max_cycles}

## Phase 4-5 Embeddings Input:
- Total embeddings vectors: {total_vectors}
- Vector similarity score: {vector_similarity}
- Behavioral complexity score: {complexity_score}
- Safety awareness score: {safety_score}
- Embedding types available: {embedding_types}

## Sample Embeddings for Context:
{json.dumps(embedding_summaries, indent=2)}

## Behavioral Metrics from Previous Phases:
{json.dumps(behavioral_metrics, indent=2)}

## Vector Metadata:
{json.dumps(vector_metadata, indent=2)}

## Processing Context:
{json.dumps(processing_context, indent=2)}

## Enhanced Phase 6: Cross-Scene Intelligence
{f'''
**Similar Scenes Found**: {len(similar_scenes)}
**Cross-Scene Context**: {cross_scene_context}

**Pattern Insights from Fleet Data**:
{json.dumps(pattern_insights[:5], indent=2) if pattern_insights else "None available"}

**Similar Scene Analysis** (Top 3):
{json.dumps(similar_scenes[:3], indent=2) if similar_scenes else "None available"}
''' if is_iterative_mode and (similar_scenes or pattern_insights) else 'Cross-scene intelligence not available for this cycle.'}

## Enhanced Phase 6: Iterative Context
{f'''
**Business Objective**: {workflow_params.get('business_objective_canonical', 'Standard analysis')}
**Workflow Priority**: {workflow_params.get('workflow_priority', 'standard')}
**Target Metrics**: {workflow_params.get('target_metrics', [])}
**Required Analysis Focus**: {workflow_params.get('required_analysis', [])}

**Previous Cycles Summary**:
{json.dumps(iterative_context.get('previous_cycles_summary', {}), indent=2)}
''' if is_iterative_mode else 'Single-pass analysis mode - no iterative context.'}

## Your HIL Scene Understanding Task:
Using the embeddings and behavioral metrics from Phase 4-5, perform comprehensive scene understanding analysis for HIL data discovery:

1. **Scene Decomposition**: Break down the driving scenario into environmental, traffic, and behavioral components
2. **Context Analysis**: Identify weather conditions, lighting, road infrastructure, and traffic complexity
3. **Interaction Cataloging**: Document vehicle-to-vehicle, vehicle-to-pedestrian, and vehicle-to-infrastructure interactions
4. **Training Value Assessment**: Score the scene for its potential value in HIL testing and model training
{f'''5. **Cross-Scene Pattern Foundation**: Compare with similar scenes to establish consistent terminology and categorization
6. **Iterative Refinement**: Build upon insights from previous cycles (Cycle {current_cycle} of {max_cycles})
7. **Business Objective Alignment**: Focus analysis on business objective: {workflow_params.get('business_objective_canonical', 'HIL scenario discovery')}''' if is_iterative_mode else ''}

## HIL Analysis Requirements:
- Focus on scene understanding that enables cost-optimized HIL testing
- Provide detailed, consistent scene descriptions for pattern matching by subsequent agents
- Identify unique or valuable scenarios for training data curation
- Score scenes for HIL testing priority and training value
{f'''- Enable anomaly detection and similarity search agents with comprehensive scene foundation
- Consider insights from {len(similar_scenes)} similar scenes for pattern recognition
- Align findings with HIL objective: {workflow_params.get('business_objective_canonical', 'HIL scenario discovery')}
- Build consistent scene characterization for cross-agent analysis''' if is_iterative_mode else ''}
- Structure response as comprehensive JSON matching the expected scene understanding output format

## Expected Output Fields:
- scene_analysis: Dict with environmental conditions, traffic complexity, vehicle behavior, interactions, infrastructure
- scene_characteristics: Dict with scenario type, complexity level, safety criticality, training relevance
- behavioral_insights: Dict with critical decisions, edge case elements, performance indicators, learning opportunities
- recommendations: Dict with HIL testing priority, similar scenario needs, training focus, regulatory considerations
- confidence_metrics: Dict with confidence levels and analysis depth

Please analyze the Phase 4-5 data and return detailed scene understanding analysis in JSON format."""

    return context

async def perform_scene_understanding_analysis(analysis_context: str) -> SceneUnderstandingResult:
    """
    Perform scene understanding analysis using Strands agent (REAL GenAI - NO hardcoded data)
    """
    try:
        # Use the Strands agent to perform analysis
        agent_response = await scene_understanding_agent.invoke_async(analysis_context)

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
        parsed_result = parse_scene_understanding_response(response_text)

        return parsed_result

    except Exception as e:
        logger.error(f"Scene understanding analysis failed: {str(e)}")
        # Return fallback result (still no hardcoded analysis data)
        return SceneUnderstandingResult(
            scene_analysis={"error": f"Analysis failed: {str(e)}"},
            scene_characteristics={"error": f"Analysis failed: {str(e)}"},
            behavioral_insights={"error": f"Analysis failed: {str(e)}"},
            recommendations={"error": f"Analysis failed: {str(e)}"},
            confidence_metrics={"overall_confidence": 0.0, "error": True}
        )

def parse_scene_understanding_response(response_text: str) -> SceneUnderstandingResult:
    """Parse agent response into structured scene understanding analysis result"""
    try:
        # Try to parse JSON response first
        if '{' in response_text and '}' in response_text:
            json_start = response_text.find('{')
            json_end = response_text.rfind('}') + 1
            json_str = response_text[json_start:json_end]
            parsed_json = json.loads(json_str)

            return SceneUnderstandingResult(
                scene_analysis=parsed_json.get('scene_analysis', {}),
                scene_characteristics=parsed_json.get('scene_characteristics', {}),
                behavioral_insights=parsed_json.get('behavioral_insights', {}),
                recommendations=parsed_json.get('recommendations', {}),
                confidence_metrics=parsed_json.get('confidence_metrics', {})
            )
    except json.JSONDecodeError:
        pass

    # Fallback: create result from text response (no hardcoded analysis)
    return SceneUnderstandingResult(
        scene_analysis={"analysis_text": response_text},
        scene_characteristics={"analysis_text": response_text},
        behavioral_insights={"analysis_text": response_text},
        recommendations={"analysis_text": response_text},
        confidence_metrics={"text_based_analysis": True, "overall_confidence": 0.7}
    )

if __name__ == "__main__":
    logger.info("Starting Fleet Scene Understanding Agent with AgentCore Runtime")
    app.run()