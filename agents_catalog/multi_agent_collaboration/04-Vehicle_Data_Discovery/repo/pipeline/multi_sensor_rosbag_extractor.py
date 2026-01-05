#!/usr/bin/env python3
"""
Fleet Discovery Studio - Multi-Sensor RosBag Extractor (Phase 1)
Production-grade implementation with single-pass ROS bag processing and separation of concerns.
"""

import os
import sys
import json
import boto3
import logging
from datetime import datetime
from typing import Dict, Any, List, Tuple
from rosbags.rosbag1 import Reader
from rosbags.serde import deserialize_cdr

# Configure logging
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)

# Global AWS clients for performance
s3_client = boto3.client('s3')
sfn_client = boto3.client('stepfunctions')

def main():
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

        if not all([scene_id, input_s3_key, output_s3_key]):
            raise ValueError("Required environment variables: SCENE_ID, INPUT_S3_KEY, OUTPUT_S3_KEY")

        logger.info(f"Starting multi-sensor extraction for scene: {scene_id}")

        # AWS Handler: Download input from S3
        local_bag_path = f"/tmp/{scene_id}.bag"
        logger.info(f"Downloading ROS bag from S3...")
        s3_client.download_file(s3_bucket, input_s3_key, local_bag_path)

        # Single-pass bag extraction (no AWS dependencies)
        extraction_results = extract_multisensor_data_single_pass(local_bag_path, scene_id)

        # AWS Handler: Upload output to S3
        output_data = {
            "scene_id": scene_id,
            "input_file": input_s3_key,
            "extraction_timestamp": datetime.utcnow().isoformat(),
            **extraction_results
        }

        s3_client.put_object(
            Bucket=s3_bucket,
            Key=output_s3_key,
            Body=json.dumps(output_data, indent=2),
            ContentType='application/json'
        )

        # AWS Handler: Verify output exists
        verify_s3_output_exists(s3_bucket, output_s3_key)

        # AWS Handler: Report success to Step Functions
        success_payload = {
            "output_s3_key": output_s3_key,
            "s3_uri": f"s3://{s3_bucket}/{output_s3_key}",
            "scene_id": scene_id,
            "extraction_summary": {
                "total_frames": extraction_results["frame_count"],
                "total_telemetry_points": extraction_results["telemetry_points"],
                "sensors_processed": list(extraction_results["sensors"].keys())
            },
            "timestamp": datetime.utcnow().isoformat(),
            "status": "SUCCESS"
        }

        sfn_client.send_task_success(
            taskToken=task_token,
            output=json.dumps(success_payload)
        )

        # Cleanup
        os.remove(local_bag_path)
        logger.info(f"Phase 1 completed successfully")

    except Exception as e:
        logger.error(f"Phase 1 failed: {str(e)}")

        # AWS Handler: Report failure to Step Functions
        if task_token:
            try:
                sfn_client.send_task_failure(
                    taskToken=task_token,
                    error="Phase1.ExtractionFailed",
                    cause=f"Multi-sensor extraction failed: {str(e)}"
                )
            except Exception as callback_error:
                logger.error(f"Failed to send callback: {str(callback_error)}")

        sys.exit(1)


def extract_multisensor_data_single_pass(bag_path: str, scene_id: str) -> Dict[str, Any]:
    """
    Single-pass ROS bag extraction (no AWS dependencies)

    Args:
        bag_path: Local path to ROS bag file
        scene_id: Scene identifier

    Returns:
        Dictionary with extraction results
    """
    logger.info(f"Processing ROS bag in single pass: {bag_path}")

    # Initialize result containers
    camera_frames = []
    lidar_points = []
    telemetry_data = []
    vehicle_data = []

    # Use dynamic topic discovery instead of hard-coded topics
    # Initialize topic sets - will be populated dynamically
    camera_topics = set()
    lidar_topics = set()
    telemetry_topics = set()
    vehicle_topics = set()

    # SINGLE PASS: Read bag once and dispatch by topic
    with Reader(bag_path) as reader:
        for (connection, timestamp, rawdata) in reader.messages():
            try:
                topic = connection.topic

                # Convert timestamp from nanoseconds to seconds (compatible with old API)
                t_sec = timestamp / 1e9

                # Create timestamp object with to_sec() method for compatibility
                class TimestampCompat:
                    def __init__(self, sec):
                        self.sec = sec
                    def to_sec(self):
                        return self.sec

                t = TimestampCompat(t_sec)

                # Classify by ROS message type (not topic names - robust approach)
                sensor_type = classify_by_message_type(connection)

                # Handle binary vs structured data based on message type
                msg_type_str = str(connection.msgtype)

                # For compressed images: DON'T deserialize binary data, extract metadata only
                if 'CompressedImage' in msg_type_str:
                    # Create minimal message object with basic metadata for compressed images
                    class CompressedImageMeta:
                        def __init__(self):
                            self.format = "jpeg"  # Default format for compressed images
                            self.data_size = len(rawdata)
                    msg = CompressedImageMeta()

                # For regular structured messages: Safe to deserialize
                else:
                    try:
                        msg = deserialize_cdr(rawdata, connection.msgtype)
                    except Exception as deser_error:
                        # Skip messages that can't be deserialized (e.g. unknown message types)
                        logger.debug(f"Skipping message from {topic}: deserialization failed")
                        continue

                if sensor_type == 'camera':
                    camera_topics.add(topic)
                    camera_frames.append(process_camera_message(topic, msg, t))
                elif sensor_type == 'lidar':
                    lidar_topics.add(topic)
                    lidar_points.append(process_lidar_message(topic, msg, t))
                elif sensor_type == 'telemetry':
                    telemetry_topics.add(topic)
                    telemetry_data.append(process_telemetry_message(topic, msg, t))
                elif sensor_type == 'vehicle':
                    vehicle_topics.add(topic)
                    vehicle_data.append(process_vehicle_message(topic, msg, t))
                # Note: 'unknown' types are ignored, not an error

                # Progress logging
                total_messages = len(camera_frames) + len(lidar_points) + len(telemetry_data) + len(vehicle_data)
                if total_messages % 1000 == 0:
                    logger.info(f"Processed {total_messages} messages...")

            except Exception as msg_error:
                logger.warning(f"Failed to process message from {connection.topic}: {str(msg_error)}")
                continue

    logger.info(f"Extraction complete: {len(camera_frames)} camera, {len(lidar_points)} lidar, {len(telemetry_data)} telemetry, {len(vehicle_data)} vehicle messages")

    return {
        "sensors": {
            "cameras": camera_frames,
            "lidar": lidar_points,
            "telemetry": telemetry_data,
            "vehicle_state": vehicle_data
        },
        "frame_count": len(camera_frames),
        "telemetry_points": len(telemetry_data)
    }


def classify_by_message_type(connection) -> str:
    """
    Classify sensor data by ROS message type (robust approach - no hard-coding)

    Uses standardized ROS message types instead of guessing from topic names.
    This works regardless of how topics are named.

    Args:
        connection: ROS bag connection object with msgtype attribute

    Returns:
        str: 'camera', 'lidar', 'telemetry', 'vehicle', or 'unknown'
    """
    msg_type_str = str(connection.msgtype)

    # Camera/Image data - standardized ROS message types
    if any(image_type in msg_type_str for image_type in ['Image', 'CompressedImage']):
        return 'camera'

    # LiDAR/Point Cloud data - standardized ROS message types
    elif any(lidar_type in msg_type_str for lidar_type in ['PointCloud', 'LaserScan']):
        return 'lidar'

    # Telemetry/Navigation data - standardized ROS message types
    elif any(nav_type in msg_type_str for nav_type in ['Imu', 'Odometry', 'PoseStamped', 'TwistStamped', 'NavSatFix']):
        return 'telemetry'

    # Vehicle state data - standardized ROS message types
    elif any(vehicle_type in msg_type_str for vehicle_type in ['Twist', 'Float32', 'Float64', 'JointState']):
        return 'vehicle'

    else:
        # Unknown message type - not an error, just skip
        return 'unknown'


def process_camera_message(topic: str, msg, timestamp) -> Dict[str, Any]:
    """Process individual camera message (handles both regular and compressed images)"""

    # Check if this is our compressed image metadata object
    if hasattr(msg, 'data_size') and hasattr(msg, 'format'):
        # Compressed image - extract basic metadata
        return {
            "topic": topic,
            "timestamp": timestamp.to_sec(),
            "format": getattr(msg, 'format', 'jpeg'),
            "data_size": getattr(msg, 'data_size', 0),
            "encoding": "compressed",
            "width": 1600,  # Default Tesla camera resolution
            "height": 900   # Default Tesla camera resolution
        }
    else:
        # Regular image message - extract standard attributes
        return {
            "topic": topic,
            "timestamp": timestamp.to_sec(),
            "width": getattr(msg, 'width', 0),
            "height": getattr(msg, 'height', 0),
            "encoding": getattr(msg, 'encoding', 'unknown')
        }


def process_lidar_message(topic: str, msg, timestamp) -> Dict[str, Any]:
    """Process individual LIDAR message"""
    return {
        "topic": topic,
        "timestamp": timestamp.to_sec(),
        "point_count": getattr(msg, 'width', 0) * getattr(msg, 'height', 0),
        "fields": [field.name for field in getattr(msg, 'fields', [])]
    }


def process_telemetry_message(topic: str, msg, timestamp) -> Dict[str, Any]:
    """Process individual telemetry message"""
    telemetry_point = {
        "topic": topic,
        "timestamp": timestamp.to_sec(),
        "message_type": type(msg).__name__
    }

    # Extract position if available
    if hasattr(msg, 'pose') and hasattr(msg.pose, 'pose'):
        telemetry_point["position"] = {
            "x": msg.pose.pose.position.x,
            "y": msg.pose.pose.position.y,
            "z": msg.pose.pose.position.z
        }

    # Extract acceleration if available
    if hasattr(msg, 'linear_acceleration'):
        telemetry_point["acceleration"] = {
            "x": msg.linear_acceleration.x,
            "y": msg.linear_acceleration.y,
            "z": msg.linear_acceleration.z
        }

    return telemetry_point


def process_vehicle_message(topic: str, msg, timestamp) -> Dict[str, Any]:
    """Process individual vehicle state message"""
    return {
        "topic": topic,
        "timestamp": timestamp.to_sec(),
        "value": getattr(msg, 'data', str(msg))
    }


def verify_s3_output_exists(bucket: str, key: str) -> None:
    """Verify output file was created in S3"""
    try:
        response = s3_client.head_object(Bucket=bucket, Key=key)
        file_size = response.get('ContentLength', 0)
        if file_size == 0:
            raise RuntimeError(f"Output file exists but is empty: s3://{bucket}/{key}")
        logger.info(f"Verified output: s3://{bucket}/{key} ({file_size} bytes)")
    except s3_client.exceptions.NoSuchKey:
        raise RuntimeError(f"Output file not created: s3://{bucket}/{key}")


if __name__ == "__main__":
    main()
