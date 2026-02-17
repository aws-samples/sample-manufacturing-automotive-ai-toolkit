"""Camera ID utility functions."""
import logging

logger = logging.getLogger(__name__)


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
