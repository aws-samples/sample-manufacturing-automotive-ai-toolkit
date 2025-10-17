"""
Main CDK Stack for Vehicle Service Management System
Implements Multi-Agent Collaboration with Supervisor Routing
"""

import aws_cdk as cdk
from datetime import datetime
from aws_cdk import (
    Stack,
    NestedStack,
    aws_lambda as lambda_,
    aws_dynamodb as dynamodb,
    aws_iam as iam,
    aws_s3 as s3,
    Duration,
    RemovalPolicy,
    CustomResource,
)
from constructs import Construct
import json
from bedrock_constructs import MultiAgentSupervisor, SpecialistAgent, ActionGroup
from template_loader import load_lambda_templates
from lambda_mapping_config import LAMBDA_FUNCTION_MAPPING, get_actual_function_name, should_create_fallback
from typing import Dict, Any, Optional

# Default model for all agents
DEFAULT_MODEL_ID = "anthropic.claude-3-haiku-20240307-v1:0"


class VistaServiceStack(NestedStack):
    def __init__(self, scope: Construct, construct_id: str,
                 shared_resources: Optional[Dict[str, Any]] = None,
                 foundation_model: str = None, **kwargs) -> None:
        super().__init__(scope, construct_id, **kwargs)

        # Store shared resources
        self.shared_resources = shared_resources or {}

        # Get foundation model from shared resources or parameter
        self.foundation_model = (
            foundation_model or
            self.shared_resources.get('bedrock_model_id') or
            DEFAULT_MODEL_ID
        )
        print(f"Using foundation model: {self.foundation_model}")

        # Use shared resources from main stack
        self.resource_bucket = self.shared_resources.get('resource_bucket')
        self.tables = self.shared_resources.get('tables', {})
        self.lambda_functions = self.shared_resources.get(
            'lambda_functions', {})
        self.bedrock_agent_role = self.shared_resources.get('agent_role')
        self.lambda_role = self.shared_resources.get('lambda_execution_role')

        if not self.resource_bucket:
            raise ValueError(
                "Vista agents require a shared S3 bucket from main stack")
        if not self.bedrock_agent_role:
            raise ValueError(
                "Vista agents require a shared Bedrock agent role from main stack")
        if not self.lambda_role:
            raise ValueError(
                "Vista agents require a shared Lambda execution role from main stack")

        print(f"Using shared S3 bucket: {self.resource_bucket.bucket_name}")
        print(f"Using shared agent role: {self.bedrock_agent_role.role_arn}")
        print(f"Available shared tables: {list(self.tables.keys())}")
        print(
            f"Available shared Lambda functions: {list(self.lambda_functions.keys())}")

        # Load templates from lambda-layer directory (for Vista-specific functions if needed)
        print("Loading Lambda templates from lambda-layer directory...")
        self.template_data = load_lambda_templates()

        # Print template summary for debugging
        print("Template summary:")
        for template_name, counts in self.template_data.get('summary', {}).items():
            print(f"  {template_name}: {counts}")

        # Set up table references from shared resources
        self.setup_table_references()

        # Set up Lambda function references from shared resources
        self.setup_lambda_references()

        # Vista agents use shared resources, so no need to create new ones
        # The main stack has already created all necessary infrastructure

        # Create specialist agents
        self.create_specialist_agents()

        # Create supervisor agent with collaboration
        self.create_supervisor_agent()

        # Create outputs
        self.create_outputs()

    def setup_table_references(self):
        """Set up references to shared DynamoDB tables"""
        # Set convenient references for backward compatibility
        self.dealer_table = self.tables.get('dealer-data')
        self.obd_table = self.tables.get('obd-data')
        self.parts_table = self.tables.get('dtc-parts-lookup')
        self.warranty_table = self.tables.get('warranty-info')
        self.appointment_table = self.tables.get('dealer-appointment-data')
        self.customer_table = self.tables.get('customer-user-profile')
        self.dealer_parts_stock_table = self.tables.get('dealer-parts-stock')
        self.dealer_parts_order_table = self.tables.get('dealer-parts-order')

        print(f"Set table references:")
        print(
            f"  dealer_table: {self.dealer_table.table_name if self.dealer_table else 'None'}")
        print(
            f"  parts_table: {self.parts_table.table_name if self.parts_table else 'None'}")
        print(
            f"  warranty_table: {self.warranty_table.table_name if self.warranty_table else 'None'}")
        print(
            f"  appointment_table: {self.appointment_table.table_name if self.appointment_table else 'None'}")
        print(
            f"  customer_table: {self.customer_table.table_name if self.customer_table else 'None'}")

    def setup_lambda_references(self):
        """Set up references to shared Lambda functions"""
        # Set convenient references for backward compatibility
        self.dealer_lambda = self.lambda_functions.get('get-dealer-data')
        self.parts_lambda = self.lambda_functions.get('get-parts-for-dtc')
        self.warranty_lambda = self.lambda_functions.get('GetWarrantyData')
        self.appointment_lambda = self.lambda_functions.get(
            'BookAppointmentStar')
        self.dealer_appt_lambda = self.lambda_functions.get(
            'get-dealer-appointment-slots')
        self.dealer_stock_lambda = self.lambda_functions.get(
            'get-dealer-stock')
        self.place_order_lambda = self.lambda_functions.get(
            'place-parts-order')

        print(f"Set Lambda function references:")
        print(
            f"  dealer_lambda: {self.dealer_lambda.function_name if self.dealer_lambda else 'None'}")
        print(
            f"  parts_lambda: {self.parts_lambda.function_name if self.parts_lambda else 'None'}")
        print(
            f"  warranty_lambda: {self.warranty_lambda.function_name if self.warranty_lambda else 'None'}")
        print(
            f"  appointment_lambda: {self.appointment_lambda.function_name if self.appointment_lambda else 'None'}")

    def create_specialist_agents(self):
        """Create specialist agents using exact names and models from JSON"""
        self.specialist_agents = {}

        # 1. SAM-agent-analyze_vehiclesymptom (Knowledge Base agent)
        self.specialist_agents['vehiclesymptom'] = SpecialistAgent(
            self, "VehicleSymptomSpecialist",
            agent_name="SAM-agent-analyze_vehiclesymptom",
            agent_description="Analyze vehicle symptom and recommend an action / next steps based on severity",
            agent_instruction="As an agent analyze the following vehicle symptom issue by reviewing vehicle manuals, recall data\nPlease provide:\n1. Potential issues\n2. Recommended diagnostic steps\n3. Possible parts that might need replacement\n4. Estimated severity (low/medium/high)\nSummarize a detailed response in 200 words with possible next steps to address it.",
            foundation_model=self.foundation_model,
            agent_resource_role_arn=self.bedrock_agent_role.role_arn,
            action_groups=[]
        )
        self.specialist_agents['vehiclesymptom'].create_alias(
            "analyze-vehiclesymptom-alias")

        # 2. SAM-agent-find-nearestdealership
        dealer_action_config = {
            "action_group_name": "action_group_findnearestdealership",
            "description": "Find nearest dealership based on city details",
            "function_schema": {
                "functions": [
                    {
                        "name": "function-getdealerdata",
                        "description": "Invoke dealerdata function by passing input parameters",
                        "parameters": {
                            "city": {
                                "description": "name of the city",
                                "required": False,
                                "type": "string"
                            }
                        }
                    }
                ]
            }
        }

        dealer_action_groups = []
        if self.dealer_lambda:
            dealer_action_groups = [ActionGroup.from_config(
                dealer_action_config, self.dealer_lambda)]

        self.specialist_agents['nearestdealership'] = SpecialistAgent(
            self, "FindNearestDealershipSpecialist",
            agent_name="SAM-agent-find-nearestdealership",
            agent_description="Find nearest automotive dealership",
            agent_instruction="As an agent find nearest automotive dealership based on city. As part of response return dealer name and details",
            foundation_model=self.foundation_model,
            agent_resource_role_arn=self.bedrock_agent_role.role_arn,
            action_groups=dealer_action_groups
        )
        self.specialist_agents['nearestdealership'].create_alias(
            "find-nearestdealership-alias")

        # 3. SAM-agent-bookdealerappt
        appointment_action_config = {
            "action_group_name": "action_group_dealerappt-starformat",
            "description": "This agent helps to book an appointment with an dealership.",
            "function_schema": {
                "functions": [
                    {
                        "name": "action-dealerapptfunction",
                        "description": "Book appt with dealership",
                        "parameters": {
                            "appointment_time": {
                                "description": "appointment time",
                                "required": False,
                                "type": "string"
                            },
                            "dealer_name": {
                                "description": "dealer name",
                                "required": False,
                                "type": "string"
                            },
                            "appointment_date": {
                                "description": "appointment date",
                                "required": False,
                                "type": "string"
                            },
                            "customer_code": {
                                "description": "customer code",
                                "required": False,
                                "type": "string"
                            }
                        }
                    }
                ]
            }
        }

        bookdealerappt_action_groups = []
        if self.appointment_lambda:
            bookdealerappt_action_groups = [ActionGroup.from_config(
                appointment_action_config, self.appointment_lambda)]

        self.specialist_agents['bookdealerappt'] = SpecialistAgent(
            self, "BookDealerApptSpecialist",
            agent_name="SAM-agent-bookdealerappt",
            agent_description="Customer books appointment with the selected dealership to analyze vehicle symptom",
            agent_instruction="This agent helps to book an appointment with an dealership. First extract the dealer code, customer code, appointment date and appointment time from the prompt and invoke the action. Based on appointment availability it return back a star compliant schema with additional data points back as part of response.",
            foundation_model=self.foundation_model,
            agent_resource_role_arn=self.bedrock_agent_role.role_arn,
            action_groups=bookdealerappt_action_groups
        )
        self.specialist_agents['bookdealerappt'].create_alias(
            "bookdealerappt-alias")

        # 4. SAM-agent-finddealeravailability
        dealeravailability_action_config = {
            "action_group_name": "action_group_finddealerslots",
            "description": "find dealer appointment slots by invoking the lambda function",
            "function_schema": {
                "functions": [
                    {
                        "name": "action_groupfunc_finddealerslots",
                        "description": "Find available appointment slots for a dealer. Input dealer name (required), appointment date (optional in YYYY-MM-DD format, e.g., 2025-06-18 for June 18, 2025)",
                        "parameters": {
                            "dealer_name": {
                                "description": "Name of the dealer/dealership (required)",
                                "required": True,
                                "type": "string"
                            },
                            "appointment_date": {
                                "description": "Appointment date in YYYY-MM-DD format (optional). For June 18, 2025 use '2025-06-18'. If not provided, shows next available slots.",
                                "required": False,
                                "type": "string"
                            }
                        }
                    }
                ]
            }
        }

        dealeravailability_action_groups = []
        if self.dealer_appt_lambda:
            dealeravailability_action_groups = [ActionGroup.from_config(
                dealeravailability_action_config, self.dealer_appt_lambda)]

        self.specialist_agents['finddealeravailability'] = SpecialistAgent(
            self, "FindDealerAvailabilitySpecialist",
            agent_name="SAM-agent-finddealeravailability",
            agent_description="Find dealership availability that will help customer to book appt",
            agent_instruction=f"""As an agent, check available appointment slots for customers to book appointments to bring their vehicle for analysis. 

IMPORTANT: Today's date is {datetime.now().strftime('%Y-%m-%d')} ({datetime.now().strftime('%B %d, %Y')}). When customers mention dates like "June 18, 2025" or "June 18th", always use the year 2025 or later.

Customer provides:
- Dealer name (required)
- Date (optional) - if not provided, show next available slots starting from tomorrow
- Time (optional)

When processing dates:
- Always interpret relative dates like "June 18" as the next occurrence (2025 or later)
- Use format YYYY-MM-DD when calling the function
- For "June 18, 2025" use "2025-06-18"

Return available appointment slots to help customers select and book appointments.""",
            foundation_model=self.foundation_model,
            agent_resource_role_arn=self.bedrock_agent_role.role_arn,
            action_groups=dealeravailability_action_groups
        )
        self.specialist_agents['finddealeravailability'].create_alias(
            "finddealeravailability-alias")

        # 5. SAM-agent-parts-availability
        parts_action_groups = []

        # Multiple action groups for parts agent
        dtc_parts_config = {
            "action_group_name": "action_group_findpartsforDTC",
            "description": "Find DTC to parts mapping",
            "function_schema": {
                "functions": [
                    {
                        "name": "function_dtctoparts",
                        "description": "Find automotive parts for this diagnostic trouble code a.ka. DTC",
                        "parameters": {
                            "dtc_code": {
                                "description": "dtc code",
                                "required": False,
                                "type": "string"
                            }
                        }
                    }
                ]
            }
        }

        dealer_stock_config = {
            "action_group_name": "action_group_checkdealerstock",
            "description": "Check dealer inventory on parts",
            "function_schema": {
                "functions": [
                    {
                        "name": "action_group_dealerstock",
                        "description": "Check dealer inventory for parts availability",
                        "parameters": {
                            "dealer_code": {
                                "description": "Dealer name or code",
                                "required": False,
                                "type": "string"
                            },
                            "part_code": {
                                "description": "Parts code",
                                "required": False,
                                "type": "string"
                            }
                        }
                    }
                ]
            }
        }

        order_parts_config = {
            "action_group_name": "action_group_orderparts",
            "description": "Order parts to refill stock",
            "function_schema": {
                "functions": [
                    {
                        "name": "function-orderparts",
                        "description": "Order parts based on parts code and quantity",
                        "parameters": {
                            "dealer_code": {
                                "description": "Dealer name or code",
                                "required": False,
                                "type": "string"
                            },
                            "quantity": {
                                "description": "Quantity",
                                "required": False,
                                "type": "string"
                            },
                            "part_code": {
                                "description": "part code",
                                "required": False,
                                "type": "string"
                            }
                        }
                    }
                ]
            }
        }

        if self.parts_lambda:
            parts_action_groups.append(ActionGroup.from_config(
                dtc_parts_config, self.parts_lambda))
        if self.dealer_stock_lambda:
            parts_action_groups.append(ActionGroup.from_config(
                dealer_stock_config, self.dealer_stock_lambda))
        if self.place_order_lambda:
            parts_action_groups.append(ActionGroup.from_config(
                order_parts_config, self.place_order_lambda))

        self.specialist_agents['parts-availability'] = SpecialistAgent(
            self, "PartsAvailabilitySpecialist",
            agent_name="SAM-agent-parts-availability",
            agent_description="Check for available parts based on DTC",
            agent_instruction="As parts availability agent do the following\na) Find parts for the vehicle DTC\nb) Using the parts information, check the dealership inventory for parts stock availability and show them\nc) In addition, If the inventory is zero place parts order. \nThis will help dealership for fast vehicle turn around to customer once the vehicle is at the dealership",
            foundation_model=self.foundation_model,
            agent_resource_role_arn=self.bedrock_agent_role.role_arn,
            action_groups=parts_action_groups
        )
        self.specialist_agents['parts-availability'].create_alias(
            "parts-availability-alias")

        # 6. SAM-agent-warrantyandrecalls
        warranty_action_config = {
            "action_group_name": "action_group_vehiclewarranty",
            "description": "vehicle warranty function",
            "function_schema": {
                "functions": [
                    {
                        "name": "get-warranty-info",
                        "description": "vehicle warranty function",
                        "parameters": {
                            "VIN": {
                                "description": "vehicle identification number",
                                "required": False,
                                "type": "string"
                            }
                        }
                    }
                ]
            }
        }

        warranty_action_groups = []
        if self.warranty_lambda:
            warranty_action_groups = [ActionGroup.from_config(
                warranty_action_config, self.warranty_lambda)]

        self.specialist_agents['warrantyandrecalls'] = SpecialistAgent(
            self, "WarrantyAndRecallsSpecialist",
            agent_name="SAM-agent-warrantyandrecalls",
            agent_description="Agent on warranties and recalls",
            agent_instruction="As an agent use the action group to find out the warranty information for a vehicle based on VIN.",
            foundation_model=self.foundation_model,
            agent_resource_role_arn=self.bedrock_agent_role.role_arn,
            action_groups=warranty_action_groups
        )
        self.specialist_agents['warrantyandrecalls'].create_alias(
            "warrantyandrecalls-alias")

    def create_supervisor_agent(self):
        """Create supervisor agent with multi-agent collaboration"""

        # Create supervisor agent - SAM-agent-orchestrater to match the JSON
        self.supervisor_agent = MultiAgentSupervisor(
            self, "VistaSupervisor",
            agent_name="SAM-agent-orchestrater",
            agent_description="Multiagent service agent orchestration with end to end flow",
            agent_instruction="""You are a vehicle service management assistant with two modes:

1. **Service Mode**: For vehicle-specific queries
 - Invoke appropriate actions
 - Access service databases
 - Schedule appointments

2. **Conversation Mode**: For general queries
 - Respond conversationally without invoking actions
 - Provide friendly greetings
 - Explain capabilities
 - Give general advice

Determine the mode based on the query:
- "Hello" → Conversation Mode
- "Find a dealer" → Service Mode
- "What can you do?" → Conversation Mode
- "Schedule service" → Service Mode

In Conversation Mode, simply respond directly without trying to invoke any actions.

In Service Mode, analyze the following vehicle issue
Please provide:
1. Potential issues
2. Recommended diagnostic steps
3. Estimated severity (low/medium/high)
4. find nearest dealership by city and return both dealer name and code
5. Find dealership availability that will help customer to book appoinment
6. Book appointment based on customer availability
7. Using DTC look up find the automotive part
7) check dealer inventory for availability of parts in their internal database. 
8) If out of stock, order parts now. This will help dealership to stock parts and service customer and deliver vehicle on time with out delay
9) Get customer details
10)Get warranty information for the vehicle""",
            foundation_model=self.foundation_model,
            agent_resource_role_arn=self.bedrock_agent_role.role_arn
        )

        # Create alias for supervisor
        self.supervisor_alias = self.supervisor_agent.create_alias(
            "orchestrater-alias")

        # Add collaborators to supervisor using the correct agent keys
        # Only add collaborators that exist
        if hasattr(self, 'specialist_agents'):
            if 'vehiclesymptom' in self.specialist_agents:
                self.supervisor_agent.add_collaborator(
                    self.specialist_agents['vehiclesymptom'].alias,
                    "vehicle-symptom-analysis",
                    "Use this agent when customers describe vehicle symptoms or need diagnostic analysis. Route here for symptom analysis and severity assessment."
                )

            if 'nearestdealership' in self.specialist_agents:
                self.supervisor_agent.add_collaborator(
                    self.specialist_agents['nearestdealership'].alias,
                    "dealer-lookup",
                    "Use this agent when customers need to find nearby dealerships or dealer information. Route here for dealer searches and location queries."
                )

            if 'bookdealerappt' in self.specialist_agents:
                self.supervisor_agent.add_collaborator(
                    self.specialist_agents['bookdealerappt'].alias,
                    "appointment-booking",
                    "Use this agent when customers want to book appointments with dealerships. Route here for appointment scheduling."
                )

            if 'finddealeravailability' in self.specialist_agents:
                self.supervisor_agent.add_collaborator(
                    self.specialist_agents['finddealeravailability'].alias,
                    "dealer-availability",
                    "Use this agent when customers need to check dealer availability or appointment slots. Route here for availability checking."
                )

            if 'parts-availability' in self.specialist_agents:
                self.supervisor_agent.add_collaborator(
                    self.specialist_agents['parts-availability'].alias,
                    "parts-availability",
                    "Use this agent when customers need parts information or availability checking. Route here for DTC code lookups and parts ordering."
                )

            if 'warrantyandrecalls' in self.specialist_agents:
                self.supervisor_agent.add_collaborator(
                    self.specialist_agents['warrantyandrecalls'].alias,
                    "warranty-recalls",
                    "Use this agent when customers need warranty information or recall checks. Route here for VIN-based warranty queries."
                )

        print("Created supervisor agent with multi-agent collaboration")

        # Configure the collaboration after all collaborators are added
        self.supervisor_agent.finalize_collaboration()

    def create_outputs(self):
        """Create stack outputs for Vista agents"""

        # Supervisor agent outputs
        if hasattr(self, 'supervisor_agent'):
            cdk.CfnOutput(self, "VistaSupevisorAgentId",
                          value=self.supervisor_agent.agent_id,
                          description="Vista supervisor agent ID")

            if hasattr(self, 'supervisor_alias'):
                cdk.CfnOutput(self, "VistaSupervisorAgentAliasId",
                              value=self.supervisor_alias.attr_agent_alias_id,
                              description="Vista supervisor agent alias ID")

        # Specialist agent outputs
        if hasattr(self, 'specialist_agents'):
            for agent_key, agent in self.specialist_agents.items():
                if hasattr(agent, 'agent_id'):
                    cdk.CfnOutput(self, f"Vista{agent_key.title()}AgentId",
                                  value=agent.agent_id,
                                  description=f"Vista {agent_key} specialist agent ID")

        # Output count of created agents
        specialist_count = len(self.specialist_agents) if hasattr(
            self, 'specialist_agents') else 0
        supervisor_count = 1 if hasattr(self, 'supervisor_agent') else 0
        total_agents = specialist_count + supervisor_count

        cdk.CfnOutput(self, "VistaTotalAgentsCreated",
                      value=str(total_agents),
                      description=f"Total Vista agents created: {specialist_count} specialists + {supervisor_count} supervisor")
