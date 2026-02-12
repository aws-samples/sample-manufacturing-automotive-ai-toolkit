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
            return {"executions": [], "total_running": 0, "state_machine_arn": ""}

        def get_current_phase(execution_arn: str, status: str) -> dict:
            if status != 'RUNNING':
                return {"current_phase": None, "phase_number": None}
            try:
                history = sfn.get_execution_history(executionArn=execution_arn, reverseOrder=True, maxResults=10)
                phase_mapping = {'Phase1Task': 1, 'Phase2Task': 2, 'Phase3Task': 3, 'Phase4Task': 4, 'Phase5Task': 5, 'Phase6Task': 6}
                for event in history.get('events', []):
                    if event.get('type') == 'TaskStateEntered':
                        state_name = event.get('stateEnteredEventDetails', {}).get('name', '')
                        if state_name in phase_mapping:
                            return {"current_phase": state_name, "phase_number": phase_mapping[state_name]}
                return {"current_phase": "Starting", "phase_number": 1}
            except:
                return {"current_phase": None, "phase_number": None}

        response = sfn.list_executions(stateMachineArn=STATE_MACHINE_ARN, maxResults=10)

        executions = []
        for exc in response.get('executions', []):
            name = exc['name']
            parts = name.split('-')
            scene_id = f"scene-{parts[2]}" if len(parts) >= 3 and 'fleet-scene-' in name else name
            
            execution_arn = exc.get('executionArn', f"{STATE_MACHINE_ARN.replace(':stateMachine:', ':execution:')}:{name}")
            phase_info = get_current_phase(execution_arn, exc['status'])

            executions.append({
                "execution_id": name,
                "status": exc['status'],
                "start_date": exc['startDate'].isoformat() if exc.get('startDate') else None,
                "scene_id": scene_id,
                "state_machine": "6-Phase Pipeline",
                "current_phase": phase_info["current_phase"],
                "phase_number": phase_info["phase_number"]
            })

        return {
            "executions": executions,
            "total_running": len([e for e in executions if e["status"] == "RUNNING"]),
            "state_machine_arn": STATE_MACHINE_ARN
        }
    except Exception as e:
        logger.error(f"Error getting pipeline status: {e}")
        return {"executions": [], "total_running": 0, "error": str(e)}
