"""Pipeline routes - execution status."""
import logging
from fastapi import APIRouter

from dependencies import sfn, STATE_MACHINE_ARN

logger = logging.getLogger(__name__)
router = APIRouter(tags=["pipeline"])


@router.get("/pipeline/executions")
def get_pipeline_status():
    """Get recent pipeline executions"""
    try:
        if not STATE_MACHINE_ARN:
            return {"executions": [], "message": "State machine not configured"}

        response = sfn.list_executions(
            stateMachineArn=STATE_MACHINE_ARN,
            maxResults=10,
            statusFilter='RUNNING'
        )

        running = []
        for exec in response.get('executions', []):
            running.append({
                "execution_id": exec['name'],
                "status": exec['status'],
                "start_time": exec['startDate'].isoformat() if exec.get('startDate') else None
            })

        # Also get recent completed
        completed_response = sfn.list_executions(
            stateMachineArn=STATE_MACHINE_ARN,
            maxResults=5,
            statusFilter='SUCCEEDED'
        )

        completed = []
        for exec in completed_response.get('executions', []):
            completed.append({
                "execution_id": exec['name'],
                "status": exec['status'],
                "start_time": exec['startDate'].isoformat() if exec.get('startDate') else None,
                "end_time": exec.get('stopDate', exec['startDate']).isoformat() if exec.get('stopDate') or exec.get('startDate') else None
            })

        return {
            "running": running,
            "recent_completed": completed,
            "state_machine_arn": STATE_MACHINE_ARN
        }
    except Exception as e:
        logger.error(f"Error getting pipeline status: {e}")
        return {"executions": [], "error": str(e)}
