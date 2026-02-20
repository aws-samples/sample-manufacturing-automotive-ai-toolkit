#!/usr/bin/env python3
"""
Copyright Amazon.com, Inc. or its affiliates. All Rights Reserved. SPDX-License-Identifier: MIT-0

SFC Knowledge Base
Provides a knowledge base of SFC configurations, protocols, targets, and other related information
"""

from typing import Dict, Any


def what_is_sfc() -> str:
    """Provide an explanation of what SFC (Shop Floor Connectivity) is

    Returns:
        String explanation of SFC
    """
    return """
🏭 **Shop Floor Connectivity (SFC)**

Shop Floor Connectivity (SFC) is an industrial data ingestion enabler, that can quickly deliver customizable greenfield & brownfield connectivity solutions.

**Key Features:**
• **Industrial Connectivity**: Connect to various industrial protocols and devices
• **Flexible Integration**: Support for both greenfield (new) and existing (brownfield) installations
• **Data Ingestion**: Collect, transform, and route industrial data
• **AWS Integration**: Seamless connection to AWS services for processing and analysis
• **Customizable**: Adaptable to specific industrial environments and requirements
• **Scalable**: Handle diverse data volumes from industrial equipment

**Benefits:**
• Accelerate digital transformation of industrial environments
• Bridge the gap between OT (Operational Technology) and IT systems
• Enable data-driven decision making for manufacturing processes
• Reduce time-to-value for industrial IoT implementations
• Simplify complex industrial data integration challenges
"""


def load_sfc_knowledge() -> Dict[str, Any]:
    """Load SFC framework knowledge base

    Returns:
        Dictionary containing SFC framework knowledge
    """
    return {
        "supported_protocols": {
            "OPCUA": {
                "description": "OPC Unified Architecture",
                "port_default": 4840,
            },
            "MODBUS": {"description": "Modbus TCP/IP", "port_default": 502},
            "S7": {"description": "Siemens S7 Communication", "port_default": 102},
            "MQTT": {
                "description": "Message Queuing Telemetry Transport",
                "port_default": 1883,
            },
            "REST": {"description": "RESTful HTTP API", "port_default": 80},
            "SQL": {"description": "SQL Database", "port_default": 1433},
            "SNMP": {
                "description": "Simple Network Management Protocol",
                "port_default": 161,
            },
            "PCCC": {
                "description": "Allen-Bradley Rockwell PCCC",
                "port_default": 44818,
            },
            "ADS": {"description": "Beckhoff ADS", "port_default": 48898},
            "J1939": {
                "description": "Vehicle CAN Bus Protocol",
                "port_default": None,
            },
            "SLMP": {"description": "Mitsubishi/Melsec SLMP", "port_default": 5007},
            "NATS": {"description": "NATS Messaging", "port_default": 4222},
            "OPCDA": {"description": "OPC Data Access", "port_default": None},
            "SIMULATOR": {"description": "Data Simulator", "port_default": None},
        },
        "aws_targets": {
            "AWS-IOT-CORE": {"service": "AWS IoT Core", "real_time": True},
            "AWS-IOT-ANALYTICS": {
                "service": "AWS IoT Analytics",
                "real_time": False,
            },
            "AWS-SITEWISE": {"service": "AWS IoT SiteWise", "real_time": True},
            "AWS-S3": {"service": "Amazon S3", "real_time": False},
            "AWS-S3-TABLES": {
                "service": "Amazon S3 Tables (S3Tables)",
                "real_time": False,
                "description": "AWS S3 Tables (also known as S3Tables, Iceberg or AWS-S3-TABLES) target adapter enables writing data to S3 in a structured format based on Apache Iceberg table format. Supports Parquet, JSON, and CSV formats with customizable partitioning, schema definition, and compression options. The Iceberg-compatible format allows for efficient data querying and analytics.",
            },
            "AWS-KINESIS": {"service": "Amazon Kinesis", "real_time": True},
            "AWS-KINESIS-FIREHOSE": {
                "service": "Amazon Kinesis Data Firehose",
                "real_time": False,
            },
            "AWS-LAMBDA": {"service": "AWS Lambda", "real_time": True},
            "AWS-SNS": {"service": "Amazon SNS", "real_time": True},
            "AWS-SQS": {"service": "Amazon SQS", "real_time": True},
            "AWS-TIMESTREAM": {"service": "Amazon Timestream", "real_time": True},
            "AWS-MSK": {"service": "Amazon MSK", "real_time": True},
        },
        "edge_targets": {
            "OPCUA": {"description": "OPC-UA Server"},
            "OPCUA-WRITER": {"description": "OPC-UA Writer"},
            "DEBUG": {"description": "Debug Terminal"},
            "FILE": {"description": "File System"},
            "MQTT": {"description": "MQTT Broker"},
            "NATS": {"description": "NATS Server"},
        },
        "common_issues": {
            "connection": [
                "Network connectivity",
                "Firewall rules",
                "Authentication",
            ],
            "configuration": [
                "Missing required fields",
                "Invalid JSON",
                "Type mismatches",
            ],
            "performance": [
                "High CPU usage",
                "Memory leaks",
                "Network bottlenecks",
            ],
            "data_quality": [
                "Missing data points",
                "Timestamp issues",
                "Data transformation errors",
            ],
        },
        "required_config_sections": [
            "AWSVersion",
            "Schedules",
            "Sources",
            "Targets",
        ],
        "aws_version": "2022-04-02",
    }
