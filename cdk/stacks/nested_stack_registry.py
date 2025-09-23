"""
Agent Registry for auto-discovery and management of nested stacks
"""

import os
import json
import yaml
from pathlib import Path
from typing import List, Dict, Any, Tuple, Optional
import aws_cdk as cdk
from constructs import Construct
import importlib.util
import sys

# Import CDK components that we need
try:
    from aws_cdk import aws_codebuild as codebuild
except ImportError:
    codebuild = None

try:
    from aws_cdk import NestedStack
except ImportError:
    NestedStack = None


class CDKStackConfig:
    """Configuration for a CDK nested stack"""
    def __init__(self, name: str, path: str, stack_class: str, category: str = ""):
        self.name = name
        self.path = path
        self.stack_class = stack_class
        self.category = category
        self.app_py_path = os.path.join(path, "app.py")
        self.requirements_path = os.path.join(path, "requirements.txt")

    def __repr__(self):
        return f"CDKStackConfig(name='{self.name}', path='{self.path}', stack_class='{self.stack_class}')"


class AgentCoreConfig:
    """Configuration for an AgentCore agent"""
    def __init__(self, name: str, path: str, manifest_path: str, category: str = ""):
        self.name = name
        self.path = path
        self.manifest_path = manifest_path
        self.category = category
        self.agentcore_config_path = os.path.join(path, ".bedrock_agentcore.yaml")
        self.dockerfile_path = os.path.join(path, "Dockerfile")
        self.requirements_path = os.path.join(path, "requirements.txt")
        self.environment = {}
        self._load_configuration()

    def _load_configuration(self):
        """Load configuration from manifest and agentcore config files"""
        # Load manifest.json if it exists
        if os.path.exists(self.manifest_path):
            try:
                with open(self.manifest_path, 'r') as f:
                    manifest_data = json.load(f)
                    self.environment.update(manifest_data.get('environment', {}))
            except Exception as e:
                print(f"Warning: Could not load manifest for {self.name}: {e}")

        # Load .bedrock_agentcore.yaml if it exists
        if os.path.exists(self.agentcore_config_path):
            try:
                with open(self.agentcore_config_path, 'r') as f:
                    agentcore_data = yaml.safe_load(f)
                    if agentcore_data:
                        self.environment.update(agentcore_data.get('environment', {}))
            except Exception as e:
                print(f"Warning: Could not load agentcore config for {self.name}: {e}")

    def __repr__(self):
        return f"AgentCoreConfig(name='{self.name}', path='{self.path}', category='{self.category}')"


class AgentRegistry:
    """
    Auto-discover and manage both CDK nested stacks and AgentCore agents.
    """

    def __init__(self, main_stack: cdk.Stack):
        self.main_stack = main_stack
        # Get the path relative to the workspace root, not the cdk directory
        current_dir = os.path.dirname(os.path.abspath(__file__))
        workspace_root = os.path.dirname(os.path.dirname(current_dir))
        self.agents_catalog_path = os.path.join(workspace_root, "agents_catalog")
        self.discovered_cdk_stacks: List[CDKStackConfig] = []
        self.discovered_agentcore_agents: List[AgentCoreConfig] = []

    def discover_agents(self) -> Tuple[List[CDKStackConfig], List[AgentCoreConfig]]:
        """
        Scan agents_catalog for both CDK and AgentCore projects.
        """
        print(f"Starting agent discovery in {self.agents_catalog_path}")
        
        if not os.path.exists(self.agents_catalog_path):
            print(f"Warning: Agents catalog directory {self.agents_catalog_path} does not exist")
            return [], []

        cdk_stacks = []
        agentcore_agents = []

        # Scan all categories in agents_catalog
        for category in os.listdir(self.agents_catalog_path):
            category_path = os.path.join(self.agents_catalog_path, category)
            
            # Skip files and hidden directories
            if not os.path.isdir(category_path) or category.startswith('.'):
                continue

            print(f"Scanning category: {category}")
            
            # Scan all agents in this category
            for agent_name in os.listdir(category_path):
                agent_path = os.path.join(category_path, agent_name)
                
                # Skip files and hidden directories
                if not os.path.isdir(agent_path) or agent_name.startswith('.'):
                    continue

                print(f"  Examining agent: {agent_name}")
                
                # Check for CDK stack
                cdk_config = self._detect_cdk_stack(agent_name, agent_path, category)
                if cdk_config:
                    cdk_stacks.append(cdk_config)
                    print(f"    Found CDK stack: {cdk_config}")

                # Check for AgentCore agent
                agentcore_config = self._detect_agentcore_agent(agent_name, agent_path, category)
                if agentcore_config:
                    agentcore_agents.append(agentcore_config)
                    print(f"    Found AgentCore agent: {agentcore_config}")

        self.discovered_cdk_stacks = cdk_stacks
        self.discovered_agentcore_agents = agentcore_agents
        
        print(f"Discovery complete: {len(cdk_stacks)} CDK stacks, {len(agentcore_agents)} AgentCore agents")
        return cdk_stacks, agentcore_agents

    def _detect_cdk_stack(self, agent_name: str, agent_path: str, category: str) -> Optional[CDKStackConfig]:
        """Detect if an agent has a CDK stack implementation"""
        cdk_path = os.path.join(agent_path, "cdk")
        app_py_path = os.path.join(cdk_path, "app.py")
        
        # Check if cdk directory exists and has app.py
        if not os.path.exists(cdk_path) or not os.path.exists(app_py_path):
            return None

        # Try to determine the stack class name from app.py
        stack_class = self._extract_stack_class_name(app_py_path, agent_name)
        
        if stack_class:
            return CDKStackConfig(
                name=agent_name,
                path=cdk_path,
                stack_class=stack_class,
                category=category
            )
        
        return None

    def _detect_agentcore_agent(self, agent_name: str, agent_path: str, category: str) -> Optional[AgentCoreConfig]:
        """Detect if an agent is an AgentCore agent"""
        agentcore_config_path = os.path.join(agent_path, ".bedrock_agentcore.yaml")
        manifest_path = os.path.join(agent_path, "manifest.json")
        
        # Check if .bedrock_agentcore.yaml exists (primary indicator)
        if os.path.exists(agentcore_config_path):
            return AgentCoreConfig(
                name=agent_name,
                path=agent_path,
                manifest_path=manifest_path,
                category=category
            )
        
        # Alternative: check for manifest.json with agentcore indicators
        if os.path.exists(manifest_path):
            try:
                with open(manifest_path, 'r') as f:
                    manifest_data = json.load(f)
                    # Check if manifest indicates this is an agentcore agent
                    if (manifest_data.get('type') == 'agentcore' or 
                        'agentcore' in manifest_data.get('deployment_method', '').lower()):
                        return AgentCoreConfig(
                            name=agent_name,
                            path=agent_path,
                            manifest_path=manifest_path,
                            category=category
                        )
            except Exception as e:
                print(f"Warning: Could not parse manifest for {agent_name}: {e}")
        
        return None

    def _extract_stack_class_name(self, app_py_path: str, agent_name: str) -> Optional[str]:
        """Extract the stack class name from app.py file"""
        try:
            with open(app_py_path, 'r') as f:
                content = f.read()
                
            import re
            
            # 1. Look for class definitions that inherit from Stack (defined in this file)
            stack_class_pattern = r'class\s+(\w+)\s*\([^)]*Stack[^)]*\):'
            matches = re.findall(stack_class_pattern, content)
            
            if matches:
                # Return the first stack class found
                return matches[0]
            
            # 2. Look for imported stack classes (e.g., "from vista_service_stack import VistaServiceStack")
            import_pattern = r'from\s+\w+\s+import\s+(\w*Stack\w*)'
            import_matches = re.findall(import_pattern, content)
            if import_matches:
                # Return the first imported Stack class
                return import_matches[0]
            
            # 3. Look for direct imports (e.g., "import vista_service_stack")
            # Then check if there's a class instantiation
            module_import_pattern = r'import\s+(\w+)'
            module_matches = re.findall(module_import_pattern, content)
            for module in module_matches:
                # Look for class instantiation like "VistaServiceStack("
                class_usage_pattern = rf'(\w*Stack\w*)\s*\('
                usage_matches = re.findall(class_usage_pattern, content)
                if usage_matches:
                    return usage_matches[0]
            
            # 4. Check if there are any stack files in the same directory
            cdk_dir = os.path.dirname(app_py_path)
            for file in os.listdir(cdk_dir):
                if file.endswith('.py') and 'stack' in file.lower() and file != 'app.py':
                    stack_file_path = os.path.join(cdk_dir, file)
                    try:
                        with open(stack_file_path, 'r') as f:
                            stack_content = f.read()
                        
                        # Look for stack class in this file
                        stack_matches = re.findall(stack_class_pattern, stack_content)
                        if stack_matches:
                            print(f"    Found stack class {stack_matches[0]} in {file}")
                            return stack_matches[0]
                    except Exception as e:
                        print(f"    Warning: Could not read {file}: {e}")
            
            # 5. Fallback: try to guess based on agent name
            # Convert agent name to PascalCase and add "Stack"
            fallback_name = self._to_pascal_case(agent_name) + "Stack"
            
            # Check if this class name appears in the file
            if fallback_name in content:
                return fallback_name
            
            # 6. Another fallback: look for any class that contains "Stack"
            general_class_pattern = r'class\s+(\w*Stack\w*)\s*\([^)]*\):'
            general_matches = re.findall(general_class_pattern, content)
            if general_matches:
                return general_matches[0]
                
        except Exception as e:
            print(f"Warning: Could not parse app.py for {agent_name}: {e}")
        
        return None

    def _to_pascal_case(self, snake_str: str) -> str:
        """Convert snake_case or kebab-case to PascalCase"""
        # Replace hyphens and underscores with spaces, then title case
        return ''.join(word.capitalize() for word in snake_str.replace('-', ' ').replace('_', ' ').split())

    def register_cdk_stack(self, config: CDKStackConfig, shared_resources: Dict[str, Any]) -> Optional[Any]:
        """
        Register and deploy a CDK nested stack.
        """
        print(f"Registering CDK stack: {config.name}")
        
        try:
            # Import the stack class dynamically
            stack_class = self._import_stack_class(config)
            if not stack_class:
                print(f"Error: Could not import stack class {config.stack_class} from {config.path}")
                return None
            
            # Create the nested stack with shared resources
            nested_stack = stack_class(
                self.main_stack,
                f"NestedStack{self._sanitize_name(config.name)}",
                shared_resources=shared_resources,
                description=f"Nested stack for {config.name} agent"
            )
            
            print(f"Successfully registered CDK nested stack: {config.name}")
            return nested_stack
            
        except Exception as e:
            print(f"Error registering CDK stack {config.name}: {str(e)}")
            return None

    def _import_stack_class(self, config: CDKStackConfig):
        """Dynamically import a stack class from the agent's CDK directory"""
        try:
            # Add the agent's CDK directory to Python path temporarily
            original_path = sys.path.copy()
            sys.path.insert(0, config.path)
            
            try:
                # Import the app module
                spec = importlib.util.spec_from_file_location("agent_app", config.app_py_path)
                if spec is None or spec.loader is None:
                    return None
                
                module = importlib.util.module_from_spec(spec)
                spec.loader.exec_module(module)
                
                # Get the stack class
                stack_class = getattr(module, config.stack_class, None)
                
                if stack_class is None:
                    print(f"Warning: Stack class {config.stack_class} not found in {config.app_py_path}")
                    # Try to find any Stack class in the module
                    for attr_name in dir(module):
                        attr = getattr(module, attr_name)
                        if (isinstance(attr, type) and 
                            hasattr(attr, '__bases__') and 
                            any('Stack' in str(base) for base in attr.__bases__)):
                            print(f"Found alternative stack class: {attr_name}")
                            stack_class = attr
                            break
                
                return stack_class
                
            finally:
                # Restore original Python path
                sys.path = original_path
                
        except Exception as e:
            print(f"Error importing stack class from {config.path}: {str(e)}")
            return None

    def _sanitize_name(self, name: str) -> str:
        """Sanitize name for use in CDK construct IDs"""
        return ''.join(c for c in name if c.isalnum()).replace('-', '').replace('_', '')

    def register_agentcore_agent(self, config: AgentCoreConfig, codebuild_construct) -> Optional[Any]:
        """
        Create CodeBuild project for AgentCore agent.
        """
        print(f"Registering AgentCore agent: {config.name}")
        
        try:
            # Use the CodeBuild construct to create a dynamic project for this agent
            project = codebuild_construct.create_dynamic_agentcore_project(
                agent_name=config.name,
                agent_config={
                    'path': config.path,
                    'category': config.category,
                    'environment': config.environment,
                    'has_dockerfile': os.path.exists(config.dockerfile_path),
                    'has_requirements': os.path.exists(config.requirements_path)
                }
            )
            
            print(f"Successfully registered AgentCore agent: {config.name}")
            return project
            
        except Exception as e:
            print(f"Error registering AgentCore agent {config.name}: {str(e)}")
            return None

    def get_shared_resources(self) -> Dict[str, Any]:
        """Return shared resources from main stack"""
        # This will be implemented when we integrate with the main stack
        return {}

    def list_discovered_agents(self) -> Dict[str, Any]:
        """Get a summary of all discovered agents"""
        return {
            'cdk_stacks': [
                {
                    'name': config.name,
                    'path': config.path,
                    'stack_class': config.stack_class,
                    'category': config.category
                }
                for config in self.discovered_cdk_stacks
            ],
            'agentcore_agents': [
                {
                    'name': config.name,
                    'path': config.path,
                    'category': config.category,
                    'has_dockerfile': os.path.exists(config.dockerfile_path),
                    'has_requirements': os.path.exists(config.requirements_path)
                }
                for config in self.discovered_agentcore_agents
            ]
        }

    def get_agent_by_name(self, name: str) -> Optional[Dict[str, Any]]:
        """Get agent configuration by name"""
        # Check CDK stacks
        for config in self.discovered_cdk_stacks:
            if config.name == name:
                return {
                    'type': 'cdk',
                    'config': config
                }
        
        # Check AgentCore agents
        for config in self.discovered_agentcore_agents:
            if config.name == name:
                return {
                    'type': 'agentcore',
                    'config': config
                }
        
        return None