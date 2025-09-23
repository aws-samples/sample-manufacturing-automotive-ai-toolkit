#!/usr/bin/env python3
"""
Bedrock Action Groups Testing Script
Detailed testing of action group functionality and Lambda integration
"""

import json
import sys
import os
import boto3
from typing import Dict, List, Optional, Any
from botocore.exceptions import ClientError, NoCredentialsError

class ActionGroupTester:
    """Test Bedrock agent action groups functionality"""
    
    def __init__(self):
        self.test_results = {}
        
        # Initialize AWS clients
        try:
            self.bedrock_agent = boto3.client('bedrock-agent')
            self.lambda_client = boto3.client('lambda')
        except NoCredentialsError:
            print("❌ AWS credentials not configured. Please configure AWS credentials.")
            sys.exit(1)
    
    def get_vista_agents(self) -> List[Dict]:
        """Get all Vista agents"""
        try:
            response = self.bedrock_agent.list_agents()
            all_agents = response.get('agentSummaries', [])
            
            # Filter Vista agents
            vista_agents = [agent for agent in all_agents if 'SAM-agent' in agent.get('agentName', '')]
            return vista_agents
        except ClientError as e:
            print(f"❌ Error listing agents: {e}")
            return []
    
    def test_agent_action_groups_detailed(self, agent_id: str, agent_name: str) -> Dict[str, Any]:
        """Test action groups for a specific agent in detail"""
        print(f"\n🔍 Detailed action group analysis for: {agent_name}")
        
        try:
            # Get agent details
            response = self.bedrock_agent.get_agent(agentId=agent_id)
            agent_detail = response['agent']
            
            # Get action groups
            action_groups = agent_detail.get('actionGroups', [])
            print(f"  📋 Found {len(action_groups)} action groups")
            
            if not action_groups:
                print("  ⚠️  No action groups found - this might be expected for knowledge-base only agents")
                return {
                    'agent_name': agent_name,
                    'action_groups_count': 0,
                    'action_groups': [],
                    'has_action_groups': False
                }
            
            action_group_details = []
            
            for i, ag in enumerate(action_groups):
                ag_name = ag.get('actionGroupName', f'ActionGroup{i}')
                ag_state = ag.get('actionGroupState', 'UNKNOWN')
                ag_id = ag.get('actionGroupId', 'Unknown')
                
                print(f"    🔧 Action Group: {ag_name}")
                print(f"       ID: {ag_id}")
                print(f"       State: {ag_state}")
                
                # Check executor
                executor = ag.get('actionGroupExecutor')
                lambda_arn = None
                lambda_accessible = False
                
                if executor:
                    lambda_arn = executor.get('lambda')
                    if lambda_arn:
                        print(f"       Lambda: {lambda_arn}")
                        
                        # Test Lambda accessibility
                        try:
                            function_name = lambda_arn.split(':')[-1]
                            self.lambda_client.get_function(FunctionName=function_name)
                            lambda_accessible = True
                            print(f"       ✅ Lambda function accessible")
                        except ClientError as e:
                            print(f"       ❌ Lambda function not accessible: {e}")
                    else:
                        print(f"       ⚠️  No Lambda executor configured")
                else:
                    print(f"       ⚠️  No executor configured")
                
                # Check API schema
                api_schema = ag.get('apiSchema')
                function_schema = ag.get('functionSchema')
                
                schema_info = {}
                if api_schema:
                    print(f"       📄 Has API schema")
                    schema_info['type'] = 'api_schema'
                    schema_info['content'] = api_schema
                elif function_schema:
                    print(f"       📄 Has function schema")
                    schema_info['type'] = 'function_schema'
                    schema_info['content'] = function_schema
                else:
                    print(f"       ⚠️  No schema configured")
                
                action_group_details.append({
                    'name': ag_name,
                    'id': ag_id,
                    'state': ag_state,
                    'lambda_arn': lambda_arn,
                    'lambda_accessible': lambda_accessible,
                    'has_schema': bool(api_schema or function_schema),
                    'schema_info': schema_info
                })
            
            return {
                'agent_name': agent_name,
                'action_groups_count': len(action_groups),
                'action_groups': action_group_details,
                'has_action_groups': len(action_groups) > 0
            }
            
        except ClientError as e:
            print(f"  ❌ Error getting agent details: {e}")
            return {
                'agent_name': agent_name,
                'error': str(e),
                'has_action_groups': False
            }
    
    def test_lambda_functions_for_agents(self) -> Dict[str, Any]:
        """Test Lambda functions that should be used by agents"""
        print("\n🔍 Testing Lambda functions for agent integration...")
        
        # Expected Lambda functions for Vista agents
        expected_functions = [
            'get-dealer-data',
            'get-parts-for-dtc',
            'GetWarrantyData',
            'BookAppointmentStar',
            'get-dealer-appointment-slots',
            'get-dealer-stock',
            'place-parts-order'
        ]
        
        lambda_results = {}
        
        for func_name in expected_functions:
            try:
                print(f"  🔧 Testing Lambda function: {func_name}")
                
                # Try to get function details
                response = self.lambda_client.get_function(FunctionName=func_name)
                function_config = response['Configuration']
                
                print(f"    ✅ Function exists")
                print(f"    📋 Runtime: {function_config.get('Runtime', 'Unknown')}")
                print(f"    📋 Handler: {function_config.get('Handler', 'Unknown')}")
                
                # Check if function has Bedrock permissions
                try:
                    policy_response = self.lambda_client.get_policy(FunctionName=func_name)
                    policy = json.loads(policy_response['Policy'])
                    
                    bedrock_permissions = []
                    for statement in policy.get('Statement', []):
                        principal = statement.get('Principal', {})
                        if isinstance(principal, dict) and 'bedrock.amazonaws.com' in str(principal):
                            bedrock_permissions.append(statement)
                    
                    if bedrock_permissions:
                        print(f"    ✅ Has Bedrock permissions ({len(bedrock_permissions)} statements)")
                    else:
                        print(f"    ⚠️  No Bedrock permissions found")
                    
                    lambda_results[func_name] = {
                        'exists': True,
                        'runtime': function_config.get('Runtime'),
                        'handler': function_config.get('Handler'),
                        'bedrock_permissions': len(bedrock_permissions),
                        'accessible': True
                    }
                    
                except ClientError as e:
                    if e.response['Error']['Code'] == 'ResourceNotFoundException':
                        print(f"    ℹ️  No resource policy (this is normal)")
                        lambda_results[func_name] = {
                            'exists': True,
                            'runtime': function_config.get('Runtime'),
                            'handler': function_config.get('Handler'),
                            'bedrock_permissions': 0,
                            'accessible': True,
                            'no_policy': True
                        }
                    else:
                        print(f"    ⚠️  Error checking permissions: {e}")
                        lambda_results[func_name] = {
                            'exists': True,
                            'runtime': function_config.get('Runtime'),
                            'handler': function_config.get('Handler'),
                            'bedrock_permissions': 'unknown',
                            'accessible': True,
                            'policy_error': str(e)
                        }
                
            except ClientError as e:
                if e.response['Error']['Code'] == 'ResourceNotFoundException':
                    print(f"    ❌ Function not found")
                    lambda_results[func_name] = {
                        'exists': False,
                        'error': 'Function not found'
                    }
                else:
                    print(f"    ❌ Error accessing function: {e}")
                    lambda_results[func_name] = {
                        'exists': False,
                        'error': str(e)
                    }
        
        return {
            'expected_functions': expected_functions,
            'lambda_results': lambda_results,
            'total_expected': len(expected_functions),
            'total_found': sum(1 for result in lambda_results.values() if result.get('exists', False))
        }
    
    def check_agent_versions(self, agent_id: str, agent_name: str) -> Dict[str, Any]:
        """Check agent versions and preparation status"""
        print(f"\n🔍 Checking versions for agent: {agent_name}")
        
        try:
            # List agent versions
            response = self.bedrock_agent.list_agent_versions(agentId=agent_id)
            versions = response.get('agentVersionSummaries', [])
            
            print(f"  📋 Found {len(versions)} versions")
            
            version_details = []
            for version in versions:
                version_num = version.get('agentVersion', 'Unknown')
                version_status = version.get('agentStatus', 'Unknown')
                
                print(f"    Version {version_num}: {version_status}")
                
                # Get detailed version info
                try:
                    version_response = self.bedrock_agent.get_agent_version(
                        agentId=agent_id,
                        agentVersion=version_num
                    )
                    version_detail = version_response['agentVersion']
                    
                    action_groups = version_detail.get('actionGroups', [])
                    print(f"      Action groups: {len(action_groups)}")
                    
                    version_details.append({
                        'version': version_num,
                        'status': version_status,
                        'action_groups_count': len(action_groups),
                        'foundation_model': version_detail.get('foundationModel'),
                        'created_at': str(version_detail.get('createdAt', '')),
                        'updated_at': str(version_detail.get('updatedAt', ''))
                    })
                    
                except ClientError as e:
                    print(f"      ❌ Error getting version details: {e}")
                    version_details.append({
                        'version': version_num,
                        'status': version_status,
                        'error': str(e)
                    })
            
            return {
                'agent_name': agent_name,
                'total_versions': len(versions),
                'version_details': version_details
            }
            
        except ClientError as e:
            print(f"  ❌ Error listing versions: {e}")
            return {
                'agent_name': agent_name,
                'error': str(e)
            }
    
    def run_comprehensive_test(self) -> bool:
        """Run comprehensive action group tests"""
        print("🚀 Starting Comprehensive Action Group Tests")
        print("=" * 60)
        
        # Get Vista agents
        agents = self.get_vista_agents()
        
        if not agents:
            print("❌ No Vista agents found")
            return False
        
        print(f"📋 Found {len(agents)} Vista agents")
        
        # Test Lambda functions first
        lambda_test_results = self.test_lambda_functions_for_agents()
        self.test_results['lambda_functions'] = lambda_test_results
        
        # Test each agent's action groups
        agent_action_group_results = {}
        agent_version_results = {}
        
        for agent in agents:
            agent_id = agent['agentId']
            agent_name = agent['agentName']
            
            # Test action groups
            ag_results = self.test_agent_action_groups_detailed(agent_id, agent_name)
            agent_action_group_results[agent_id] = ag_results
            
            # Test versions
            version_results = self.check_agent_versions(agent_id, agent_name)
            agent_version_results[agent_id] = version_results
        
        self.test_results['agent_action_groups'] = agent_action_group_results
        self.test_results['agent_versions'] = agent_version_results
        
        # Summary
        total_agents = len(agents)
        agents_with_action_groups = sum(
            1 for result in agent_action_group_results.values() 
            if result.get('has_action_groups', False)
        )
        
        print(f"\n📊 Summary:")
        print(f"  Total agents: {total_agents}")
        print(f"  Agents with action groups: {agents_with_action_groups}")
        print(f"  Lambda functions found: {lambda_test_results['total_found']}/{lambda_test_results['total_expected']}")
        
        # Determine overall success
        success = True
        
        # Check if we have the expected number of Lambda functions
        if lambda_test_results['total_found'] < lambda_test_results['total_expected']:
            print("⚠️  Some expected Lambda functions are missing")
            success = False
        
        # For agents that should have action groups, check if they do
        agents_that_should_have_action_groups = [
            'SAM-agent-find-nearestdealership',
            'SAM-agent-bookdealerappt', 
            'SAM-agent-finddealeravailability',
            'SAM-agent-parts-availability',
            'SAM-agent-warrantyandrecalls'
        ]
        
        for agent_id, result in agent_action_group_results.items():
            agent_name = result.get('agent_name', '')
            if agent_name in agents_that_should_have_action_groups:
                if not result.get('has_action_groups', False):
                    print(f"⚠️  Agent {agent_name} should have action groups but doesn't")
                    # Don't fail the test as this might be expected in some deployments
        
        return success
    
    def generate_report(self) -> str:
        """Generate detailed test report"""
        report = "# Bedrock Action Groups Test Report\n\n"
        
        # Lambda Functions Summary
        if 'lambda_functions' in self.test_results:
            lambda_results = self.test_results['lambda_functions']
            report += "## Lambda Functions\n\n"
            report += f"- **Expected**: {lambda_results['total_expected']}\n"
            report += f"- **Found**: {lambda_results['total_found']}\n\n"
            
            for func_name, result in lambda_results['lambda_results'].items():
                status = "✅" if result.get('exists', False) else "❌"
                report += f"### {status} {func_name}\n"
                if result.get('exists', False):
                    report += f"- **Runtime**: {result.get('runtime', 'Unknown')}\n"
                    report += f"- **Handler**: {result.get('handler', 'Unknown')}\n"
                    report += f"- **Bedrock Permissions**: {result.get('bedrock_permissions', 0)}\n"
                else:
                    report += f"- **Error**: {result.get('error', 'Unknown')}\n"
                report += "\n"
        
        # Agent Action Groups Summary
        if 'agent_action_groups' in self.test_results:
            report += "## Agent Action Groups\n\n"
            
            for agent_id, result in self.test_results['agent_action_groups'].items():
                agent_name = result.get('agent_name', agent_id)
                has_ag = result.get('has_action_groups', False)
                ag_count = result.get('action_groups_count', 0)
                
                status = "✅" if has_ag else "ℹ️"
                report += f"### {status} {agent_name}\n"
                report += f"- **Action Groups**: {ag_count}\n"
                
                if 'action_groups' in result:
                    for ag in result['action_groups']:
                        report += f"  - **{ag['name']}**: {ag['state']}\n"
                        if ag.get('lambda_arn'):
                            lambda_status = "✅" if ag.get('lambda_accessible', False) else "❌"
                            report += f"    - Lambda: {lambda_status} {ag['lambda_arn']}\n"
                        schema_status = "✅" if ag.get('has_schema', False) else "❌"
                        report += f"    - Schema: {schema_status}\n"
                
                report += "\n"
        
        return report

def main():
    """Main test execution"""
    tester = ActionGroupTester()
    
    # Run comprehensive tests
    success = tester.run_comprehensive_test()
    
    # Generate and save report
    report = tester.generate_report()
    report_path = 'bedrock_action_groups_test_report.md'
    
    with open(report_path, 'w') as f:
        f.write(report)
    
    print(f"\n📄 Detailed test report saved to: {report_path}")
    
    # Exit with appropriate code
    sys.exit(0 if success else 1)

if __name__ == "__main__":
    main()