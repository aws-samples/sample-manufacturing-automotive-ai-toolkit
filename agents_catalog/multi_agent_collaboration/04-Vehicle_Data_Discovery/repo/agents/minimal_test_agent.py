#!/usr/bin/env python3
"""
Minimal test agent to isolate timeout root cause
"""

import json
import logging
from datetime import datetime
from typing import Dict, Any
from bedrock_agentcore.runtime import BedrockAgentCoreApp

# Configure logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# AgentCore Application
app = BedrockAgentCoreApp()

@app.entrypoint
async def invoke(payload: Dict[str, Any]) -> Dict[str, Any]:
    """Minimal test entrypoint"""
    logger.info("Minimal test agent invoked successfully")
    return {
        "status": "success",
        "message": "Minimal agent initialized and running",
        "timestamp": datetime.utcnow().isoformat()
    }

if __name__ == "__main__":
    logger.info("Starting minimal test agent")
    app.run()