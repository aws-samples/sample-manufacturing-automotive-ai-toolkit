"""
Template Loader for Lambda Functions
Automatically loads and parses CloudFormation templates from lambda-layer directory
"""

import yaml
import json
import os
from pathlib import Path
from typing import Dict, List, Any, Optional
import re

# Custom YAML constructors for CloudFormation intrinsic functions
def cfn_tag_constructor(loader, tag_suffix, node):
    """Generic constructor for CloudFormation tags"""
    if isinstance(node, yaml.ScalarNode):
        return {f'!{tag_suffix}': loader.construct_scalar(node)}
    elif isinstance(node, yaml.SequenceNode):
        return {f'!{tag_suffix}': loader.construct_sequence(node)}
    elif isinstance(node, yaml.MappingNode):
        return {f'!{tag_suffix}': loader.construct_mapping(node)}

# Register CloudFormation intrinsic functions
yaml.add_multi_constructor('!', cfn_tag_constructor, Loader=yaml.SafeLoader)

class LambdaTemplateLoader:
    def __init__(self, templates_dir: str = "../lambda-layer"):
        self.templates_dir = Path(__file__).parent / templates_dir
        self.templates = {}
        self.load_templates()
    
    def load_templates(self):
        """Load all YAML templates from the templates directory"""
        if not self.templates_dir.exists():
            print(f"Warning: Templates directory {self.templates_dir} does not exist")
            return
        
        for template_file in self.templates_dir.glob("*.yaml"):
            try:
                with open(template_file, 'r') as f:
                    template_content = yaml.safe_load(f)
                    template_name = template_file.stem
                    self.templates[template_name] = template_content
                    print(f"Loaded template: {template_name}")
            except Exception as e:
                print(f"Error loading template {template_file}: {str(e)}")
    
    def get_lambda_functions(self) -> Dict[str, Dict[str, Any]]:
        """Extract Lambda function definitions from all templates"""
        lambda_functions = {}
        
        for template_name, template in self.templates.items():
            resources = template.get('Resources', {})
            
            for resource_name, resource_def in resources.items():
                if resource_def.get('Type') == 'AWS::Lambda::Function':
                    function_name = resource_def.get('Properties', {}).get('FunctionName')
                    if function_name:
                        lambda_functions[function_name] = {
                            'template_name': template_name,
                            'resource_name': resource_name,
                            'properties': resource_def.get('Properties', {}),
                            'code': self._extract_lambda_code(resource_def),
                            'environment': resource_def.get('Properties', {}).get('Environment', {}),
                            'role_policies': self._extract_role_policies(template, resource_def),
                            'timeout': resource_def.get('Properties', {}).get('Timeout', 300),
                            'memory_size': resource_def.get('Properties', {}).get('MemorySize', 256),
                            'runtime': resource_def.get('Properties', {}).get('Runtime', 'python3.12'),
                            'architecture': resource_def.get('Properties', {}).get('Architectures', ['x86_64'])[0]
                        }
        
        return lambda_functions
    
    def get_dynamodb_tables(self) -> Dict[str, Dict[str, Any]]:
        """Extract DynamoDB table definitions from all templates"""
        tables = {}
        
        for template_name, template in self.templates.items():
            resources = template.get('Resources', {})
            
            for resource_name, resource_def in resources.items():
                if resource_def.get('Type') == 'AWS::DynamoDB::Table':
                    table_name = resource_def.get('Properties', {}).get('TableName')
                    if table_name:
                        tables[table_name] = {
                            'template_name': template_name,
                            'resource_name': resource_name,
                            'properties': resource_def.get('Properties', {})
                        }
        
        return tables
    
    def _extract_lambda_code(self, resource_def: Dict[str, Any]) -> str:
        """Extract Lambda function code from resource definition"""
        code_def = resource_def.get('Properties', {}).get('Code', {})
        if 'ZipFile' in code_def:
            return code_def['ZipFile']
        return ""
    
    def _extract_role_policies(self, template: Dict[str, Any], lambda_resource: Dict[str, Any]) -> List[Dict[str, Any]]:
        """Extract IAM role policies for the Lambda function"""
        policies = []
        resources = template.get('Resources', {})
        
        # Find the role referenced by this Lambda function
        role_ref = lambda_resource.get('Properties', {}).get('Role', {})
        if isinstance(role_ref, dict) and '!GetAtt' in str(role_ref):
            # Parse CloudFormation function to get role name
            role_name = self._parse_cf_function(role_ref)
            if role_name and role_name in resources:
                role_def = resources[role_name]
                role_policies = role_def.get('Properties', {}).get('Policies', [])
                managed_policies = role_def.get('Properties', {}).get('ManagedPolicyArns', [])
                
                policies.extend(role_policies)
                for managed_policy in managed_policies:
                    policies.append({'ManagedPolicyArn': managed_policy})
        
        return policies
    
    def _parse_cf_function(self, cf_ref: Any) -> Optional[str]:
        """Parse CloudFormation intrinsic functions to extract resource names"""
        if isinstance(cf_ref, dict):
            if 'Ref' in cf_ref:
                return cf_ref['Ref']
            elif 'Fn::GetAtt' in cf_ref or '!GetAtt' in str(cf_ref):
                # Handle both formats
                if 'Fn::GetAtt' in cf_ref:
                    return cf_ref['Fn::GetAtt'][0]
                else:
                    # Extract from string representation
                    match = re.search(r'GetAtt\s+(\w+)', str(cf_ref))
                    if match:
                        return match.group(1)
        return None
    
    def get_sample_data_functions(self) -> Dict[str, Dict[str, Any]]:
        """Extract sample data population functions from templates"""
        data_functions = {}
        
        for template_name, template in self.templates.items():
            resources = template.get('Resources', {})
            
            for resource_name, resource_def in resources.items():
                if resource_def.get('Type') == 'AWS::Lambda::Function':
                    function_name = resource_def.get('Properties', {}).get('FunctionName', resource_name)
                    
                    # Only include actual data loading/population functions
                    # Be very specific to avoid including business logic functions
                    is_data_loader = (
                        'Insert' in resource_name or 'insert' in function_name.lower() or
                        'populate' in resource_name.lower() or 'populate' in function_name.lower() or
                        'sample' in resource_name.lower() or 'sample' in function_name.lower() or
                        'data-loader' in resource_name.lower() or 'data-loader' in function_name.lower() or
                        'SampleDataFunction' in resource_name or 'SampleDataFunction' in function_name
                    )
                    
                    # Exclude business logic functions that happen to have "data" in the name
                    is_business_logic = (
                        'GetWarrantyData' in function_name or 'get-dealer-data' in function_name or
                        'get-parts-for-dtc' in function_name or 'get-dealer-stock' in function_name or
                        'place-parts-order' in function_name or 'BookAppointment' in function_name or
                        'get-dealer-appointment-slots' in function_name
                    )
                    
                    if is_data_loader and not is_business_logic:
                        data_functions[function_name] = {
                            'template_name': template_name,
                            'resource_name': resource_name,
                            'properties': resource_def.get('Properties', {}),
                            'code': self._extract_lambda_code(resource_def)
                        }
        
        return data_functions
    
    def get_custom_resources(self) -> Dict[str, Dict[str, Any]]:
        """Extract custom resource definitions from templates"""
        custom_resources = {}
        
        for template_name, template in self.templates.items():
            resources = template.get('Resources', {})
            
            for resource_name, resource_def in resources.items():
                resource_type = resource_def.get('Type', '')
                if resource_type.startswith('Custom::'):
                    custom_resources[resource_name] = {
                        'template_name': template_name,
                        'resource_name': resource_name,
                        'type': resource_type,
                        'properties': resource_def.get('Properties', {})
                    }
        
        return custom_resources
    
    def list_available_templates(self) -> List[str]:
        """List all available template names"""
        return list(self.templates.keys())
    
    def get_template_summary(self) -> Dict[str, Dict[str, int]]:
        """Get a summary of resources in each template"""
        summary = {}
        
        for template_name, template in self.templates.items():
            resources = template.get('Resources', {})
            resource_counts = {}
            
            for resource_name, resource_def in resources.items():
                resource_type = resource_def.get('Type', 'Unknown')
                resource_counts[resource_type] = resource_counts.get(resource_type, 0) + 1
            
            summary[template_name] = resource_counts
        
        return summary

# Convenience function for CDK stack
def load_lambda_templates():
    """Load Lambda templates and return organized data"""
    loader = LambdaTemplateLoader()
    
    return {
        'lambda_functions': loader.get_lambda_functions(),
        'dynamodb_tables': loader.get_dynamodb_tables(),
        'sample_data_functions': loader.get_sample_data_functions(),
        'custom_resources': loader.get_custom_resources(),
        'summary': loader.get_template_summary()
    }
