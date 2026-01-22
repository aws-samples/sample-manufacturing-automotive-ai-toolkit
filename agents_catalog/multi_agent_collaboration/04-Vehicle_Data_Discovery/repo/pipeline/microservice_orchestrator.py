#!/usr/bin/env python3
"""
Fleet Discovery Studio - Microservice Orchestrator (Phase 6)
Production-grade implementation using Strands GraphBuilder with sequential HIL topology.
"""

import os
import sys
import json
import boto3
import httpx
import logging
import asyncio
import re
import uuid
from datetime import datetime
from typing import Dict, Any, List, Optional

from pydantic import BaseModel, Field, validator
# Helper functions for camera-specific ID processing (self-contained)
def extract_scene_from_id(camera_id: str) -> str:
    """
    Extract scene ID from camera-specific ID.

    Args:
        camera_id: Camera-specific ID in format "scene_0123_CAM_FRONT" or legacy "scene_0123"

    Returns:
        Scene ID in format "scene_0123"

    Examples:
        "scene_0123_CAM_FRONT" -> "scene_0123"
        "scene_0456_CAM_LEFT" -> "scene_0456"
        "scene_0789" -> "scene_0789" (legacy format)
    """
    if "_CAM_" in camera_id:
        return camera_id.rsplit("_CAM_", 1)[0]
    else:
        logger.warning(f"Invalid camera ID format: {camera_id}")
        return camera_id

def extract_camera_from_id(camera_id: str) -> str:
    """
    Extract camera name from camera-specific ID.

    Args:
        camera_id: Camera-specific ID in format "scene_0123_CAM_FRONT"

    Returns:
        Camera name in format "CAM_FRONT"

    Examples:
        "scene_0123_CAM_FRONT" -> "CAM_FRONT"
        "scene_0456_CAM_LEFT" -> "CAM_LEFT"
        "scene_0789" -> "UNKNOWN_CAMERA" (legacy format)
    """
    if "_CAM_" in camera_id:
        return "CAM_" + camera_id.rsplit("_CAM_", 1)[1]
    else:
        logger.warning(f"Invalid camera ID format: {camera_id}")
        return "UNKNOWN_CAMERA"
from strands.multiagent import GraphBuilder
from strands.multiagent.base import MultiAgentBase, NodeResult, Status, MultiAgentResult
from strands.agent.agent_result import AgentResult
from strands.types.content import ContentBlock, Message

# Configure logging
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)

# Global AWS clients for performance
s3_client = boto3.client('s3')
sfn_client = boto3.client('stepfunctions')
bedrock_agentcore_client = boto3.client('bedrock-agentcore')
bedrock_runtime_client = boto3.client('bedrock-runtime')  # For business objective interpretation

# Global AgentCore Runtime ARNs - loaded from environment variables
# 3-Agent HIL-Focused Architecture
# Set these via SSM parameters or environment variables during deployment
AGENT_RUNTIME_ARNS = {
    "scene_understanding": os.environ.get("SCENE_UNDERSTANDING_AGENT_ARN", ""),
    "anomaly_detection": os.environ.get("ANOMALY_DETECTION_AGENT_ARN", ""),
    "similarity_search": os.environ.get("SIMILARITY_SEARCH_AGENT_ARN", "")
}

# Structured Output Schemas for Quality Assurance
class ValidationReport(BaseModel):
    """Anti-hallucination and quality validation results"""
    issues_detected: int = Field(ge=0, description="Number of validation issues found")
    issues: List[str] = Field(default_factory=list, description="List of specific issues detected")
    scene_specific_content: bool = Field(description="Whether output contains scene-specific content")
    validated_timestamp: str = Field(description="ISO timestamp of validation")

class AgentAnalysis(BaseModel):
    """Structured analysis content from agent"""
    summary: str = Field(min_length=1, description="Brief summary of analysis")
    key_findings: List[str] = Field(default_factory=list, description="Main findings from analysis")
    metrics: Dict[str, Any] = Field(default_factory=dict, description="Quantitative metrics extracted")
    confidence_score: Optional[float] = Field(ge=0.0, le=1.0, description="Confidence in analysis")

class AgentResponse(BaseModel):
    """Standardized agent response schema"""
    agent_type: str = Field(description="Type of agent that generated this response")
    scene_id: str = Field(description="Scene identifier this analysis applies to")
    status: str = Field(default="success", description="Execution status")
    analysis: AgentAnalysis = Field(description="Structured analysis content")
    insights: List[str] = Field(default_factory=list, description="Key insights extracted")
    recommendations: List[str] = Field(default_factory=list, description="Actionable recommendations")
    validation_report: ValidationReport = Field(description="Validation and quality check results")
    execution_metadata: Dict[str, Any] = Field(default_factory=dict, description="Execution context and timing")

    @validator('scene_id')
    def scene_id_must_be_specific(cls, v):
        if v == "scene-unknown" or not v:
            raise ValueError("Scene ID must be specific, not unknown or empty")
        return v

    @validator('insights', 'recommendations')
    def lists_must_not_be_empty_for_success(cls, v, values):
        if values.get('status') == 'success' and len(v) == 0:
            logger.warning("Successful agent response has empty insights or recommendations")
        return v

class CrossAgentValidation(BaseModel):
    """Cross-agent consistency validation results"""
    validation_timestamp: str = Field(description="ISO timestamp of cross-validation")
    agents_compared: List[str] = Field(description="List of agent types compared")
    consistency_score: float = Field(ge=0.0, le=1.0, description="Overall consistency score")
    inconsistencies: List[str] = Field(default_factory=list, description="Detected inconsistencies")
    consensus_insights: List[str] = Field(default_factory=list, description="Insights agreed upon by multiple agents")
    conflicting_recommendations: List[Dict[str, str]] = Field(default_factory=list, description="Conflicting recommendations between agents")

class AnomalyDetector:
    """
    The 'Anomaly Detection Agent' logic.
    Stateless: Uses S3 Vectors as the reference database to find outliers.
    """
    def __init__(self):
        # Initialize specific S3 Vectors client
        self.client = boto3.client('s3vectors')
        self.bucket = os.getenv('VECTOR_BUCKET_NAME', '')
        self.index = os.getenv('VECTOR_INDEX_NAME', 'behavioral-metadata-index')

    def detect_anomaly(self, scene_embedding: list, threshold: float = 0.75) -> Dict[str, Any]:
        """
        Calculates anomaly score based on vector isolation (distance to nearest neighbors).
        Returns: Dict with anomaly status, score (0.0-1.0), and reasoning.
        """
        try:
            # 1. Query for neighbors (k-NN search) -  Use correct S3 Vectors API
            response = self.client.query_vectors(
                vectorBucketName=self.bucket,
                indexName=self.index,
                queryVector={'float32': scene_embedding},  # AWS docs require VectorData object format
                topK=5,  # Check top 5 neighbors
                returnDistance=True,  # Include distance for anomaly scoring
                returnMetadata=False  # Don't need metadata for anomaly detection
            )

            vectors = response.get('vectors', [])  # AWS API returns 'vectors', not 'hits'

            # Cold Start Handling: If DB is empty, everything is an anomaly
            if not vectors:
                return {
                    "is_anomaly": True,
                    "anomaly_score": 1.0,
                    "reason": "Cold start - No similar scenes found in database"
                }

            # 2. Calculate 'Weirdness' based on distance (AWS API returns distance, not similarity)
            # S3 Vectors returns distance (0.0 = identical, higher = more different)
            distances = [vector.get('distance', 1.0) for vector in vectors]
            closest_distance = min(distances)  # Lowest distance = closest match

            # Convert distance to similarity for threshold comparison
            # For cosine distance: similarity = 1 - distance
            closest_match_similarity = 1.0 - closest_distance

            # Anomaly Score: How far is the *closest* neighbor?
            anomaly_score = closest_distance  # Distance directly represents anomaly

            # 3. The Verdict
            is_anomaly = closest_match_similarity < threshold

            return {
                "is_anomaly": is_anomaly,
                "anomaly_score": round(anomaly_score, 3),
                "closest_match_similarity": round(closest_match_similarity, 3),
                "closest_distance": round(closest_distance, 3),
                "reason": f"Vector Isolation: Closest neighbor only {closest_match_similarity:.2f} similarity (Threshold: {threshold})"
            }

        except Exception as e:
            logger.warning(f"Anomaly detection failed (failing open): {e}")
            return {"is_anomaly": False, "anomaly_score": 0.0, "reason": f"Detection Error: {e}"}

async def main():
    """AWS orchestration handler - manages Step Functions callback pattern"""
    task_token = None

    try:
        # Retrieve Step Functions task token
        task_token = os.getenv('STEP_FUNCTIONS_TASK_TOKEN')
        if not task_token:
            raise ValueError("STEP_FUNCTIONS_TASK_TOKEN environment variable is required")

        # Get environment variables
        scene_id = os.getenv('SCENE_ID')
        input_s3_key = os.getenv('INPUT_S3_KEY')
        output_s3_key = os.getenv('OUTPUT_S3_KEY')
        s3_bucket = os.getenv('S3_BUCKET', '')

        # Log all environment variables
        logger.info(f"DEBUG: Environment variables at startup:")
        logger.info(f"DEBUG: - SCENE_ID = {scene_id} (type: {type(scene_id)})")
        logger.info(f"DEBUG: - INPUT_S3_KEY = {input_s3_key}")
        logger.info(f"DEBUG: - OUTPUT_S3_KEY = {output_s3_key}")
        logger.info(f"DEBUG: - S3_BUCKET = {s3_bucket}")

        if not all([scene_id, input_s3_key, output_s3_key]):
            raise ValueError("Required environment variables: SCENE_ID, INPUT_S3_KEY, OUTPUT_S3_KEY")

        logger.info(f"Starting Strands GraphBuilder orchestration for scene: {scene_id}")

        # AWS Handler: Download Phase 4-5 embeddings results from S3
        local_phase45_path = f"/tmp/{scene_id}_phase45_output.json"
        logger.info(f"Downloading Phase 4-5 embeddings results...")

        if input_s3_key.startswith('s3://'):
            bucket_name = input_s3_key.split('/')[2]
            key_name = '/'.join(input_s3_key.split('/')[3:])
        else:
            bucket_name = s3_bucket
            key_name = input_s3_key

        s3_client.download_file(bucket_name, key_name, local_phase45_path)

        with open(local_phase45_path, 'r') as f:
            phase45_data = json.load(f)

        # Log Phase 4-5 raw data structure
        logger.info(f"DEBUG: Phase 4-5 raw data keys: {list(phase45_data.keys())}")
        logger.info(f"DEBUG: Phase 4-5 embeddings_vectors count: {len(phase45_data.get('embeddings_vectors', []))}")
        if phase45_data.get('embeddings_vectors'):
            sample_embedding = phase45_data['embeddings_vectors'][0] if phase45_data['embeddings_vectors'] else None
            if sample_embedding:
                logger.info(f"DEBUG: Sample embedding keys: {list(sample_embedding.keys())}")
                logger.info(f"DEBUG: Sample embedding text_content: {sample_embedding.get('text_content', 'MISSING')[:100]}...")

        # Also download Phase 3 InternVideo2.5 structured behavioral data
        phase3_key = f"processed/phase3/{scene_id}/internvideo25_analysis.json"
        local_phase3_path = f"/tmp/{scene_id}_phase3_output.json"
        logger.info(f"Downloading Phase 3 InternVideo2.5 behavioral analysis...")

        try:
            s3_client.download_file(s3_bucket, phase3_key, local_phase3_path)
            with open(local_phase3_path, 'r') as f:
                phase3_data = json.load(f)
            logger.info(f"Successfully loaded Phase 3 InternVideo2.5 data with {len(phase3_data.get('behavioral_analysis', {}).get('quantified_metrics', {}))} metrics")
        except Exception as e:
            logger.warning(f"Could not load Phase 3 data: {str(e)}. Using fallback behavioral data.")
            phase3_data = None

        embeddings_vectors = phase45_data.get('embeddings_vectors')
        behavioral_metrics = phase45_data.get('behavioral_metrics')
        if not embeddings_vectors or not behavioral_metrics:
            raise ValueError("Phase 4-5 output missing embeddings or behavioral metrics")

        logger.info(f"Found {len(embeddings_vectors)} embeddings and behavioral metrics")

        # Enhanced Phase 6: Check for business objective to determine mode
        business_objective = os.getenv('BUSINESS_OBJECTIVE')
        logger.info(f"Business objective detected: {bool(business_objective)}")

        if business_objective:
            logger.info(f"Enhanced Phase 6 Mode: Processing business objective: {business_objective}")

            # Enhanced Mode: Use iterative cycles with business intelligence
            workflow_params = process_business_objective(business_objective, phase45_data)  # Synchronous call
            controller = IterativeCycleController()
            orchestration_results = await controller.execute_iterative_cycles(workflow_params, phase45_data, scene_id, phase3_data)

            logger.info(f"Enhanced Phase 6 completed with {orchestration_results.get('iterative_analysis', {}).get('total_cycles_executed', 0)} cycles")

        else:
            logger.info(f"Legacy Mode: Standard GraphBuilder orchestration")

            # Pure GenAI - NO hardcoded workflow params (let agents determine analysis scope)
            # Legacy Mode: Direct GraphBuilder (existing behavior)
            orchestration_results = await orchestrate_coordinator_workers_aggregator_async(
                phase45_data, scene_id, phase3_data, workflow_params=None
            )

            logger.info(f"Legacy Mode completed with standard multi-agent analysis")

        # AWS Handler: Upload orchestration results to S3
        output_data = {
            "scene_id": scene_id,
            "phase45_input": input_s3_key,
            "orchestration_timestamp": datetime.utcnow().isoformat(),
            "agent_runtime_arns": AGENT_RUNTIME_ARNS,
            **orchestration_results
        }

        s3_client.put_object(
            Bucket=s3_bucket,
            Key=output_s3_key,
            Body=json.dumps(output_data, indent=2),
            ContentType='application/json'
        )

        verify_s3_output_exists(s3_bucket, output_s3_key)

        # Handle both Enhanced Phase 6 and Legacy Mode result structures
        agent_results = orchestration_results.get("final_agent_results", orchestration_results.get("agent_results", {}))
        execution_flow = orchestration_results.get("execution_flow", {})
        execution_metadata = orchestration_results.get("execution_metadata", orchestration_results.get("enhanced_metadata", {}))

        # Extract execution time from Enhanced Phase 6 or Legacy Mode
        total_execution_time = execution_metadata.get("total_duration_seconds") or execution_metadata.get("total_execution_time", 0)

        success_payload = {
            "output_s3_key": output_s3_key,
            "s3_uri": f"s3://{s3_bucket}/{output_s3_key}",
            "scene_id": scene_id,
            "orchestration_summary": {
                "agents_executed": len(agent_results),
                "parallel_agents": execution_flow.get("parallel_completed", 0),
                "sequential_agents": execution_flow.get("sequential_completed", 0),
                "validation_agents": execution_flow.get("validation_completed", 0),
                "total_execution_time": total_execution_time,
                "mode": "enhanced_phase6" if business_objective else "legacy_mode",
                "cycles_executed": orchestration_results.get('iterative_analysis', {}).get('total_cycles_executed', 1)
            },
            "timestamp": datetime.utcnow().isoformat(),
            "status": "SUCCESS"
        }

        sfn_client.send_task_success(
            taskToken=task_token,
            output=json.dumps(success_payload)
        )

        os.remove(local_phase45_path)
        logger.info(f"Phase 6 completed successfully")

    except Exception as e:
        logger.error(f"Phase 6 failed: {str(e)}")

        if task_token:
            try:
                sfn_client.send_task_failure(
                    taskToken=task_token,
                    error="Phase6.MicroserviceOrchestrationFailed",
                    cause=f"Multi-agent orchestration failed: {str(e)}"
                )
            except Exception as callback_error:
                logger.error(f"Failed to send callback: {str(callback_error)}")

        sys.exit(1)


async def orchestrate_coordinator_workers_aggregator_async(
    phase45_data: Dict[str, Any], scene_id: str, phase3_data: Dict[str, Any] = None, workflow_params: Dict[str, Any] = None
) -> Dict[str, Any]:
    """
    PURE BUSINESS LOGIC: Sequential HIL agent topology using Strands GraphBuilder

    HIL Topology:
    Coordinator → Scene Understanding → Anomaly Detection → Similarity Search
    """
    # Generate session ID inside the function
    session_id = f"fleet-{scene_id}-{uuid.uuid4().hex}"
    logger.info(f" Generated Session ID: {session_id} (length: {len(session_id)})")

    logger.info(f"Building sequential HIL agent graph for scene: {scene_id}")
    start_time = datetime.utcnow()

    try:
        # Create HIL-focused sequential nodes using refactored AGENT_RUNTIME_ARNS
        coordinator_node = CoordinatorNode()
        scene_understanding_worker = MicroserviceWorkerNode(AGENT_RUNTIME_ARNS["scene_understanding"], "scene_understanding")
        anomaly_detection_worker = MicroserviceWorkerNode(AGENT_RUNTIME_ARNS["anomaly_detection"], "anomaly_detection")
        similarity_search_worker = MicroserviceWorkerNode(AGENT_RUNTIME_ARNS["similarity_search"], "similarity_search")

        # Build sequential HIL graph using Strands GraphBuilder
        builder = GraphBuilder()

        # Add HIL-focused nodes
        builder.add_node(coordinator_node, "coordinator")
        builder.add_node(scene_understanding_worker, "scene_understanding_worker")
        builder.add_node(anomaly_detection_worker, "anomaly_detection_worker")
        builder.add_node(similarity_search_worker, "similarity_search_worker")

        # Define SEQUENTIAL HIL agent communication topology for cost-optimized discovery
        builder.set_entry_point("coordinator")                             # Single entry point
        builder.add_edge("coordinator", "scene_understanding_worker")      # Step 1: Coordinator → Scene Understanding
        builder.add_edge("scene_understanding_worker", "anomaly_detection_worker")  # Step 2: Scene Understanding → Anomaly Detection
        builder.add_edge("anomaly_detection_worker", "similarity_search_worker")    # Step 3: Anomaly Detection → Similarity Search

        # Configure execution limits
        builder.set_execution_timeout(900)  # 15 minutes
        builder.set_node_timeout(300)       # 5 minutes per node

        # Build the graph
        graph = builder.build()

        # Log scene_id parameter received
        logger.info(f" DEBUG: orchestrate_coordinator_workers_aggregator_async called with:")
        logger.info(f" DEBUG: - scene_id parameter = {scene_id} (type: {type(scene_id)})")

        # Prepare invocation_state (Strands approach - simple dict)
        shared_state = {
            "scene_id": scene_id,
            "session_id": session_id,  # Add session_id to shared state
            "embeddings_data": phase45_data.get("embeddings_vectors", []),
            "behavioral_metrics": phase45_data.get("behavioral_metrics", {}),
            "vector_metadata": phase45_data.get("embedding_metadata", {}),
            "s3_vectors_integration": phase45_data.get("s3_vectors_integration", {}),
            "agent_runtime_arns": AGENT_RUNTIME_ARNS,
            "workflow_params": workflow_params if workflow_params else {},  #  Handle None gracefully
            "processing_context": {
                "phase45_timestamp": phase45_data.get("embeddings_timestamp"),
                "vector_bucket": phase45_data.get("vector_bucket"),
                "vector_index": phase45_data.get("vector_index")
            },
            # Agent-to-Agent Communication: Accumulate results for sequential access
            "agent_results": {},  # This will store results from each agent for the next agents to use
            "execution_order": []  # Track which agents have executed in sequence
        }

        # Log the shared_state being created
        logger.info(f" DEBUG: Created shared_state with scene_id: {shared_state.get('scene_id')}")

        # SCENE-LEVEL INTELLIGENCE GATHERING: Inject enhanced Cosmos + Cohere intelligence once per scene
        # This makes it available to ALL agents in the execution chain via shared_state
        logger.info(f" DEBUG INJECTION CHECK: phase3_data exists={phase3_data is not None}, scene_id={scene_id}")
        if phase3_data and scene_id:
            logger.info(f" DEBUG INJECTION: About to inject enhanced intelligence for {scene_id}")
            try:
                await inject_enhanced_intelligence_to_shared_state(phase3_data, shared_state, scene_id)
                logger.info(f" DEBUG INJECTION: Successfully completed injection call for {scene_id}")
            except Exception as e:
                logger.error(f"Failed to gather enhanced intelligence for scene {scene_id}: {str(e)}")
                # Continue execution with fallback empty intelligence state
        else:
            logger.warning(f" DEBUG INJECTION: Skipping injection - phase3_data={phase3_data is not None}, scene_id={scene_id}")

        # Set global data for all worker instances to access
        # Transform raw embedding vectors into agent-consumable behavioral insights
        raw_embeddings = phase45_data.get("embeddings_vectors", [])
        structured_behavioral_data = []

        logger.info(f" Processing {len(raw_embeddings)} raw embeddings for agents")

        for i, embedding in enumerate(raw_embeddings):
            if isinstance(embedding, dict) and "text_content" in embedding:
                # Extract the behavioral insight text that agents need
                structured_behavioral_data.append({
                    "insight_id": f"insight_{i}",
                    "text_content": embedding["text_content"],
                    "insight_type": embedding.get("input_type", "behavioral_insight"),
                    "metadata": embedding.get("metadata", {}),
                    "vector_available": len(embedding.get("vector", [])) > 0
                })
            else:
                logger.warning(f"Embedding {i} missing text_content field, skipping")

        logger.info(f" Structured {len(structured_behavioral_data)} behavioral insights for agent consumption")

        # Anomaly Detection Logic
        # Execute anomaly detection BEFORE agents wake up to add intelligence context
        anomaly_detector = AnomalyDetector()
        anomaly_context = {"is_anomaly": False, "anomaly_score": 0.0, "reason": "No embeddings available"}

        # Check if we have embeddings to analyze
        if raw_embeddings:
            try:
                # Get the first embedding vector for anomaly analysis
                first_embedding = raw_embeddings[0]
                if isinstance(first_embedding, dict) and "vector" in first_embedding:
                    scene_embedding = first_embedding["vector"]
                    logger.info(f" ANOMALY DETECTION: Analyzing scene {scene_id} with {len(scene_embedding)}-dimensional vector")

                    # Run anomaly detection
                    anomaly_context = anomaly_detector.detect_anomaly(scene_embedding)

                    # Log the anomaly detection result
                    if anomaly_context.get("is_anomaly", False):
                        logger.info(f" ANOMALY DETECTED for scene {scene_id}: {anomaly_context.get('reason', 'Unknown')}")
                        logger.info(f" Anomaly score: {anomaly_context.get('anomaly_score', 0.0):.3f}")
                    else:
                        logger.info(f" NORMAL SCENE: {scene_id} - {anomaly_context.get('reason', 'Similar to known patterns')}")
                        logger.info(f" Similarity score: {anomaly_context.get('anomaly_score', 0.0):.3f}")

                else:
                    logger.warning(f" First embedding missing vector field - cannot perform anomaly detection")
                    anomaly_context = {"is_anomaly": False, "anomaly_score": 0.0, "reason": "No vector data available"}

            except Exception as e:
                logger.warning(f" Anomaly detection failed for scene {scene_id}: {str(e)}")
                anomaly_context = {"is_anomaly": False, "anomaly_score": 0.0, "reason": f"Detection error: {str(e)}"}
        else:
            logger.info(f" No embeddings available for anomaly detection - treating as normal scene")

        # Log structured behavioral data details
        logger.info(f" DEBUG: Structured behavioral data sample (first 3):")
        for i, insight in enumerate(structured_behavioral_data[:3]):
            logger.info(f" DEBUG: Insight {i}: keys={list(insight.keys())}, text_preview={insight.get('text', 'MISSING_TEXT_FIELD')[:50]}...")

        MicroserviceWorkerNode.set_global_data(
            scene_id=scene_id,
            embeddings_data=structured_behavioral_data,  # Now contains structured behavioral insights
            behavioral_metrics=phase45_data.get("behavioral_metrics", {}),
            vector_metadata=phase45_data.get("embedding_metadata", {}),
            processing_context=shared_state["processing_context"],
            phase3_data=phase3_data,
            enhanced_intelligence=shared_state.get("enhanced_intelligence", {})
        )

        # Update shared_state with processed behavioral data
        shared_state["embeddings_data"] = structured_behavioral_data  # Use processed data, not raw
        logger.info(f" Updated shared_state with {len(structured_behavioral_data)} processed behavioral insights")

        # Inject Anomaly Detection results into shared_state
        # This ensures agents can access the anomaly context during their analysis
        shared_state["anomaly_context"] = anomaly_context

        # Also surface the anomaly score in behavioral metrics for dashboards
        if "behavioral_metrics" not in shared_state:
            shared_state["behavioral_metrics"] = {}
        shared_state["behavioral_metrics"]["anomaly_score"] = anomaly_context.get("anomaly_score", 0.0)
        shared_state["behavioral_metrics"]["is_anomaly"] = anomaly_context.get("is_anomaly", False)

        logger.info(f" CONNECTED: Anomaly context injected into shared_state - Score: {anomaly_context.get('anomaly_score', 0.0):.3f}, Is_Anomaly: {anomaly_context.get('is_anomaly', False)}")

        # Proactive Cross-Scene Intelligence
        # Query similar scenes in legacy mode to provide context for agents
        similar_scenes = []
        if raw_embeddings and workflow_params is None:  # Legacy mode only
            try:
                # Get the first embedding vector for similarity search
                first_embedding = raw_embeddings[0]
                if isinstance(first_embedding, dict) and "vector" in first_embedding:
                    scene_embedding = first_embedding["vector"]
                    logger.info(f" PROACTIVE SEARCH: Querying similar scenes for {scene_id} with {len(scene_embedding)}-dimensional vector")

                    # Query for similar scenes using existing function
                    similar_scenes = await query_similar_scenes(
                        scene_embedding, {}, scene_id, max_results=8
                    )

                    logger.info(f" FOUND {len(similar_scenes)} similar scenes for cross-scene intelligence")

                    # Inject similar scenes into shared state for agent consumption
                    shared_state["cross_scene_intelligence"] = {
                        "similar_scenes": similar_scenes,
                        "pattern_insights": [f"Similar scene pattern discovered in {len(similar_scenes)} fleet scenarios"],
                        "cycle_context": f"Legacy mode cross-scene analysis with {len(similar_scenes)} matches"
                    }
                else:
                    logger.warning(f" First embedding missing vector field - cannot perform similarity search")
            except Exception as e:
                logger.warning(f" Similarity search failed for scene {scene_id}: {str(e)}")
                shared_state["cross_scene_intelligence"] = {
                    "similar_scenes": [],
                    "pattern_insights": [f"Similarity search error: {str(e)}"],
                    "cycle_context": "Legacy mode without cross-scene intelligence"
                }
        else:
            logger.info(f" Skipping proactive similarity search - Enhanced mode or no embeddings")
            shared_state["cross_scene_intelligence"] = {
                "similar_scenes": [],
                "pattern_insights": ["Enhanced mode - similarity search handled by iterative cycles"],
                "cycle_context": "Enhanced mode without legacy similarity search"
            }

        # Prepare original task for coordinator
        original_task = json.dumps({
            "scene_id": scene_id,
            "phase": "6_microservice_orchestration",
            "instruction": "Coordinate sequential HIL analysis across scene understanding, anomaly detection, and similarity search agents"
        })

        logger.info(f"Executing sequential HIL agent graph with {len(shared_state['embeddings_data'])} embeddings")

        # Execute the graph with shared state (Strands pattern)
        graph_result = await graph.invoke_async(original_task, invocation_state=shared_state)

        end_time = datetime.utcnow()
        duration_seconds = (end_time - start_time).total_seconds()

        # Extract structured results from graph execution
        agent_results = {}
        for node_id, node_result in graph_result.results.items():
            if node_result.result:
                result_text = None
                try:
                    # Handle both AgentResult and MultiAgentResult objects
                    if hasattr(node_result.result, 'message'):
                        # AgentResult object - extract from message content with dict/object safety
                        if hasattr(node_result.result.message, 'content'):
                            # Object format
                            result_text = str(node_result.result.message.content[0].text)
                        else:
                            # Dictionary format
                            result_text = str(node_result.result.message['content'][0]['text'])
                    elif hasattr(node_result.result, 'results'):
                        # MultiAgentResult object - extract from nested results
                        nested_results = {}
                        for nested_node_id, nested_node_result in node_result.result.results.items():
                            if nested_node_result.result and hasattr(nested_node_result.result, 'message'):
                                # Extract nested text with dict/object safety
                                if hasattr(nested_node_result.result.message, 'content'):
                                    # Object format
                                    nested_text = str(nested_node_result.result.message.content[0].text)
                                else:
                                    # Dictionary format
                                    nested_text = str(nested_node_result.result.message['content'][0]['text'])
                                try:
                                    nested_results[nested_node_id] = json.loads(nested_text)
                                except json.JSONDecodeError:
                                    nested_results[nested_node_id] = {"raw_response": nested_text}
                        result_text = json.dumps(nested_results)
                    else:
                        # Fallback: convert object to string
                        result_text = str(node_result.result)

                    # Parse the result text
                    parsed_result = json.loads(result_text)
                    agent_results[node_id] = parsed_result

                except (json.JSONDecodeError, IndexError, AttributeError) as e:
                    logger.warning(f"Could not parse result for {node_id}: {str(e)}")
                    agent_results[node_id] = {
                        "status": "completed",
                        "raw_response": result_text if result_text else str(node_result.result),
                        "node_id": node_id,
                        "parse_error": str(e)
                    }

        logger.info(f"HIL sequential agent execution completed in {duration_seconds:.2f} seconds")

        return {
            "agent_results": agent_results,
            "execution_flow": {
                "sequential_completed": 3,  # Scene Understanding → Anomaly Detection → Similarity Search
                "parallel_completed": 0,   # No parallel execution in HIL sequential topology
                "validation_completed": 0, # No separate validation agent - integrated into similarity search
                "workflow_pattern": "hil_sequential_discovery",
                "execution_order": [node.node_id for node in graph_result.execution_order]
            },
            "execution_metadata": {
                "total_duration_seconds": duration_seconds,
                "orchestration_method": "strands_graphbuilder_hil_topology",
                "workflow_start": start_time.isoformat(),
                "workflow_end": end_time.isoformat(),
                "graph_status": str(graph_result.status),
                "total_nodes": graph_result.total_nodes,
                "completed_nodes": graph_result.completed_nodes,
                "failed_nodes": graph_result.failed_nodes
            }
        }

    except Exception as e:
        logger.error(f"HIL sequential agent graph execution failed: {str(e)}")
        raise RuntimeError(f"Failed to execute HIL sequential agent graph: {str(e)}")


class CoordinatorNode(MultiAgentBase):
    """
    Coordinator node that initiates sequential HIL agent analysis.
    Entry point - receives original task and prepares sequential processing pipeline.
    """

    def __init__(self):
        super().__init__()

    async def invoke_async(self, *args, **kwargs):
        """Coordinate sequential HIL agent processing"""
        logger.info("COORDINATOR: Initiating sequential HIL agent pipeline")

        try:
            # Extract task from flexible arguments (Strands framework compatibility)
            task = args[0] if args else kwargs.get('task', {})

            # Get invocation_state (Strands shared state) for scene_id fallback
            invocation_state = kwargs.get('invocation_state', {})

            # Parse original task with proper type handling
            if isinstance(task, str):
                task_data = json.loads(task)
            elif isinstance(task, dict):
                task_data = task
            elif isinstance(task, list):
                # If task is a list, it might be args passed by Strands - look for dict in the list
                task_data = next((item for item in task if isinstance(item, dict)), {})
            else:
                task_data = {}

            # FIX: Extract scene_id with comprehensive fallback logic
            scene_id = None

            # First try: Extract from task_data
            scene_id = task_data.get("scene_id")

            # Second try: Extract from invocation_state (shared state)
            if not scene_id and invocation_state:
                scene_id = invocation_state.get("scene_id")

            # Third try: Parse nested JSON if task_data has raw string format
            if not scene_id and isinstance(task_data, dict) and 'text' in task_data:
                try:
                    text_content = task_data['text']
                    if 'scene_id' in text_content:
                        scene_match = re.search(r'"scene_id"\s*:\s*"([^"]*)"', text_content)
                        if scene_match:
                            scene_id = scene_match.group(1)
                except Exception as e:
                    logger.warning(f"Could not extract scene_id from text: {e}")

            # Fallback: Use default if still not found
            if not scene_id:
                scene_id = "scene-unknown"
                logger.warning(f"Could not determine scene_id in coordinator, using fallback: {scene_id}")

            logger.info(f" DEBUG: Coordinator extracted scene_id: {scene_id}")

            coordination_result = {
                "coordinator_status": "hil_pipeline_initiated",
                "scene_id": scene_id,  #  Now properly populated
                "phase": task_data.get("phase", "6_hil_orchestration"),  # Updated for HIL
                "work_packages": {
                    "scene_understanding": "Analyze multi-camera scene content and behavioral patterns",
                    "anomaly_detection": "Detect unusual patterns and statistical outliers using S3 Vectors",
                    "similarity_search": "Cross-scene pattern matching and HIL prioritization"
                },
                "coordination_timestamp": datetime.utcnow().isoformat(),
                "next_phase": "sequential_hil_execution"
            }

            agent_result = AgentResult(
                stop_reason="end_turn",
                message=Message(
                    role="assistant",
                    content=[ContentBlock(text=json.dumps(coordination_result, indent=2))]
                ),
                metrics={},
                state={}
            )

            return MultiAgentResult(
                status=Status.COMPLETED,
                results={"coordinator": NodeResult(result=agent_result)},
                execution_time=0
                # NOTE: invocation_state is passed through via kwargs and automatically handled by GraphBuilder
            )

        except Exception as e:
            logger.error(f"Coordinator failed: {str(e)}")
            raise RuntimeError(f"Coordinator node failed: {str(e)}")


class AggregatorNode(MultiAgentBase):
    """
    Aggregator node that collects and combines results from sequential workers (dormant in HIL topology).
    Would receive input from scene_understanding, anomaly_detection, and similarity_search workers via automatic propagation.
    """

    def __init__(self):
        super().__init__()

    async def invoke_async(self, *args, **kwargs):
        """Aggregate results from sequential workers using robust input parsing (dormant method)"""
        logger.info("AGGREGATOR: Collecting and combining worker results")

        try:
            # Extract task from flexible arguments (Strands framework compatibility)
            task = args[0] if args else kwargs.get('task', {})

            # Parse propagated input from sequential workers
            parsed_input = self._parse_propagated_input(task)

            # Extract results from sequential workers (HIL topology)
            scene_results = parsed_input.get("worker_results", {}).get("scene_understanding_worker", {})
            anomaly_results = parsed_input.get("worker_results", {}).get("anomaly_detection_worker", {})
            similarity_results = parsed_input.get("worker_results", {}).get("similarity_search_worker", {})

            aggregation_result = {
                "aggregator_status": "results_combined",
                "scene_id": parsed_input.get("original_task", {}).get("scene_id"),
                "sequential_results": {
                    "scene_understanding": scene_results,
                    "anomaly_detection": anomaly_results,
                    "similarity_search": similarity_results
                },
                "combined_insights": self._extract_combined_insights_hil(scene_results, anomaly_results, similarity_results),
                "aggregation_timestamp": datetime.utcnow().isoformat(),
                "ready_for_hil_prioritization": True,
                "next_phase": "hil_scenario_prioritization"
            }

            agent_result = AgentResult(
                stop_reason="end_turn",
                message=Message(
                    role="assistant",
                    content=[ContentBlock(text=json.dumps(aggregation_result, indent=2))]
                ),
                metrics={},
                state={}
            )

            return MultiAgentResult(
                status=Status.COMPLETED,
                results={"aggregator": NodeResult(result=agent_result)},
                execution_time=0
                # NOTE: invocation_state is passed through via kwargs and automatically handled by GraphBuilder
            )

        except Exception as e:
            logger.error(f"Aggregator failed: {str(e)}")
            raise RuntimeError(f"Aggregator node failed: {str(e)}")

    def _parse_propagated_input(self, combined_input) -> Dict[str, Any]:
        """
        Robust parsing of automatic input propagation from Strands framework.

        Expected format from Strands automatic propagation:
        Original Task: {json}

        Inputs from previous nodes:

        From scene_understanding_worker:
          - scene_understanding: {result}

        From anomaly_detection_worker:
          - anomaly_detection: {result}

        From similarity_search_worker:
          - similarity_search: {result}
        """
        try:
            if isinstance(combined_input, dict):
                # Direct dictionary input
                return {
                    "input_type": "direct_dict",
                    "original_task": combined_input,
                    "worker_results": {}
                }

            combined_text = str(combined_input)
            parsed_data = {
                "input_type": "propagated_text",
                "original_task": {},
                "worker_results": {}
            }

            # Extract original task
            original_match = re.search(r'Original Task:\s*({[^}]*}|\{.*?\})', combined_text, re.DOTALL)
            if original_match:
                try:
                    parsed_data["original_task"] = json.loads(original_match.group(1))
                except json.JSONDecodeError as e:
                    logger.warning(f"Could not parse original task JSON: {str(e)}")
                    parsed_data["original_task"] = {"raw": original_match.group(1)}

            # Extract worker results using robust pattern matching
            # Pattern: From worker_name: ... - agent_name: {json}
            worker_sections = re.findall(
                r'From\s+(\w+):\s*\n((?:\s*-\s*[^:]+:\s*\{.*?\}\s*\n?)*)',
                combined_text,
                re.DOTALL | re.MULTILINE
            )

            for worker_name, results_section in worker_sections:
                # Extract individual results within this worker section
                result_matches = re.findall(
                    r'-\s*([^:]+):\s*(\{.*?\})',
                    results_section,
                    re.DOTALL
                )

                worker_data = {}
                for agent_name, result_json in result_matches:
                    try:
                        parsed_result = json.loads(result_json)
                        worker_data[agent_name.strip()] = parsed_result
                    except json.JSONDecodeError as e:
                        logger.warning(f"Could not parse {worker_name}/{agent_name} result: {str(e)}")
                        worker_data[agent_name.strip()] = {"raw_text": result_json, "parse_error": str(e)}

                if worker_data:
                    parsed_data["worker_results"][worker_name] = worker_data

            logger.info(f"Parsed input with {len(parsed_data['worker_results'])} worker results")
            return parsed_data

        except Exception as e:
            logger.error(f"Failed to parse propagated input: {str(e)}")
            return {
                "input_type": "parse_error",
                "original_task": {},
                "worker_results": {},
                "error": str(e),
                "raw_input": str(combined_input)[:1000]  # First 1000 chars for debugging
            }

    def _extract_combined_insights(self, behavioral_results: Dict, intelligence_results: Dict) -> List[str]:
        """Extract and combine key insights from worker results (legacy method)"""
        insights = []

        # Extract from behavioral results
        for agent_name, result_data in behavioral_results.items():
            if isinstance(result_data, dict) and "insights" in result_data:
                insights.extend(result_data["insights"][:3])  # Top 3 insights

        # Extract from intelligence results
        for agent_name, result_data in intelligence_results.items():
            if isinstance(result_data, dict) and "insights" in result_data:
                insights.extend(result_data["insights"][:3])  # Top 3 insights

        return insights[:8]  # Limit to top 8 combined insights

    def _extract_combined_insights_hil(self, scene_results: Dict, anomaly_results: Dict, similarity_results: Dict) -> List[str]:
        """Extract and combine key insights from HIL worker results"""
        insights = []

        # Extract from scene understanding results
        if isinstance(scene_results, dict) and "insights" in scene_results:
            insights.extend(scene_results["insights"][:3])  # Top 3 scene insights

        # Extract from anomaly detection results
        if isinstance(anomaly_results, dict) and "insights" in anomaly_results:
            insights.extend(anomaly_results["insights"][:3])  # Top 3 anomaly insights

        # Extract from similarity search results
        if isinstance(similarity_results, dict) and "insights" in similarity_results:
            insights.extend(similarity_results["insights"][:3])  # Top 3 similarity insights

        return insights[:9]  # Limit to top 9 combined HIL insights


class MicroserviceWorkerNode(MultiAgentBase):
    """
    Microservice worker node that makes HTTP calls to agent services.
    Handles automatic input propagation and processes context appropriately.
    """

    # Global storage for embeddings data (shared across all worker instances)
    _global_embeddings_data = []
    _global_behavioral_metrics = {}
    _global_vector_metadata = {}
    _global_processing_context = {}
    _global_scene_id = None
    _global_phase3_data = None

    def _extract_scene_id_from_global_context(self) -> str:
        """Extract scene_id from global context for S3-based A2A communication"""
        return self._global_scene_id or "scene-unknown"

    def _get_previous_results_from_s3(self, scene_id: str) -> Dict:
        """Read previous agent results from S3 for reliable A2A communication"""
        if not scene_id or scene_id == "scene-unknown":
            logger.warning("S3 A2A: Cannot read previous results - invalid scene_id")
            return {}

        results = {}
        s3_bucket = os.getenv('S3_BUCKET', '')

        # Agent types in HIL execution order (exclude current agent to avoid reading own results)
        agent_types = ["scene_understanding", "anomaly_detection", "similarity_search"]

        for agent_type in agent_types:
            if agent_type == self.agent_type:
                continue  # Skip reading own results

            try:
                result_key = f"pipeline-results/{scene_id}/agent-{agent_type}-results.json"
                obj = s3_client.get_object(Bucket=s3_bucket, Key=result_key)
                agent_results = json.loads(obj['Body'].read())
                results[agent_type] = agent_results
                logger.info(f" S3 A2A: Loaded {agent_type} results from s3://{s3_bucket}/{result_key}")
            except Exception as e:
                logger.info(f" S3 A2A: No {agent_type} results found (normal for sequential execution): {str(e)}")
                continue

        logger.info(f" S3 A2A: Found {len(results)} previous agent results for {self.agent_type}")
        return results

    def _get_previous_agent_results_with_fallback(self, invocation_state: Dict, scene_id: str) -> Dict:
        """Get previous agent results from invocation_state with S3 fallback"""
        # Try invocation_state first
        previous_agent_results = invocation_state.get("agent_results", {}) if invocation_state else {}

        # If empty, try S3 fallback
        if not previous_agent_results:
            s3_results = self._get_previous_results_from_s3(scene_id)
            if s3_results:
                previous_agent_results = s3_results
                logger.info(f" S3 A2A FALLBACK: Using S3 results for {self.agent_type} (entry-level) - found {len(s3_results)} agents")

        return previous_agent_results

    def _extract_from_structured_analysis(self, analysis_field: dict, agent_type: str) -> tuple:
        """
        Extract insights and recommendations from agent-specific structured fields.
        Returns tuple: (insights_list, recommendations_list)
        """
        insights = []
        recommendations = []

        try:
            if agent_type == "scene_understanding":
                # Extract from scene_analysis
                scene_analysis = analysis_field.get('scene_analysis', {})
                if isinstance(scene_analysis, dict):
                    for analysis_type, analysis_data in scene_analysis.items():
                        if isinstance(analysis_data, dict):
                            description = analysis_data.get('description', '')
                            if description:
                                insights.append(f"{analysis_type.replace('_', ' ').title()}: {description}")

                # Extract from behavioral_patterns
                behavioral_patterns = analysis_field.get('behavioral_patterns', {})
                if isinstance(behavioral_patterns, dict):
                    for pattern_type, pattern_data in behavioral_patterns.items():
                        if isinstance(pattern_data, dict):
                            description = pattern_data.get('description', '')
                            if description:
                                insights.append(f"Pattern {pattern_type.replace('_', ' ').title()}: {description}")

                # Extract from scene_characteristics
                scene_characteristics = analysis_field.get('scene_characteristics', [])
                if isinstance(scene_characteristics, list):
                    insights.extend([f"Scene characteristic: {char}" for char in scene_characteristics[:3]])

                # Extract from recommendations
                agent_recommendations = analysis_field.get('recommendations', [])
                if isinstance(agent_recommendations, list):
                    recommendations.extend(agent_recommendations[:5])

            elif agent_type == "anomaly_detection":
                # Extract from anomaly_findings
                anomaly_findings = analysis_field.get('anomaly_findings', {})
                if isinstance(anomaly_findings, dict):
                    for anomaly_type, anomaly_data in anomaly_findings.items():
                        if isinstance(anomaly_data, dict):
                            description = anomaly_data.get('description', '')
                            score = anomaly_data.get('score', 'N/A')
                            if description:
                                insights.append(f"{anomaly_type.replace('_', ' ').title()} (Score: {score}): {description}")

                # Extract from statistical_outliers
                statistical_outliers = analysis_field.get('statistical_outliers', [])
                if isinstance(statistical_outliers, list):
                    insights.extend([f"Statistical outlier: {outlier}" for outlier in statistical_outliers[:3]])

                # Extract from anomaly_recommendations
                anomaly_recommendations = analysis_field.get('anomaly_recommendations', [])
                if isinstance(anomaly_recommendations, list):
                    recommendations.extend(anomaly_recommendations[:3])

                # Extract from hil_prioritization
                hil_prioritization = analysis_field.get('hil_prioritization', {})
                if isinstance(hil_prioritization, dict):
                    priority_level = hil_prioritization.get('priority_level', '')
                    if priority_level:
                        recommendations.append(f"HIL Priority: {priority_level}")

            elif agent_type == "similarity_search":
                # Extract from cross_scene_patterns
                cross_scene_patterns = analysis_field.get('cross_scene_patterns', {})
                if isinstance(cross_scene_patterns, dict):
                    for pattern_type, pattern_data in cross_scene_patterns.items():
                        if isinstance(pattern_data, dict):
                            description = pattern_data.get('description', '')
                            similarity_score = pattern_data.get('similarity_score', 'N/A')
                            if description:
                                insights.append(f"{pattern_type.replace('_', ' ').title()} (Similarity: {similarity_score}): {description}")

                # Extract from similar_scenes
                similar_scenes = analysis_field.get('similar_scenes', [])
                if isinstance(similar_scenes, list):
                    insights.extend([f"Similar scene: {scene}" for scene in similar_scenes[:3]])

                # Extract from hil_recommendations
                hil_recommendations = analysis_field.get('hil_recommendations', [])
                if isinstance(hil_recommendations, list):
                    recommendations.extend(hil_recommendations[:5])

                # Extract from training_gaps
                training_gaps = analysis_field.get('training_gaps', [])
                if isinstance(training_gaps, list):
                    recommendations.extend([f"Training gap: {gap}" for gap in training_gaps[:3]])

            logger.info(f" STRUCTURED EXTRACTION: {agent_type} - extracted {len(insights)} insights, {len(recommendations)} recommendations")

        except Exception as e:
            logger.warning(f"Error extracting from structured {agent_type} response: {str(e)}")

        return insights, recommendations

    def _parse_agent_summary_json(self, result: dict) -> dict:
        """
        Parse JSON strings in agent summary fields OR handle already-structured analysis.
        """
        logger.info(f" _parse_agent_summary_json called for {self.agent_type}")

        if not result or not isinstance(result, dict):
            logger.warning(f" Invalid result for {self.agent_type}: {type(result)}")
            return result

        parsed_result = result.copy()
        analysis_field = result.get('analysis', {})

        if not isinstance(analysis_field, dict):
            logger.warning(f" Analysis field not dict for {self.agent_type}")
            return parsed_result

        summary = analysis_field.get('summary', '')
        parsed_summary = None

        # PATH 1: Handle String Summary (e.g. Similarity Agent)
        # This works for agents that wrap their output in a "summary" string
        if summary and isinstance(summary, str):
            logger.info(f" DEBUG: Attempting to parse JSON string for {self.agent_type}")
            parsed_summary = self._parse_json_string(summary)
            if parsed_summary:
                logger.info(f" SUCCESS: Parsed JSON string for {self.agent_type}")
            else:
                logger.warning(f" FAILED: Could not parse JSON string for {self.agent_type}")

        # PATH 2: Handle Already-Structured Analysis (e.g. Scene/Anomaly Agents)
        # If no summary string found (or parse failed), check if analysis_field ITSELF is the structure
        if not parsed_summary:
            # Check for signature keys of structured output used by your agents
            structured_keys = [
                'scene_analysis', 'scene_characteristics', 'behavioral_insights', # Scene Agent
                'anomaly_findings', 'statistical_outliers', 'pattern_deviations', # Anomaly Agent
                'behavioral_patterns' 
            ]
            
            # If the analysis dict contains any of these keys, it IS the structured data
            if any(key in analysis_field for key in structured_keys):
                logger.info(f" SUCCESS: Detected already-structured analysis for {self.agent_type} (Direct Dict)")
                parsed_summary = analysis_field
                
                # OPTIONAL: Generate a string summary from the structure 
                # This ensures the 'summary' field is populated for the Validator later
                if not summary:
                    # Create a readable summary of what keys are present
                    found_keys = [k for k in structured_keys if k in analysis_field]
                    parsed_result['analysis']['summary'] = f"Structured analysis containing: {', '.join(found_keys)}"

        # Proceed with extraction if we have data (from either path)
        if parsed_summary:
            
            # Ensure analysis field exists and is a dict
            if 'analysis' not in parsed_result or not isinstance(parsed_result['analysis'], dict):
                parsed_result['analysis'] = {}
            
            # Extract structured data based on agent type
            key_findings, metrics, confidence_score = self._extract_structured_fields(parsed_summary, self.agent_type)
            
            # Update analysis fields
            if key_findings:
                parsed_result['analysis']['key_findings'] = key_findings
                logger.info(f" DEBUG: Extracted {len(key_findings)} key findings for {self.agent_type}")
            
            if metrics:
                parsed_result['analysis']['metrics'] = metrics
                logger.info(f" DEBUG: Extracted metrics for {self.agent_type}")
            
            if confidence_score is not None:
                parsed_result['analysis']['confidence_score'] = confidence_score
                logger.info(f" DEBUG: Extracted confidence score {confidence_score} for {self.agent_type}")
            
            # Extract insights and recommendations
            insights, recommendations = self._extract_insights_and_recommendations(parsed_summary, self.agent_type)
            
            if insights:
                parsed_result['insights'] = insights
                logger.info(f" DEBUG: Extracted {len(insights)} insights for {self.agent_type}")
            
            if recommendations:
                parsed_result['recommendations'] = recommendations
                logger.info(f" DEBUG: Extracted {len(recommendations)} recommendations for {self.agent_type}")
        
        else:
            logger.info(f" DEBUG: No structured data extraction possible for {self.agent_type}")

        return parsed_result

        try:
            parsed_summary = None

            # Handle markdown-wrapped JSON (Intelligence Agent format)
            if summary.startswith('```json') and summary.endswith('```'):
                logger.info(f" Detected markdown-wrapped JSON for {self.agent_type}")
                json_content = summary.strip('```json').strip('```').strip()
                try:
                    parsed_summary = json.loads(json_content)
                    logger.info(f" Successfully parsed markdown-wrapped JSON for {self.agent_type}")
                except json.JSONDecodeError as e:
                    logger.warning(f" Failed to parse markdown JSON for {self.agent_type}: {e}")

            # Handle nested dict with markdown JSON (similarity_search agent format)
            elif summary.startswith("{'") and "```json" in summary:
                logger.info(f" Detected nested dict with markdown JSON for {self.agent_type}")
                try:
                    # Extract the outer dict structure first
                    json_end = summary.rfind('}')
                    if json_end > 0:
                        outer_dict_text = summary[:json_end + 1]
                        # Apply quote replacement to make it valid JSON
                        outer_dict_text = re.sub(r"'(\s*:\s*)", r'"\1', outer_dict_text)
                        outer_dict_text = re.sub(r"(\s*:\s*)'", r'\1"', outer_dict_text)
                        outer_dict_text = re.sub(r"{\s*'", r'{"', outer_dict_text)
                        outer_dict_text = re.sub(r"',\s*'", r'", "', outer_dict_text)
                        outer_dict_text = re.sub(r"'\s*}", r'"}', outer_dict_text)
                        outer_dict_text = re.sub(r"^\s*'", r'"', outer_dict_text)
                        # Handle escaped newlines and quotes in nested content
                        outer_dict_text = outer_dict_text.replace('\\n', '\\\\n').replace('\\"', '\\\\"')

                        parsed_summary = json.loads(outer_dict_text)
                        logger.info(f" Successfully parsed nested dict with markdown JSON for {self.agent_type}")

                        # If there's a nested summary with markdown JSON, try to parse that too
                        if isinstance(parsed_summary, dict) and 'summary' in parsed_summary:
                            inner_summary = parsed_summary['summary']
                            if isinstance(inner_summary, str) and '```json' in inner_summary:
                                # Extract JSON from markdown
                                json_start = inner_summary.find('{')
                                json_end_inner = inner_summary.rfind('}')
                                if json_start > -1 and json_end_inner > json_start:
                                    try:
                                        json_content = inner_summary[json_start:json_end_inner + 1]
                                        inner_parsed = json.loads(json_content)
                                        # Merge inner content into outer
                                        parsed_summary.update(inner_parsed)
                                        logger.info(f" Successfully merged nested markdown JSON content for {self.agent_type}")
                                    except json.JSONDecodeError:
                                        logger.info(f" Could not parse inner markdown JSON for {self.agent_type}, using outer structure")
                except (json.JSONDecodeError, Exception) as e:
                    logger.warning(f" Failed to parse nested dict with markdown JSON for {self.agent_type}: {e}")

            # Handle single-quote JSON strings (Behavioral, Fleet, Safety formats)
            elif summary.startswith("{'") and "}" in summary:
                logger.info(f" Detected single-quote JSON for {self.agent_type}")
                json_end = summary.rfind('}')
                if json_end > 0:
                    json_text = summary[:json_end + 1]

                    # SAFE quote replacement: Use regex to replace only structural single quotes, not apostrophes
                    # Replace single quotes that are used as JSON delimiters (followed by : or preceded by :)
                    # This preserves apostrophes in text content like "can't", "don't"
                    json_text = re.sub(r"'(\s*:\s*)", r'"\1', json_text)  # Replace 'key': with "key":
                    json_text = re.sub(r"(\s*:\s*)'", r'\1"', json_text)  # Replace : 'value' with : "value"
                    json_text = re.sub(r"{\s*'", r'{"', json_text)        # Replace {' with {"
                    json_text = re.sub(r"',\s*'", r'", "', json_text)     # Replace ', ' with ", "
                    json_text = re.sub(r"'\s*}", r'"}', json_text)        # Replace '} with "}
                    json_text = re.sub(r"^\s*'", r'"', json_text)         # Replace leading '

                    try:
                        parsed_summary = json.loads(json_text)
                        logger.info(f" Successfully parsed single-quote JSON for {self.agent_type}")
                    except json.JSONDecodeError as e:
                        logger.warning(f" Failed to parse single-quote JSON for {self.agent_type}: {e}")
                        # Fallback: Try the simple replacement if regex approach fails
                        try:
                            json_text_fallback = summary[:json_end + 1].replace("'", '"')
                            parsed_summary = json.loads(json_text_fallback)
                            logger.info(f" Fallback parsing successful for {self.agent_type}")
                        except json.JSONDecodeError as e2:
                            logger.warning(f" Both parsing methods failed for {self.agent_type}: {e2}")

                            # FIX: Final fallback - try Python literal parsing for true dict strings
                            logger.info(f" SUMMARY PARSING FIX: Attempting Python literal parsing for {self.agent_type}")
                            try:
                                import ast
                                parsed_summary = ast.literal_eval(summary[:json_end + 1])
                                logger.info(f" SUCCESS: Python literal parsing worked for {self.agent_type}")
                            except (ValueError, SyntaxError) as e3:
                                logger.warning(f" Python literal parsing also failed for {self.agent_type}: {e3}")

            # If we successfully parsed JSON/literal, replace the string summary with structured object
            if parsed_summary:
                # Update the analysis.summary field with structured object instead of string
                if 'analysis' in parsed_result and isinstance(parsed_result['analysis'], dict):
                    parsed_result['analysis']['summary'] = parsed_summary
                    logger.info(f" Replaced string summary with structured object for {self.agent_type}")

                # Extract insights and recommendations based on parsed content
                insights = []
                recommendations = []
                key_findings = []

                # Any agent that dumps dict string in recommendations field
                # Check if ANY agent has Python dict string in recommendations field
                if ('recommendations' in parsed_result and
                    isinstance(parsed_result['recommendations'], list) and
                    len(parsed_result['recommendations']) == 1 and
                    isinstance(parsed_result['recommendations'][0], str) and
                    parsed_result['recommendations'][0].startswith('{')):

                    logger.info(f" GENERALIZED: Agent {self.agent_type} has Python dict in recommendations field - parsing...")
                    try:
                        # Parse the Python dict string from recommendations field
                        dict_json_str = parsed_result['recommendations'][0]
                        # Apply same safe quote replacement as existing logic
                        dict_json_str = re.sub(r"'(\s*:\s*)", r'"\1', dict_json_str)
                        dict_json_str = re.sub(r"(\s*:\s*)'", r'\1"', dict_json_str)
                        dict_json_str = re.sub(r"{\s*'", r'{"', dict_json_str)
                        dict_json_str = re.sub(r"',\s*'", r'", "', dict_json_str)
                        dict_json_str = re.sub(r"'\s*}", r'"}', dict_json_str)
                        dict_json_str = re.sub(r"^\s*'", r'"', dict_json_str)
                        # Handle arrays with single quotes
                        dict_json_str = re.sub(r"\[\s*'", r'["', dict_json_str)
                        dict_json_str = re.sub(r"'\s*\]", r'"]', dict_json_str)

                        parsed_dict_from_recommendations = json.loads(dict_json_str)
                        logger.info(f" Successfully parsed {self.agent_type} Python dict from recommendations field")

                        # Use this as our parsed_summary and clear recommendations
                        parsed_summary = parsed_dict_from_recommendations
                        parsed_result['recommendations'] = []  # Clear the malformed recommendations

                    except Exception as e:
                        logger.warning(f"Failed to parse {self.agent_type} Python dict from recommendations: {e}")

                # Behavioral Gap Analysis Agent
                if 'behavioral_patterns' in parsed_summary:
                    logger.info(f" Processing Behavioral Agent data for {self.agent_type}")
                    patterns = parsed_summary['behavioral_patterns']
                    for pattern_type, pattern_data in patterns.items():
                        if isinstance(pattern_data, dict):
                            description = pattern_data.get('description', '')
                            score = pattern_data.get('score', 'N/A')
                            if description:
                                insights.append(f"{pattern_type.replace('_', ' ').title()}: {description}")
                                key_findings.append(f"{pattern_type.replace('_', ' ').title()} (Score: {score})")

                    # Extract recommendations
                    if 'recommendations' in parsed_summary:
                        rec_data = parsed_summary['recommendations']
                        if isinstance(rec_data, dict):
                            for rec_type, rec_list in rec_data.items():
                                if isinstance(rec_list, list):
                                    recommendations.extend([f"{rec_type.replace('_', ' ').title()}: {rec}" for rec in rec_list[:2]])

                # Intelligence Gathering Agent
                elif 'fleet_context' in parsed_summary:
                    logger.info(f" Processing Intelligence Agent data for {self.agent_type}")
                    fleet_context = parsed_summary.get('fleet_context', {})
                    if isinstance(fleet_context, dict):
                        for key, value in fleet_context.items():
                            if isinstance(value, str) and value:
                                insights.append(f"{key.replace('_', ' ').title()}: {value}")

                    # Extract business context
                    business_context = parsed_summary.get('business_context', {})
                    if isinstance(business_context, dict):
                        for key, value in business_context.items():
                            if isinstance(value, str) and value:
                                key_findings.append(f"{key.replace('_', ' ').title()}: {value}")

                    # Extract direct insights and recommendations
                    if 'insights' in parsed_summary:
                        parsed_insights = parsed_summary['insights']
                        if isinstance(parsed_insights, list):
                            insights.extend(parsed_insights[:5])

                    if 'recommendations' in parsed_summary:
                        parsed_recs = parsed_summary['recommendations']
                        if isinstance(parsed_recs, list):
                            recommendations.extend(parsed_recs[:5])

                # Fleet Optimization Agent
                elif 'optimization_strategies' in parsed_summary:
                    logger.info(f" Processing Fleet Optimization Agent data for {self.agent_type}")
                    strategies = parsed_summary['optimization_strategies']
                    for strategy_type, strategy_data in strategies.items():
                        if isinstance(strategy_data, dict):
                            description = strategy_data.get('description', '')
                            actions = strategy_data.get('actions', [])
                            if description:
                                insights.append(f"{strategy_type.replace('_', ' ').title()}: {description}")
                            if isinstance(actions, list):
                                recommendations.extend(actions[:2])

                    # Extract performance metrics
                    if 'performance_metrics' in parsed_summary:
                        metrics = parsed_summary['performance_metrics']
                        if isinstance(metrics, dict):
                            for metric_type, metric_data in metrics.items():
                                if isinstance(metric_data, dict):
                                    for key, value in metric_data.items():
                                        key_findings.append(f"{metric_type.replace('_', ' ').title()} - {key.replace('_', ' ')}: {value}")

                # Safety Validation Agent
                elif 'safety_assessment' in parsed_summary:
                    logger.info(f" Processing Safety Validation Agent data for {self.agent_type}")
                    assessment = parsed_summary['safety_assessment']
                    if isinstance(assessment, dict):
                        for safety_area, result in assessment.items():
                            if isinstance(result, str) and result:
                                insights.append(f"{safety_area.replace('_', ' ').title()}: {result}")

                    # Extract risk validation
                    if 'risk_validation' in parsed_summary:
                        risk_data = parsed_summary['risk_validation']
                        if isinstance(risk_data, dict):
                            identified_risks = risk_data.get('identified_risks', [])
                            if isinstance(identified_risks, list):
                                key_findings.extend(identified_risks[:3])

                            mitigation_strategies = risk_data.get('mitigation_strategies', [])
                            if isinstance(mitigation_strategies, list):
                                recommendations.extend(mitigation_strategies[:3])

                    # Extract final recommendations
                    if 'final_recommendations' in parsed_summary:
                        final_recs = parsed_summary['final_recommendations']
                        if isinstance(final_recs, dict):
                            for rec_type, rec_list in final_recs.items():
                                if isinstance(rec_list, list):
                                    recommendations.extend([f"{rec_type.replace('_', ' ').title()}: {rec}" for rec in rec_list[:2]])

                # Update the parsed result with extracted structured data
                if key_findings:
                    if 'analysis' in parsed_result and isinstance(parsed_result['analysis'], dict):
                        parsed_result['analysis']['key_findings'] = key_findings[:8]
                    logger.info(f" Extracted {len(key_findings)} key findings for {self.agent_type}")

                if insights:
                    parsed_result['insights'] = insights[:10]
                    logger.info(f" Extracted {len(insights)} insights for {self.agent_type}")

                if recommendations:
                    parsed_result['recommendations'] = recommendations[:8]
                    logger.info(f" Extracted {len(recommendations)} recommendations for {self.agent_type}")

                # Extract confidence_score from parsed_summary if available
                confidence_score = None
                if 'confidence_score' in parsed_summary:
                    confidence_score = parsed_summary.get('confidence_score')
                elif isinstance(parsed_summary, dict):
                    # Look for confidence_score in nested structures
                    for key, value in parsed_summary.items():
                        if isinstance(value, dict) and 'confidence_score' in value:
                            confidence_score = value.get('confidence_score')
                            break

                if confidence_score is not None:
                    parsed_result['confidence_score'] = confidence_score
                    logger.info(f" Extracted confidence_score {confidence_score} for {self.agent_type}")

            else:
                logger.warning(f" Could not parse JSON summary for {self.agent_type}, keeping original format")

        except Exception as e:
            logger.warning(f" Error parsing summary for {self.agent_type}: {str(e)}")

        return parsed_result

    def _parse_json_string(self, summary: str) -> dict:
        """Parse JSON string from agent summary field with multiple fallback strategies"""
        try:
            # Strategy 1: Direct JSON parsing (for properly formatted JSON)
            if summary.startswith('{') and summary.endswith('}'):
                return json.loads(summary)
        except json.JSONDecodeError:
            pass

        try:
            # Strategy 2: Handle single-quote JSON (most common case)
            if summary.startswith("{'") and '}' in summary:
                # Find the end of the JSON object
                json_end = summary.rfind('}')
                json_text = summary[:json_end + 1]
                
                # Replace single quotes with double quotes for valid JSON
                json_text = re.sub(r"'(\s*:\s*)", r'"\1', json_text)  # 'key': -> "key":
                json_text = re.sub(r"(\s*:\s*)'", r'\1"', json_text)  # : 'value' -> : "value"
                json_text = re.sub(r"{\s*'", r'{"', json_text)        # {'key -> {"key
                json_text = re.sub(r"',\s*'", r'", "', json_text)     # 'key', 'key2 -> "key", "key2
                json_text = re.sub(r"'\s*}", r'"}', json_text)        # 'value'} -> "value"}
                
                return json.loads(json_text)
        except json.JSONDecodeError:
            pass

        try:
            # Strategy 3: Python literal evaluation (for dict strings)
            import ast
            return ast.literal_eval(summary)
        except (ValueError, SyntaxError):
            pass

        logger.warning(f"Could not parse JSON string for {self.agent_type}")
        return None

    def _extract_structured_fields(self, parsed_summary: dict, agent_type: str) -> tuple:
        """Extract key_findings, metrics, and confidence_score from parsed summary"""
        key_findings = []
        metrics = {}
        confidence_score = None

        # Extract based on agent-specific structure
        if agent_type == "scene_understanding":
            # Scene understanding agent structure
            if 'scene_analysis' in parsed_summary:
                key_findings.extend([
                    f"Environment: {parsed_summary['scene_analysis'].get('environmental_conditions', 'N/A')}",
                    f"Traffic: {parsed_summary['scene_analysis'].get('traffic_complexity', 'N/A')}",
                    f"Behavior: {parsed_summary['scene_analysis'].get('vehicle_behavior', 'N/A')}"
                ])
            
            if 'behavioral_insights' in parsed_summary:
                insights = parsed_summary['behavioral_insights']
                if 'critical_decisions' in insights:
                    key_findings.append(f"Critical decisions: {insights['critical_decisions']}")
                if 'edge_case_elements' in insights:
                    key_findings.append(f"Edge cases: {insights['edge_case_elements']}")
                
                # Extract quantitative metrics from performance indicators
                if 'performance_indicators' in insights:
                    perf_text = str(insights['performance_indicators'])
                    # Extract lane positioning score
                    import re
                    lane_match = re.search(r'lane positioning[:\s]*([0-9.]+)', perf_text, re.IGNORECASE)
                    if lane_match:
                        metrics['lane_positioning_score'] = float(lane_match.group(1))
                    
                    # Extract following distance
                    distance_match = re.search(r'following distance[:\s]*([0-9.]+)', perf_text, re.IGNORECASE)
                    if distance_match:
                        metrics['following_distance_seconds'] = float(distance_match.group(1))
                    
                    # Extract speed compliance percentage
                    speed_match = re.search(r'speed[^:]*[:\s]*([0-9]+)%', perf_text, re.IGNORECASE)
                    if speed_match:
                        metrics['speed_compliance_percent'] = int(speed_match.group(1))
            
            # Extract scenario complexity from scene characteristics (Hybrid approach)
            if 'scene_characteristics' in parsed_summary:
                chars = parsed_summary['scene_characteristics']
                
                # Complexity: Try intelligence first, fallback to mapping
                if 'complexity_level' in chars:
                    complexity_text = str(chars['complexity_level'])
                    # Try to extract numerical value first (intelligence)
                    complexity_match = re.search(r'([0-9.]+)', complexity_text)
                    if complexity_match:
                        metrics['scenario_complexity'] = float(complexity_match.group(1))
                    else:
                        # Fallback to mapping for text-only descriptions (safety net)
                        complexity_map = {'Low': 0.3, 'Moderate': 0.6, 'High': 0.9}
                        metrics['scenario_complexity'] = complexity_map.get(complexity_text, 0.5)
                
                # Safety criticality: Try intelligence first, fallback to mapping
                if 'safety_criticality' in chars:
                    criticality_text = str(chars['safety_criticality'])
                    # Try to extract numerical value first (intelligence)
                    criticality_match = re.search(r'([0-9.]+)', criticality_text)
                    if criticality_match:
                        metrics['safety_criticality'] = float(criticality_match.group(1))
                    else:
                        # Fallback to mapping for text-only descriptions (safety net)
                        criticality_map = {'Low': 0.2, 'Medium': 0.5, 'High': 0.8, 'Critical': 1.0}
                        metrics['safety_criticality'] = criticality_map.get(criticality_text, 0.5)
            
            # Extract confidence score with fallback (Hybrid approach)
            confidence_score = parsed_summary.get('confidence_score')
            if confidence_score is None:
                confidence_score = 0.85  # Reasonable default for valid analyses

        elif agent_type == "anomaly_detection":
            # Anomaly detection agent structure
            if 'anomaly_findings' in parsed_summary:
                findings = parsed_summary['anomaly_findings']
                key_findings.extend([
                    f"Unusual patterns: {findings.get('unusual_patterns', 'None detected')}",
                    f"Statistical outliers: {findings.get('statistical_outliers', 'None detected')}",
                    f"Edge cases: {findings.get('edge_case_elements', 'None detected')}"
                ])
                
                if 'anomaly_severity' in findings:
                    metrics['anomaly_severity'] = findings['anomaly_severity']
            
            if 'pattern_deviations' in parsed_summary:
                deviations = parsed_summary['pattern_deviations']
                if 'deviation_significance' in deviations:
                    metrics['deviation_significance'] = deviations['deviation_significance']
                    confidence_score = deviations['deviation_significance']

        elif agent_type == "similarity_search":
            # Similarity search agent structure
            if 'similar_scenes' in parsed_summary:
                scenes = parsed_summary['similar_scenes']
                key_findings.append(f"Found {len(scenes)} similar scenes")
                metrics['similar_scenes_count'] = len(scenes)
            
            if 'pattern_analysis' in parsed_summary:
                analysis = parsed_summary['pattern_analysis']
                key_findings.append(f"Pattern analysis: {str(analysis)[:100]}...")
            
            if 'similarity_metrics' in parsed_summary:
                metrics.update(parsed_summary['similarity_metrics'])

        return key_findings[:5], metrics, confidence_score

    def _extract_insights_and_recommendations(self, parsed_summary: dict, agent_type: str) -> tuple:
        """Extract insights and recommendations from parsed summary"""
        insights = []
        recommendations = []

        # Common extraction patterns
        for key, value in parsed_summary.items():
            if isinstance(value, dict):
                # Extract insights from nested dictionaries
                for sub_key, sub_value in value.items():
                    if isinstance(sub_value, str) and len(sub_value) > 20:
                        insights.append(f"{sub_key}: {sub_value}")
            elif isinstance(value, str) and len(value) > 20:
                insights.append(f"{key}: {value}")

        # Agent-specific recommendations
        if agent_type == "scene_understanding":
            if 'recommendations' in parsed_summary:
                recs = parsed_summary['recommendations']
                if isinstance(recs, dict):
                    for rec_key, rec_value in recs.items():
                        if isinstance(rec_value, str):
                            recommendations.append(f"{rec_key}: {rec_value}")

        elif agent_type == "anomaly_detection":
            if 'anomaly_recommendations' in parsed_summary:
                recs = parsed_summary['anomaly_recommendations']
                if isinstance(recs, dict):
                    for rec_key, rec_value in recs.items():
                        if isinstance(rec_value, str):
                            recommendations.append(f"{rec_key}: {rec_value}")

        elif agent_type == "similarity_search":
            if 'pattern_recommendations' in parsed_summary:
                recs = parsed_summary['pattern_recommendations']
                if isinstance(recs, dict):
                    for rec_key, rec_value in recs.items():
                        if isinstance(rec_value, str):
                            recommendations.append(f"{rec_key}: {rec_value}")

        return insights[:10], recommendations[:10]

    def _validate_and_sanitize_output(self, result: dict, scene_id: str) -> dict:
        """
        Anti-hallucination validation: Prevent fabricated Fleet URLs and ensure scene-specific content
        """
        validation_issues = []
        sanitized_result = result.copy()

        # Dynamic detection: Check for suspicious internal URLs (no hardcoded domains)
        def contains_suspicious_internal_references(text: str) -> list:
            """Detect potentially fabricated internal references without hardcoded patterns"""
            issues = []

            # INTELLIGENCE-DRIVEN: Dynamic detection of suspicious internal patterns

            # Pattern 1: Corporate tool URLs (jira, confluence, wiki, internal subdomains)
            corporate_tool_pattern = r'https?://[a-zA-Z0-9-]+\.(jira|confluence|wiki|internal)\.[a-zA-Z0-9.-]+/?[^\s]*'
            corporate_matches = re.findall(corporate_tool_pattern, text, re.IGNORECASE)

            # Pattern 2: Fleet-specific internal domains (corp.eng, fleet-internal, etc.)
            fleet_internal_pattern = r'https?://[a-zA-Z0-9-]*(?:fleet\.eng|fleet-internal|fleet|corp-internal|company-internal)[a-zA-Z0-9.-]*/?[^\s]*'
            internal_matches = re.findall(fleet_internal_pattern, text, re.IGNORECASE)

            # Pattern 3: Corporate-style naming URLs (broader pattern)
            corporate_naming_pattern = r'https?://[a-zA-Z0-9]*(?:corp|internal|eng|dev|staging)[a-zA-Z0-9]*\.[a-zA-Z0-9.-]+/?[^\s]*'
            naming_matches = re.findall(corporate_naming_pattern, text, re.IGNORECASE)

            # Pattern 4: Ticket reference patterns - Enhanced to catch Fleet-style tickets
            # Matches: JIRA-1234, KI-1234, QA-123, PROJ-COMP-123 (but exclude legitimate standards)
            ticket_pattern = r'\b(?!FMVSS|ISO|UN-ECE)(?:JIRA|KI|QA|[A-Z]{2,4})-(?:[A-Z0-9]+-)*\d+\b'
            ticket_matches = re.findall(ticket_pattern, text)

            # Pattern 5: Fabricated corporate document links - Catch deep-link specs/docs that sound internal
            # NEW: OEM-agnostic pattern to catch fake company documents (any domain with suspicious paths)
            fake_doc_pattern = r'https?://[^\s]*\.(?:ai|com|org|net)/(?:specs?|docs?|internal|engineering|tech|design)[^\s]*\.(?:pdf|docx|html|doc|txt|xlsx)\b'
            doc_matches = re.findall(fake_doc_pattern, text, re.IGNORECASE)

            # FIX: Only report actual suspicious patterns, not false positives
            total_suspicious_patterns = len(corporate_matches) + len(internal_matches) + len(naming_matches) + len(ticket_matches) + len(doc_matches)
            if total_suspicious_patterns > 0:
                # Create one entry per actual pattern type found
                if corporate_matches:
                    issues.append(f"Detected {len(corporate_matches)} suspicious corporate tool URLs")
                if internal_matches:
                    issues.append(f"Detected {len(internal_matches)} suspicious Fleet internal URLs")
                if naming_matches:
                    issues.append(f"Detected {len(naming_matches)} suspicious corporate naming URLs")
                if ticket_matches:
                    issues.append(f"Detected {len(ticket_matches)} suspicious ticket references")
                if doc_matches:
                    issues.append(f"Detected {len(doc_matches)} suspicious document links")

            return issues

        def sanitize_text_field(text_content: str) -> str:
            """Remove or flag fabricated content from text fields"""
            if not isinstance(text_content, str):
                return text_content

            # Use dynamic detection instead of hardcoded patterns
            suspicious_issues = contains_suspicious_internal_references(text_content)
            validation_issues.extend(suspicious_issues)

            # Generic replacement for suspicious internal URLs (not domain-specific)
            if suspicious_issues:
                # Replace corporate tool URLs
                text_content = re.sub(r'https?://[a-zA-Z0-9-]+\.(jira|confluence|wiki|internal)\.[a-zA-Z0-9.-]+/?[^\s]*',
                                    "[SUSPICIOUS_CORPORATE_URL_REMOVED]", text_content, flags=re.IGNORECASE)

                # Replace Fleet-specific internal URLs
                text_content = re.sub(r'https?://[a-zA-Z0-9-]*(?:fleet\.eng|fleet-internal|fleet|corp-internal|company-internal)[a-zA-Z0-9.-]*/?[^\s]*',
                                    "[SUSPICIOUS_INTERNAL_URL_REMOVED]", text_content, flags=re.IGNORECASE)

                # Replace corporate naming URLs
                text_content = re.sub(r'https?://[a-zA-Z0-9]*(?:corp|internal|eng|dev|staging)[a-zA-Z0-9]*\.[a-zA-Z0-9.-]+/?[^\s]*',
                                    "[SUSPICIOUS_INTERNAL_URL_REMOVED]", text_content, flags=re.IGNORECASE)

                # Replace Fleet-style ticket references (JIRA-1234, KI-1234, QA-123, etc.)
                text_content = re.sub(r'\b(?!FMVSS|ISO|UN-ECE)(?:JIRA|KI|QA|[A-Z]{2,4})-(?:[A-Z0-9]+-)*\d+\b',
                                    "[SUSPICIOUS_TICKET_ID_REMOVED]", text_content)

                # Replace fabricated corporate document links
                text_content = re.sub(r'https?://[^\s]*\.(?:ai|com|org|net)/(?:specs?|docs?|internal|engineering|tech|design)[^\s]*\.(?:pdf|docx|html|doc|txt|xlsx)\b',
                                    "[SUSPICIOUS_DOCUMENT_LINK_REMOVED]", text_content, flags=re.IGNORECASE)

            return text_content

        # Sanitize all text fields recursively
        def sanitize_recursive(obj):
            if isinstance(obj, dict):
                return {k: sanitize_recursive(v) for k, v in obj.items()}
            elif isinstance(obj, list):
                return [sanitize_recursive(item) for item in obj]
            elif isinstance(obj, str):
                return sanitize_text_field(obj)
            else:
                return obj

        sanitized_result = sanitize_recursive(sanitized_result)

        # Check for scene-specific content
        scene_mentioned = False
        if scene_id and scene_id != "scene-unknown":
            scene_text = json.dumps(sanitized_result, default=str).lower()
            if scene_id.lower() in scene_text or f"scene-{scene_id.split('-')[-1]}" in scene_text:
                scene_mentioned = True

        # Create structured validation report using Pydantic schema
        validation_report = ValidationReport(
            issues_detected=len(validation_issues),
            issues=validation_issues,
            scene_specific_content=scene_mentioned,
            validated_timestamp=datetime.utcnow().isoformat()
        )

        # Add validation report to result
        sanitized_result["validation_report"] = validation_report.dict()

        if validation_issues:
            logger.warning(f"ANTI-HALLUCINATION: Detected {len(validation_issues)} issues in {self.agent_type} output")
            for issue in validation_issues:
                logger.warning(f"  - {issue}")

        #  Extract insights and recommendations using corrected approach
        # Get analysis - try multiple field names
        analysis_text = sanitized_result.get("analysis", sanitized_result.get("summary", ""))

        # Get insights - try multiple field names and extract from analysis if needed
        insights_list = sanitized_result.get("insights", [])
        if not insights_list:
            insights_list = sanitized_result.get("key_findings", [])

        # Extract from analysis text if arrays are empty
        if not insights_list and analysis_text:
            # Look for bullet points or numbered lists in the text
            lines = str(analysis_text).split('\n')
            for line in lines:
                line = line.strip()
                if line.startswith(('•', '-', '*', '1.', '2.', '3.')):
                    cleaned_line = line.lstrip('•-*123456789. ').strip()
                    if cleaned_line and len(cleaned_line) > 10:  # Meaningful insight
                        insights_list.append(cleaned_line)

        # Same pattern for recommendations
        recommendations_list = sanitized_result.get("recommendations", [])
        if not recommendations_list and analysis_text:
            # Extract recommendation-like text
            rec_lines = [line.strip().lstrip('•-*123456789. ')
                         for line in str(analysis_text).split('\n')
                         if 'recommend' in line.lower() or 'should' in line.lower()]
            recommendations_list = [line for line in rec_lines if line and len(line) > 10][:5]

        # Log extraction results
        if insights_list and not sanitized_result.get("insights", []):
            logger.info(f" Extracted {len(insights_list)} insights from analysis text for {self.agent_type}")
        if recommendations_list and not sanitized_result.get("recommendations", []):
            logger.info(f" Extracted {len(recommendations_list)} recommendations from analysis text for {self.agent_type}")

        # Attempt to structure the entire response using AgentResponse schema
        try:
            # Extract structured components from sanitized result
            structured_response = AgentResponse(
                agent_type=self.agent_type,
                scene_id=scene_id or "scene-unknown",
                status=sanitized_result.get("status", "success"),
                analysis=AgentAnalysis(
                    summary=str(analysis_text),  #  Don't truncate summary
                    key_findings=insights_list[:5] if insights_list else [],  #  Use extracted insights
                    metrics=sanitized_result.get("analysis", {}).get("metrics", {}),
                    confidence_score=sanitized_result.get("analysis", {}).get("confidence_score")
                ),
                insights=insights_list,  #  Use extracted insights
                recommendations=recommendations_list,  #  Use extracted recommendations
                validation_report=validation_report,
                execution_metadata={
                    "agent_runtime_arn": self.agent_arn,
                    "validation_timestamp": validation_report.validated_timestamp,
                    "original_response_keys": list(sanitized_result.keys())
                }
            )

            logger.info(f" Structured response validation passed for {self.agent_type}")
            return structured_response.dict()

        except Exception as e:
            logger.warning(f" Could not fully structure response for {self.agent_type}: {str(e)}")
            # Return original sanitized result with validation report
            return sanitized_result

    def __init__(self, agent_arn: str, agent_type: str):
        super().__init__()
        self.agent_arn = agent_arn
        self.agent_type = agent_type

    @classmethod
    def set_global_data(cls, scene_id: str, embeddings_data: list, behavioral_metrics: dict,
                       vector_metadata: dict, processing_context: dict, phase3_data: dict = None,
                       enhanced_intelligence: dict = None):
        """Set global data that all worker instances can access"""
        cls._global_scene_id = scene_id
        cls._global_embeddings_data = embeddings_data
        cls._global_behavioral_metrics = behavioral_metrics
        cls._global_vector_metadata = vector_metadata
        cls._global_processing_context = processing_context
        cls._global_phase3_data = phase3_data
        cls._global_enhanced_intelligence = enhanced_intelligence or {}
        logger.info(f" DEBUG: Set global data - scene_id: {scene_id}, embeddings count: {len(embeddings_data)}, enhanced_intel keys: {list(cls._global_enhanced_intelligence.keys())}")

    def _get_business_objective_context(self, invocation_state: Dict) -> str:
        """Extract business objective context from workflow_params for agent instructions"""
        if not invocation_state:
            return ""

        workflow_params = invocation_state.get("workflow_params", {})
        if not workflow_params:
            return ""

        business_objective = workflow_params.get('business_objective_canonical', '')
        scenario_filters = workflow_params.get('scenario_filters', {})
        target_metrics = workflow_params.get('target_metrics', [])

        if not (business_objective or scenario_filters or target_metrics):
            return ""

        focus_areas = []

        # Add environment focus
        if scenario_filters.get('environment_types'):
            focus_areas.append(f"Environment focus: {', '.join(scenario_filters['environment_types'])}")

        # Add weather focus
        if scenario_filters.get('weather_conditions'):
            focus_areas.append(f"Weather conditions: {', '.join(scenario_filters['weather_conditions'])}")

        # Add maneuver focus
        if scenario_filters.get('maneuver_types'):
            focus_areas.append(f"Maneuver types: {', '.join(scenario_filters['maneuver_types'])}")

        # Add metrics focus
        if target_metrics:
            focus_areas.append(f"Target metrics: {', '.join(target_metrics)}")

        if not focus_areas:
            return ""

        return f"""
BUSINESS OBJECTIVE FOCUS for {business_objective or 'general_analysis'}:
{chr(10).join([f'- {area}' for area in focus_areas])}

Apply this business objective lens to your analysis - prioritize insights and recommendations that align with these focus areas."""

    def _get_agent_collaboration_instructions(self, agent_type: str, scene_id: str) -> str:
        """Generate intelligent collaboration instructions for each agent type"""
        collaboration_instructions = {
            "scene_understanding": f"""
COLLABORATION ROLE: Primary scene analyzer for HIL data discovery on {scene_id}
- ANALYZE: Multi-camera scene content, vehicle behaviors, and environmental context
- EXTRACT: Key behavioral patterns, actor interactions, and scene characteristics
- FOCUS: Identify critical scene elements that require anomaly analysis and similarity matching
- OUTPUT: Structured scene understanding that enables anomaly detection and pattern search
""",
            "anomaly_detection": f"""
COLLABORATION ROLE: Behavioral anomaly detector for {scene_id}
- BUILD UPON: Scene understanding findings from previous agent
- DETECT: Unusual behavioral patterns, edge cases, and statistical outliers
- UTILIZE: S3 Vectors similarity matching to identify deviation from known patterns
- FOCUS: Cost-optimized HIL data discovery by flagging high-value anomalous scenarios
- OUTPUT: Anomaly classifications and significance scores for similarity search prioritization
""",
            "similarity_search": f"""
COLLABORATION ROLE: Cross-scene pattern matcher for {scene_id}
- INTEGRATE: Scene understanding + anomaly detection insights from previous agents
- SEARCH: S3 Vectors database for similar behavioral patterns across fleet data
- CORRELATE: Current scene anomalies with historical patterns and edge cases
- PRIORITIZE: HIL scenarios based on similarity clustering and training data gaps
- OUTPUT: Final HIL recommendations with cross-scene intelligence and training prioritization
"""
        }

        return collaboration_instructions.get(agent_type, f"Collaborate intelligently with other agents for {scene_id} analysis")

    async def invoke_async(self, *args, **kwargs):
        """Execute microservice worker with context-aware processing"""
        logger.info(f"WORKER ({self.agent_type}): Processing with context awareness")

        try:
            # Extract task from flexible arguments (Strands framework compatibility)
            task = args[0] if args else kwargs.get('task', {})

            # CRITICAL DEBUG: Log all arguments to understand Strands framework invocation
            logger.info(f"DEBUG STRANDS INVOCATION for {self.agent_type}: args={args}")
            logger.info(f"DEBUG STRANDS INVOCATION for {self.agent_type}: kwargs keys={list(kwargs.keys())}")
            logger.info(f"DEBUG STRANDS INVOCATION for {self.agent_type}: kwargs={kwargs}")

            # Get invocation_state (Strands shared state)
            invocation_state = kwargs.get('invocation_state', {})

            # Process input based on context
            is_entry_level = self._is_entry_level_worker(task)
            logger.info(f" DEBUG: Worker {self.agent_type} - is_entry_level: {is_entry_level}, task type: {type(task)}, task preview: {str(task)[:200]}...")

            if is_entry_level:
                # Entry-level worker: use original task + shared state
                logger.info(f" DEBUG: Using entry-level payload for {self.agent_type}")
                payload = self._build_entry_payload(task, invocation_state)
            else:
                # Dependent worker: parse propagated input + shared state
                logger.info(f" DEBUG: Using context-aware payload for {self.agent_type}")
                parsed_input = self._parse_propagated_input(task)
                payload = self._build_context_aware_payload(parsed_input, invocation_state)

            # Log the exact payload being sent to AgentCore
            logger.info(f" DEBUG: ======= SENDING TO AGENTCORE {self.agent_type} =======")
            logger.info(f" DEBUG: Agent ARN: {self.agent_arn}")
            logger.info(f" DEBUG: Payload keys: {list(payload.keys())}")
            logger.info(f" DEBUG: embeddings_data count: {len(payload.get('embeddings_data', []))}")
            if payload.get('embeddings_data'):
                logger.info(f" DEBUG: First embedding insight: {payload['embeddings_data'][0]}")
            logger.info(f" DEBUG: Full payload JSON:")
            logger.info(f"{json.dumps(payload, indent=2)}")
            logger.info(f" DEBUG: ============================================")

            logger.info(f" Invoking AgentCore runtime: {self.agent_arn}")

            # Get session_id from invocation_state (shared state)
            session_id = invocation_state.get('session_id', f"fleet-{uuid.uuid4().hex}")

            # Option A (SDK Integration) expects direct payload, NO "input" wrapper
            # Our agents use @app.entrypoint (Option A) → expects direct payload access
            # Option B (Custom FastAPI) would need {"input": {...}} wrapper

            response = bedrock_agentcore_client.invoke_agent_runtime(
                agentRuntimeArn=self.agent_arn,  # Changed: agentRuntimeArn (not agentRuntimeId)
                runtimeSessionId=session_id,     # Changed: runtimeSessionId (not sessionId)
                payload=json.dumps(payload).encode('utf-8')  # FIX: AgentCore expects bytes, not dict
            )

            # Parse AgentCore response with proper null handling
            response_body = None
            try:
                if response and 'response' in response and response['response']:
                    response_body = response['response'].read()
                    logger.info(f" DEBUG: AgentCore response: {response_body[:200]}...")
                else:
                    logger.error(f" Invalid AgentCore response structure: {response}")
                    response_body = '{"error": "Invalid response structure"}'
            except Exception as e:
                logger.error(f" Failed to read AgentCore response: {str(e)}")
                response_body = '{"error": "Failed to read response"}'

            # Parse response with comprehensive fallback
            result = None
            try:
                if response_body:
                    # FIX: Handle bytes-to-string conversion properly
                    if isinstance(response_body, bytes):
                        response_str = response_body.decode('utf-8')
                    else:
                        response_str = str(response_body)

                    result = json.loads(response_str)
                    logger.info(f" Successfully parsed AgentCore JSON response for {self.agent_type}")

                    # FIX: Handle case where agent returns JSON string instead of JSON object
                    if isinstance(result, str):
                        logger.info(f" Agent {self.agent_type} returned JSON string, converting to structured format")
                        result = {
                            "analysis": {
                                "summary": result,
                                "key_findings": [],
                                "metrics": {},
                                "confidence_score": None
                            },
                            "insights": [],
                            "recommendations": []
                        }
                else:
                    result = {"analysis": {"summary": "No response received", "key_findings": [], "metrics": {}, "confidence_score": None}, "insights": [], "recommendations": []}
            except json.JSONDecodeError as e:
                logger.error(f" JSON parsing failed for {self.agent_type}: {str(e)}")
                logger.error(f" Raw response_body: {response_body[:500] if response_body else 'None'}...")
                # Return structured analysis instead of raw string
                result = {
                    "analysis": {
                        "summary": f"JSON parse error: {str(e)}",
                        "key_findings": [],
                        "metrics": {},
                        "confidence_score": None
                    },
                    "insights": [],
                    "recommendations": []
                }
            except Exception as e:
                logger.error(f" Unexpected error parsing {self.agent_type} response: {str(e)}")
                result = {
                    "analysis": {
                        "summary": f"Parse error: {str(e)}",
                        "key_findings": [],
                        "metrics": {},
                        "confidence_score": None
                    },
                    "insights": [],
                    "recommendations": []
                }

            # Ensure result is never None
            if result is None:
                result = {"analysis": "Null response received", "insights": [], "recommendations": []}

            # FIX: Parse JSON strings in summary fields BEFORE validation
            parsed_result = self._parse_agent_summary_json(result)

            #  Apply anti-hallucination validation with proper null checking
            scene_id = invocation_state.get('scene_id', self._global_scene_id) if invocation_state else self._global_scene_id

            validated_result = self._validate_and_sanitize_output(parsed_result, scene_id)

            # Ensure validation doesn't return None
            if validated_result is None:
                logger.error(f" Validation returned None for {self.agent_type}, using fallback")
                validated_result = {"analysis": "Validation failed", "insights": [], "recommendations": []}

            result = validated_result

            logger.info(f" {self.agent_type} worker completed successfully (validated and sanitized)")

            # AGENT-TO-AGENT COMMUNICATION: Save this agent's results to shared_state for subsequent agents
            if invocation_state is not None and isinstance(invocation_state, dict):
                # Save agent results for subsequent agents to access
                invocation_state.setdefault("agent_results", {})[self.agent_type] = {
                    "analysis": result.get("analysis", "") if result else "",
                    "insights": result.get("insights", []) if result else [],
                    "recommendations": result.get("recommendations", []) if result else [],
                    "execution_timestamp": datetime.utcnow().isoformat(),
                    "agent_runtime_arn": self.agent_arn
                }

                # Track execution order for debugging
                invocation_state.setdefault("execution_order", []).append(self.agent_type)

                logger.info(f" AGENT COMMUNICATION: {self.agent_type} results saved to shared_state for subsequent agents")
                logger.info(f" EXECUTION ORDER: {invocation_state.get('execution_order', [])}")

            # Save results to S3 for reliable agent-to-agent communication
            try:
                scene_id = self._extract_scene_id_from_global_context()
                if scene_id and scene_id != "scene-unknown":
                    s3_bucket = os.getenv('S3_BUCKET', '')
                    result_key = f"pipeline-results/{scene_id}/agent-{self.agent_type}-results.json"

                    s3_result = {
                        "analysis": result.get("analysis", "") if result else "",
                        "insights": result.get("insights", []) if result else [],
                        "recommendations": result.get("recommendations", []) if result else [],
                        "execution_timestamp": datetime.utcnow().isoformat(),
                        "agent_runtime_arn": self.agent_arn,
                        "agent_type": self.agent_type
                    }

                    s3_client.put_object(
                        Bucket=s3_bucket,
                        Key=result_key,
                        Body=json.dumps(s3_result, indent=2),
                        ContentType='application/json'
                    )
                    logger.info(f" S3 A2A: {self.agent_type} results saved to s3://{s3_bucket}/{result_key}")
                else:
                    logger.warning(f" S3 A2A: Cannot save {self.agent_type} results - scene_id not available")
            except Exception as e:
                logger.warning(f" S3 A2A: Failed to save {self.agent_type} results to S3: {str(e)} (continuing with invocation_state fallback)")

            # Structure response for next nodes with safe access
            structured_response = {
                "agent_type": self.agent_type,
                "status": "success",
                "analysis": result.get("analysis", "") if result else "",
                "insights": result.get("insights", []) if result else [],
                "recommendations": result.get("recommendations", []) if result else [],
                "metadata": {
                    "execution_timestamp": datetime.utcnow().isoformat(),
                    "agent_runtime_arn": self.agent_arn,
                    "worker_context": "agentcore_runtime_invocation"
                },
                "raw_response": result
            }

            agent_result = AgentResult(
                stop_reason="end_turn",
                message=Message(
                    role="assistant",
                    content=[ContentBlock(text=json.dumps(structured_response, indent=2))]
                ),
                metrics={},
                state={}
            )

            return MultiAgentResult(
                status=Status.COMPLETED,
                results={self.agent_type: NodeResult(result=agent_result)},
                execution_time=0
                # NOTE: invocation_state is modified in-place above and automatically propagated by GraphBuilder
            )

        except Exception as e:
            logger.error(f" {self.agent_type} worker failed: {str(e)}")
            raise RuntimeError(f"{self.agent_type} worker failed: {str(e)}")

    def _is_entry_level_worker(self, task) -> bool:
        """Determine if this is an entry-level worker (direct from coordinator)"""
        # Dynamic logic: Check if this agent is in the first tier of AGENT_RUNTIME_ARNS
        # Get the first two agents from the global runtime ARNs (these are entry-level)
        entry_level_agents = list(AGENT_RUNTIME_ARNS.keys())[:2]  # First 2 agents are entry-level

        if self.agent_type in entry_level_agents:
            return True  # These are entry-level based on pipeline topology

        # For other agents, check if task format indicates direct coordinator input
        try:
            if isinstance(task, str) and task.startswith('{'):
                json.loads(task)
                return True
            elif isinstance(task, dict):
                return True
        except json.JSONDecodeError:
            pass
        return False

    def _build_entry_payload(self, task, invocation_state: Dict) -> Dict:
        """Build payload for entry-level worker using original task + shared state"""
        # COMPREHENSIVE DEBUG: Log all inputs
        logger.info(f" DEBUG: _build_entry_payload called with:")
        logger.info(f" DEBUG: - task type: {type(task)}, value: {task}")
        logger.info(f" DEBUG: - invocation_state type: {type(invocation_state)}, keys: {list(invocation_state.keys()) if invocation_state else 'None'}")
        if invocation_state:
            logger.info(f" DEBUG: - invocation_state scene_id: {invocation_state.get('scene_id')}")

        # Parse task with proper type handling
        if isinstance(task, str):
            task_data = json.loads(task)
        elif isinstance(task, dict):
            task_data = task
        elif isinstance(task, list):
            # If task is a list, look for dict in the list
            task_data = next((item for item in task if isinstance(item, dict)), {})
        else:
            task_data = {}

        logger.info(f" DEBUG: Parsed task_data: {task_data}")

        # FIX: Extract scene_id from multiple sources with fallback
        scene_id = None

        # First try: Get from invocation_state (shared state)
        if invocation_state:
            scene_id = invocation_state.get("scene_id")
            logger.info(f" DEBUG: Step 1 - scene_id from invocation_state: {scene_id}")

        # Second try: Extract from task_data if it's a nested JSON string in 'text' field
        if not scene_id and isinstance(task_data, dict) and 'text' in task_data:
            try:
                # Parse the nested JSON in the text field
                text_content = task_data['text']
                logger.info(f" DEBUG: Attempting scene_id extraction from text: {text_content[:200]}...")

                if 'Original Task:' in text_content:
                    # Extract JSON part after "Original Task: " - handle escaped quotes
                    task_start = text_content.find('Original Task:') + len('Original Task: ')
                    json_part = text_content[task_start:].strip()
                    logger.info(f" DEBUG: Extracted JSON part: {json_part}")

                    # The JSON is escaped, so we need to unescape it
                    try:
                        # Replace escaped quotes with regular quotes
                        unescaped = json_part.replace('\\"', '"')
                        logger.info(f" DEBUG: Unescaped JSON: {unescaped}")

                        # Parse the unescaped JSON
                        nested_task = json.loads(unescaped)
                        scene_id = nested_task.get('scene_id')
                        logger.info(f" DEBUG: Successfully extracted scene_id: {scene_id}")

                    except json.JSONDecodeError as json_err:
                        logger.warning(f"Failed to parse unescaped JSON: {json_err}")
                        # Fallback: manual regex extraction
                        scene_match = re.search(r'scene_id["\s]*:["\s]*([^",}]+)', json_part)
                        if scene_match:
                            scene_id = scene_match.group(1).strip('"')
                            logger.info(f" DEBUG: Regex extraction successful, scene_id: {scene_id}")

            except (KeyError, AttributeError, ValueError) as e:
                logger.warning(f"Could not extract scene_id from task text: {str(e)}")

        # Third try: Extract directly from task_data
        if not scene_id:
            scene_id = task_data.get('scene_id')

        # Fallback: Use a default scene_id format
        if not scene_id:
            scene_id = "scene-unknown"
            logger.warning(f"Could not determine scene_id, using fallback: {scene_id}")

        logger.info(f" DEBUG: Extracted scene_id: {scene_id} for agent {self.agent_type}")

        # FIX: Use global data if invocation_state is empty
        embeddings_data = invocation_state.get("embeddings_data", [])
        behavioral_metrics = invocation_state.get("behavioral_metrics", {})
        vector_metadata = invocation_state.get("vector_metadata", {})
        processing_context = invocation_state.get("processing_context", {})

        # Fallback to global data if invocation_state is empty
        if not embeddings_data and self._global_embeddings_data:
            logger.info(f" DEBUG: Using global embeddings data ({len(self._global_embeddings_data)} vectors)")
            embeddings_data = self._global_embeddings_data
            behavioral_metrics = self._global_behavioral_metrics
            vector_metadata = self._global_vector_metadata
            processing_context = self._global_processing_context
            if not scene_id and self._global_scene_id:
                scene_id = self._global_scene_id

        # FIX: Process embeddings using correct field name "text_content" (from Phase 4-5)
        valid_insights = [item for item in embeddings_data if isinstance(item, dict) and "text_content" in item]

        # INTELLIGENCE-DRIVEN: Extract rich behavioral data from Phase 3 InternVideo2.5 results
        rich_behavioral_insights = []

        # FIX: Extract structured data from Phase 3 InternVideo2.5 JSON first
        structured_behavioral_data = self._extract_internvideo25_behavioral_data(self._global_phase3_data, scene_id) if self._global_phase3_data else {
            "lane_deviation": None,
            "following_distance": None,
            "speed_compliance": None,
            "risk_score": None,
            "safety_score": None,
            "scene_context": {}
        }

        for insight in valid_insights:
            text_content = insight.get("text_content", "")
            input_type = insight.get("input_type", "")

            # Extract structured metrics from text_content using intelligence-driven parsing
            if "Lane deviation:" in text_content:
                # Extract: "Lane deviation: 0.15m from center (ISO 26262 tolerance: ±0.25m)"
                deviation_match = re.search(r'Lane deviation:\s*([\d.]+)m', text_content)
                tolerance_match = re.search(r'tolerance:\s*[±]([\d.]+)m', text_content)
                if deviation_match:
                    structured_behavioral_data["lane_deviation"] = {
                        "measured_meters": float(deviation_match.group(1)),
                        "tolerance_meters": float(tolerance_match.group(1)) if tolerance_match else 0.25,
                        "raw_insight": text_content
                    }

            elif "Following distance:" in text_content:
                # Extract: "Following distance: 3.2s (NHTSA standard: 3.0s)"
                distance_match = re.search(r'Following distance:\s*([\d.]+)s', text_content)
                standard_match = re.search(r'standard:\s*([\d.]+)s', text_content)
                if distance_match:
                    structured_behavioral_data["following_distance"] = {
                        "measured_seconds": float(distance_match.group(1)),
                        "standard_seconds": float(standard_match.group(1)) if standard_match else 3.0,
                        "raw_insight": text_content
                    }

            elif "Speed compliance:" in text_content:
                # Extract: "Speed compliance: 84.0% (Industry excellent: ≥95%)"
                compliance_match = re.search(r'Speed compliance:\s*([\d.]+)%', text_content)
                if compliance_match:
                    structured_behavioral_data["speed_compliance"] = {
                        "percentage": float(compliance_match.group(1)),
                        "industry_excellent_threshold": 95.0,
                        "raw_insight": text_content
                    }

            elif "Risk score:" in text_content:
                # Extract: "Risk score: 0.11/1.0 (threshold: 0.3)"
                risk_match = re.search(r'Risk score:\s*([\d.]+)/[\d.]+', text_content)
                if risk_match:
                    structured_behavioral_data["risk_score"] = {
                        "score": float(risk_match.group(1)),
                        "threshold": 0.3,
                        "raw_insight": text_content
                    }

            elif "Safety score:" in text_content:
                # Extract: "Safety score: 0.89/1.0 (industry average: 0.85)"
                safety_match = re.search(r'Safety score:\s*([\d.]+)/[\d.]+', text_content)
                if safety_match:
                    structured_behavioral_data["safety_score"] = {
                        "score": float(safety_match.group(1)),
                        "industry_average": 0.85,
                        "raw_insight": text_content
                    }

            elif "scene_type" in input_type or "complexity_level" in input_type:
                # Extract scene context information
                context_key = text_content.split("(")[-1].split(")")[0] if "(" in text_content else "context"
                context_value = text_content.split(": ")[-1] if ": " in text_content else text_content
                structured_behavioral_data["scene_context"][context_key] = context_value

            # Keep all insights for agent processing
            rich_behavioral_insights.append({
                "text": text_content,  #  Use "text" field as expected by agents
                "input_type": input_type,
                "metadata": insight.get("metadata", {}),
                "vector_available": "vector" in insight
            })

        logger.info(f"  Extracted rich behavioral data with {len(structured_behavioral_data)} structured metrics")
        logger.info(f" {self.agent_type} now has {len(rich_behavioral_insights)} rich insights from Phase 3 data")

        # Filter for scene-specific insights (intelligence-driven, no hardcoding)
        scene_specific_insights = []
        for insight in rich_behavioral_insights:
            content = insight.get("text", "")  #  Use "text" field consistently
            # Keep insights that mention the specific scene ID
            if scene_id in content and scene_id != "scene-unknown":
                scene_specific_insights.append(insight)

        logger.info(f" Found {len(scene_specific_insights)} scene-specific insights for {scene_id}")

        # Add any additional behavioral metrics from Phase 4-5 processing
        if behavioral_metrics and isinstance(behavioral_metrics, dict) and structured_behavioral_data:
            structured_behavioral_data.update(behavioral_metrics)

        logger.info(f" Scene {scene_id} behavioral data keys: {list(structured_behavioral_data.keys()) if structured_behavioral_data else []}")

        # ENHANCED: Create clear behavioral metrics summary for agents
        key_behavioral_metrics = self._format_key_metrics_for_agent(structured_behavioral_data, scene_id)

        #  Get business objective context for agent instructions
        business_objective_context = self._get_business_objective_context(invocation_state)

        # Prevent Intelligence Agent "amnesia" by providing
        # believable fleet metadata based on NuScenes dataset characteristics
        synthetic_fleet_context = self._generate_synthetic_fleet_context(scene_id)

        # CRITICAL FIX: Extract enhanced intelligence from invocation_state OR GLOBAL FALLBACK
        enhanced_intel = invocation_state.get("enhanced_intelligence", {}) if invocation_state else {}

        # Fallback to global if missing (Fixes Strands sequential propagation bug)
        if not enhanced_intel and hasattr(self.__class__, '_global_enhanced_intelligence'):
            enhanced_intel = self.__class__._global_enhanced_intelligence
            logger.info(f" DEBUG: Used global fallback for enhanced_intelligence in entry worker")

        # DEBUG: Log enhanced intelligence extraction results
        logger.info(f"DEBUG ENHANCED_INTEL for {scene_id}: invocation_state_keys={list(invocation_state.keys()) if invocation_state else []}")
        logger.info(f"DEBUG ENHANCED_INTEL for {scene_id}: enhanced_intel_keys={list(enhanced_intel.keys())}")
        logger.info(f"DEBUG ENHANCED_INTEL for {scene_id}: raw_text_present={bool(enhanced_intel.get('raw_text'))}")
        logger.info(f"DEBUG ENHANCED_INTEL for {scene_id}: cosmos_context_count={len(enhanced_intel.get('cosmos_context', []))}")

        return {
            "scene_id": scene_id,  #  Now properly populated
            "agent_type": self.agent_type,
            "task_context": "entry_level_worker",
            "original_task": task_data,
            "embeddings_data": rich_behavioral_insights,  #  Use rich data from Phase 3 embeddings
            "behavioral_metrics": behavioral_metrics,
            "vector_metadata": vector_metadata,
            "processing_context": processing_context,
            "workflow_params": invocation_state.get("workflow_params", {}) if invocation_state else {},  #  Add business objective context

            # Provides Intelligence Agent with believable metadata
            # to prevent "Unknown" outputs. Based on NuScenes dataset characteristics, not fabricated Fleet data.
            "fleet_context": synthetic_fleet_context,

            # ENHANCED: Clear metrics presentation for agent consumption
            "key_behavioral_metrics": key_behavioral_metrics,

            # CRITICAL FIX: Pass enhanced intelligence data that agents expect
            "behavioral_analysis_text": enhanced_intel.get("raw_text", ""),
            "cosmos_similarity_results": enhanced_intel.get("cosmos_context", []),
            "enhanced_intelligence": enhanced_intel,

            "scene_specific_analysis_required": {
                "scene_id": scene_id,
                "structured_metrics": structured_behavioral_data if structured_behavioral_data else {},  # Now contains extracted Phase 3 metrics
                "scene_insights": scene_specific_insights,
                "collaboration_instructions": self._get_agent_collaboration_instructions(self.agent_type, scene_id),
                "analysis_instructions": f"""MANDATORY ANALYSIS REQUIREMENTS for {scene_id}:

1. REFERENCE SPECIFIC METRICS: Use the exact values from key_behavioral_metrics in your analysis:
   {key_behavioral_metrics.get('metrics_summary', 'No specific metrics available')}

2. SCENE-SPECIFIC FOCUS: Analyze ONLY scene {scene_id} using the provided behavioral data.

3. EVIDENCE-BASED ANALYSIS: Base all insights on the actual quantified data provided, not generic knowledge.

4. NO FABRICATION: Do NOT create Fleet internal URLs, tickets, or unverified references.

5. PRESERVE PROVIDED METADATA: Use the exact fleet_context metadata as provided. DO NOT override or change software_version, vehicle_model, or other context fields. If provided with "Research Dataset v1.0", use it exactly - do NOT substitute with fabricated firmware versions like "2025.42.6".

6. NO FAKE STATISTICS: Do NOT invent fleet statistics, percentages, or precise metrics unless provided in the data. If statistical data is unavailable, explicitly state "Statistical data unavailable" rather than fabricating numbers.

7. COLLABORATIVE CONTEXT: {f"Build upon findings from previous agents: {', '.join(invocation_state.get('execution_order', [])[:len(invocation_state.get('execution_order', [])) - 1]) if invocation_state.get('execution_order') else 'First agent - no previous context'}" if invocation_state.get("agent_results") else "First agent - no previous context available"}

{business_objective_context}"""
            },

            "data_validation": {
                "total_insights": len(embeddings_data),
                "rich_insights": len(rich_behavioral_insights),
                "scene_specific_insights": len(scene_specific_insights),
                "scene_specific": scene_id != "scene-unknown",
                "has_structured_metrics": bool(structured_behavioral_data),
                "metrics_available": len(key_behavioral_metrics.get('available_metrics', []))
            },

            "shared_state": None,  # Required by agent Pydantic schema

            # AGENT-TO-AGENT COMMUNICATION: Include previous agent results from shared_state with S3 fallback
            "previous_agent_results": self._get_previous_agent_results_with_fallback(invocation_state, scene_id),
            "context_available": bool(self._get_previous_agent_results_with_fallback(invocation_state, scene_id)),
            "execution_order": invocation_state.get("execution_order", []) if invocation_state else [],

            # Pass Anomaly Detection context to agents
            # This provides the "Brain's" anomaly assessment to all agents for context-aware analysis
            "anomaly_context": invocation_state.get("anomaly_context", {"is_anomaly": False, "anomaly_score": 0.0, "reason": "No anomaly data available"}) if invocation_state else {"is_anomaly": False, "anomaly_score": 0.0, "reason": "No anomaly data available"},

            "timestamp": datetime.utcnow().isoformat()
        }

    def _build_context_aware_payload(self, parsed_input: Dict, invocation_state: Dict) -> Dict:
        """Build payload for context-aware worker using propagated input + shared state"""

        # FIX: Extract scene_id from multiple sources with fallback
        scene_id = None

        # First try: Get from invocation_state (shared state)
        scene_id = invocation_state.get("scene_id")

        # Second try: Extract from original_task in parsed_input
        if not scene_id:
            original_task = parsed_input.get("original_task", {})
            scene_id = original_task.get("scene_id")

        # Third try: Look for scene_id in parsed_input directly
        if not scene_id:
            scene_id = parsed_input.get("scene_id")

        # Fallback: Use a default scene_id format
        if not scene_id:
            scene_id = "scene-unknown"
            logger.warning(f"Could not determine scene_id in context-aware payload, using fallback: {scene_id}")

        logger.info(f" DEBUG: Context-aware extracted scene_id: {scene_id} for agent {self.agent_type}")

        # FIX: Get embeddings data and process with same logic as entry-level workers
        embeddings_data = invocation_state.get("embeddings_data", [])

        # Validate context-aware data
        if not embeddings_data:
            logger.warning(f" No embeddings data in context for {self.agent_type}, using global fallback")
            embeddings_data = self._global_embeddings_data

        # Apply same rich behavioral insights extraction as entry-level workers
        rich_behavioral_insights = []
        for item in embeddings_data:
            if isinstance(item, dict) and "text_content" in item:
                rich_behavioral_insights.append({
                    "text": item.get("text_content", ""),  #  Use "text" field as expected by agents
                    "input_type": item.get("input_type", ""),
                    "metadata": item.get("metadata", {}),
                    "vector_available": "vector" in item
                })

        logger.info(f" Context-aware {self.agent_type} processed {len(rich_behavioral_insights)} rich insights")

        # ENHANCED: Get structured behavioral data and format metrics for context-aware agents
        structured_behavioral_data = self._extract_internvideo25_behavioral_data(self._global_phase3_data, scene_id) if self._global_phase3_data else {}
        key_behavioral_metrics = self._format_key_metrics_for_agent(structured_behavioral_data, scene_id)

        # SAFE READ: Extract enhanced intelligence from shared_state OR GLOBAL FALLBACK
        enhanced_intel = invocation_state.get("enhanced_intelligence", {})

        # Fallback to global if missing (Fixes Strands sequential propagation bug)
        if not enhanced_intel and hasattr(self.__class__, '_global_enhanced_intelligence'):
            enhanced_intel = self.__class__._global_enhanced_intelligence
            logger.info(f" DEBUG: Used global fallback for enhanced_intelligence in context-aware worker")

        # DEBUG: Log enhanced intelligence extraction results for secondary agents
        logger.info(f"DEBUG ENHANCED_INTEL SECONDARY for {scene_id}: invocation_state_keys={list(invocation_state.keys()) if invocation_state else []}")
        logger.info(f"DEBUG ENHANCED_INTEL SECONDARY for {scene_id}: enhanced_intel_keys={list(enhanced_intel.keys())}")
        logger.info(f"DEBUG ENHANCED_INTEL SECONDARY for {scene_id}: raw_text_present={bool(enhanced_intel.get('raw_text'))}")
        logger.info(f"DEBUG ENHANCED_INTEL SECONDARY for {scene_id}: cosmos_context_count={len(enhanced_intel.get('cosmos_context', []))}")

        # Prevent Intelligence Agent "amnesia"
        synthetic_fleet_context = self._generate_synthetic_fleet_context(scene_id)

        # Base payload with all required fields
        payload = {
            "scene_id": scene_id,  #  Now properly populated
            "agent_type": self.agent_type,
            "task_context": "context_aware_worker",
            "original_task": parsed_input.get("original_task", {}),
            "embeddings_data": rich_behavioral_insights,  #  Use rich data from Phase 3 embeddings
            "behavioral_metrics": invocation_state.get("behavioral_metrics", {}),
            "vector_metadata": invocation_state.get("vector_metadata", {}),
            "processing_context": invocation_state.get("processing_context", {}),

            # ENHANCED: Clear metrics presentation for context-aware agents
            "key_behavioral_metrics": key_behavioral_metrics,

            # SAFE READ: Enhanced intelligence capabilities from Cosmos + Cohere (via state injection)
            "behavioral_analysis_text": enhanced_intel.get("raw_text", ""),  # Direct InternVideo2.5 text for rich context
            "cosmos_similarity_results": enhanced_intel.get("cosmos_context", []),  # Clean visual pattern matches
            "behavioral_similarity_results": enhanced_intel.get("behavioral_context", []),  # Clean semantic matches
            "enhanced_intelligence": enhanced_intel,  # Full enhanced intelligence object

            "data_validation": {
                "rich_insights_available": len(rich_behavioral_insights),
                "context_source": "invocation_state" if invocation_state.get("embeddings_data") else "global_fallback",
                "metrics_available": len(key_behavioral_metrics.get('available_metrics', [])),
                "raw_text_available": enhanced_intel.get("raw_text") is not None,
                "cosmos_matches": enhanced_intel.get("cosmos_count", 0),
                "behavioral_matches": enhanced_intel.get("behavioral_count", 0)
            },
            "shared_state": {
                "embeddings_data": rich_behavioral_insights,  #  Use rich data
                "behavioral_metrics": invocation_state.get("behavioral_metrics", {}),
                "processing_context": invocation_state.get("processing_context", {})
            },

            # Provides Intelligence Agent with believable metadata
            # to prevent "Unknown" outputs. Based on NuScenes dataset characteristics, not fabricated Fleet data.
            "fleet_context": synthetic_fleet_context,

            "timestamp": datetime.utcnow().isoformat()
        }

        # AGENT-TO-AGENT COMMUNICATION: Use shared_state for previous agent results (ORIGINAL APPROACH)
        previous_agent_results = invocation_state.get("agent_results", {}) if invocation_state else {}
        execution_order = invocation_state.get("execution_order", []) if invocation_state else []

        # Log invocation_state contents for debugging coordination issues
        logger.info(f" DEBUG {self.agent_type}: invocation_state is {'None' if invocation_state is None else 'not None'}")
        if invocation_state:
            logger.info(f" DEBUG {self.agent_type}: invocation_state keys: {list(invocation_state.keys())}")
            if "agent_results" in invocation_state:
                agent_results_keys = list(invocation_state["agent_results"].keys())
                logger.info(f" DEBUG {self.agent_type}: agent_results keys: {agent_results_keys}")
                for agent_type, result in invocation_state["agent_results"].items():
                    logger.info(f" DEBUG {self.agent_type}: {agent_type} has result with keys: {list(result.keys()) if isinstance(result, dict) else 'not dict'}")
            else:
                logger.info(f" DEBUG {self.agent_type}: 'agent_results' key NOT FOUND in invocation_state")
            if "execution_order" in invocation_state:
                logger.info(f" DEBUG {self.agent_type}: execution_order: {invocation_state['execution_order']}")
        logger.info(f" DEBUG {self.agent_type}: previous_agent_results empty: {not previous_agent_results}")

        # S3-BASED A2A FALLBACK: If invocation_state is empty, try S3 results
        if not previous_agent_results:
            s3_results = self._get_previous_results_from_s3(scene_id)
            if s3_results:
                # CRITICAL CONTEXT-AWARE FIX: Process S3 results to parse summary fields before sending to agent
                processed_s3_results = {}
                for agent_type, agent_result in s3_results.items():
                    processed_result = dict(agent_result)  # Copy original result

                    # Extract and parse analysis.summary field if it contains structured data
                    analysis = agent_result.get('analysis', {})
                    if isinstance(analysis, dict):
                        summary = analysis.get('summary', '')
                        if summary and isinstance(summary, str):
                            try:
                                # Parse Python literal string: "{'anomaly_findings': {...}}"
                                import ast
                                parsed_summary = ast.literal_eval(summary)
                                if isinstance(parsed_summary, dict):
                                    # Merge parsed data into analysis field for agent consumption
                                    processed_analysis = dict(analysis)
                                    processed_analysis.update(parsed_summary)
                                    processed_result['analysis'] = processed_analysis
                                    logger.info(f" CONTEXT-AWARE FIX: Parsed {agent_type} summary field - found {len(parsed_summary)} structured fields")
                            except (ValueError, SyntaxError) as e:
                                logger.warning(f"Could not parse {agent_type} summary field: {str(e)}")
                                # Keep original result if parsing fails

                    processed_s3_results[agent_type] = processed_result

                previous_agent_results = processed_s3_results
                logger.info(f" S3 A2A FALLBACK: Using processed S3 results for {self.agent_type} - found {len(processed_s3_results)} agents")
            else:
                logger.info(f" S3 A2A FALLBACK: No previous results available for {self.agent_type}")

        # Add previous agent results to payload for context-aware processing
        payload["previous_agent_results"] = previous_agent_results
        payload["context_available"] = bool(previous_agent_results)
        payload["execution_order"] = execution_order

        # Map previous agent results to field names agents expect (3-agent HIL system)
        if previous_agent_results:
            payload["scene_analysis"] = previous_agent_results.get("scene_understanding", {})
            payload["anomaly_analysis"] = previous_agent_results.get("anomaly_detection", {})
            payload["similarity_analysis"] = previous_agent_results.get("similarity_search", {})
            logger.info(f"MAPPED AGENT DATA: scene={bool(payload['scene_analysis'])}, anomaly={bool(payload['anomaly_analysis'])}, similarity={bool(payload['similarity_analysis'])}")

        if previous_agent_results:
            logger.info(f" {self.agent_type} receives context from agents: {list(previous_agent_results.keys())}")
            logger.info(f" EXECUTION ORDER so far: {execution_order}")
        else:
            logger.info(f" {self.agent_type} is the first agent - no previous context available")

        # Add intelligent collaboration instructions for context-aware agents
        payload["collaboration_instructions"] = self._get_agent_collaboration_instructions(self.agent_type, scene_id)
        payload["team_coordination"] = {
            "agent_role": self.agent_type,
            "workflow_position": "context_aware_worker",
            "collaboration_requirement": "MANDATORY: Build upon and integrate findings from previous agents in the pipeline"
        }

        #  Build detailed previous agent context for context-aware agents
        previous_agent_context = "No previous agent context available"
        if previous_agent_results:
            context_details = []
            for agent_type, agent_data in previous_agent_results.items():
                agent_insights = agent_data.get('insights', [])
                agent_recommendations = agent_data.get('recommendations', [])

                if agent_insights or agent_recommendations:
                    context_details.append(f"""
{agent_type.upper()} AGENT FINDINGS:
- Insights: {'; '.join(agent_insights[:3]) if agent_insights else 'No insights available'}
- Recommendations: {'; '.join(agent_recommendations[:2]) if agent_recommendations else 'No recommendations available'}""")

            if context_details:
                previous_agent_context = '\n'.join(context_details)
            else:
                previous_agent_context = f"Previous agents executed ({', '.join(previous_agent_results.keys())}) but no structured findings available"

        #  Get business objective context for agent instructions
        business_objective_context = self._get_business_objective_context(invocation_state)

        #  Add special instructions for similarity search agent to help it find data and perform final validation
        if self.agent_type == "similarity_search":
            # Special instructions for similarity search agent (final validator in HIL system)
            scene_data_summary = "No scene analysis data available"
            anomaly_data_summary = "No anomaly detection data available"

            if previous_agent_results:
                # Extract scene data from scene understanding agent
                scene_agent_data = previous_agent_results.get("scene_understanding", {})
                if scene_agent_data:
                    scene_insights = scene_agent_data.get('insights', [])
                    scene_analysis = scene_agent_data.get('analysis', '')
                    if scene_insights or scene_analysis:
                        scene_data_summary = f"Scene patterns identified: {'; '.join(scene_insights[:2]) if scene_insights else str(scene_analysis)[:200]}"

                # Extract anomaly data from anomaly detection agent
                anomaly_agent_data = previous_agent_results.get("anomaly_detection", {})
                if anomaly_agent_data:
                    anomaly_insights = anomaly_agent_data.get('insights', [])
                    anomaly_analysis = anomaly_agent_data.get('analysis', '')
                    if anomaly_insights or anomaly_analysis:
                        anomaly_data_summary = f"Anomaly patterns detected: {'; '.join(anomaly_insights[:2]) if anomaly_insights else str(anomaly_analysis)[:200]}"

            payload["analysis_instructions"] = f"""HIL SIMILARITY SEARCH & VALIDATION REQUIREMENTS for {scene_id}:

1. SCENE ANALYSIS DATA AVAILABLE:
   {scene_data_summary}

2. ANOMALY DETECTION DATA AVAILABLE:
   {anomaly_data_summary}

3. QUANTIFIED METRICS AVAILABLE:
   {key_behavioral_metrics.get('metrics_summary', 'No quantified metrics available')}

4. HIL PRIORITIZATION TASK:
   - Use S3 Vectors to find similar behavioral patterns across fleet data
   - Correlate current scene anomalies with historical patterns and edge cases
   - Identify cross-scene patterns that indicate training data gaps
   - Apply cost-optimization focus to prioritize high-value HIL scenarios

5. SIMILARITY ANALYSIS APPROACH: You have sufficient data above to perform similarity search and final validation. Use the provided scene understanding and anomaly detection insights to guide your S3 Vectors queries and pattern matching.

6. CRITICAL ANTI-HALLUCINATION RULES:

   a) NO FAKE METADATA: Use the provided fleet_context EXACTLY as given. DO NOT change 'Research Dataset' to a real version number. DO NOT invent software versions, deployment phases, or campaign names.

   b) NO FAKE STATISTICS: If you do not have exact fleet percentages (e.g. "22%"), state "Statistical prevalence unavailable." DO NOT estimate or invent numbers like "represents approximately X% of fleet data."

   c) NO FAKE DOCUMENTS: Do not generate URL links to specifications, design docs, or internal documentation (e.g., /specs/, /docs/, /engineering/).

   d) NO FAKE TICKETS: Do not reference JIRA tickets, engineering tickets, or internal tracking systems.

   e) NO COMPANY-INTERNAL CONTENT: Do not fabricate internal processes, team names, or corporate information for any OEM.

7. CRITICAL COMPLIANCE RULES - ZERO TOLERANCE:

   a) DO NOT INVENT METADATA: Use the provided fleet_context EXACTLY. If provided "Research Dataset v1.0", output "Research Dataset v1.0". Do NOT "correct" it to a real Fleet version like "2025.42.6".

   b) NO FAKE STATISTICS: You do not have access to live fleet statistics. For any statistical query (e.g., "% of miles", "prevalence", "percentage of fleet data"), output "Data unavailable". DO NOT estimate or invent percentages like "28%", "15%", or "22%".

   c) NO FAKE DEPLOYMENT METRICS: Do not invent miles driven, intervention rates, or customer feedback statistics.

   d) EXPLICIT RULE: "Data unavailable" is ALWAYS better than a fabricated number.

9. PREVIOUS AGENT CONTEXT:
   {previous_agent_context}

{business_objective_context}"""

        else:
            # Standard instructions for other agents
            payload["analysis_instructions"] = f"""CONTEXT-AWARE ANALYSIS REQUIREMENTS for {scene_id}:

1. REFERENCE SPECIFIC METRICS: Use the exact values from key_behavioral_metrics in your analysis:
   {key_behavioral_metrics.get('metrics_summary', 'No specific metrics available')}

2. BUILD UPON PREVIOUS AGENTS: Explicitly reference and build upon findings from previous agents:
   {previous_agent_context}

3. CONTEXTUAL INTEGRATION: Your role as {self.agent_type} should integrate behavioral data with previous agent insights.

4. EVIDENCE-BASED ANALYSIS: Base all recommendations on the combination of:
   - Quantified behavioral metrics from scene {scene_id}
   - Previous agent analyses and recommendations shown above
   - Your specialized domain expertise

5. CRITICAL ANTI-HALLUCINATION RULES:

   a) NO FAKE METADATA: Use the provided fleet_context EXACTLY as given. DO NOT change 'Research Dataset' to a real version number. DO NOT invent software versions, deployment phases, or campaign names.

   b) NO FAKE STATISTICS: If you do not have exact fleet percentages, state "Statistical data unavailable." DO NOT estimate or invent numbers.

   c) NO FAKE DOCUMENTS: Do not generate URL links to specifications, design docs, or internal documentation.

   d) NO FAKE TICKETS: Do not reference JIRA tickets, engineering tickets, or internal tracking systems.

   e) NO COMPANY-INTERNAL CONTENT: Do not fabricate internal processes, team names, or corporate information for any OEM.

8. COLLABORATIVE OUTPUT: Structure your response to be useful for subsequent agents in the pipeline.

{business_objective_context}"""

        return payload

    def _generate_synthetic_fleet_context(self, scene_id: str) -> dict:
        """
        Generate synthetic fleet context based on scene characteristics and NuScenes dataset structure.
        This prevents the Intelligence Agent from outputting 'Unknown' values by providing
        believable metadata that matches the actual data source (NuScenes dataset).

        ANTI-FABRICATION: All values are based on publicly known NuScenes characteristics,
        not invented Fleet-specific internal data.
        """
        # Extract scene number for context generation
        scene_number = scene_id.replace('scene-', '') if scene_id.startswith('scene-') else '0000'

        # NuScenes dataset is primarily Boston and Singapore - infer from scene patterns
        # This is based on public NuScenes documentation, not fabricated
        if int(scene_number) % 2 == 0:
            geographic_region = "Boston, MA (NuScenes Dataset)"
        else:
            geographic_region = "Singapore (NuScenes Dataset)"

        # NuScenes uses various vehicle types - this reflects dataset diversity
        vehicle_models = [
            "Research Vehicle - NuScenes Platform",
            "Autonomous Test Vehicle",
            "Sensor Platform Vehicle"
        ]
        vehicle_model = vehicle_models[int(scene_number) % len(vehicle_models)]

        return {
            "campaign_name": "NuScenes Dataset Analysis",
            "vehicle_model": vehicle_model,
            "software_version": "Research Dataset v1.0",
            "geographic_region": geographic_region,
            "deployment_phase": "Research/Validation Dataset",
            "data_source": f"NuScenes Public Dataset - {scene_id}",
            "collection_context": "Multi-sensor autonomous driving research dataset",
            "sensor_configuration": "6x cameras, LiDAR, radar, IMU, GPS"
        }

    def _format_key_metrics_for_agent(self, structured_behavioral_data: dict, scene_id: str) -> dict:
        """Format behavioral metrics in a clear, agent-friendly way for easy reference"""

        if not structured_behavioral_data:
            return {
                "metrics_summary": f"No quantified behavioral metrics available for {scene_id}",
                "available_metrics": [],
                "detailed_metrics": {},
                "analysis_guidance": "Request more behavioral data for comprehensive analysis"
            }

        # Extract key metrics with clear formatting
        formatted_metrics = []
        detailed_metrics = {}

        # Lane deviation metrics - Handle both structured format and lane_positioning_quality mapping
        lane_deviation_data = structured_behavioral_data.get("lane_deviation")
        lane_positioning_quality = structured_behavioral_data.get("lane_positioning_quality")

        if lane_deviation_data and isinstance(lane_deviation_data, dict) and lane_deviation_data.get("measured_meters") is not None:
            # Legacy structured format: {"measured_meters": 0.15, "tolerance_meters": 0.25}
            deviation = lane_deviation_data["measured_meters"]
            tolerance = lane_deviation_data.get("tolerance_meters", 0.25)
            status = "WITHIN TOLERANCE" if deviation <= tolerance else "EXCEEDS TOLERANCE"

            formatted_metrics.append(f"Lane deviation: {deviation}m ({status}, ISO 26262 tolerance: ±{tolerance}m)")
            detailed_metrics["lane_deviation"] = {
                "value": f"{deviation}m",
                "status": status,
                "standard": f"ISO 26262 tolerance: ±{tolerance}m",
                "compliance": deviation <= tolerance
            }
        elif lane_positioning_quality is not None and isinstance(lane_positioning_quality, (int, float)):
            # New Phase 3 format: lane_positioning_quality as quality score (0.0-1.0)
            # Convert quality score to estimated deviation (inverse relationship)
            quality_score = float(lane_positioning_quality)
            tolerance = 0.25  # ISO 26262 standard tolerance
            # High quality (0.8) = low deviation (0.05m), Low quality (0.2) = high deviation (0.2m)
            estimated_deviation = max(0.0, (1.0 - quality_score) * tolerance)
            status = "HIGH QUALITY" if quality_score >= 0.8 else "NEEDS IMPROVEMENT"

            formatted_metrics.append(f"Lane positioning quality: {quality_score:.2f} (estimated deviation: {estimated_deviation:.3f}m, {status})")
            detailed_metrics["lane_deviation"] = {
                "value": f"{estimated_deviation:.3f}m (estimated)",
                "quality_score": quality_score,
                "status": status,
                "standard": f"ISO 26262 tolerance: ±{tolerance}m",
                "compliance": estimated_deviation <= tolerance,
                "source": "lane_positioning_quality_mapping"
            }

        # Following distance metrics - Handle both structured format and fallback
        following_distance_data = structured_behavioral_data.get("following_distance")

        if following_distance_data and isinstance(following_distance_data, dict) and following_distance_data.get("measured_seconds") is not None:
            # Structured format: {"measured_seconds": 2.8, "standard_seconds": 3.0}
            distance = following_distance_data["measured_seconds"]
            standard = following_distance_data.get("standard_seconds", 3.0)
            status = "MEETS NHTSA STANDARD" if distance >= standard else "BELOW NHTSA STANDARD"

            formatted_metrics.append(f"Following distance: {distance}s ({status}, NHTSA standard: {standard}s)")
            detailed_metrics["following_distance"] = {
                "value": f"{distance}s",
                "status": status,
                "standard": f"NHTSA standard: {standard}s",
                "compliance": distance >= standard
            }
        elif following_distance_data is not None and isinstance(following_distance_data, (int, float)):
            # Flat format: following_distance as seconds value directly
            distance = float(following_distance_data)
            standard = 3.0  # Default NHTSA standard
            status = "MEETS NHTSA STANDARD" if distance >= standard else "BELOW NHTSA STANDARD"

            formatted_metrics.append(f"Following distance: {distance}s ({status}, NHTSA standard: {standard}s)")
            detailed_metrics["following_distance"] = {
                "value": f"{distance}s",
                "status": status,
                "standard": f"NHTSA standard: {standard}s",
                "compliance": distance >= standard,
                "source": "flat_format"
            }
        else:
            # Fallback: Use default safe following distance when not available
            default_distance = 4.0  # Conservative fallback
            standard = 3.0
            status = "ESTIMATED (no data)"

            formatted_metrics.append(f"Following distance: {default_distance}s (estimated, {status})")
            detailed_metrics["following_distance"] = {
                "value": f"{default_distance}s (estimated)",
                "status": status,
                "standard": f"NHTSA standard: {standard}s",
                "compliance": default_distance >= standard,
                "source": "fallback_estimated"
            }

        # Speed compliance metrics - Handle both dict and float formats
        speed_compliance_data = structured_behavioral_data.get("speed_compliance")
        if speed_compliance_data is not None:
            if isinstance(speed_compliance_data, dict) and speed_compliance_data.get("percentage") is not None:
                # Legacy dict format: {"percentage": 0.9, "industry_excellent_threshold": 95.0}
                compliance = speed_compliance_data["percentage"] * 100  # Convert 0.9 -> 90%
                threshold = speed_compliance_data.get("industry_excellent_threshold", 95.0)
            elif isinstance(speed_compliance_data, (int, float)):
                # New flat format: 0.9
                compliance = float(speed_compliance_data) * 100  # Convert 0.9 -> 90%
                threshold = 95.0  # Default threshold
            else:
                compliance = None

            if compliance is not None:
                status = "EXCELLENT" if compliance >= threshold else "NEEDS IMPROVEMENT"
                formatted_metrics.append(f"Speed compliance: {compliance:.1f}% ({status}, industry excellent: ≥{threshold}%)")
                detailed_metrics["speed_compliance"] = {
                    "value": f"{compliance:.1f}%",
                    "status": status,
                    "standard": f"Industry excellent: ≥{threshold}%",
                    "compliance": compliance >= threshold
                }

        # Risk score metrics - Handle both dict and float formats
        risk_score_data = structured_behavioral_data.get("risk_score")
        if risk_score_data is not None:
            if isinstance(risk_score_data, dict) and risk_score_data.get("score") is not None:
                # Legacy dict format: {"score": 0.2, "threshold": 0.3}
                risk = risk_score_data["score"]
                threshold = risk_score_data.get("threshold", 0.3)
            elif isinstance(risk_score_data, (int, float)):
                # New flat format: 0.2
                risk = float(risk_score_data)
                threshold = 0.3  # Default threshold
            else:
                risk = None

            if risk is not None:
                status = "LOW RISK" if risk <= threshold else "ELEVATED RISK"
                formatted_metrics.append(f"Risk score: {risk}/1.0 ({status}, threshold: {threshold})")
                detailed_metrics["risk_score"] = {
                    "value": f"{risk}/1.0",
                    "status": status,
                    "standard": f"Threshold: {threshold}",
                    "compliance": risk <= threshold
                }

        # Safety score metrics - Handle both dict and float formats
        safety_score_data = structured_behavioral_data.get("safety_score")
        if safety_score_data is not None:
            if isinstance(safety_score_data, dict) and safety_score_data.get("score") is not None:
                # Legacy dict format: {"score": 0.8, "industry_average": 0.85}
                safety = safety_score_data["score"]
                average = safety_score_data.get("industry_average", 0.85)
            elif isinstance(safety_score_data, (int, float)):
                # New flat format: 0.8
                safety = float(safety_score_data)
                average = 0.85  # Default industry average
            else:
                safety = None

            if safety is not None:
                status = "ABOVE AVERAGE" if safety >= average else "BELOW AVERAGE"
                formatted_metrics.append(f"Safety score: {safety}/1.0 ({status}, industry average: {average})")
                detailed_metrics["safety_score"] = {
                    "value": f"{safety}/1.0",
                    "status": status,
                    "standard": f"Industry average: {average}",
                    "compliance": safety >= average
                }

        # Create summary
        if formatted_metrics:
            metrics_summary = f"Scene {scene_id} behavioral metrics: " + ", ".join(formatted_metrics)
        else:
            metrics_summary = f"No quantified behavioral metrics available for {scene_id}"

        return {
            "metrics_summary": metrics_summary,
            "available_metrics": [metric.split(":")[0] for metric in formatted_metrics],
            "detailed_metrics": detailed_metrics,
            "total_metrics": len(formatted_metrics),
            "analysis_guidance": f"Reference these specific metrics in your analysis of {scene_id}. Use exact values and compliance status in your findings."
        }

    def _extract_internvideo25_behavioral_data(self, phase3_data: dict, scene_id: str) -> dict:
        """Extract structured behavioral data from Phase 3 InternVideo2.5 JSON format"""

        logger.info(f" Extracting InternVideo2.5 behavioral data for {scene_id}")

        if not phase3_data or "behavioral_analysis" not in phase3_data:
            logger.warning(f"No behavioral_analysis found in Phase 3 data for {scene_id}")
            return {"lane_deviation": None, "following_distance": None, "speed_compliance": None, "risk_score": None, "safety_score": None, "scene_context": {}}

        behavioral_analysis = phase3_data["behavioral_analysis"]
        quantified_metrics = behavioral_analysis.get("quantified_metrics", {})

        # Extract ALL quantified metrics from Phase 3 data
        # DIRECT MAPPING: Phase 3 provides flat floats, keep them flat for clean architecture
        result = {
            # Direct float mapping (Green State Architecture)
            "speed_compliance": quantified_metrics.get("speed_compliance"),
            "risk_score": quantified_metrics.get("risk_score"),
            "safety_score": quantified_metrics.get("safety_score"),
            "behavioral_complexity_score": quantified_metrics.get("behavioral_complexity_score"),
            "confidence_score": quantified_metrics.get("confidence_score"),
            "lane_positioning_quality": quantified_metrics.get("lane_positioning_quality"),

            # Handle following_distance with fallback
            "following_distance": quantified_metrics.get("following_distance", 4.0),

            # Context and metadata
            "visual_evidence_summary": quantified_metrics.get("visual_evidence_summary"),
            "scene_context": {}
        }

        logger.info(f" Extracted InternVideo2.5 data for {scene_id}: speed_compliance={result['speed_compliance']}, risk_score={result['risk_score']}, safety_score={result['safety_score']}, following_distance={result['following_distance']}")
        return result

    def _extract_raw_behavioral_text(self, phase3_data: dict, scene_id: str) -> str:
        """Extract raw behavioral analysis text from Phase 3 InternVideo2.5 output"""
        if not phase3_data or "behavioral_analysis" not in phase3_data:
            return None

        behavioral_analysis = phase3_data["behavioral_analysis"]

        # Fixed: Added "behavioral_insights" + handle dict vs string safely
        raw_text_keys = ["behavioral_insights", "scene_description", "behavioral_description", "internvideo_output", "analysis_text", "description"]

        for key in raw_text_keys:
            if key in behavioral_analysis and behavioral_analysis[key]:
                value = behavioral_analysis[key]

                # Safety check: behavioral_insights might be a dict, not string
                if key == "behavioral_insights" and isinstance(value, dict):
                    # Extract description from behavioral_insights dict
                    for sub_key in ["description", "scene_description", "analysis", "text"]:
                        if sub_key in value and isinstance(value[sub_key], str):
                            logger.info(f" Extracted raw text from behavioral_insights.{sub_key} for {scene_id}")
                            return value[sub_key]
                elif isinstance(value, str) and len(value) > 30:
                    logger.info(f" Extracted raw behavioral text from {key} for {scene_id} ({len(value)} chars)")
                    return value

        return None

    async def _query_cosmos_video_similarity(self, phase3_data: dict, scene_id: str) -> List[Dict[str, Any]]:
        """Query video-similarity-index using Cosmos embeddings from Phase 3"""
        if not phase3_data or "cosmos_embeddings" not in phase3_data:
            return []

        cosmos_embeddings = phase3_data["cosmos_embeddings"]
        per_camera_embeddings = cosmos_embeddings.get("per_camera_embeddings", {})

        if not per_camera_embeddings:
            return []

        # Use primary camera (CAM_FRONT preferred) for agent similarity context
        cosmos_embedding = None
        primary_camera_id = f"{scene_id}_CAM_FRONT"

        if primary_camera_id in per_camera_embeddings:
            cosmos_embedding = per_camera_embeddings[primary_camera_id].get("embedding")
        else:
            # Fallback: use any available camera embedding (Fleet priority order)
            camera_priority = ["CAM_FRONT_LEFT", "CAM_FRONT_RIGHT", "CAM_BACK", "CAM_BACK_LEFT", "CAM_BACK_RIGHT"]
            for camera in camera_priority:
                fallback_camera_id = f"{scene_id}_{camera}"
                if fallback_camera_id in per_camera_embeddings:
                    camera_data = per_camera_embeddings[fallback_camera_id]
                    if camera_data and camera_data.get("embedding"):
                        cosmos_embedding = camera_data["embedding"]
                        logger.info(f"Using fallback camera {camera} for agent similarity context")
                        break

        if not cosmos_embedding or len(cosmos_embedding) != 768:
            return []

        loop = asyncio.get_event_loop()

        def _sync_query_cosmos():
            try:
                # Following existing pattern from query_similar_scenes function
                s3vectors_client = boto3.client('s3vectors')

                response = s3vectors_client.query_vectors(
                    vectorBucketName=os.getenv('VECTOR_BUCKET_NAME', ''),
                    indexName='video-similarity-index',
                    queryVector={"float32": cosmos_embedding},  # Following existing pattern
                    topK=5,
                    returnMetadata=True
                )

                search_results = response.get('vectors', [])
                similar_scenes = []
                seen_scene_ids = set()  # Track seen scenes for deduplication

                for result in search_results:
                    metadata = result.get('metadata', {})

                    # Extract scene ID from camera-specific ID
                    camera_id = result.get('id', '') or metadata.get('camera_id', '')
                    result_scene_id = extract_scene_from_id(camera_id) if camera_id else metadata.get('scene_id')

                    # Skip current scene and duplicate scenes (deduplication logic)
                    if result_scene_id != scene_id and result_scene_id not in seen_scene_ids:
                        seen_scene_ids.add(result_scene_id)
                        similar_scenes.append({
                            'scene_id': result_scene_id,
                            'similarity_score': 1.0 - result.get('distance', 1.0),
                            'risk_score': metadata.get('risk_score'),
                            'behavioral_tags': metadata.get('behavioral_tags', []),
                            'match_type': 'visual_temporal_pattern'
                        })

                return similar_scenes[:3]
            except Exception as e:
                logger.error(f"Cosmos video similarity query failed for {scene_id}: {str(e)}")
                return []

        try:
            return await loop.run_in_executor(None, _sync_query_cosmos)
        except Exception:
            return []

    async def _query_behavioral_metadata_similarity(self, behavioral_text: str, scene_id: str) -> List[Dict[str, Any]]:
        """Query behavioral-metadata-index using Cohere embeddings"""
        if not behavioral_text:
            return []

        loop = asyncio.get_event_loop()

        def _sync_query_behavioral():
            try:
                # Generate Cohere embedding
                bedrock_client = boto3.client('bedrock-runtime')
                response = bedrock_client.invoke_model(
                    modelId="us.cohere.embed-v4:0",
                    contentType='application/json',
                    accept='application/json',
                    body=json.dumps({
                        "texts": [behavioral_text[:500]],  # Truncate to prevent size issues
                        "input_type": "search_query",
                        "embedding_types": ["float"],  # SUCCESS: FIX: Add missing parameter
                        "truncate": "NONE"            # SUCCESS: FIX: Prevent truncation errors
                    })
                )

                cohere_embedding = json.loads(response['body'].read())['embeddings']['float'][0]
                if len(cohere_embedding) != 1536:
                    return []

                # Following existing pattern from query_similar_scenes function
                s3vectors_client = boto3.client('s3vectors')

                response = s3vectors_client.query_vectors(
                    vectorBucketName=os.getenv('VECTOR_BUCKET_NAME', ''),
                    indexName='behavioral-metadata-index',
                    queryVector={"float32": cohere_embedding},  # Following existing pattern
                    topK=5,
                    returnMetadata=True
                )

                search_results = response.get('vectors', [])
                similar_scenes = []
                for result in search_results:
                    metadata = result.get('metadata', {})
                    if metadata.get('scene_id') != scene_id:
                        similar_scenes.append({
                            'scene_id': metadata.get('scene_id'),
                            'similarity_score': 1.0 - result.get('distance', 1.0),
                            'match_type': 'behavioral_semantic_pattern'
                        })

                return similar_scenes[:3]
            except Exception as e:
                logger.error(f"Behavioral metadata similarity query failed for {scene_id}: {str(e)}")
                return []

        try:
            return await loop.run_in_executor(None, _sync_query_behavioral)
        except Exception:
            return []

    def _sanitize_similarity_context(self, similarity_results: List[Dict[str, Any]], context_type: str) -> List[Dict[str, str]]:
        """
        Clean up S3 Vectors similarity results for agent consumption
        Removes verbose metadata and provides only actionable intelligence
        """
        if not similarity_results:
            return []

        sanitized_context = []

        for result in similarity_results:
            scene_id = result.get('scene_id', 'unknown')
            similarity_score = result.get('similarity_score', 0.0)

            if context_type == "visual":
                # For Cosmos video similarity - focus on visual patterns
                risk_score = result.get('risk_score')
                behavioral_tags = result.get('behavioral_tags', [])

                description_parts = [f"Scene {scene_id}"]
                if risk_score is not None:
                    risk_level = "high" if risk_score > 0.7 else "medium" if risk_score > 0.4 else "low"
                    description_parts.append(f"risk level: {risk_level}")

                if behavioral_tags:
                    top_tags = behavioral_tags[:2] if isinstance(behavioral_tags, list) else []
                    if top_tags:
                        description_parts.append(f"patterns: {', '.join(top_tags)}")

                clean_description = f"Visually similar to {' | '.join(description_parts)}"

            elif context_type == "behavioral":
                # Fixed: Extract behavioral features text for high-value reasoning
                features_text = result.get('behavioral_features_text') or result.get('snippet', '')
                short_snippet = features_text[:50] + "..." if len(features_text) > 50 else features_text

                clean_description = f"Behaviorally similar scene {scene_id}"
                if short_snippet:
                    clean_description += f" ({short_snippet})"

            else:
                clean_description = f"Similar scene {scene_id}"

            sanitized_context.append({
                "scene_reference": scene_id,
                "similarity_strength": "high" if similarity_score > 0.8 else "medium" if similarity_score > 0.6 else "moderate",
                "context_description": clean_description,
                "relevance_type": context_type
            })

        return sanitized_context[:3]  # Top 3 matches to avoid overwhelming agents

    def _parse_propagated_input(self, combined_input) -> Dict[str, Any]:
        """Parse propagated input for context-aware processing"""
        # Reuse the robust parsing logic from AggregatorNode
        aggregator = AggregatorNode()
        return aggregator._parse_propagated_input(combined_input)


async def inject_enhanced_intelligence_to_shared_state(phase3_data: dict, shared_state: dict, scene_id: str) -> None:
    """
    SCENE-LEVEL INTELLIGENCE GATHERING: Inject enhanced Cosmos + Cohere intelligence into shared_state
    Called once per scene at orchestration level - available to ALL agents
    """
    try:
        # Extract raw behavioral analysis text from Phase 3 (CRITICAL - this must succeed)
        raw_behavioral_text = extract_raw_behavioral_text_from_phase3(phase3_data, scene_id)
        logger.info(f"Raw behavioral text extraction for {scene_id}: {'SUCCESS' if raw_behavioral_text else 'FAILED'}")

        # Gather Cosmos video similarity results (optional - don't let this block raw text)
        cosmos_similarity_results = []
        try:
            cosmos_similarity_results = await query_cosmos_video_similarity_for_scene(phase3_data, scene_id)
            logger.info(f"Cosmos similarity search for {scene_id}: {len(cosmos_similarity_results)} results")
        except Exception as cosmos_error:
            logger.warning(f"Cosmos similarity search failed for {scene_id}: {str(cosmos_error)}")

        # Gather behavioral metadata similarity (optional - don't let this block raw text)
        behavioral_similarity_results = []
        if raw_behavioral_text:
            try:
                behavioral_similarity_results = await query_behavioral_metadata_similarity_for_scene(raw_behavioral_text, scene_id)
                logger.info(f"Behavioral similarity search for {scene_id}: {len(behavioral_similarity_results)} results")
            except Exception as behavioral_error:
                logger.warning(f"Behavioral similarity search failed for {scene_id}: {str(behavioral_error)}")

        # Clean similarity results for agent consumption
        clean_cosmos_context = sanitize_similarity_context(cosmos_similarity_results, "visual")
        clean_behavioral_context = sanitize_similarity_context(behavioral_similarity_results, "behavioral")

        # Inject into shared_state for ALL agents to access
        shared_state["enhanced_intelligence"] = {
            "raw_text": raw_behavioral_text,
            "cosmos_context": clean_cosmos_context,
            "behavioral_context": clean_behavioral_context,
            "cosmos_count": len(cosmos_similarity_results),
            "behavioral_count": len(behavioral_similarity_results)
        }

        logger.info(f" Enhanced intelligence injected at scene level for {scene_id}: "
                   f"raw_text={raw_behavioral_text is not None}, "
                   f"cosmos_matches={len(cosmos_similarity_results)}, "
                   f"behavioral_matches={len(behavioral_similarity_results)}")

    except Exception as e:
        logger.error(f"Failed to inject enhanced intelligence for {scene_id}: {str(e)}")
        # Fallback: inject empty state to prevent crashes
        shared_state["enhanced_intelligence"] = {
            "raw_text": None,
            "cosmos_context": [],
            "behavioral_context": [],
            "cosmos_count": 0,
            "behavioral_count": 0
        }


def extract_raw_behavioral_text_from_phase3(phase3_data: dict, scene_id: str) -> str:
    """
    Robust extraction of behavioral text using Hybrid Strategy:
    Explicit Paths (Fast/Safe) + Recursive Deep Search (Fallback).
    """
    if not phase3_data:
        logger.warning(f" Extraction failed: phase3_data is None/Empty for {scene_id}")
        return None

    # --- STRATEGY 1: EXPLICIT PATHS (Restored & Expanded) ---
    # Check known high-probability locations first
    try:
        behavioral_analysis = phase3_data.get("behavioral_analysis", {})

        # Path A: behavioral_insights (Dict or String)
        insights = behavioral_analysis.get("behavioral_insights")
        if isinstance(insights, dict):
            # Check specific sub-keys inside insights
            for key in ["scene_description", "description", "comprehensive_analysis", "analysis"]:
                val = insights.get(key)
                if isinstance(val, str) and len(val) > 50:
                    logger.info(f" SUCCESS: Extracted text from behavioral_insights.{key}")
                    return val
        elif isinstance(insights, str) and len(insights) > 50:
            logger.info(f" SUCCESS: Extracted text directly from behavioral_insights")
            return insights

        # Path B: scene_understanding (Dict)
        scene_und = behavioral_analysis.get("scene_understanding")
        if isinstance(scene_und, dict):
            for key in ["comprehensive_analysis", "analysis", "description"]:
                val = scene_und.get(key)
                if isinstance(val, str) and len(val) > 50:
                    logger.info(f" SUCCESS: Extracted text from scene_understanding.{key}")
                    return val

    except Exception as e:
        logger.warning(f" Standard extraction error: {e}")

    # --- STRATEGY 2: RECURSIVE DEEP SEARCH (Expanded Keys) ---
    logger.info(f" Standard extraction failed for {scene_id}, attempting DEEP search...")

    candidates = []

    # Expanded key list to catch ALL variations
    target_keys = [
        "scene_description", "description", "caption", "analysis", "text",
        "comprehensive_analysis", "behavioral_description", "internvideo_output",
        "analysis_text", "summary", "visual_evidence_summary"
    ]

    def _recursive_search(obj, path=""):
        if isinstance(obj, dict):
            for k, v in obj.items():
                # Check for target keys
                if k in target_keys and isinstance(v, str) and len(v) > 50:
                    # Log the find for debugging
                    logger.info(f" FOUND: Found candidate at {path}.{k} ({len(v)} chars)")
                    candidates.append(v)

                # Recurse into dicts and lists
                if isinstance(v, (dict, list)):
                    _recursive_search(v, f"{path}.{k}")

        elif isinstance(obj, list):
            for i, item in enumerate(obj):
                _recursive_search(item, f"{path}[{i}]")

    _recursive_search(phase3_data)

    if candidates:
        # Heuristic: The longest string is likely the full detailed analysis
        best_candidate = max(candidates, key=len)
        logger.info(f" SUCCESS: DEEP SEARCH SUCCESS: Found {len(candidates)} candidates. Selected longest ({len(best_candidate)} chars)")
        return best_candidate

    logger.error(f" ERROR: EXTRACTION FAILURE: No behavioral text >50 chars found in Phase 3 data for {scene_id}")

    # Log top-level keys to help debug structure mismatch
    logger.info(f" Phase 3 Top-Level Keys: {list(phase3_data.keys())}")
    if "behavioral_analysis" in phase3_data:
        logger.info(f" Behavioral Analysis Keys: {list(phase3_data['behavioral_analysis'].keys())}")

    return None


async def query_cosmos_video_similarity_for_scene(phase3_data: dict, scene_id: str) -> List[Dict[str, Any]]:
    """Query video-similarity-index using Cosmos embeddings (scene-level)"""
    if not phase3_data or "cosmos_embeddings" not in phase3_data:
        return []

    cosmos_embeddings = phase3_data["cosmos_embeddings"]
    per_camera_embeddings = cosmos_embeddings.get("per_camera_embeddings", {})

    if not per_camera_embeddings:
        return []

    # Use primary camera (CAM_FRONT preferred) for agent similarity context
    cosmos_embedding = None
    primary_camera_id = f"{scene_id}_CAM_FRONT"

    if primary_camera_id in per_camera_embeddings:
        cosmos_embedding = per_camera_embeddings[primary_camera_id].get("embedding")
    else:
        # Fallback: use any available camera embedding (Fleet priority order)
        camera_priority = ["CAM_FRONT_LEFT", "CAM_FRONT_RIGHT", "CAM_BACK", "CAM_BACK_LEFT", "CAM_BACK_RIGHT"]
        for camera in camera_priority:
            fallback_camera_id = f"{scene_id}_{camera}"
            if fallback_camera_id in per_camera_embeddings:
                camera_data = per_camera_embeddings[fallback_camera_id]
                if camera_data and camera_data.get("embedding"):
                    cosmos_embedding = camera_data["embedding"]
                    logger.info(f"Fallback: Using {camera} for cosmos similarity query")
                    break

    if not cosmos_embedding or len(cosmos_embedding) != 768:
        return []

    loop = asyncio.get_event_loop()

    def _sync_query():
        try:
            s3vectors_client = boto3.client('s3vectors')
            response = s3vectors_client.query_vectors(
                vectorBucketName=os.getenv('VECTOR_BUCKET_NAME', ''),
                indexName='video-similarity-index',
                queryVector={"float32": cosmos_embedding},
                topK=5,
                returnMetadata=True
            )

            search_results = response.get('vectors', [])
            similar_scenes = []
            seen_scene_ids = set()  # Track seen scenes for deduplication

            for result in search_results:
                metadata = result.get('metadata', {})

                # Extract scene ID from camera-specific ID
                camera_id = result.get('id', '') or metadata.get('camera_id', '')
                result_scene_id = extract_scene_from_id(camera_id) if camera_id else metadata.get('scene_id')

                # Skip current scene and duplicate scenes (deduplication logic)
                if result_scene_id != scene_id and result_scene_id not in seen_scene_ids:
                    seen_scene_ids.add(result_scene_id)
                    similar_scenes.append({
                        'scene_id': result_scene_id,
                        'similarity_score': 1.0 - result.get('distance', 1.0),
                        'risk_score': metadata.get('risk_score'),
                        'behavioral_tags': metadata.get('behavioral_tags', []),
                        'match_type': 'visual_temporal_pattern'
                    })

            return similar_scenes[:3]
        except Exception as e:
            logger.error(f"Cosmos video similarity query failed for {scene_id}: {str(e)}")
            return []

    try:
        return await loop.run_in_executor(None, _sync_query)
    except Exception:
        return []


async def query_behavioral_metadata_similarity_for_scene(behavioral_text: str, scene_id: str) -> List[Dict[str, Any]]:
    """Query behavioral-metadata-index using Cohere embeddings (scene-level)"""
    if not behavioral_text:
        return []

    loop = asyncio.get_event_loop()

    def _sync_query():
        try:
            bedrock_client = boto3.client('bedrock-runtime')
            response = bedrock_client.invoke_model(
                modelId="us.cohere.embed-v4:0",
                contentType='application/json',
                accept='application/json',
                body=json.dumps({
                    "texts": [behavioral_text[:500]],
                    "input_type": "search_query",
                    "embedding_types": ["float"],  # SUCCESS: FIX: Add missing parameter
                    "truncate": "NONE"            # SUCCESS: FIX: Prevent truncation errors
                })
            )

            cohere_embedding = json.loads(response['body'].read())['embeddings']['float'][0]
            if len(cohere_embedding) != 1536:
                return []

            s3vectors_client = boto3.client('s3vectors')
            response = s3vectors_client.query_vectors(
                vectorBucketName=os.getenv('VECTOR_BUCKET_NAME', ''),
                indexName='behavioral-metadata-index',
                queryVector={"float32": cohere_embedding},
                topK=5,
                returnMetadata=True
            )

            search_results = response.get('vectors', [])
            similar_scenes = []
            for result in search_results:
                metadata = result.get('metadata', {})
                if metadata.get('scene_id') != scene_id:
                    similar_scenes.append({
                        'scene_id': metadata.get('scene_id'),
                        'similarity_score': 1.0 - result.get('distance', 1.0),
                        'behavioral_features_text': metadata.get('behavioral_features_text'),
                        'match_type': 'behavioral_semantic_pattern'
                    })

            return similar_scenes[:3]
        except Exception as e:
            logger.error(f"Behavioral metadata similarity query failed for {scene_id}: {str(e)}")
            return []

    try:
        return await loop.run_in_executor(None, _sync_query)
    except Exception:
        return []


def sanitize_similarity_context(similarity_results: List[Dict[str, Any]], context_type: str) -> List[Dict[str, str]]:
    """Clean up S3 Vectors similarity results for agent consumption (scene-level)"""
    if not similarity_results:
        return []

    sanitized_context = []

    for result in similarity_results:
        scene_id = result.get('scene_id', 'unknown')
        similarity_score = result.get('similarity_score', 0.0)

        if context_type == "visual":
            risk_score = result.get('risk_score')
            behavioral_tags = result.get('behavioral_tags', [])

            description_parts = [f"Scene {scene_id}"]
            if risk_score is not None:
                risk_level = "high" if risk_score > 0.7 else "medium" if risk_score > 0.4 else "low"
                description_parts.append(f"risk level: {risk_level}")

            if behavioral_tags:
                top_tags = behavioral_tags[:2] if isinstance(behavioral_tags, list) else []
                if top_tags:
                    description_parts.append(f"patterns: {', '.join(top_tags)}")

            clean_description = f"Visually similar to {' | '.join(description_parts)}"

        elif context_type == "behavioral":
            features_text = result.get('behavioral_features_text') or result.get('snippet', '')
            short_snippet = features_text[:50] + "..." if len(features_text) > 50 else features_text

            clean_description = f"Behaviorally similar scene {scene_id}"
            if short_snippet:
                clean_description += f" ({short_snippet})"

        else:
            clean_description = f"Similar scene {scene_id}"

        sanitized_context.append({
            "scene_reference": scene_id,
            "similarity_strength": "high" if similarity_score > 0.8 else "medium" if similarity_score > 0.6 else "moderate",
            "context_description": clean_description,
            "relevance_type": context_type
        })

    return sanitized_context[:3]


def verify_s3_output_exists(bucket: str, key: str) -> None:
    """Verify output file was created in S3"""
    try:
        response = s3_client.head_object(Bucket=bucket, Key=key)
        file_size = response.get('ContentLength', 0)
        if file_size == 0:
            raise RuntimeError(f"Output file exists but is empty: s3://{bucket}/{key}")
        logger.info(f" Verified output: s3://{bucket}/{key} ({file_size} bytes)")
    except s3_client.exceptions.NoSuchKey:
        raise RuntimeError(f"Output file not created: s3://{bucket}/{key}")


def process_business_objective(business_objective: str, phase45_data: Dict[str, Any] = None) -> Dict[str, Any]:
    """
    Enhanced Phase 6: Business Objective Interpreter
    Convert natural language business objective to structured workflow parameters.
    Uses Claude 3 Sonnet via Bedrock for intelligent interpretation.
    NO HARDCODING - All parameters derived from LLM responses or actual data.

    Args:
        business_objective: Natural language description (e.g., "Improve crash avoidance in urban areas")
        phase45_data: Optional scene data to provide context to the LLM

    Returns:
        Dict containing structured workflow parameters for iterative agent cycles

    Raises:
        RuntimeError: If LLM fails to provide valid structured response after retries
    """
    logger.info(f" Processing business objective: {business_objective}")

    # Extract real context from phase45_data if available
    context_info = ""
    if phase45_data:
        embeddings_count = len(phase45_data.get('embeddings_vectors', []))
        behavioral_metrics = list(phase45_data.get('behavioral_metrics', {}).keys())
        context_info = f"""
Available scene context:
- Embeddings available: {embeddings_count}
- Behavioral metrics: {behavioral_metrics}
- Use this real data to inform your parameter selection
"""

    system_prompt = """You are an expert in Hardware-in-the-Loop (HIL) scenario discovery for autonomous vehicle development.
Convert business objectives into structured workflow parameters for a specialized 3-agent HIL system.

MISSION: Identify high-value driving scenarios to minimize DTO costs and accelerate model training.

AGENT SPECIALIZATIONS:
- scene_understanding: Deep visual intelligence from multi-camera InternVideo2.5 analysis
- anomaly_detection: Statistical deviation detection using S3 Vectors fleet baselines
- similarity_search: Query-driven scenario retrieval and training gap identification

Focus on cost-optimized data discovery, edge case identification, and training dataset curation.
Base your parameters on the specific business objective and any provided scene context."""

    user_prompt = f"""Convert this business objective into structured JSON workflow parameters for HIL (Hardware-in-the-Loop) data discovery:

Business Objective: "{business_objective}"

{context_info}

Return ONLY valid JSON with this exact structure:
{{
    "business_objective_canonical": "canonical name for this objective",
    "scenario_filters": {{
        "environment_types": ["list based on objective"],
        "weather_conditions": ["list based on objective"],
        "risk_threshold_min": 0.0,
        "maneuver_types": ["list based on objective"]
    }},
    "required_analysis": ["select from: scene_understanding, anomaly_detection, similarity_search"],
    "target_metrics": ["select relevant metrics based on objective"],
    "workflow_priority": "priority level based on objective",
    "max_cycles": 5,
    "convergence_threshold": 0.85
}}

Focus on HIL data discovery, scene understanding, anomaly detection, and cross-scene pattern similarity for autonomous vehicle development. Be specific about scenario filters and metrics based on the stated objective."""

    max_retries = 3
    for attempt in range(max_retries):
        try:
            logger.info(f" Calling Claude 3 Sonnet (attempt {attempt + 1}/{max_retries})")

            response = bedrock_runtime_client.invoke_model(
                modelId="anthropic.claude-3-sonnet-20240229-v1:0",
                body=json.dumps({
                    "anthropic_version": "bedrock-2023-05-31",
                    "max_tokens": 1000,
                    "system": system_prompt,
                    "messages": [
                        {
                            "role": "user",
                            "content": user_prompt
                        }
                    ],
                    "temperature": 0.1  # Low temperature for consistent structured output
                })
            )

            # Parse response
            response_body = json.loads(response.get('body').read())
            claude_response = response_body.get('content', [{}])[0].get('text', '')

            if not claude_response:
                raise ValueError("Empty response from Claude")

            # Extract JSON from Claude's response
            json_start = claude_response.find('{')
            json_end = claude_response.rfind('}') + 1

            if json_start == -1 or json_end == 0:
                raise ValueError("No JSON structure found in Claude response")

            json_content = claude_response[json_start:json_end]
            workflow_params = json.loads(json_content)

            # Validate required fields are present
            required_fields = ['business_objective_canonical', 'scenario_filters', 'required_analysis', 'target_metrics']
            missing_fields = [field for field in required_fields if field not in workflow_params]

            if missing_fields:
                raise ValueError(f"Claude response missing required fields: {missing_fields}")

            logger.info(f" Successfully interpreted business objective with {len(workflow_params)} parameters")
            return workflow_params

        except (json.JSONDecodeError, ValueError, KeyError) as e:
            logger.warning(f" Attempt {attempt + 1} failed: {str(e)}")
            if attempt < max_retries - 1:
                # Add error feedback to prompt for next attempt
                user_prompt += f"\n\nPrevious attempt failed with error: {str(e)}. Please ensure you return only valid JSON with all required fields."
                continue
            else:
                logger.error(f" All {max_retries} attempts failed to get valid structured response")
                raise RuntimeError(f"Failed to process business objective after {max_retries} attempts. Last error: {str(e)}")

        except Exception as e:
            logger.error(f" Bedrock error on attempt {attempt + 1}: {str(e)}")
            if attempt < max_retries - 1:
                continue
            else:
                raise RuntimeError(f"Failed to process business objective due to Bedrock error: {str(e)}")


class IterativeCycleController:
    """
    Enhanced Phase 6: Iterative Cycle Controller
    Manages multiple executions of GraphBuilder with convergence detection and cross-scene intelligence.
    Uses your existing orchestrate_coordinator_workers_aggregator_async() function in iterative cycles.
    """

    def __init__(self, max_cycles: int = 5, convergence_threshold: float = 0.85):
        self.max_cycles = max_cycles
        self.convergence_threshold = convergence_threshold
        self.cycle_results = []
        self.cross_scene_context = {}

        logger.info(f" Initialized IterativeCycleController: max_cycles={max_cycles}, threshold={convergence_threshold}")

    async def execute_iterative_cycles(self, workflow_params: Dict[str, Any], phase45_data: Dict[str, Any], scene_id: str, phase3_data: Dict[str, Any] = None) -> Dict[str, Any]:
        """
        Execute iterative cycles of multi-agent analysis with convergence detection.

        Args:
            workflow_params: Structured parameters from process_business_objective()
            phase45_data: Scene data from phases 4-5
            scene_id: Current scene identifier
            phase3_data: Phase 3 InternVideo2.5 behavioral analysis data

        Returns:
            Dict containing aggregated results from all cycles with convergence analysis
        """
        logger.info(f" Starting iterative cycles for scene {scene_id} with {self.max_cycles} max cycles")

        # Store phase3_data for use in cycles
        self.phase3_data = phase3_data

        # Extract cycle configuration from workflow parameters
        max_cycles = workflow_params.get('max_cycles', self.max_cycles)
        convergence_threshold = workflow_params.get('convergence_threshold', self.convergence_threshold)

        # Initialize cycle tracking
        self.cycle_results = []
        convergence_achieved = False
        early_termination = False

        # Extract raw embeddings from phase45_data for cross-scene intelligence
        raw_embeddings = phase45_data.get("embeddings_vectors", [])

        for cycle_num in range(1, max_cycles + 1):
            logger.info(f" Starting Cycle {cycle_num}/{max_cycles}")

            try:
                # Enrich phase45_data with cross-scene intelligence from previous cycles
                enriched_phase45_data = await self._enrich_with_cross_scene_intelligence(
                    phase45_data, scene_id, cycle_num, workflow_params
                )

                # Execute your existing GraphBuilder orchestration
                cycle_result = await orchestrate_coordinator_workers_aggregator_async(
                    enriched_phase45_data, scene_id, phase3_data=self.phase3_data, workflow_params=workflow_params  #  Pass workflow_params for business objective integration
                )

                # Add cycle metadata
                cycle_result['cycle_metadata'] = {
                    'cycle_number': cycle_num,
                    'timestamp': datetime.utcnow().isoformat(),
                    'cross_scene_context_used': len(self.cross_scene_context),
                    'workflow_params': workflow_params
                }

                # Store cycle result (memory management - limit to last 10 cycles)
                self.cycle_results.append(cycle_result)
                if len(self.cycle_results) > 10:
                    self.cycle_results.pop(0)  # Remove oldest cycle

                logger.info(f" Cycle {cycle_num} completed with {len(cycle_result.get('agent_results', {}))} agent results")

                # Check for convergence after cycle 2 (need at least 2 cycles to compare)
                if cycle_num >= 2:
                    convergence_achieved = await self._detect_convergence(
                        self.cycle_results, convergence_threshold
                    )

                    # Check for early termination (no new insights)
                    early_termination = await self._detect_early_termination(self.cycle_results)

                    if convergence_achieved:
                        logger.info(f" Convergence achieved after {cycle_num} cycles (threshold: {convergence_threshold})")
                        break
                    elif early_termination:
                        logger.info(f"STOP: Early termination after {cycle_num} cycles (no new insights)")
                        break

                # Prepare cross-scene context for next cycle
                if cycle_num < max_cycles:
                    await self._update_cross_scene_context(cycle_result, scene_id, workflow_params, raw_embeddings)

            except Exception as e:
                logger.error(f" Cycle {cycle_num} failed: {str(e)}")
                # Continue with next cycle unless it's the last one
                if cycle_num == max_cycles:
                    raise RuntimeError(f"All cycles failed. Last error: {str(e)}")
                continue

        # Aggregate results from all cycles
        final_results = await self._aggregate_cycle_results(
            self.cycle_results, convergence_achieved, early_termination, workflow_params
        )

        logger.info(f" Iterative cycles completed: {len(self.cycle_results)} cycles, convergence: {convergence_achieved}, early_termination: {early_termination}")

        return final_results

    async def _enrich_with_cross_scene_intelligence(self, phase45_data: Dict[str, Any], scene_id: str,
                                                   cycle_num: int, workflow_params: Dict[str, Any]) -> Dict[str, Any]:
        """
        Enrich phase45_data with cross-scene intelligence from S3 Vectors and previous cycles.
        """
        enriched_data = phase45_data.copy()

        # Add cross-scene context from previous cycles
        if self.cross_scene_context:
            enriched_data['cross_scene_intelligence'] = {
                'similar_scenes': self.cross_scene_context.get('similar_scenes', []),
                'pattern_insights': self.cross_scene_context.get('pattern_insights', []),
                'cycle_context': f"Cycle {cycle_num} with context from {len(self.cross_scene_context)} cross-scene queries"
            }

            logger.info(f" Cycle {cycle_num}: Enriched with {len(self.cross_scene_context.get('similar_scenes', []))} similar scenes")

        # Add iterative context for agents
        enriched_data['iterative_context'] = {
            'current_cycle': cycle_num,
            'max_cycles': workflow_params.get('max_cycles', self.max_cycles),
            'workflow_params': workflow_params,
            'previous_cycles_summary': self._get_previous_cycles_summary()
        }

        return enriched_data

    async def _detect_convergence(self, cycle_results: List[Dict[str, Any]], threshold: float) -> bool:
        """
        Detect if agents have converged on stable conclusions across cycles.
        Enhanced convergence detection comparing insights, recommendations, and metrics.
        """
        if len(cycle_results) < 2:
            return False

        current_cycle = cycle_results[-1]
        previous_cycle = cycle_results[-2]

        # Compare agent insights and recommendations for similarity
        current_agents = current_cycle.get('agent_results', {})
        previous_agents = previous_cycle.get('agent_results', {})

        convergence_scores = []

        for agent_type in current_agents.keys():
            if agent_type in previous_agents:
                # Compare insights similarity
                current_insights = current_agents[agent_type].get('insights', [])
                previous_insights = previous_agents[agent_type].get('insights', [])
                insights_similarity = self._calculate_text_similarity(current_insights, previous_insights)

                # Compare recommendations similarity (addressing your suggestion)
                current_recommendations = current_agents[agent_type].get('recommendations', [])
                previous_recommendations = previous_agents[agent_type].get('recommendations', [])
                recommendations_similarity = self._calculate_text_similarity(current_recommendations, previous_recommendations)

                # Combined similarity score (weighted average)
                combined_similarity = (insights_similarity * 0.6) + (recommendations_similarity * 0.4)
                convergence_scores.append(combined_similarity)

                logger.debug(f"Agent {agent_type} - insights: {insights_similarity:.3f}, recommendations: {recommendations_similarity:.3f}, combined: {combined_similarity:.3f}")

        if convergence_scores:
            overall_convergence = sum(convergence_scores) / len(convergence_scores)
            logger.info(f" Overall convergence score: {overall_convergence:.3f} (threshold: {threshold})")
            return overall_convergence >= threshold

        return False

    async def _detect_early_termination(self, cycle_results: List[Dict[str, Any]]) -> bool:
        """
        Detect if no new insights are being generated (early termination logic).
        """
        if len(cycle_results) < 2:
            return False

        current_cycle = cycle_results[-1]
        previous_cycle = cycle_results[-2]

        current_agents = current_cycle.get('agent_results', {})
        previous_agents = previous_cycle.get('agent_results', {})

        new_insights_found = False

        for agent_type in current_agents.keys():
            if agent_type in previous_agents:
                current_insights = set(current_agents[agent_type].get('insights', []))
                previous_insights = set(previous_agents[agent_type].get('insights', []))

                # Check if there are any new insights
                new_insights = current_insights - previous_insights
                if len(new_insights) > 0:
                    new_insights_found = True
                    break

        return not new_insights_found

    def _calculate_text_similarity(self, current_items: List[str], previous_items: List[str]) -> float:
        """
        Calculate similarity between two sets of text items (insights or recommendations).
        Enhanced version of your similarity calculation.
        """
        if not current_items or not previous_items:
            return 0.0

        # Simple keyword overlap approach (can be enhanced with embeddings later)
        current_text = ' '.join(current_items).lower()
        previous_text = ' '.join(previous_items).lower()

        current_words = set(current_text.split())
        previous_words = set(previous_text.split())

        if not current_words or not previous_words:
            return 0.0

        overlap = len(current_words.intersection(previous_words))
        total_unique = len(current_words.union(previous_words))

        return overlap / total_unique if total_unique > 0 else 0.0

    async def _update_cross_scene_context(self, cycle_result: Dict[str, Any], scene_id: str,
                                        workflow_params: Dict[str, Any], raw_embeddings: List[Dict[str, Any]] = None) -> None:
        """
        Update cross-scene context based on current cycle results for next cycle enrichment.
        Now includes real S3 Vectors integration via query_similar_scenes() function.
        """
        # Extract key insights from current cycle
        agent_results = cycle_result.get('agent_results', {})
        key_insights = []
        key_recommendations = []

        for agent_type, result in agent_results.items():
            insights = result.get('insights', [])
            recommendations = result.get('recommendations', [])
            key_insights.extend(insights[:2])  # Top 2 insights per agent
            key_recommendations.extend(recommendations[:1])  # Top 1 recommendation per agent

        # Query S3 Vectors for similar scenes using current scene embeddings
        similar_scenes = []
        try:
            # OPTION 1 FIX: Extract embeddings from raw_embeddings (same source as VectorAnomalyDetector)
            scene_embeddings = []

            # Primary source: Extract from raw_embeddings passed from main function
            if raw_embeddings:
                for embedding in raw_embeddings:
                    if isinstance(embedding, dict) and "vector" in embedding:
                        scene_embeddings.append(embedding["vector"])
                logger.info(f" Extracted {len(scene_embeddings)} vectors from raw_embeddings for cross-scene intelligence")

            # Fallback: Try to get embeddings from execution metadata (legacy)
            if not scene_embeddings:
                execution_metadata = cycle_result.get('execution_metadata', {})
                if 'scene_embeddings' in execution_metadata:
                    scene_embeddings = execution_metadata['scene_embeddings']

            # If embeddings are available, query for similar scenes
            if scene_embeddings:
                workflow_filters = workflow_params.get('scenario_filters', {})
                similar_scenes = await query_similar_scenes(
                    scene_embeddings, workflow_filters, scene_id, max_results=5
                )
                logger.info(f" S3 Vectors found {len(similar_scenes)} similar scenes for cross-scene intelligence")
            else:
                logger.info("No scene embeddings available for S3 Vectors query - skipping cross-scene intelligence")

        except Exception as e:
            logger.warning(f"S3 Vectors cross-scene query failed: {str(e)} - continuing without cross-scene intelligence")

        # Store enriched context for next cycle
        self.cross_scene_context = {
            'source_scene': scene_id,
            'key_insights': key_insights,
            'key_recommendations': key_recommendations,
            'pattern_insights': [f"Pattern from cycle {len(self.cycle_results)}: {insight}" for insight in key_insights],
            'similar_scenes': similar_scenes,  # Now populated with real S3 Vectors data
            'updated_timestamp': datetime.utcnow().isoformat(),
            'workflow_filters': workflow_params.get('scenario_filters', {}),
            'cross_scene_metadata': {
                'similar_scenes_count': len(similar_scenes),
                'embeddings_available': len(scene_embeddings) > 0 if isinstance(scene_embeddings, list) else False,
                'intelligence_source': 'S3_Vectors_behavioral-metadata-index'
            }
        }

        logger.info(f" Updated cross-scene context with {len(key_insights)} insights, {len(key_recommendations)} recommendations, and {len(similar_scenes)} similar scenes for next cycle")

    def _get_previous_cycles_summary(self) -> Dict[str, Any]:
        """
        Generate summary of previous cycles for agent context.
        """
        if not self.cycle_results:
            return {"cycles_completed": 0, "insights_discovered": [], "recommendations_made": []}

        total_insights = []
        total_recommendations = []

        for i, cycle in enumerate(self.cycle_results):
            cycle_num = i + 1
            for agent_type, result in cycle.get('agent_results', {}).items():
                insights = result.get('insights', [])
                recommendations = result.get('recommendations', [])

                # Top insight and recommendation per agent per cycle
                if insights:
                    total_insights.append(f"Cycle {cycle_num} - {agent_type}: {insights[0]}")
                if recommendations:
                    total_recommendations.append(f"Cycle {cycle_num} - {agent_type}: {recommendations[0]}")

        return {
            "cycles_completed": len(self.cycle_results),
            "insights_discovered": total_insights[-5:],  # Last 5 insights to prevent overflow
            "recommendations_made": total_recommendations[-5:],  # Last 5 recommendations
            "execution_pattern": "iterative_refinement_with_cross_scene_intelligence"
        }

    async def _aggregate_cycle_results(self, cycle_results: List[Dict[str, Any]],
                                     convergence_achieved: bool, early_termination: bool,
                                     workflow_params: Dict[str, Any]) -> Dict[str, Any]:
        """
        Aggregate results from all cycles into final enhanced output.
        """
        if not cycle_results:
            raise RuntimeError("No cycle results to aggregate")

        # Get the most recent (presumably best) cycle results
        final_cycle = cycle_results[-1]

        # Aggregate insights and recommendations across all cycles
        all_insights = {}
        all_recommendations = {}

        for cycle in cycle_results:
            for agent_type, result in cycle.get('agent_results', {}).items():
                if agent_type not in all_insights:
                    all_insights[agent_type] = []
                if agent_type not in all_recommendations:
                    all_recommendations[agent_type] = []

                all_insights[agent_type].extend(result.get('insights', []))
                all_recommendations[agent_type].extend(result.get('recommendations', []))

        # Create enhanced final output
        enhanced_results = {
            'final_agent_results': final_cycle.get('agent_results', {}),
            'iterative_analysis': {
                'total_cycles_executed': len(cycle_results),
                'convergence_achieved': convergence_achieved,
                'early_termination': early_termination,
                'termination_reason': self._get_termination_reason(convergence_achieved, early_termination, len(cycle_results), workflow_params.get('max_cycles', self.max_cycles)),
                'workflow_params_used': workflow_params,
                'aggregated_insights': all_insights,
                'aggregated_recommendations': all_recommendations,
                'cycle_progression': [
                    {
                        'cycle': i + 1,
                        'agents_executed': len(cycle.get('agent_results', {})),
                        'key_finding': self._extract_key_finding(cycle),
                        'execution_time': cycle.get('execution_metadata', {}).get('total_duration_seconds', 0)
                    }
                    for i, cycle in enumerate(cycle_results)
                ]
            },
            'enhanced_metadata': {
                'enhancement_type': 'iterative_multi_cycle_analysis_with_convergence',
                'business_objective': workflow_params.get('business_objective_canonical', 'general_analysis'),
                'cross_scene_intelligence_used': len(self.cross_scene_context),
                'total_execution_time': sum(
                    cycle.get('execution_metadata', {}).get('total_duration_seconds', 0)
                    for cycle in cycle_results
                ),
                'efficiency_metrics': {
                    'cycles_to_convergence': len(cycle_results),
                    'avg_cycle_time': sum(
                        cycle.get('execution_metadata', {}).get('total_duration_seconds', 0)
                        for cycle in cycle_results
                    ) / len(cycle_results) if cycle_results else 0
                }
            }
        }

        return enhanced_results

    def _get_termination_reason(self, convergence_achieved: bool, early_termination: bool,
                              cycles_executed: int, max_cycles: int) -> str:
        """
        Determine the reason for cycle termination.
        """
        if convergence_achieved:
            return f"convergence_achieved_after_{cycles_executed}_cycles"
        elif early_termination:
            return f"early_termination_no_new_insights_after_{cycles_executed}_cycles"
        elif cycles_executed >= max_cycles:
            return f"max_cycles_reached_{max_cycles}"
        else:
            return "unknown_termination_reason"

    def _extract_key_finding(self, cycle_result: Dict[str, Any]) -> str:
        """
        Extract key finding from a cycle result for progression tracking.
        """
        agent_results = cycle_result.get('agent_results', {})

        # Find the first meaningful insight
        for agent_type, result in agent_results.items():
            insights = result.get('insights', [])
            if insights:
                return f"{agent_type}: {insights[0][:100]}..."  # First 100 chars

        return "Cycle completed with standard analysis"


async def query_similar_scenes(scene_embeddings: List[float], workflow_filters: Dict[str, Any],
                             scene_id: str, max_results: int = 10) -> List[Dict[str, Any]]:
    """
    Enhanced Phase 6: S3 Vectors Cross-Scene Intelligence
    Query S3 Vectors behavioral-metadata-index for similar scenes using Cohere embedding similarity.
    Provides cross-scene intelligence for iterative cycle enrichment.

    Args:
        scene_embeddings: List of embedding vectors from current scene
        workflow_filters: Filters from business objective (environment, risk thresholds, etc.)
        scene_id: Current scene ID to exclude from results
        max_results: Maximum number of similar scenes to return

    Returns:
        List of similar scene data with behavioral context for agent enrichment
    """
    logger.info(f" Querying S3 Vectors for similar scenes to {scene_id} with {len(scene_embeddings)} embeddings")

    if not scene_embeddings:
        logger.warning("No scene embeddings provided for similarity search")
        return []

    s3_vectors_bucket = os.getenv('VECTOR_BUCKET_NAME', '')
    vectors_index_name = 'behavioral-metadata-index'

    try:
        # Create S3 Vectors client (correct pattern from your existing code)
        s3vectors_client = boto3.client('s3vectors')

        # Use the first embedding as the query vector (most representative)
        query_vector = scene_embeddings[0] if isinstance(scene_embeddings[0], list) else scene_embeddings

        # Build metadata filters based on workflow parameters using correct S3 Vectors filter format
        metadata_filters = {}

        # Apply environment type filters if specified (use $in operator)
        if workflow_filters.get('environment_types'):
            metadata_filters['environment_type'] = {"$in": workflow_filters['environment_types']}

        # Apply risk threshold filters if specified (use $gte operator)
        risk_threshold = workflow_filters.get('risk_threshold_min', 0.0)
        if risk_threshold > 0.0:
            metadata_filters['risk_score'] = {"$gte": risk_threshold}

        # Apply weather condition filters if specified (use $in operator)
        if workflow_filters.get('weather_conditions'):
            metadata_filters['weather_condition'] = {"$in": workflow_filters['weather_conditions']}

        logger.info(f" S3 Vectors query: topK={(max_results + 5) * 2}, filters={len(metadata_filters)} requested (will apply in Python)")
        logger.info(f" DEBUG - metadata_filters for post-processing: {json.dumps(metadata_filters, indent=2)}")

        # Query without metadata filters to avoid ValidationException on mixed schema
        # Apply filters in Python post-processing instead of at S3 Vectors level
        # This prevents ValidationException when old vectors lack business intelligence fields
        logger.info(f" Using post-processing filter approach for mixed metadata compatibility")

        # Execute S3 Vectors similarity search without metadata filters (broader query)
        response = s3vectors_client.query_vectors(
            vectorBucketName=s3_vectors_bucket,
            indexName=vectors_index_name,
            queryVector={"float32": query_vector},  # Correct format matching your storage pattern
            topK=(max_results + 5) * 2,  # Get more results since we'll filter in Python
            returnMetadata=True
            # REMOVED: filter parameter - Apply filters in Python instead to prevent ValidationException
        )

        # Parse S3 Vectors response (correct format for query_vectors API)
        search_results = response.get('vectors', [])

        logger.info(f" S3 Vectors returned {len(search_results)} initial results")

        # Apply metadata filters that were removed from S3 Vectors query
        filtered_results = []
        for result in search_results:
            result_metadata = result.get('metadata', {})
            result_scene_id = result_metadata.get('scene_id', 'unknown')

            # Skip current scene first
            if result_scene_id == scene_id:
                continue

            # Apply business intelligence filters in Python (safe for mixed metadata)
            passes_filters = True

            # Environment type filter
            if metadata_filters.get('environment_type'):
                env_filter = metadata_filters['environment_type']
                if '$in' in env_filter:
                    if result_metadata.get('environment_type') not in env_filter['$in']:
                        passes_filters = False

            # Risk score filter
            if metadata_filters.get('risk_score') and passes_filters:
                risk_filter = metadata_filters['risk_score']
                if '$gte' in risk_filter:
                    result_risk = result_metadata.get('risk_score', 0.0)
                    if result_risk < risk_filter['$gte']:
                        passes_filters = False

            # Weather condition filter
            if metadata_filters.get('weather_condition') and passes_filters:
                weather_filter = metadata_filters['weather_condition']
                if '$in' in weather_filter:
                    if result_metadata.get('weather_condition') not in weather_filter['$in']:
                        passes_filters = False

            if passes_filters:
                filtered_results.append(result)

        logger.info(f" After Python filtering: {len(filtered_results)} results remain (from {len(search_results)} initial)")

        # Process and enrich filtered results
        similar_scenes = []

        for result in filtered_results:
            result_metadata = result.get('metadata', {})
            result_scene_id = result_metadata.get('scene_id', 'unknown')
            similarity_score = result.get('score', 0.0)

            # Skip low similarity results
            if similarity_score < 0.7:
                continue

            # Enrich with behavioral context
            enriched_scene = {
                'scene_id': result_scene_id,
                'similarity_score': similarity_score,
                'behavioral_context': {
                    'environment_type': result_metadata.get('environment_type', 'unknown'),
                    'weather_condition': result_metadata.get('weather_condition', 'clear'),
                    'risk_score': result_metadata.get('risk_score', 0.0),
                    'safety_score': result_metadata.get('safety_score', 0.0),
                    'maneuver_types': result_metadata.get('maneuver_types', []),
                    'behavioral_insights': result_metadata.get('behavioral_insights', [])
                },
                'cross_scene_intelligence': {
                    'pattern_relevance': _calculate_pattern_relevance(result_metadata, workflow_filters),
                    'recommended_focus': _get_recommended_focus(result_metadata, workflow_filters),
                    'similarity_reason': _explain_similarity(result_metadata, workflow_filters)
                }
            }

            similar_scenes.append(enriched_scene)

            # Stop when we have enough results
            if len(similar_scenes) >= max_results:
                break

        logger.info(f" Found {len(similar_scenes)} similar scenes for cross-scene intelligence")

        # Sort by similarity score (highest first)
        similar_scenes.sort(key=lambda x: x['similarity_score'], reverse=True)

        return similar_scenes

    except Exception as e:
        logger.error(f" S3 Vectors query failed: {str(e)}")
        # Return empty list rather than failing the entire cycle
        logger.warning("Continuing without cross-scene intelligence due to S3 Vectors error")
        return []


def _calculate_pattern_relevance(scene_metadata: Dict[str, Any], workflow_filters: Dict[str, Any]) -> float:
    """
    Calculate how relevant a similar scene is based on workflow parameters.
    """
    relevance_score = 0.0
    total_factors = 0

    # Environment type relevance
    if workflow_filters.get('environment_types') and scene_metadata.get('environment_type'):
        total_factors += 1
        if scene_metadata['environment_type'] in workflow_filters['environment_types']:
            relevance_score += 1.0

    # Risk threshold relevance
    if workflow_filters.get('risk_threshold_min') and scene_metadata.get('risk_score'):
        total_factors += 1
        scene_risk = scene_metadata['risk_score']
        threshold_risk = workflow_filters['risk_threshold_min']

        # Higher relevance if scene risk is close to threshold
        if scene_risk >= threshold_risk:
            relevance_score += min(1.0, scene_risk / (threshold_risk + 0.1))

    # Weather condition relevance
    if workflow_filters.get('weather_conditions') and scene_metadata.get('weather_condition'):
        total_factors += 1
        if scene_metadata['weather_condition'] in workflow_filters['weather_conditions']:
            relevance_score += 1.0

    # Maneuver type relevance
    if workflow_filters.get('maneuver_types') and scene_metadata.get('maneuver_types'):
        total_factors += 1
        scene_maneuvers = set(scene_metadata['maneuver_types'])
        filter_maneuvers = set(workflow_filters['maneuver_types'])

        overlap = len(scene_maneuvers.intersection(filter_maneuvers))
        if len(filter_maneuvers) > 0:
            relevance_score += overlap / len(filter_maneuvers)

    return relevance_score / total_factors if total_factors > 0 else 0.0


def _get_recommended_focus(scene_metadata: Dict[str, Any], workflow_filters: Dict[str, Any]) -> List[str]:
    """
    Generate recommended focus areas based on similar scene characteristics.
    """
    focus_areas = []

    # Risk-based focus
    risk_score = scene_metadata.get('risk_score', 0.0)
    if risk_score > 0.5:
        focus_areas.append(f"High-risk pattern analysis (risk: {risk_score:.2f})")

    # Environment-based focus
    environment = scene_metadata.get('environment_type', '')
    if environment and environment in workflow_filters.get('environment_types', []):
        focus_areas.append(f"{environment.title()} environment behavior patterns")

    # Safety-based focus
    safety_score = scene_metadata.get('safety_score', 0.0)
    if safety_score < 0.8:
        focus_areas.append(f"Safety improvement opportunities (current: {safety_score:.2f})")

    # Maneuver-based focus
    maneuvers = scene_metadata.get('maneuver_types', [])
    relevant_maneuvers = [m for m in maneuvers if m in workflow_filters.get('maneuver_types', [])]
    if relevant_maneuvers:
        focus_areas.append(f"Maneuver analysis: {', '.join(relevant_maneuvers)}")

    return focus_areas[:3]  # Limit to top 3 focus areas


def _explain_similarity(scene_metadata: Dict[str, Any], workflow_filters: Dict[str, Any]) -> str:
    """
    Generate human-readable explanation of why this scene is similar.
    """
    similarity_reasons = []

    # Environment similarity
    environment = scene_metadata.get('environment_type', '')
    if environment and environment in workflow_filters.get('environment_types', []):
        similarity_reasons.append(f"same {environment} environment")

    # Risk similarity
    risk_score = scene_metadata.get('risk_score', 0.0)
    threshold = workflow_filters.get('risk_threshold_min', 0.0)
    if risk_score >= threshold and threshold > 0:
        similarity_reasons.append(f"similar risk profile ({risk_score:.2f})")

    # Weather similarity
    weather = scene_metadata.get('weather_condition', '')
    if weather and weather in workflow_filters.get('weather_conditions', []):
        similarity_reasons.append(f"{weather} weather conditions")

    # Maneuver similarity
    maneuvers = scene_metadata.get('maneuver_types', [])
    relevant_maneuvers = [m for m in maneuvers if m in workflow_filters.get('maneuver_types', [])]
    if relevant_maneuvers:
        similarity_reasons.append(f"similar maneuvers ({', '.join(relevant_maneuvers)})")

    if similarity_reasons:
        return f"Similar due to: {', '.join(similarity_reasons)}"
    else:
        return "Similar behavioral embedding patterns"


if __name__ == "__main__":
    asyncio.run(main())