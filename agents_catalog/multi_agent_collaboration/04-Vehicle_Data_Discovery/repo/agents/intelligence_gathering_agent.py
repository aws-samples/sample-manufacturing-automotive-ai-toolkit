#!/usr/bin/env python3
"""
Tesla Fleet Discovery Studio - Context Researcher (Intelligence Gathering Agent)
Production-grade AgentCore microservice using Strands SDK + AgentCore Runtime

Core Objective: Research specialist that enriches scene analysis with external and internal knowledge,
connecting scenes to business, regulatory, and engineering context.
"""

import os
import sys
import json
import logging
import asyncio
import re
from datetime import datetime
from typing import Dict, Any, List, Optional
from dataclasses import dataclass

# Heavy imports moved to lazy initialization to avoid 30s timeout
from bedrock_agentcore.runtime import BedrockAgentCoreApp

# Configure logging
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)

# AgentCore Application
app = BedrockAgentCoreApp()

@dataclass
class SimilaritySearchResult:
    """Structured result from similarity search analysis"""
    similar_scenes: List[Dict[str, Any]]
    pattern_analysis: Dict[str, Any]
    cross_scene_insights: Dict[str, Any]
    similarity_metrics: Dict[str, Any]
    pattern_recommendations: Dict[str, Any]
    insights: List[str]
    recommendations: List[str]
    search_summary: str

# Intelligence Agent now uses Strands http_request tool for regulatory research

# Global agent - initialized on startup
similarity_search_agent: Optional["Agent"] = None

def initialize_similarity_search_agent():
    """Initialize the Strands agent for similarity search analysis"""
    global similarity_search_agent

    system_prompt = """You are Tesla's expert Similarity Search Agent in the HIL (Hardware-in-the-Loop) multi-agent system, the third and final agent in a sequential 3-agent topology focused on pattern matching, cross-scene analysis, and fleet-wide similarity discovery for cost-optimized HIL testing data curation.

Your core mission is to analyze the scene understanding and anomaly detection results from previous agents, then use S3 Vectors similarity search to find related scenes, identify patterns across the fleet, and provide comprehensive recommendations for HIL testing data collection and training optimization.

## Your Expertise Areas:

**Fleet & Campaign Research**: You understand Tesla's fleet management, vehicle campaigns, software versions, and can connect scene data to specific vehicle contexts.

**Regulatory & Safety Research**: You research regulatory requirements, safety standards, NHTSA guidelines, and compliance frameworks that relate to identified driving behaviors.

**Internal Documentation**: You search through engineering specifications, design documents, and internal systems to find relevant context for behavioral patterns.

**Business Intelligence**: You connect technical findings to business implications, market conditions, and strategic initiatives.

**Enhanced Phase 6 Capabilities**:
- **Cross-Scene Intelligence Research**: You can research regulatory and business context across similar scenes from the fleet using S3 Vectors similarity data
- **Iterative Research Refinement**: You can build upon research findings from previous analysis cycles to reach deeper contextual insights
- **Business Objective-Driven Research**: You can focus your research based on specific business objectives and workflow parameters
- **Fleet-Wide Regulatory Analysis**: You can identify regulatory patterns vs. anomalies by comparing with similar scenarios

## CRITICAL: Use Statistical Similarity Tools for Fleet-Wide Analysis

You have access to fleet-wide statistical similarity tools that provide QUANTITATIVE pattern analysis:

**MANDATORY TOOL USAGE**:
1. **query_similar_behavioral_patterns_tool**: Use this to find similar scenes across available fleet scenes
   - Provides ranked similar scenes with similarity scores (0.0-1.0)
   - Returns behavioral context: environment types, weather conditions, risk/safety scores
   - Enables cross-scene intelligence: "Found 8 similar scenarios with 0.85+ similarity"
   - Includes pattern relevance and focus recommendations

2. **query_fleet_statistics_tool**: Use this to get statistical context for pattern analysis
   - Provides fleet-wide distributions for risk scores, safety scores, environments
   - Enables statistical pattern assessment: "This pattern appears in 12% of urban scenarios"
   - Returns quantitative baselines for comparative analysis

**Replace general research with statistical fleet analysis**:
- OLD: "This scenario might be related to similar situations"
- NEW: "Found 5 similar scenes with 0.87+ similarity, all in urban environments with pedestrian interactions"
- OLD: "Edge cases like this are important"
- NEW: "This pattern appears in only 3% of fleet (97th percentile rarity), high training value"

**Always call these tools with the scene's embeddings_data to perform statistical similarity analysis.**

## Your Research Framework:

When analyzing scene data with behavioral insights, you MUST provide:

1. **Fleet Context**: Vehicle and campaign information
   - campaign_name: Associated marketing/testing campaign
   - vehicle_model: Specific Tesla model (Model S, 3, X, Y, Cybertruck)
   - software_version: FSD software version during scene
   - geographic_region: Market region (US, Europe, China, etc.)
   - deployment_phase: Beta, production, etc.

2. **Regulatory Context**: Compliance and safety framework
   - applicable_regulations: Relevant safety standards (FMVSS, UN-ECE, etc.)
   - safety_requirements: Specific safety requirements for identified behaviors
   - compliance_status: Current compliance assessment
   - regulatory_gaps: Areas needing attention for compliance

3. **Internal Documentation**: Engineering and design context (NO URLs)
   - design_specs: Refer to internal design specifications as appropriate
   - engineering_tickets: Note relevant engineering work areas (no specific ticket IDs)
   - test_procedures: Reference internal testing protocols as needed
   - known_issues: Mention related issue categories if applicable

4. **Campaign Metadata**: Marketing and deployment context
   - target_market: Primary market for campaign
   - deployment_metrics: Usage and performance metrics
   - customer_feedback: Related customer reports
   - business_priority: Strategic importance level

5. **Business Context**: Strategic and operational implications
   - market_impact: Potential market implications
   - competitive_analysis: How this relates to competitors
   - resource_requirements: Engineering resources needed
   - timeline_implications: Impact on development roadmap

## Research Guidelines:

- Connect technical findings to business strategy
- Identify regulatory compliance requirements
- Find relevant internal documentation and specifications
- Assess market and competitive implications
- Prioritize findings by business impact
- Provide actionable intelligence for decision-making

**Enhanced Phase 6 Guidelines**:
- **Cross-Scene Research**: When similar scenes are provided, research regulatory patterns across the fleet to identify systematic vs. anomalous compliance issues
- **Iterative Research Refinement**: In multi-cycle mode, build upon previous research findings to reach deeper regulatory and business insights
- **Business Objective-Driven Focus**: Tailor research focus based on provided business objectives and workflow parameters
- **Fleet Intelligence Research**: Use similarity data to determine if regulatory concerns are consistent across similar scenarios
- **Pattern-Based Compliance**: Identify when compliance issues that appear problematic in isolation are actually acceptable within specific regulatory contexts

## Available Research Tools:

You have access to the `http_request` tool to fetch real regulatory data from these sources:

**NHTSA (National Highway Traffic Safety Administration):**
- General AV Guidelines: https://aashtojournal.transportation.org/nhtsa-introduces-new-automated-vehicle-framework/, https://www.nhtsa.gov/vehicle-safety/automated-vehicles-safety
- AV Testing Guidance: https://www.nhtsa.gov/automated-vehicles-guidance/voluntary-guidance-automated-vehicles
- FMVSS Standards: https://www.nhtsa.gov/fmvss (add specific standard numbers like /108, /111, etc.)

**DOT (Department of Transportation):**
- AV Policy Framework: https://landline.media/dot-releases-av-framework-as-auroras-driverless-deadline-nears/
- AV 4.0 Policy: https://www.transportation.gov/briefing-room/trumps-transportation-secretary-sean-p-duffy-unveils-new-automated-vehicle-framework, https://www.mayerbrown.com/en/insights/publications/2025/04/dot-and-nhtsa-announce-autonomous-vehicle-framework

**State Regulations:**
- California DMV AV: https://www.dmv.ca.gov/portal/vehicle-industry-services/autonomous-vehicles/california-autonomous-vehicle-regulations/
- Michigan AV Laws: https://www.crowell.com/en/insights/client-alerts/californian-autonomous-vehicles-get-a-revised-regulatory-load-if-new-dmv-law-passes
- Arizona AV Executive Order: https://www.crowell.com/en/insights/client-alerts/californian-autonomous-vehicles-get-a-revised-regulatory-load-if-new-dmv-law-passes

**Safety Standards:**
- IIHS AV Safety: https://aashtojournal.transportation.org/nhtsa-introduces-new-automated-vehicle-framework/
- SAE Automation Levels: https://aashtojournal.transportation.org/nhtsa-introduces-new-automated-vehicle-framework/

## How to Use Research Tools:

When you identify behavioral gaps like "Late braking for pedestrian in urban intersection", use http_request to:
1. Fetch NHTSA pedestrian safety guidelines
2. Research FMVSS 108 (lighting) and 111 (rearview mirrors) standards
3. Check state-specific pedestrian right-of-way laws
4. Look up IIHS pedestrian safety ratings

Example: `http_request(url="https://www.nhtsa.gov/vehicle-safety/automated-vehicles-safety", method="GET")`

## WARNING: CRITICAL: ANTI-HALLUCINATION PROTOCOL WARNING

CONTENT GROUNDING REQUIREMENTS:
- ONLY use information explicitly provided in the input data
- For fleet context fields (campaign_name, vehicle_model, etc.), use general categories if specific data unavailable

PROHIBITED FABRICATIONS:
ERROR: DO NOT create: URLs ("https://tesla.ai/specs/..."), specific ticket IDs ("JIRA-1234"), document links
ERROR: DO NOT invent: customer feedback quotes, specific deployment statistics, incident numbers
ERROR: DO NOT fabricate: engineering ticket references, internal system names

ALLOWED APPROACHES:
SUCCESS:Fleet context: Use "Urban Driving Validation", "Model 3", "North America" (general categories)
SUCCESS:Documentation: "Refer to internal documentation for [topic]" (no URLs)
SUCCESS:Statistics: "Data unavailable" instead of invented percentages

## Output Format:

CRITICAL: Return a structured response object (NOT a JSON string) with these exact fields populated based on your similarity search and intelligence analysis:

Required response structure - return the actual object with these fields:
- similar_scenes: list of dicts containing scene information and similarity scores
- pattern_analysis: dict containing cross-scene patterns and insights
- cross_scene_insights: dict containing fleet-wide intelligence and recommendations
- similarity_metrics: dict containing quantified similarity measurements
- pattern_recommendations: dict containing actionable recommendations based on patterns found

IMPORTANT: Do NOT wrap your response in JSON markdown blocks or return it as a string. Return the structured object directly."""

    try:
        # Import heavy dependencies at runtime to avoid 30s init timeout
        import boto3
        from strands import Agent
        from strands_tools import http_request
        from s3_vectors_tools import (
            query_similar_behavioral_patterns_tool,
            query_fleet_statistics_tool
        )

        similarity_search_agent = Agent(
            name="intelligence_researcher",
            system_prompt=system_prompt,
            model="anthropic.claude-3-sonnet-20240229-v1:0",  # Same as working safety agent
            tools=[
                http_request,
                query_similar_behavioral_patterns_tool,
                query_fleet_statistics_tool
            ]
        )
        logger.info("Intelligence Gathering agent initialized successfully")
        return True
    except Exception as e:
        logger.error(f"Failed to initialize Intelligence Gathering agent: {str(e)}")
        return False

# Agent will be initialized lazily on first invoke (30s timeout fix)

@app.entrypoint
async def invoke(payload: Dict[str, Any]) -> Dict[str, Any]:
    """
    Main AgentCore entrypoint - performs intelligence gathering and contextual research
    """
    global similarity_search_agent  # Access the global variable

    try:
        # --- LAZY INITIALIZATION FIX ---
        if similarity_search_agent is None:
            logger.info("Agent not initialized. Initializing now (Lazy Loading)...")
            success = initialize_similarity_search_agent()
            if not success:
                raise RuntimeError("Failed to lazily initialize Intelligence Gathering agent")
        # -------------------------------

        # Handle JSON string payload from orchestrator
        if isinstance(payload, str):
            try:
                logger.info("Converting JSON string payload to dictionary")
                payload = json.loads(payload)
            except json.JSONDecodeError as e:
                logger.error(f"Failed to parse JSON payload: {e}")
                raise ValueError(f"Invalid JSON payload: {e}")
        elif not isinstance(payload, dict):
            logger.error(f"Unexpected payload type: {type(payload)}")
            raise ValueError(f"Expected dict or JSON string, got {type(payload)}")

        # Extract payload data (dict instead of typed model)
        scene_id = payload.get("scene_id", "unknown")
        agent_type = payload.get("agent_type", "intelligence_gathering")
        task_context = payload.get("task_context", "direct")
        embeddings_data = payload.get("embeddings_data", [])
        behavioral_metrics = payload.get("behavioral_metrics", {})
        vector_metadata = payload.get("vector_metadata", {})
        processing_context = payload.get("processing_context", {})
        shared_state = payload.get("shared_state", {})
        behavioral_analysis = payload.get("behavioral_analysis", {})
        original_task = payload.get("original_task", {})
        timestamp = payload.get("timestamp", datetime.utcnow().isoformat())

        logger.info(f"Starting intelligence gathering for {scene_id} (context: {task_context})")

        # Prepare research context based on request type (SAME LOGIC)
        if task_context == "entry_level_worker":
            research_context = prepare_entry_level_context(payload)
        elif task_context == "context_aware_worker":
            research_context = prepare_context_aware_context(payload)
        else:
            # Fallback for direct requests
            research_context = prepare_direct_context(payload)

        # Perform similarity search using Strands agent (SAME LOGIC)
        similarity_result = await perform_similarity_search_analysis(research_context)

        # Return dict response instead of typed model
        response = {
            "scene_id": scene_id,
            "agent_type": "similarity_search",
            "status": "success",
            "analysis": {
                "summary": similarity_result.search_summary,
                "key_findings": [],  # Will be populated by orchestrator parsing
                "metrics": similarity_result.similarity_metrics,
                "confidence_score": None
            },
            "insights": similarity_result.insights,
            "recommendations": similarity_result.recommendations,
            "similar_scenes": similarity_result.similar_scenes,
            "pattern_analysis": similarity_result.pattern_analysis,
            "cross_scene_insights": similarity_result.cross_scene_insights,
            "pattern_recommendations": similarity_result.pattern_recommendations,
            "metadata": {
                "search_timestamp": datetime.utcnow().isoformat(),
                "agent_version": "1.0.0",
                "model_used": "anthropic.claude-3-sonnet-20240229-v1:0",
                "behavioral_analysis_consumed": bool(behavioral_analysis),
                "task_context": task_context,
                "search_depth": "comprehensive",
                "deployment_type": "agentcore_runtime"
            }
        }

        logger.info(f"Similarity search completed for {scene_id}")
        return response

    except Exception as e:
        logger.error(f"Similarity search failed for {scene_id}: {str(e)}")
        return {
            "scene_id": scene_id,
            "agent_type": "similarity_search",
            "status": "error",
            "error": f"Similarity search failed: {str(e)}",
            "analysis": "",
            "insights": [],
            "recommendations": [],
            "similar_scenes": [],
            "pattern_analysis": {},
            "cross_scene_insights": {},
            "pattern_recommendations": {},
            "metadata": {
                "error_timestamp": datetime.utcnow().isoformat(),
                "agent_version": "1.0.0",
                "deployment_type": "agentcore_runtime"
            }
        }

def prepare_entry_level_context(payload: Dict[str, Any]) -> str:
    """Prepare research context for entry-level worker with Enhanced Phase 6 multi-cycle support"""
    scene_id = payload.get("scene_id", "unknown")
    embeddings_data = payload.get("embeddings_data", [])
    behavioral_metrics = payload.get("behavioral_metrics", {})
    vector_metadata = payload.get("vector_metadata", {})
    processing_context = payload.get("processing_context", {})

    # Extract previous agent results for agent-to-agent communication
    previous_agent_results = payload.get("previous_agent_results", {})

    # Handle both possible agent type names for robustness
    scene_understanding = (previous_agent_results.get("scene_understanding", {}) or
                          previous_agent_results.get("behavioral_gap_analysis", {}))
    anomaly_detection = (previous_agent_results.get("anomaly_detection", {}) or
                        previous_agent_results.get("safety_validation", {}))

    # Build previous analysis context for LLM reasoning
    previous_analysis_context = ""
    if scene_understanding:
        analysis = scene_understanding.get("analysis", {})
        insights = scene_understanding.get("insights", [])
        recommendations = scene_understanding.get("recommendations", [])

        previous_analysis_context += "\n**SCENE UNDERSTANDING ANALYSIS:**\n"
        if isinstance(analysis, str):
            # Handle malformed JSON string from agent response
            previous_analysis_context += f"{analysis}\n"
        else:
            previous_analysis_context += f"{json.dumps(analysis, indent=2)}\n"

        if insights:
            previous_analysis_context += f"**Key Insights:** {insights}\n"
        if recommendations:
            previous_analysis_context += f"**Recommendations:** {recommendations}\n"

    if anomaly_detection:
        analysis = anomaly_detection.get("analysis", {})
        insights = anomaly_detection.get("insights", [])

        previous_analysis_context += "\n**ANOMALY DETECTION RESULTS:**\n"
        if isinstance(analysis, str):
            previous_analysis_context += f"{analysis}\n"
        else:
            previous_analysis_context += f"{json.dumps(analysis, indent=2)}\n"

        if insights:
            previous_analysis_context += f"**Anomaly Insights:** {insights}\n"

    # Enhanced Phase 6: New multi-cycle context fields
    cross_scene_intelligence = payload.get("cross_scene_intelligence", {})
    iterative_context = payload.get("iterative_context", {})

    # Extract Anomaly Context (Essential for Discovery Mode)
    anomaly_context = payload.get("anomaly_context", {})
    is_anomaly = anomaly_context.get("is_anomaly", False)
    anomaly_score = anomaly_context.get("anomaly_score", 0.0)
    anomaly_reason = anomaly_context.get("reason", "No anomaly data available")

    # Extract fleet_context from payload
    fleet_context = payload.get("fleet_context", {})
    vehicle_model = fleet_context.get("vehicle_model", "Unknown Vehicle")
    campaign_name = fleet_context.get("campaign_name", "Unknown Campaign")
    software_version = fleet_context.get("software_version", "Unknown Version")
    geographic_region = fleet_context.get("geographic_region", "Unknown Region")
    deployment_phase = fleet_context.get("deployment_phase", "Unknown Phase")

    # Extract pre-calculated metrics from orchestrator (not manual reconstruction)
    key_behavioral_metrics = payload.get("key_behavioral_metrics", {})
    if not key_behavioral_metrics:
        # Fallback only if missing
        key_behavioral_metrics = {
            "metrics_summary": "No metrics provided by Orchestrator",
            "detailed_metrics": behavioral_metrics
        }

    # Extract intelligence insights from dense scene descriptions
    # No hardcoded metric field lookups - use dynamic analysis from actual content
    scene_descriptions = [emb.get("text", emb.get("text_content", "")) for emb in embeddings_data if isinstance(emb, dict)]
    intelligence_insights = [desc for desc in scene_descriptions if any(keyword in desc.lower()
                           for keyword in ['regulation', 'standard', 'compliance', 'nhtsa', 'iso', 'fmvss', 'safety', 'requirement'])]

    # Dynamic analysis from content length and regulatory keywords
    total_descriptions = len(scene_descriptions)
    regulatory_complexity_score = len([desc for desc in scene_descriptions if any(word in desc.lower()
                                     for word in ['regulation', 'standard', 'compliance'])]) / max(total_descriptions, 1)
    safety_awareness_score = len([desc for desc in scene_descriptions if any(word in desc.lower()
                                for word in ['safety', 'safe', 'secure'])]) / max(total_descriptions, 1)

    # Define variables to prevent NameErrors in prompt template
    embeddings_count = len(embeddings_data)
    behavioral_complexity_score = key_behavioral_metrics.get("behavioral_complexity_score", regulatory_complexity_score)  # Use actual behavioral score
    vector_dimensions = vector_metadata.get('vector_dimensions', len(embeddings_data[0].get('vector', [])) if embeddings_data else 'Unknown')

    # Enhanced Phase 6: Multi-cycle context processing
    is_iterative_mode = bool(iterative_context)
    current_cycle = iterative_context.get('current_cycle', 1) if is_iterative_mode else 1
    max_cycles = iterative_context.get('max_cycles', 1) if is_iterative_mode else 1
    workflow_params = iterative_context.get('workflow_params', {}) if is_iterative_mode else {}

    # Cross-scene intelligence processing
    similar_scenes = cross_scene_intelligence.get('similar_scenes', [])
    pattern_insights = cross_scene_intelligence.get('pattern_insights', [])
    cross_scene_context = cross_scene_intelligence.get('cycle_context', '')

    context = f"""## Enhanced Phase 6 Intelligence Gathering Request - Entry Level Processing

## PREVIOUS AGENT ANALYSIS RESULTS:
{previous_analysis_context if previous_analysis_context else "No previous agent analysis available - this is the first agent in the sequence."}

## ANOMALY DETECTION RESULTS:
**ANOMALY STATUS**: {"ANOMALY DETECTED" if is_anomaly else "NORMAL SCENE"}
**Anomaly Score**: {anomaly_score:.3f} (0.0=normal, 1.0=highly anomalous)
**Detection Reason**: {anomaly_reason}
**Research Priority**: {"HIGH - Focus on understanding why this scene is anomalous" if is_anomaly else "Standard - routine intelligence gathering"}

**Scene ID**: {scene_id}
**Processing Context**: {'Iterative Multi-Cycle Research' if is_iterative_mode else 'Standard Entry-Level Research'} (parallel processing)
**Current Cycle**: {current_cycle} of {max_cycles}
**Data Available**: {embeddings_count} embedding vectors, behavioral metrics

## Embeddings Data Summary:
- Total vectors: {embeddings_count}
- Vector dimensions: {vector_dimensions}
- Regulatory complexity score: {behavioral_complexity_score:.3f} (dynamic analysis from content)
- Safety awareness score: {safety_awareness_score:.3f} (dynamic analysis from content)

## FLEET CONTEXT (TRUTH DATA):
**Vehicle Model**: {vehicle_model}
**Campaign**: {campaign_name}
**Software Version**: {software_version}
**Region**: {geographic_region}
**Deployment Phase**: {deployment_phase}

## QUANTIFIED VISUAL METRICS:
{json.dumps(key_behavioral_metrics, indent=2)}

## Enhanced Phase 6: Cross-Scene Intelligence Research
{f'''
**Similar Scenes Found**: {len(similar_scenes)}
**Cross-Scene Context**: {cross_scene_context}

**Fleet Pattern Insights**:
{json.dumps(pattern_insights[:5], indent=2) if pattern_insights else "None available"}

**Similar Scene Regulatory Context** (Top 3):
{json.dumps(similar_scenes[:3], indent=2) if similar_scenes else "None available"}
''' if is_iterative_mode and (similar_scenes or pattern_insights) else 'Cross-scene intelligence not available for this cycle.'}

## Enhanced Phase 6: Iterative Research Context
{f'''
**Business Objective**: {workflow_params.get('business_objective_canonical', 'Standard analysis')}
**Workflow Priority**: {workflow_params.get('workflow_priority', 'standard')}
**Target Metrics**: {workflow_params.get('target_metrics', [])}
**Required Research Focus**: {workflow_params.get('required_analysis', [])}

**Previous Cycles Summary**:
{json.dumps(iterative_context.get('previous_cycles_summary', {}), indent=2)}
''' if is_iterative_mode else 'Single-pass research mode - no iterative context.'}

## Your Enhanced Research Task:
Perform comprehensive intelligence gathering and contextual research on this driving scene. Focus on:

1. **Fleet & Campaign Lookup**: Research vehicle context, campaign information, and deployment details
2. **Regulatory Research**: Identify applicable safety regulations and compliance requirements
3. **Internal Documentation**: Find relevant engineering specs and design documents
4. **Business Intelligence**: Assess market implications and strategic context
{f'''5. **Cross-Scene Regulatory Analysis**: Research regulatory patterns across {len(similar_scenes)} similar scenes
6. **Iterative Research Refinement**: Build upon research from previous cycles (Cycle {current_cycle} of {max_cycles})
7. **Business Objective-Driven Research**: Focus research on business objective: {workflow_params.get('business_objective_canonical', 'general analysis')}''' if is_iterative_mode else ''}

## Available Research Data:
- Scene embeddings: {json.dumps(embeddings_data[:2] if embeddings_data else [], indent=2)}...
- Behavioral metrics: {json.dumps(behavioral_metrics, indent=2)}
- Processing metadata: {json.dumps(processing_context, indent=2)}

## Research Databases Available:
- Fleet Management Database (VIN, campaigns, software versions)
- Regulatory Database (NHTSA, FMVSS, UN-ECE standards)
- Internal Engineering Systems (Confluence, Jira, design specs)
- Market Intelligence Database (competitive analysis, customer feedback)

Please provide comprehensive intelligence research in JSON format with all required fields:
- fleet_context (dict with campaign_name, vehicle_model, software_version, geographic_region)
- regulatory_context (dict with applicable_regulations, safety_requirements, compliance_status)
- internal_documentation_links (list of dicts with title, url, type)
- campaign_metadata (dict with target_market, deployment_metrics, business_priority)
- business_context (dict with market_impact, competitive_analysis, resource_requirements)
- insights (list)
- recommendations (list)"""

    return context

def prepare_context_aware_context(payload: Dict[str, Any]) -> str:
    """Prepare research context for context-aware worker (with behavioral analysis results)"""
    scene_id = payload.get("scene_id", "unknown")
    behavioral_analysis = payload.get("behavioral_analysis", {})
    shared_state = payload.get("shared_state", {})

    # Extract previous agent results for context-aware processing
    previous_agent_results = payload.get("previous_agent_results", {})
    scene_understanding = (previous_agent_results.get("scene_understanding", {}) or
                          previous_agent_results.get("behavioral_gap_analysis", {}))
    anomaly_detection = (previous_agent_results.get("anomaly_detection", {}) or
                        previous_agent_results.get("safety_validation", {}))

    # Build previous analysis context
    previous_analysis_context = ""
    if scene_understanding or anomaly_detection:
        previous_analysis_context = "\n**PREVIOUS AGENT RESULTS:**\n"
        if scene_understanding:
            previous_analysis_context += f"Scene Understanding: {scene_understanding.get('analysis', 'No analysis')}\n"
        if anomaly_detection:
            previous_analysis_context += f"Anomaly Detection: {anomaly_detection.get('analysis', 'No analysis')}\n"

    context = f"""## Intelligence Gathering Request - Context-Aware Processing

## PREVIOUS AGENT ANALYSIS RESULTS:
{previous_analysis_context if previous_analysis_context else "No previous agent analysis available from earlier agents."}

**Scene ID**: {scene_id}
**Processing Context**: Context-aware intelligence gathering building on previous agent results
**Analysis Type**: Intelligence research using comprehensive scene understanding and anomaly detection results

## Current Cycle Behavioral Analysis:
{json.dumps(behavioral_analysis, indent=2) if behavioral_analysis else "No current cycle behavioral analysis - using previous agent results above"}

## Shared Processing State:
{json.dumps(shared_state, indent=2) if shared_state else "No shared state - this is the final agent in the sequence"}

## Your Enhanced Research Task:
Building on the PREVIOUS AGENT ANALYSIS RESULTS above, perform targeted intelligence gathering. Focus on:

1. **Gap-Specific Research**: Research regulatory and technical context for identified performance gaps
2. **Risk-Based Compliance**: Investigate safety requirements related to specific risk scores
3. **Tag-Based Fleet Analysis**: Research fleet performance for similar scene tags
4. **Business Impact Assessment**: Evaluate business implications of identified behavioral patterns

## Enhanced Research Queries:
Based on behavioral analysis, research:
- Regulatory requirements for identified gaps: {behavioral_analysis.get('identified_gaps', [])}
- Fleet performance for scene tags: {behavioral_analysis.get('scene_tags', [])}
- Safety standards for risk areas: {behavioral_analysis.get('risk_scores', {})}
- Engineering specifications for behavioral recommendations: {behavioral_analysis.get('recommendations', [])}

Please provide enhanced intelligence research in JSON format with all required fields."""

    return context

def prepare_direct_context(payload: Dict[str, Any]) -> str:
    """Prepare research context for direct requests"""
    scene_id = payload.get("scene_id", "unknown")
    embeddings_data = payload.get("embeddings_data", [])
    behavioral_metrics = payload.get("behavioral_metrics", {})
    vector_metadata = payload.get("vector_metadata", {})
    behavioral_analysis = payload.get("behavioral_analysis", {})

    return f"""## Direct Intelligence Gathering Request

**Scene ID**: {scene_id}
**Request Type**: Direct intelligence research request

## Available Data:
- Embeddings: {len(embeddings_data)} vectors
- Behavioral metrics: {bool(behavioral_metrics)}
- Vector metadata: {bool(vector_metadata)}
- Behavioral analysis: {bool(behavioral_analysis)}

## Task:
Perform comprehensive intelligence gathering and contextual research on the provided scene data.

{json.dumps(payload, indent=2)}

Please provide intelligence research in JSON format with all required fields."""

async def perform_similarity_search_analysis(research_context: str) -> SimilaritySearchResult:
    """
    Perform similarity search using Strands agent
    """
    try:
        # Use the Strands agent to perform similarity search
        agent_response = await similarity_search_agent.invoke_async(research_context)

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
        parsed_result = parse_similarity_response(response_text)

        # Return directly, no enhancement function
        return parsed_result

    except Exception as e:
        logger.error(f"Similarity search failed: {str(e)}")
        # Return empty result (NO FALLBACKS)
        return SimilaritySearchResult(
            similar_scenes=[],
            pattern_analysis={},
            cross_scene_insights={},
            similarity_metrics={},
            pattern_recommendations={},
            insights=[],
            recommendations=[],
            search_summary=f"Search failed: {str(e)}"
        )

def parse_similarity_response(response_text: str) -> SimilaritySearchResult:
    """Parse agent response into structured similarity search result with robust markdown handling"""
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
                logger.info("Similarity Agent: Extracted JSON from markdown wrapper")
                return json_content

        # Fallback: extract JSON by finding first { to last }
        if '{' in text and '}' in text:
            json_start = text.find('{')
            json_end = text.rfind('}') + 1
            json_content = text[json_start:json_end]
            logger.info("Similarity Agent: Extracted JSON using bracket matching")
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
            logger.info("Similarity Agent: Successfully parsed JSON response")
        except json.JSONDecodeError:
            # Try Python literal evaluation for dict strings with single quotes
            try:
                parsed_json = ast.literal_eval(json_content)
                logger.info("Similarity Agent: Successfully parsed using ast.literal_eval")
            except (ValueError, SyntaxError):
                # Try fixing common quote issues
                try:
                    fixed_json = json_content.replace("'", '"')
                    parsed_json = json.loads(fixed_json)
                    logger.info("Similarity Agent: Successfully parsed after quote fixing")
                except json.JSONDecodeError:
                    # Try regex extraction as last resort
                    json_pattern = r'\{.*\}'
                    matches = re.findall(json_pattern, response_text, re.DOTALL)
                    if matches:
                        longest_match = max(matches, key=len)
                        parsed_json = json.loads(longest_match)
                        logger.info("Similarity Agent: Successfully parsed using regex fallback")

        if parsed_json:
            # Handle insights as either dict or list format
            raw_insights = parsed_json.get('insights', [])
            if isinstance(raw_insights, list) and len(raw_insights) > 0:
                processed_insights = []
                for insight in raw_insights:
                    if isinstance(insight, dict):
                        insight_text = insight.get('text', str(insight))
                        processed_insights.append(insight_text)
                    elif isinstance(insight, str):
                        processed_insights.append(insight)
                    else:
                        processed_insights.append(str(insight))
                insights_list = processed_insights
            else:
                insights_list = raw_insights if isinstance(raw_insights, list) else []

            # Handle recommendations as either dict or list format
            raw_recommendations = parsed_json.get('recommendations', [])
            if isinstance(raw_recommendations, list) and len(raw_recommendations) > 0:
                processed_recommendations = []
                for recommendation in raw_recommendations:
                    if isinstance(recommendation, dict):
                        recommendation_text = (
                            recommendation.get('text') or
                            recommendation.get('recommendation') or
                            recommendation.get('description') or
                            str(recommendation)
                        )
                        processed_recommendations.append(recommendation_text)
                    elif isinstance(recommendation, str):
                        processed_recommendations.append(recommendation)
                    else:
                        processed_recommendations.append(str(recommendation))
                recommendations_list = processed_recommendations
            else:
                recommendations_list = raw_recommendations if isinstance(raw_recommendations, list) else []

            return SimilaritySearchResult(
                similar_scenes=parsed_json.get('similar_scenes', []),
                pattern_analysis=parsed_json.get('pattern_analysis', {}),
                cross_scene_insights=parsed_json.get('cross_scene_insights', {}),
                similarity_metrics=parsed_json.get('similarity_metrics', {}),
                pattern_recommendations=parsed_json.get('pattern_recommendations', {}),
                insights=insights_list,
                recommendations=recommendations_list,
                search_summary=parsed_json.get('search_summary', response_text)
            )

    except Exception as e:
        logger.error(f"Similarity Agent: Unexpected error during JSON parsing: {str(e)}")

    # Fallback: extract information from text response
    logger.warning("Similarity Agent: Using text extraction fallback due to parsing failure")
    return extract_from_similarity_text_response(response_text)


def extract_from_similarity_text_response(response_text: str) -> SimilaritySearchResult:
    """Fallback: Extract structured information from text response if JSON parsing fails"""

    # Attempt to extract similar scenes using regex or basic parsing
    # (Simple fallback: just put the whole text in the summary)

    return SimilaritySearchResult(
        similar_scenes=[], # We can't reliably parse lists from raw text easily
        pattern_analysis={},
        cross_scene_insights={},
        similarity_metrics={"parsing_fallback": True},
        pattern_recommendations={},
        insights=["Analysis extracted from raw text response"],
        recommendations=["Check raw search summary for details"],
        search_summary=response_text
    )


if __name__ == "__main__":
    logger.info("Starting Similarity Search Agent with AgentCore Runtime")
    app.run()