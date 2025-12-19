#!/usr/bin/env python
"""
SFC Documentation MCP Server

This server provides tools to interact with the Shopfloor Connectivity (SFC)
GitHub repository documentation and functionality.
"""

import os
import re
import json
import git
from fastmcp import FastMCP
from typing import Dict, Any, Optional, List


# Define the repository path
REPO_PATH = os.path.join(os.path.dirname(os.path.abspath(__file__)), "sfc-repo")

# Define the repository URL from environment variable with a fallback to default
REPO_URL = os.environ.get(
    "SFC_REPO_URL", "https://github.com/awslabs/industrial-shopfloor-connect.git"
)


# tools-functions


def generate_config_template(
    protocol: str, target: str, environment: str, sfc_knowledge: Dict[str, Any]
) -> str:
    """Generate a configuration template

    Args:
        protocol: Source protocol (e.g., OPCUA, MODBUS, S7)
        target: Target service (e.g., AWS-S3, AWS-IOT-CORE, DEBUG)
        environment: Environment type (development, production)
        sfc_knowledge: Dictionary containing SFC framework knowledge

    Returns:
        String containing the generated configuration template
    """
    if protocol not in sfc_knowledge["supported_protocols"]:
        return f"❌ Unsupported protocol: {protocol}. Supported: {', '.join(sfc_knowledge['supported_protocols'].keys())}"

    # Create basic template structure
    template = {
        "AWSVersion": sfc_knowledge["aws_version"],
        "Name": f"{protocol} to {target} Configuration",
        "Description": f"{environment.title()} configuration for {protocol} protocol to {target} target",
        "LogLevel": "Info" if environment == "production" else "Trace",
        "Schedules": [
            {
                "Name": f"{protocol}Schedule",
                "Interval": 1000 if environment == "development" else 5000,
                "Active": True,
                "TimestampLevel": "Both",
                "Sources": {f"{protocol}-SOURCE": ["*"]},
                "Targets": [f"{target}Target"],
            }
        ],
        "Sources": generate_source_template(protocol, sfc_knowledge),
        "Targets": generate_target_template(target, environment, sfc_knowledge),
        "TargetTypes": generate_target_types(target, sfc_knowledge),
        "AdapterTypes": generate_adapter_types(protocol, sfc_knowledge),
        "ProtocolAdapters": generate_protocol_adapter_config(protocol, sfc_knowledge),
    }

    return f"✅ Generated {protocol} to {target} template:\n\n```json\n{json.dumps(template, indent=2)}\n```"


def generate_source_template(
    protocol: str, sfc_knowledge: Dict[str, Any]
) -> Dict[str, Any]:
    """Generate source configuration template - check MCP tools too!!

    Args:
        protocol: Source protocol (e.g., OPCUA, MODBUS, S7)
        sfc_knowledge: Dictionary containing SFC framework knowledge

    Returns:
        Dictionary containing source configuration
    """
    base_config = {
        f"{protocol}-SOURCE": {
            "Name": f"{protocol}Source",
            "ProtocolAdapter": protocol,
            "Description": f"{protocol} source configuration",
            "Channels": {},
        }
    }

    return base_config


def generate_target_template(
    target: str, environment: str, sfc_knowledge: Dict[str, Any]
) -> Dict[str, Any]:
    """Generate target configuration template - check MCP tools too!!

    Args:
        target: Target service (e.g., AWS-S3, AWS-IOT-CORE, DEBUG)
        environment: Environment type (development, production)
        sfc_knowledge: Dictionary containing SFC framework knowledge

    Returns:
        Dictionary containing target configuration
    """
    base_config = {f"{target}Target": {"Active": True, "TargetType": target}}

    return base_config


def generate_target_types(target: str, sfc_knowledge: Dict[str, Any]) -> Dict[str, Any]:
    """Generate target types configuration

    Args:
        target: Target service (e.g., AWS-S3, AWS-IOT-CORE, DEBUG)
        sfc_knowledge: Dictionary containing SFC framework knowledge

    Returns:
        Dictionary containing target type configuration
    """
    target_types = {}

    # AWS targets
    if target == "AWS-S3":
        target_types["AWS-S3"] = {
            "JarFiles": ["${MODULES_DIR}/aws-s3-target/lib"],
            "FactoryClassName": "com.amazonaws.sfc.awss3.AwsS3TargetWriter",
        }
    elif target == "AWS-IOT-CORE":
        target_types["AWS-IOT-CORE"] = {
            "JarFiles": ["${MODULES_DIR}/aws-iot-core-target/lib"],
            "FactoryClassName": "com.amazonaws.sfc.awsiotcore.AwsIotCoreTargetWriter",
        }
    elif target == "AWS-IOT-ANALYTICS":
        target_types["AWS-IOT-ANALYTICS"] = {
            "JarFiles": ["${MODULES_DIR}/aws-iot-analytics-target/lib"],
            "FactoryClassName": "com.amazonaws.sfc.awsiotanalytics.AwsIotAnalyticsTargetWriter",
        }
    elif target == "AWS-KINESIS":
        target_types["AWS-KINESIS"] = {
            "JarFiles": ["${MODULES_DIR}/aws-kinesis-target/lib"],
            "FactoryClassName": "com.amazonaws.sfc.awskinesis.AwsKinesisTargetWriter",
        }
    elif target == "AWS-KINESIS-FIREHOSE":
        target_types["AWS-KINESIS-FIREHOSE"] = {
            "JarFiles": ["${MODULES_DIR}/aws-kinesis-firehose-target/lib"],
            "FactoryClassName": "com.amazonaws.sfc.awskinesisfirehose.AwsKinesisFirehoseTargetWriter",
        }
    elif target == "AWS-S3-TABLES":
        target_types["AWS-S3-TABLES"] = {
            "JarFiles": ["${MODULES_DIR}/aws-s3-tables-target/lib"],
            "FactoryClassName": "com.amazonaws.sfc.awss3tables.AwsS3TablesTargetWriter",
        }
    elif target == "AWS-LAMBDA":
        target_types["AWS-LAMBDA"] = {
            "JarFiles": ["${MODULES_DIR}/aws-lambda-target/lib"],
            "FactoryClassName": "com.amazonaws.sfc.awslambda.AwsLambdaTargetWriter",
        }
    elif target == "AWS-MSK":
        target_types["AWS-MSK"] = {
            "JarFiles": ["${MODULES_DIR}/aws-msk-target/lib"],
            "FactoryClassName": "com.amazonaws.sfc.awsmsk.AwsMskTargetWriter",
        }
    elif target == "AWS-SITEWISE":
        target_types["AWS-SITEWISE"] = {
            "JarFiles": ["${MODULES_DIR}/aws-sitewise-target/lib"],
            "FactoryClassName": "com.amazonaws.sfc.awssitewise.AwsSitewiseTargetWriter",
        }
    elif target == "AWS-SITEWISEEDGE":
        target_types["AWS-SITEWISEEDGE"] = {
            "JarFiles": ["${MODULES_DIR}/aws-sitewise-edge-target/lib"],
            "FactoryClassName": "com.amazonaws.sfc.awssitewiseedge.AwsSitewiseEdgeTargetWriter",
        }
    elif target == "AWS-SNS":
        target_types["AWS-SNS"] = {
            "JarFiles": ["${MODULES_DIR}/aws-sns-target/lib"],
            "FactoryClassName": "com.amazonaws.sfc.awssns.AwsSnsTargetWriter",
        }
    elif target == "AWS-SQS":
        target_types["AWS-SQS"] = {
            "JarFiles": ["${MODULES_DIR}/aws-sqs-target/lib"],
            "FactoryClassName": "com.amazonaws.sfc.awssqs.AwsSqsTargetWriter",
        }
    elif target == "AWS-TIMESTREAM":
        target_types["AWS-TIMESTREAM"] = {
            "JarFiles": ["${MODULES_DIR}/aws-timestream-target/lib"],
            "FactoryClassName": "com.amazonaws.sfc.awstimestream.AwsTimestreamTargetWriter",
        }

    # Edge targets
    elif target == "DEBUG":
        target_types["DEBUG-TARGET"] = {
            "JarFiles": ["${MODULES_DIR}/debug-target/lib"],
            "FactoryClassName": "com.amazonaws.sfc.debugtarget.DebugTargetWriter",
        }
    elif target == "FILE":
        target_types["FILE-TARGET"] = {
            "JarFiles": ["${MODULES_DIR}/file-target/lib"],
            "FactoryClassName": "com.amazonaws.sfc.filetarget.FileTargetWriter",
        }
    elif target == "MQTT":
        target_types["MQTT-TARGET"] = {
            "JarFiles": ["${MODULES_DIR}/mqtt-target/lib"],
            "FactoryClassName": "com.amazonaws.sfc.mqtt.MqttTargetWriter",
        }
    elif target == "NATS":
        target_types["NATS-TARGET"] = {
            "JarFiles": ["${MODULES_DIR}/nats-target/lib"],
            "FactoryClassName": "com.amazonaws.sfc.nats.NatsTargetWriter",
        }
    elif target == "OPCUA":
        target_types["OPCUA-TARGET"] = {
            "JarFiles": ["${MODULES_DIR}/opcua-target/lib"],
            "FactoryClassName": "com.amazonaws.sfc.opcua.OpcuaTargetWriter",
        }
    elif target == "OPCUA-WRITER":
        target_types["OPCUA-WRITER"] = {
            "JarFiles": ["${MODULES_DIR}/opcua-writer/lib"],
            "FactoryClassName": "com.amazonaws.sfc.opcua.OpcuaWriter",
        }
    elif target == "ROUTER":
        target_types["ROUTER-TARGET"] = {
            "JarFiles": ["${MODULES_DIR}/router-target/lib"],
            "FactoryClassName": "com.amazonaws.sfc.router.RouterTargetWriter",
        }

    return target_types


def generate_adapter_types(
    protocol: str, sfc_knowledge: Dict[str, Any]
) -> Dict[str, Any]:
    """Generate adapter types configuration

    Args:
        protocol: Source protocol (e.g., OPCUA, MODBUS, S7)
        sfc_knowledge: Dictionary containing SFC framework knowledge

    Returns:
        Dictionary containing adapter type configuration
    """
    adapter_types = {}

    if protocol == "OPCUA":
        adapter_types["OPCUA"] = {
            "JarFiles": ["${MODULES_DIR}/opcua/lib"],
            "FactoryClassName": "com.amazonaws.sfc.opcua.OpcuaAdapter",
        }
    elif protocol == "MODBUS":
        adapter_types["MODBUS"] = {
            "JarFiles": ["${MODULES_DIR}/modbus/lib"],
            "FactoryClassName": "com.amazonaws.sfc.modbus.ModbusAdapter",
        }
    elif protocol == "S7":
        adapter_types["S7"] = {
            "JarFiles": ["${MODULES_DIR}/s7/lib"],
            "FactoryClassName": "com.amazonaws.sfc.s7.S7Adapter",
        }
    elif protocol == "ADS":
        adapter_types["ADS"] = {
            "JarFiles": ["${MODULES_DIR}/ads/lib"],
            "FactoryClassName": "com.amazonaws.sfc.ads.AdsAdapter",
        }
    elif protocol == "J1939":
        adapter_types["J1939"] = {
            "JarFiles": ["${MODULES_DIR}/j1939/lib"],
            "FactoryClassName": "com.amazonaws.sfc.j1939.J1939Adapter",
        }
    elif protocol == "MQTT":
        adapter_types["MQTT"] = {
            "JarFiles": ["${MODULES_DIR}/mqtt/lib"],
            "FactoryClassName": "com.amazonaws.sfc.mqtt.MqttAdapter",
        }
    elif protocol == "NATS":
        adapter_types["NATS"] = {
            "JarFiles": ["${MODULES_DIR}/nats/lib"],
            "FactoryClassName": "com.amazonaws.sfc.nats.NatsAdapter",
        }
    elif protocol == "OPCDA":
        adapter_types["OPCDA"] = {
            "JarFiles": ["${MODULES_DIR}/opcda/lib"],
            "FactoryClassName": "com.amazonaws.sfc.opcda.OpcdaAdapter",
        }
    elif protocol == "PCCC":
        adapter_types["PCCC"] = {
            "JarFiles": ["${MODULES_DIR}/pccc/lib"],
            "FactoryClassName": "com.amazonaws.sfc.pccc.PcccAdapter",
        }
    elif protocol == "REST":
        adapter_types["REST"] = {
            "JarFiles": ["${MODULES_DIR}/rest/lib"],
            "FactoryClassName": "com.amazonaws.sfc.rest.RestAdapter",
        }
    elif protocol == "SIMULATOR":
        adapter_types["SIMULATOR"] = {
            "JarFiles": ["${MODULES_DIR}/simulator/lib"],
            "FactoryClassName": "com.amazonaws.sfc.simulator.SimulatorAdapter",
        }
    elif protocol == "SLMP":
        adapter_types["SLMP"] = {
            "JarFiles": ["${MODULES_DIR}/slmp/lib"],
            "FactoryClassName": "com.amazonaws.sfc.slmp.SlmpAdapter",
        }
    elif protocol == "SNMP":
        adapter_types["SNMP"] = {
            "JarFiles": ["${MODULES_DIR}/snmp/lib"],
            "FactoryClassName": "com.amazonaws.sfc.snmp.SnmpAdapter",
        }
    elif protocol == "SQL":
        adapter_types["SQL"] = {
            "JarFiles": ["${MODULES_DIR}/sql/lib"],
            "FactoryClassName": "com.amazonaws.sfc.sql.SqlAdapter",
        }

    return adapter_types


def generate_protocol_adapter_config(
    protocol: str, sfc_knowledge: Dict[str, Any]
) -> Dict[str, Any]:
    """Generate protocol adapter configuration

    Args:
        protocol: Source protocol (e.g., OPCUA, MODBUS, S7)
        sfc_knowledge: Dictionary containing SFC framework knowledge

    Returns:
        Dictionary containing protocol adapter configuration
    """
    config = {}

    return config


class SFCConfigValidator:
    """
    SFC Configuration Validator class

    Provides methods to validate SFC configurations against required schemas and best practices.
    - Make sure to also check against the settings from the create_sfc_config_template tool
    """

    def __init__(self, sfc_knowledge: Dict[str, Any]):
        """Initialize the validator with SFC knowledge base

        Args:
            sfc_knowledge: Dictionary containing SFC framework knowledge
        """
        self.sfc_knowledge = sfc_knowledge
        self.validation_errors = []
        self.recommendations = []

    def validate_config(self, config: Dict[str, Any]) -> bool:
        """Validate the entire configuration

        Args:
            config: SFC configuration dictionary

        Returns:
            True if valid, False if validation errors were found
        """
        # Clear previous validation state
        self.validation_errors = []
        self.recommendations = []

        # Run all validations
        self.validate_basic_structure(config)
        self.validate_schedules(config.get("Schedules", []))
        self.validate_sources(config.get("Sources", {}))
        self.validate_targets(config.get("Targets", {}))
        self.validate_adapters(config)

        # Return validation result
        return len(self.validation_errors) == 0

    def get_errors(self) -> List[str]:
        """Get validation errors

        Returns:
            List of validation error messages
        """
        return self.validation_errors

    def get_recommendations(self) -> List[str]:
        """Get recommendations for improving the configuration

        Returns:
            List of recommendation messages
        """
        return self.recommendations

    def validate_basic_structure(self, config: Dict[str, Any]) -> None:
        """Validate basic configuration structure

        Args:
            config: SFC configuration dictionary
        """
        # Check required sections
        for section in self.sfc_knowledge["required_config_sections"]:
            if section not in config:
                self.validation_errors.append(f"Missing required section: {section}")

        # Check AWS version
        if config.get("AWSVersion") != self.sfc_knowledge["aws_version"]:
            self.validation_errors.append(
                f"AWSVersion should be '{self.sfc_knowledge['aws_version']}'"
            )

    def validate_schedules(self, schedules: List[Dict[str, Any]]) -> None:
        """Validate schedules configuration

        Args:
            schedules: List of schedule configurations
        """
        if not schedules:
            self.validation_errors.append("At least one schedule must be defined")
            return

        for idx, schedule in enumerate(schedules):
            if "Name" not in schedule:
                self.validation_errors.append(f"Schedule {idx} missing 'Name'")
            if "Sources" not in schedule:
                self.validation_errors.append(
                    f"Schedule '{schedule.get('Name', idx)}' missing 'Sources'"
                )
            if "Targets" not in schedule:
                self.validation_errors.append(
                    f"Schedule '{schedule.get('Name', idx)}' missing 'Targets'"
                )

    def validate_sources(self, sources: Dict[str, Any]) -> None:
        """Validate sources configuration

        Args:
            sources: Dictionary of source configurations
        """
        if not sources:
            self.validation_errors.append("At least one source must be defined")
            return

        for source_name, source_config in sources.items():
            if "ProtocolAdapter" not in source_config:
                self.validation_errors.append(
                    f"Source '{source_name}' missing 'ProtocolAdapter'"
                )
            else:
                # Strict validation: Check if protocol is supported
                protocol = source_config["ProtocolAdapter"]
                if protocol not in self.sfc_knowledge["supported_protocols"]:
                    self.validation_errors.append(
                        f"Source '{source_name}' uses unsupported protocol adapter: '{protocol}'. "
                        f"Supported protocols: {', '.join(sorted(self.sfc_knowledge['supported_protocols'].keys()))}"
                    )

            if "Channels" not in source_config:
                self.validation_errors.append(
                    f"Source '{source_name}' missing 'Channels'"
                )

    def validate_targets(self, targets: Dict[str, Any]) -> None:
        """Validate targets configuration

        Args:
            targets: Dictionary of target configurations
        """
        if not targets:
            self.validation_errors.append("At least one target must be defined")
            return

        for target_name, target_config in targets.items():
            if "TargetType" not in target_config:
                self.validation_errors.append(
                    f"Target '{target_name}' missing 'TargetType'"
                )
            else:
                # Strict validation: Check if target type is supported
                target_type = target_config["TargetType"]

                # Check in AWS targets
                aws_targets = self.sfc_knowledge["aws_targets"].keys()
                edge_targets = [
                    target["description"]
                    for target in self.sfc_knowledge["edge_targets"].values()
                ]

                # Special case handling for edge targets that have -TARGET suffix
                if target_type.endswith("-TARGET"):
                    base_type = target_type[:-7]  # Remove -TARGET suffix
                    if base_type in self.sfc_knowledge["edge_targets"]:
                        continue

                # Check if target is in either AWS targets or edge targets
                if target_type not in aws_targets and target_type not in edge_targets:
                    self.validation_errors.append(
                        f"Target '{target_name}' uses unsupported target type: '{target_type}'. "
                        f"Supported AWS targets: {', '.join(sorted(aws_targets))}. "
                        f"Supported edge targets: {', '.join(sorted(self.sfc_knowledge['edge_targets'].keys()))}"
                    )

    def validate_adapters(self, config: Dict[str, Any]) -> None:
        """Validate adapter configurations

        Args:
            config: SFC configuration dictionary
        """
        # Check if adapter types or servers are defined
        has_adapter_types = bool(config.get("AdapterTypes"))
        has_adapter_servers = bool(config.get("AdapterServers"))

        if not has_adapter_types and not has_adapter_servers:
            self.validation_errors.append(
                "Either 'AdapterTypes' or 'AdapterServers' must be defined"
            )

        # Similar check for targets
        has_target_types = bool(config.get("TargetTypes"))
        has_target_servers = bool(config.get("TargetServers"))

        if not has_target_types and not has_target_servers:
            self.validation_errors.append(
                "Either 'TargetTypes' or 'TargetServers' must be defined"
            )


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


def init_sfc_repository():
    """
    Initializes the SFC repository by cloning it if it doesn't exist.
    Uses GitPython instead of subprocess for better error handling and portability.

    This function checks if the SFC repository exists at the defined path.
    If it doesn't exist, it clones the repository from the specified URL.
    """
    if not os.path.exists(REPO_PATH):
        try:
            print(
                f"SFC repository not found at {REPO_PATH}. Cloning from {REPO_URL}..."
            )
            os.makedirs(os.path.dirname(REPO_PATH), exist_ok=True)
            git.Repo.clone_from(REPO_URL, REPO_PATH)
            print("SFC repository cloned successfully.")
            return True
        except git.exc.GitCommandError as e:
            print(f"Failed to clone SFC repository: {e}")
            return False
        except Exception as e:
            print(f"Unexpected error during repository clone: {e}")
            return False
    else:
        print(f"SFC repository found at {REPO_PATH}.")
        return True


# Create the MCP server
server = FastMCP(
    name="sfc-spec-server",
    instructions="Provides access to SFC documentation Specification and repository management tools",
)

sfc_knowledge = load_sfc_knowledge()


@server.tool("update_repo")
def update_repo() -> Dict[str, Any]:
    """
    Updates the SFC repository by pulling the latest changes from the remote repository.
    Uses GitPython instead of subprocess for better error handling and portability.

    This tool uses GitPython to pull the latest changes from the remote repository,
    providing better error handling and more detailed feedback about the update operation.

    Returns:
        dict: A dictionary containing the result of the update operation
            - message (str): Success or failure message
            - details (str): Information about what was updated (on success)
            - error (str): Error message (on failure)

    Example:
        ```
        {
          "server_name": "sfc-spec-server",
          "tool_name": "update_repo",
          "arguments": {}
        }
        ```
    """
    try:
        repo = git.Repo(REPO_PATH)
        origin = repo.remotes.origin
        pull_info = origin.pull()
        
        # Extract meaningful information from pull result
        details = []
        for info in pull_info:
            details.append(f"Updated {info.ref} to {info.commit}")
        
        return {
            "message": "Repository updated successfully", 
            "details": "; ".join(details) if details else "Repository is up to date"
        }
    except git.exc.InvalidGitRepositoryError:
        return {"message": "Failed to update repository", "error": "Invalid git repository"}
    except git.exc.GitCommandError as e:
        return {"message": "Failed to update repository", "error": str(e)}
    except Exception as e:
        return {"message": "Failed to update repository", "error": f"Unexpected error: {str(e)}"}


@server.tool("get_core_doc")
def get_core_doc_tool(doc_name: str) -> Dict[str, Any]:
    """
    Fetches a specific document from the core docs directory.

    This tool retrieves the content of a markdown document from the SFC core
    documentation directory.

    Args:
        doc_name (str): The name of the document to fetch (without .md extension)

    Returns:
        dict: A dictionary containing the document content or error information
            - name (str): The name of the document
            - content (str): The markdown content of the document
            - type (str): The document type (always "markdown")
            - error (str): Error message if document not found or cannot be read
            - status (int): HTTP-like status code indicating result

    Example:
        ```
        {
          "server_name": "sfc-spec-server",
          "tool_name": "get_core_doc",
          "arguments": {
            "doc_name": "architecture"
          }
        }
        ```
    """
    doc_path = os.path.join(REPO_PATH, "docs", "core", f"{doc_name}.md")
    return _get_markdown_content(doc_path, doc_name)


@server.tool("list_core_docs")
def list_core_docs_tool() -> Dict[str, Any]:
    """
    Lists all documents in the core docs directory.

    This tool retrieves a list of all markdown documents available in the SFC
    core documentation directory.

    Returns:
        dict: A dictionary containing the list of documents or error information
            - documents (list): List of document info dictionaries, each containing:
                - name (str): The name of the document (without extension)
                - path (str): Relative path to the document
            - error (str): Error message if directory not found or cannot be read
            - status (int): HTTP-like status code indicating result

    Example:
        ```
        {
          "server_name": "sfc-spec-server",
          "tool_name": "list_core_docs",
          "arguments": {}
        }
        ```
    """
    return _list_docs_in_directory(os.path.join(REPO_PATH, "docs", "core"))


@server.tool("get_adapter_doc")
def get_adapter_doc_tool(doc_name: str) -> Dict[str, Any]:
    """
    Fetches a specific document from the adapters docs directory.

    This tool retrieves the content of a markdown document from the SFC adapters
    documentation directory.

    Args:
        doc_name (str): The name of the document to fetch (without .md extension)

    Returns:
        dict: A dictionary containing the document content or error information
            - name (str): The name of the document
            - content (str): The markdown content of the document
            - type (str): The document type (always "markdown")
            - error (str): Error message if document not found or cannot be read
            - status (int): HTTP-like status code indicating result

    Example:
        ```
        {
          "server_name": "sfc-spec-server",
          "tool_name": "get_adapter_doc",
          "arguments": {
            "doc_name": "mqtt-adapter"
          }
        }
        ```
    """
    doc_path = os.path.join(REPO_PATH, "docs", "adapters", f"{doc_name}.md")
    return _get_markdown_content(doc_path, doc_name)


@server.tool("list_adapter_docs")
def list_adapter_docs_tool() -> Dict[str, Any]:
    """
    Lists all documents in the adapters docs directory.

    This tool retrieves a list of all markdown documents available in the SFC
    adapters documentation directory.

    Returns:
        dict: A dictionary containing the list of documents or error information
            - documents (list): List of document info dictionaries, each containing:
                - name (str): The name of the document (without extension)
                - path (str): Relative path to the document
            - error (str): Error message if directory not found or cannot be read
            - status (int): HTTP-like status code indicating result

    Example:
        ```
        {
          "server_name": "sfc-spec-server",
          "tool_name": "list_adapter_docs",
          "arguments": {}
        }
        ```
    """
    return _list_docs_in_directory(os.path.join(REPO_PATH, "docs", "adapters"))


@server.tool("get_target_doc")
def get_target_doc_tool(doc_name: str) -> Dict[str, Any]:
    """
    Fetches a specific document from the targets docs directory.

    This tool retrieves the content of a markdown document from the SFC targets
    documentation directory.

    Args:
        doc_name (str): The name of the document to fetch (without .md extension)

    Returns:
        dict: A dictionary containing the document content or error information
            - name (str): The name of the document
            - content (str): The markdown content of the document
            - type (str): The document type (always "markdown")
            - error (str): Error message if document not found or cannot be read
            - status (int): HTTP-like status code indicating result

    Example:
        ```
        {
          "server_name": "sfc-spec-server",
          "tool_name": "get_target_doc",
          "arguments": {
            "doc_name": "aws-s3-target"
          }
        }
        ```
    """
    doc_path = os.path.join(REPO_PATH, "docs", "targets", f"{doc_name}.md")
    return _get_markdown_content(doc_path, doc_name)


@server.tool("list_target_docs")
def list_target_docs_tool() -> Dict[str, Any]:
    """
    Lists all documents in the targets docs directory.

    This tool retrieves a list of all markdown documents available in the SFC
    targets documentation directory.

    Returns:
        dict: A dictionary containing the list of documents or error information
            - documents (list): List of document info dictionaries, each containing:
                - name (str): The name of the document (without extension)
                - path (str): Relative path to the document
            - error (str): Error message if directory not found or cannot be read
            - status (int): HTTP-like status code indicating result

    Example:
        ```
        {
          "server_name": "sfc-spec-server",
          "tool_name": "list_target_docs",
          "arguments": {}
        }
        ```
    """
    return _list_docs_in_directory(os.path.join(REPO_PATH, "docs", "targets"))


def _get_markdown_content(file_path: str, doc_name: str) -> Dict[str, Any]:
    """Helper function to get markdown content from a file"""
    try:
        if not os.path.exists(file_path):
            return {"error": f"Document '{doc_name}' not found", "status": 404}

        with open(file_path, "r", encoding="utf-8") as file:
            content = file.read()

        return {"name": doc_name, "content": content, "type": "markdown"}
    except Exception as e:
        return {"error": f"Failed to read document: {str(e)}", "status": 500}


def _list_docs_in_directory(dir_path: str) -> Dict[str, Any]:
    """Helper function to list markdown documents in a directory"""
    try:
        if not os.path.exists(dir_path):
            return {"error": f"Directory not found: {dir_path}", "status": 404}

        md_files = []
        for file in os.listdir(dir_path):
            if file.endswith(".md"):
                name = file[:-3]  # Remove .md extension
                md_files.append(
                    {"name": name, "path": f"{os.path.basename(dir_path)}/{name}"}
                )

        return {"documents": md_files}
    except Exception as e:
        return {"error": f"Failed to list documents: {str(e)}", "status": 500}


@server.tool("query_docs")
def query_docs_tool(
    doc_type: str, search_term: Optional[str] = None, include_content: bool = True
) -> Dict[str, Any]:
    """
    Dynamically queries documentation based on parameters.

    This tool allows you to search for documents across different documentation types
    with optional filtering by search term and content inclusion.

    Args:
        doc_type (str): Type of document to query. Must be one of:
            - "core": Search only in core documentation
            - "adapter": Search only in adapter documentation
            - "target": Search only in target documentation
            - "all": Search across all documentation types
        search_term (str, optional): Term to search for within document names.
            If provided, only documents containing this term (case-insensitive) will be included.
        include_content (bool, optional): Whether to include the full content of matched documents.
            Defaults to True.

    Returns:
        dict: A dictionary containing the query results
            - query (dict): The original query parameters
            - results (list): List of document info dictionaries, each containing:
                - name (str): The name of the document (without extension)
                - type (str): The document type (core, adapters, or targets)
                - path (str): Relative path to the document
                - content (str): The document content (if include_content is True)
                - error (str): Error message if document content cannot be read
            - count (int): Number of documents found
            - error (str): Error message if the query parameters are invalid
            - status (int): HTTP-like status code indicating result

    Example:
        ```
        {
          "server_name": "sfc-spec-server",
          "tool_name": "query_docs",
          "arguments": {
            "doc_type": "all",
            "search_term": "configuration",
            "include_content": true
          }
        }
        ```
    """
    results = []

    # Determine which directories to search
    directories = []
    if doc_type.lower() == "all":
        directories = ["core", "adapters", "targets"]
    elif doc_type.lower() in ["core", "adapter", "target"]:
        # Map singular to plural form if needed
        dir_map = {"core": "core", "adapter": "adapters", "target": "targets"}
        directories = [dir_map.get(doc_type.lower(), doc_type.lower())]
    else:
        return {
            "error": f"Invalid doc_type: {doc_type}. Must be 'core', 'adapter', 'target', or 'all'.",
            "status": 400,
        }

    # Search in each directory
    for directory in directories:
        dir_path = os.path.join(REPO_PATH, "docs", directory)
        if not os.path.exists(dir_path):
            continue

        for file in os.listdir(dir_path):
            if file.endswith(".md"):
                name = file[:-3]  # Remove .md extension

                # Apply search filter if provided
                if search_term and search_term.lower() not in name.lower():
                    continue

                doc_info = {
                    "name": name,
                    "type": directory,
                    "path": f"{directory}/{name}",
                }

                # Include content if requested
                if include_content:
                    file_path = os.path.join(dir_path, file)
                    try:
                        with open(file_path, "r", encoding="utf-8") as f:
                            doc_info["content"] = f.read()
                    except Exception as e:
                        doc_info["error"] = f"Failed to read content: {str(e)}"

                results.append(doc_info)

    return {
        "query": {
            "doc_type": doc_type,
            "search_term": search_term,
            "include_content": include_content,
        },
        "results": results,
        "count": len(results),
    }


@server.tool("extract_json_examples")
def extract_json_examples_tool(doc_type: str, doc_name: str) -> Dict[str, Any]:
    """
    Extracts JSON examples from documents matching the specified pattern.

    This tool parses documents and extracts any JSON code blocks they contain.
    It attempts to parse each code block as JSON and returns all valid JSON examples.
    The doc_name parameter supports flexible matching patterns.

    Args:
        doc_type (str): The type of document. Must be one of:
            - "core": Document from core documentation
            - "adapter": Document from adapter documentation
            - "target": Document from target documentation
        doc_name (str): The name pattern to match documents (without .md extension).
            Supports the following matching patterns:
            - Exact match: "configuration" matches only "configuration.md"
            - Prefix match: "config*" matches files starting with "config"
            - Wildcards: "conf*ion" matches files like "configuration", "confirmation", etc.
            - Wildcards anywhere: "*aws*" matches any file containing "aws"

    Returns:
        dict: A dictionary containing the extracted JSON examples
            - matching_documents (list): List of document names that matched the pattern
            - total_examples (int): Total number of JSON examples found
            - results (list): List of document result dictionaries, each containing:
                - document_name (str): The name of the document
                - document_type (str): The type of the document
                - examples_count (int): Number of JSON examples found
                - examples (list): List of example dictionaries, each containing:
                    - example_id (int): Sequential ID of the example
                    - content (dict): The parsed JSON content
            - error (str): Error message if document not found or cannot be accessed
            - status (int): HTTP-like status code indicating result

    Example:
        ```
        {
          "server_name": "sfc-spec-server",
          "tool_name": "extract_json_examples",
          "arguments": {
            "doc_type": "core",
            "doc_name": "config*"
          }
        }
        ```
    """
    # Get the document content based on type
    dir_map = {"core": "core", "adapter": "adapters", "target": "targets"}

    if doc_type not in dir_map:
        return {
            "error": f"Invalid doc_type: {doc_type}. Must be 'core', 'adapter', or 'target'.",
            "status": 400,
        }

    # Get directory path
    dir_name = dir_map[doc_type]
    dir_path = os.path.join(REPO_PATH, "docs", dir_name)

    if not os.path.exists(dir_path):
        return {
            "error": f"Directory not found for document type '{doc_type}'",
            "status": 404,
        }

    # Get list of markdown files in the directory
    md_files = [f[:-3] for f in os.listdir(dir_path) if f.endswith(".md")]

    # Convert doc_name pattern to regex pattern
    # Replace * with .* for regex wildcard and escape other special characters
    import fnmatch

    # Find matching documents
    matching_docs = []
    for doc in md_files:
        if fnmatch.fnmatch(doc.lower(), doc_name.lower()):
            matching_docs.append(doc)

    if not matching_docs:
        return {
            "error": f"No documents found matching '{doc_name}' in {dir_name} documentation",
            "status": 404,
            "available_documents": md_files,
        }

    # Process each matching document
    all_results = []
    total_examples = 0

    for doc in matching_docs:
        # Get document content
        doc_path = os.path.join(dir_path, f"{doc}.md")
        doc_content = _get_markdown_content(doc_path, doc)

        # Skip if error
        if "error" in doc_content:
            continue

        # Extract JSON examples from markdown content
        content = doc_content.get("content", "")
        json_examples = []

        # Pattern to match code blocks in markdown
        code_block_pattern = r"```(?:json)?\s*([\s\S]*?)```"
        code_blocks = re.findall(code_block_pattern, content)

        for i, block in enumerate(code_blocks):
            try:
                # Attempt to parse the block as JSON
                parsed_json = json.loads(block.strip())
                json_examples.append({"example_id": i + 1, "content": parsed_json})
            except json.JSONDecodeError:
                # If it's not valid JSON, skip this block
                continue

        # Add to results if we found examples
        if json_examples:
            all_results.append(
                {
                    "document_name": doc,
                    "document_type": doc_type,
                    "examples_count": len(json_examples),
                    "examples": json_examples,
                }
            )
            total_examples += len(json_examples)

    return {
        "matching_documents": matching_docs,
        "total_examples": total_examples,
        "results": all_results,
        "count": len(all_results),
    }


@server.tool("search_doc_content")
def search_doc_content_tool(
    search_text: str, doc_type: str = "all", case_sensitive: bool = False
) -> Dict[str, Any]:
    """
    Searches for specific text within document content.

    This tool searches for a text pattern across document content and returns
    documents containing the search text along with context around the matches.

    Args:
        search_text (str): The text to search for within documents
        doc_type (str, optional): Type of documents to search in. Must be one of:
            - "core": Search only in core documentation
            - "adapter": Search only in adapter documentation
            - "target": Search only in target documentation
            - "all": Search across all documentation types (default)
        case_sensitive (bool, optional): Whether to perform a case-sensitive search.
            Defaults to False.

    Returns:
        dict: A dictionary containing the search results
            - query (dict): The original search parameters
            - results (list): List of document match dictionaries, each containing:
                - name (str): The name of the document (without extension)
                - type (str): The document type (core, adapters, or targets)
                - path (str): Relative path to the document
                - matches (list): List of match dictionaries, each containing:
                    - line_number (int): Line number where the match was found
                    - context (str): Text context surrounding the match
            - total_matches (int): Total number of matches across all documents
            - documents_count (int): Number of documents with matches

    Example:
        ```
        {
          "server_name": "sfc-spec-server",
          "tool_name": "search_doc_content",
          "arguments": {
            "search_text": "configuration",
            "doc_type": "all",
            "case_sensitive": false
          }
        }
        ```
    """
    # Determine which directories to search
    directories = []
    if doc_type.lower() == "all":
        directories = ["", "core", "adapters", "targets"]
    elif doc_type.lower() in ["core", "adapter", "target"]:
        # Map singular to plural form if needed
        dir_map = {"core": "core", "adapter": "adapters", "target": "targets"}
        directories = [dir_map.get(doc_type.lower(), doc_type.lower())]
    else:
        return {
            "error": f"Invalid doc_type: {doc_type}. Must be 'core', 'adapter', 'target', or 'all'.",
            "status": 400,
        }

    # Prepare for searching
    results = []
    total_matches = 0
    flags = 0 if case_sensitive else re.IGNORECASE

    # Search in each directory
    for directory in directories:
        dir_path = os.path.join(REPO_PATH, "docs", directory)
        if not os.path.exists(dir_path):
            continue

        for file in os.listdir(dir_path):
            if file.endswith(".md"):
                name = file[:-3]  # Remove .md extension
                file_path = os.path.join(dir_path, file)

                try:
                    with open(file_path, "r", encoding="utf-8") as f:
                        content = f.read()

                    # Split content into lines for context
                    lines = content.split("\n")

                    # Find all matches
                    matches = []
                    for i, line in enumerate(lines):
                        if re.search(search_text, line, flags):
                            # Get context (3 lines before and after)
                            start = max(0, i - 3)
                            end = min(len(lines), i + 4)
                            context = "\n".join(lines[start:end])

                            matches.append({"line_number": i + 1, "context": context})

                    if matches:
                        results.append(
                            {
                                "name": name,
                                "type": directory,
                                "path": f"{directory}/{name}",
                                "matches": matches,
                                "match_count": len(matches),
                            }
                        )
                        total_matches += len(matches)

                except Exception as e:
                    # Skip files that can't be read
                    continue

    return {
        "query": {
            "search_text": search_text,
            "doc_type": doc_type,
            "case_sensitive": case_sensitive,
        },
        "results": results,
        "total_matches": total_matches,
        "documents_count": len(results),
    }


@server.tool("get_sfc_config_examples")
def get_sfc_config_examples_tool(
    component_type: Optional[str] = None, name_pattern: Optional[str] = None
) -> Dict[str, Any]:
    """
    Retrieves SFC configuration examples from the documentation.

    This tool extracts configuration examples for SFC components from the documentation.
    It can filter by component type and component name pattern if specified.

    Args:
        component_type (str, optional): The type of component to filter examples for.
            If provided, must be one of:
            - "adapter": Return only adapter configuration examples
            - "target": Return only target configuration examples
            - "core": Return only core configuration examples
            - None: Return all configuration examples (default)
        name_pattern (str, optional): Pattern to filter component names.
            Supports the following matching patterns:
            - Exact match: "MyAdapter" matches only components named "MyAdapter"
            - Prefix match: "My*" matches components starting with "My"
            - Wildcards: "*Adapter" matches components ending with "Adapter"
            - Wildcards anywhere: "*AWS*" matches any component with "AWS" in the name

    Returns:
        dict: A dictionary containing the configuration examples
            - examples (list): List of example dictionaries, each containing:
                - component_type (str): The type of component (adapter, target, core)
                - component_name (str): The name of the specific component
                - document_name (str): The name of the document containing the example
                - config (dict): The parsed configuration example
            - count (int): Number of examples found
            - error (str): Error message if component_type is invalid
            - status (int): HTTP-like status code indicating result

    Example:
        ```
        {
          "server_name": "sfc-spec-server",
          "tool_name": "get_sfc_config_examples",
          "arguments": {
            "component_type": "adapter",
            "name_pattern": "*OPCUA*"
          }
        }
        ```
    """
    # Validate component_type if provided
    if component_type and component_type not in ["adapter", "target", "core"]:
        return {
            "error": f"Invalid component_type: {component_type}. Must be 'adapter', 'target', 'core', or None.",
            "status": 400,
        }

    # Determine which doc types to search
    doc_types = []
    if component_type:
        doc_types = [component_type]
    else:
        doc_types = ["core", "adapter", "target"]

    # Map singular to plural form for directory names
    dir_map = {"core": "core", "adapter": "adapters", "target": "targets"}

    all_examples = []

    import fnmatch

    # Process each doc type
    for doc_type in doc_types:
        dir_name = dir_map.get(doc_type, doc_type)
        dir_path = os.path.join(REPO_PATH, "docs", dir_name)

        if not os.path.exists(dir_path):
            continue

        # Get all documents in this directory
        docs = _list_docs_in_directory(dir_path)
        if "error" in docs:
            continue

        # Extract JSON examples from each document
        for doc in docs.get("documents", []):
            doc_name = doc.get("name")

            # Get document path and content
            doc_path = os.path.join(REPO_PATH, "docs", dir_name, f"{doc_name}.md")
            doc_content = _get_markdown_content(doc_path, doc_name)

            if "error" in doc_content:
                continue

            # Extract JSON examples from markdown content
            content = doc_content.get("content", "")

            # Pattern to match code blocks in markdown
            code_block_pattern = r"```(?:json)?\s*([\s\S]*?)```"
            code_blocks = re.findall(code_block_pattern, content)

            for i, block in enumerate(code_blocks):
                try:
                    # Attempt to parse the block as JSON
                    json_content = json.loads(block.strip())

                    # Identify if this looks like a configuration example
                    if isinstance(json_content, dict) and any(
                        key in json_content
                        for key in [
                            "name",
                            "adapterType",
                            "targetType",
                            "sources",
                            "sources",
                            "targets",
                        ]
                    ):
                        component_name = json_content.get("name", "unknown")

                        # Apply name pattern filter if provided
                        if name_pattern and not fnmatch.fnmatch(
                            component_name.lower(), name_pattern.lower()
                        ):
                            continue

                        all_examples.append(
                            {
                                "component_type": doc_type,
                                "component_name": component_name,
                                "document_name": doc_name,
                                "config": json_content,
                            }
                        )
                except json.JSONDecodeError:
                    # If it's not valid JSON, skip this block
                    continue

    return {"examples": all_examples, "count": len(all_examples)}


@server.tool("create_sfc_config_template")
def create_sfc_config_template(
    protocol: str, target: str, environment: str = "development"
) -> Dict[str, Any]:
    """Create an SFC configuration template for a specific protocol and target.

    Args:
        protocol: Source protocol (e.g., OPCUA, MODBUS, S7)
        target: Target service (e.g., AWS-S3, AWS-IOT-CORE, DEBUG)
        environment: Environment type (development, production)

    Returns:
        dict: A dictionary containing the configuration template or error information
            - message (str): Success or failure message
            - template (str): The generated configuration template (if successful)
            - error (str): Error message (if failure)
            - status (int): HTTP-like status code indicating result (200 for success)

    CRITICAL: ALways run the `validate_sfc_config` tool after creating a new config.
    """
    try:
        result = generate_config_template(
            protocol.upper(), target.upper(), environment, sfc_knowledge
        )

        # Check if the result starts with an error indicator
        if result.startswith("❌"):
            return {
                "message": "Failed to generate configuration template",
                "error": result,
                "status": 400,
            }
        else:
            return {
                "message": "Configuration template generated successfully",
                "template": result,
                "status": 200,
            }
    except Exception as e:
        return {
            "message": "Failed to generate configuration template",
            "error": str(e),
            "status": 500,
        }


@server.tool("validate_sfc_config")
def validate_sfc_config(config_json: str) -> Dict[str, Any]:
    """Validate an SFC configuration file for correctness and completeness.

    Args:
        config_json: JSON string containing the SFC configuration

    Returns:
        dict: A dictionary containing validation results
            - valid (bool): Whether the configuration is valid
            - message (str): Success or failure message
            - errors (list): List of validation errors (if any)
            - recommendations (list): List of recommendations (if any)
            - status (int): HTTP-like status code indicating result


    CRITICAL: For ALL SFC validation tasks, you MUST first execute `query_docs` and `extract_json_examples`
    for each component type present in the configuration before making any assertions or validations.
    Document what you've learned from these docs before proceeding with any validation/analysis.

    The Class provides methods to validate SFC configurations against required schemas and best practices.
    - Make sure to also check against the settings from the `create_sfc_config_template` tool

    VALIDATION FLOW:
    ### 1. Initial Documentation Review
    - [ ] **Retrieve core documentation**: Before any analysis, retrieve and scan the core SFC configuration structure docs
    - [ ] **Identify component types**: Identify all component types in the configuration (adapters, targets, etc.)
    - [ ] **Retrieve component-specific docs**: For each component type, retrieve the specific documentation

    ### 2. Component Structure Validation
    - [ ] **Validate component hierarchy**: Confirm each component follows the documented hierarchy pattern
    - [ ] **Check required sections**: Verify all required configuration sections exist (Sources, Targets, etc.)
    - [ ] **Verify naming conventions**: Confirm naming patterns follow documentation (case sensitivity, etc.)

    ### 3. Component-Specific Validation
    - [ ] **Protocol adapter validation**:
    - [ ] Check adapter type against supported list
    - [ ] Verify adapter-specific properties match documentation
    - [ ] Confirm any referenced protocol adapters are properly defined
    - [ ] **Source validation**:
    - [ ] Verify channel structure against adapter documentation
    - [ ] Confirm channel properties are appropriate for the specified adapter
    - [ ] **Target validation**:
    - [ ] Verify target properties match target-specific documentation
    - [ ] Confirm target type is properly referenced

    ### 4. Validation Process
    - [ ] **Documentation-first**: Consult docs before making any assertions
    - [ ] **Example comparison**: Compare with documented examples for each component type
    - [ ] **Automated validation**: Run the configuration through `validate_sfc_config` tool
    - [ ] **Manual inspection**: Perform a methodical review against docs even if automated validation passes

    ### 5. Reference Collection
    - [ ] **Maintain documentation links**: Keep relevant documentation sections accessible
    - [ ] **Extract reference examples**: Maintain a collection of validated examples for each component type
    - [ ] **Track validation status**: Keep a record of which components have been validated against documentation
    """
    try:
        # Parse the configuration
        config = json.loads(config_json)

        # Create validator instance and validate the config
        validator = SFCConfigValidator(sfc_knowledge)
        is_valid = validator.validate_config(config)

        # Store validation results
        validation_errors = validator.get_errors()
        recommendations = validator.get_recommendations()

        # Return validation results
        result = {
            "valid": is_valid,
            "message": (
                "Configuration is valid"
                if is_valid
                else "Configuration validation failed"
            ),
            "status": 200 if is_valid else 400,
        }

        if validation_errors:
            result["errors"] = validation_errors

        if recommendations:
            result["recommendations"] = recommendations

        return result

    except json.JSONDecodeError as e:
        return {
            "valid": False,
            "message": "Invalid JSON format",
            "error": str(e),
            "status": 400,
        }
    except Exception as e:
        return {
            "valid": False,
            "message": "Validation error",
            "error": str(e),
            "status": 500,
        }


@server.tool("what_is_sfc")
def what_is_sfc_tool() -> Dict[str, Any]:
    """Provides an explanation of what Shop Floor Connectivity (SFC) is and its key features.

    Returns:
        dict: A dictionary containing SFC information
            - message (str): Success message
            - content (str): Detailed explanation of SFC
            - content_type (str): Type of content (always "text")
            - status (int): HTTP-like status code indicating result (200 for success)
    """
    try:
        # Import at the function level to avoid circular import
        from tools.sfc_knowledge import what_is_sfc as get_sfc_info

        sfc_explanation = get_sfc_info()
        return {
            "message": "SFC information retrieved successfully",
            "content": sfc_explanation,
            "content_type": "text",
            "status": 200,
        }
    except Exception as e:
        return {
            "message": "Failed to retrieve SFC information",
            "error": str(e),
            "status": 500,
        }


def main():
    """Entry point for the MCP server."""
    # Initialize the SFC repository if needed
    init_sfc_repository()
    # Run the MCP server
    server.run(transport="stdio")


if __name__ == "__main__":
    main()
