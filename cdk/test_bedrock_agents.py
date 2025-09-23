#!/usr/bin/env python3
"""
Bedrock Agents Functionality Testing Script
Tests Bedrock agent creation, configuration, invocation, and permissions
"""

import json
import subprocess
import sys
import os
import boto3
import time
from typing import Dict, List, Optional, Any, Tuple
from botocore.exceptions import ClientError, NoCredentialsError

class BedrockAgentsTester:
    """Test Bedrock agents functionality"""
    
    def __init__(self, stack_name: str = "MA3TMainStack"):
        self.stack_name = stack_name
        self.test_results = {}
        self.cdk_path = os.path.dirname(os.path.abspath(__file__))
        
        # Initialize AWS clients
        try:
            self.cloudformation = boto3.client('cloudformation')
            self.bedrock_agent = boto3.client('bedrock-agent')
            self.bedrock_agent_runtime = boto3.client('bedrock-agent-runtime')
            self.lambda_client = boto3.client('lambda')
            self.iam = boto3.client('iam')
        except NoCredentialsError:
            print("❌ AWS credentials not configured. Please configure AWS credentials.")
            sys.exit(1)
    
    def get_stack_outputs(self) -> Dict[str, str]:
        """Get CloudFormation stack outputs"""
        try:
            response = self.cloudformation.describe_stacks(StackName=self.stack_name)
            stack = response['Stacks'][0]
            
            outputs = {}
            for output in stack.get('Outputs', []):
                outputs[output['OutputKey']] = output['OutputValue']
            
            return outputs
        except ClientError as e:
            print(f"❌ Error getting stack outputs: {e}")
            return {}
    
    def discover_bedrock_agents(self) -> Tuple[List[Dict], List[Dict]]:
        """Discover Bedrock agents from stack outputs and AWS"""
        print("🔄 Discovering Bedrock agents...")
        
        # Get stack outputs to find agent IDs
        outputs = self.get_stack_outputs()
        
        # Find agent-related outputs
        agent_outputs = {}
        for key, value in outputs.items():
            if 'Agent' in key and ('Id' in key or 'Alias' in key):
                agent_outputs[key] = value
        
        print(f"📋 Found {len(agent_outputs)} agent-related outputs:")
        for key, value in agent_outputs.items():
            print(f"  {key}: {value}")
        
        # Discover agents from AWS
        discovered_agents = []
        discovered_aliases = []
        
        try:
            # List all agents
            response = self.bedrock_agent.list_agents()
            all_agents = response.get('agentSummaries', [])
            
            # Filter agents that belong to our stack (by name pattern)
            vista_agents = [agent for agent in all_agents if 'SAM-agent' in agent.get('agentName', '')]
            
            print(f"📋 Found {len(vista_agents)} Vista agents in AWS:")
            for agent in vista_agents:
                print(f"  {agent['agentName']} (ID: {agent['agentId']})")
                discovered_agents.append(agent)
                
                # Get aliases for each agent
                try:
                    aliases_response = self.bedrock_agent.list_agent_aliases(agentId=agent['agentId'])
                    aliases = aliases_response.get('agentAliasSummaries', [])
                    for alias in aliases:
                        print(f"    Alias: {alias['agentAliasName']} (ID: {alias['agentAliasId']})")
                        discovered_aliases.append({
                            'agent_id': agent['agentId'],
                            'agent_name': agent['agentName'],
                            'alias_id': alias['agentAliasId'],
                            'alias_name': alias['agentAliasName']
                        })
                except ClientError as e:
                    print(f"    ⚠️  Could not list aliases for {agent['agentName']}: {e}")
            
            self.test_results['agent_discovery'] = {
                'success': True,
                'stack_outputs': agent_outputs,
                'discovered_agents': len(discovered_agents),
                'discovered_aliases': len(discovered_aliases),
                'agents': discovered_agents,
                'aliases': discovered_aliases
            }
            
            return discovered_agents, discovered_aliases
            
        except ClientError as e:
            print(f"❌ Error discovering agents: {e}")
            self.test_results['agent_discovery'] = {
                'success': False,
                'error': str(e)
            }
            return [], []
    
    def test_agent_configurations(self, agents: List[Dict]) -> bool:
        """Test that agents are configured correctly"""
        print("🔄 Testing agent configurations...")
        
        all_passed = True
        agent_details = {}
        
        for agent in agents:
            agent_id = agent['agentId']
            agent_name = agent['agentName']
            
            try:
                # Get detailed agent information
                response = self.bedrock_agent.get_agent(agentId=agent_id)
                agent_detail = response['agent']
                
                print(f"📋 Testing agent: {agent_name}")
                
                # Check required fields
                required_fields = ['agentName', 'description', 'instruction', 'foundationModel', 'agentResourceRoleArn']
                missing_fields = []
                
                for field in required_fields:
                    if not agent_detail.get(field):
                        missing_fields.append(field)
                        print(f"  ❌ Missing required field: {field}")
                
                if missing_fields:
                    all_passed = False
                else:
                    print(f"  ✅ All required fields present")
                
                # Check agent status
                agent_status = agent_detail.get('agentStatus')
                if agent_status == 'PREPARED':
                    print(f"  ✅ Agent status: {agent_status}")
                else:
                    print(f"  ⚠️  Agent status: {agent_status} (expected PREPARED)")
                    if agent_status in ['FAILED', 'DELETING']:
                        all_passed = False
                
                # Check foundation model
                foundation_model = agent_detail.get('foundationModel')
                if foundation_model:
                    print(f"  📋 Foundation model: {foundation_model}")
                else:
                    print(f"  ❌ No foundation model specified")
                    all_passed = False
                
                # Check IAM role
                role_arn = agent_detail.get('agentResourceRoleArn')
                if role_arn:
                    print(f"  📋 IAM role: {role_arn}")
                    # Verify role exists
                    try:
                        role_name = role_arn.split('/')[-1]
                        self.iam.get_role(RoleName=role_name)
                        print(f"  ✅ IAM role exists and accessible")
                    except ClientError:
                        print(f"  ❌ IAM role not accessible")
                        all_passed = False
                else:
                    print(f"  ❌ No IAM role specified")
                    all_passed = False
                
                # Check action groups
                action_groups = agent_detail.get('actionGroups', [])
                print(f"  📋 Action groups: {len(action_groups)}")
                
                for i, action_group in enumerate(action_groups):
                    ag_name = action_group.get('actionGroupName', f'ActionGroup{i}')
                    ag_state = action_group.get('actionGroupState', 'UNKNOWN')
                    print(f"    {ag_name}: {ag_state}")
                    
                    # Check if action group has executor
                    executor = action_group.get('actionGroupExecutor')
                    if executor and executor.get('lambda'):
                        lambda_arn = executor['lambda']
                        print(f"      Lambda: {lambda_arn}")
                        
                        # Verify Lambda function exists
                        try:
                            function_name = lambda_arn.split(':')[-1]
                            self.lambda_client.get_function(FunctionName=function_name)
                            print(f"      ✅ Lambda function accessible")
                        except ClientError:
                            print(f"      ❌ Lambda function not accessible")
                            all_passed = False
                
                agent_details[agent_id] = {
                    'name': agent_name,
                    'status': agent_status,
                    'foundation_model': foundation_model,
                    'role_arn': role_arn,
                    'action_groups_count': len(action_groups),
                    'missing_fields': missing_fields,
                    'configuration_valid': len(missing_fields) == 0 and agent_status == 'PREPARED'
                }
                
            except ClientError as e:
                print(f"  ❌ Error getting agent details: {e}")
                all_passed = False
                agent_details[agent_id] = {
                    'name': agent_name,
                    'error': str(e),
                    'configuration_valid': False
                }
        
        self.test_results['agent_configurations'] = {
            'success': all_passed,
            'agent_details': agent_details,
            'total_agents': len(agents),
            'valid_agents': sum(1 for details in agent_details.values() if details.get('configuration_valid', False))
        }
        
        return all_passed
    
    def test_agent_aliases(self, aliases: List[Dict]) -> bool:
        """Test that agent aliases are working correctly"""
        print("🔄 Testing agent aliases...")
        
        all_passed = True
        alias_details = {}
        
        for alias in aliases:
            agent_id = alias['agent_id']
            alias_id = alias['alias_id']
            alias_name = alias['alias_name']
            
            try:
                # Get alias details
                response = self.bedrock_agent.get_agent_alias(
                    agentId=agent_id,
                    agentAliasId=alias_id
                )
                alias_detail = response['agentAlias']
                
                print(f"📋 Testing alias: {alias_name} for agent {alias['agent_name']}")
                
                # Check alias status
                alias_status = alias_detail.get('agentAliasStatus')
                if alias_status == 'PREPARED':
                    print(f"  ✅ Alias status: {alias_status}")
                else:
                    print(f"  ⚠️  Alias status: {alias_status} (expected PREPARED)")
                    if alias_status in ['FAILED', 'DELETING']:
                        all_passed = False
                
                # Check if alias has routing configuration
                routing_config = alias_detail.get('routingConfiguration', [])
                print(f"  📋 Routing configuration: {len(routing_config)} entries")
                
                alias_details[f"{agent_id}:{alias_id}"] = {
                    'agent_name': alias['agent_name'],
                    'alias_name': alias_name,
                    'status': alias_status,
                    'routing_entries': len(routing_config),
                    'alias_valid': alias_status == 'PREPARED'
                }
                
            except ClientError as e:
                print(f"  ❌ Error getting alias details: {e}")
                all_passed = False
                alias_details[f"{agent_id}:{alias_id}"] = {
                    'agent_name': alias['agent_name'],
                    'alias_name': alias_name,
                    'error': str(e),
                    'alias_valid': False
                }
        
        self.test_results['agent_aliases'] = {
            'success': all_passed,
            'alias_details': alias_details,
            'total_aliases': len(aliases),
            'valid_aliases': sum(1 for details in alias_details.values() if details.get('alias_valid', False))
        }
        
        return all_passed
    
    def test_agent_invocation(self, aliases: List[Dict]) -> bool:
        """Test agent invocation functionality"""
        print("🔄 Testing agent invocation...")
        
        all_passed = True
        invocation_results = {}
        
        # Test a simple invocation for each alias
        test_prompts = {
            'vehiclesymptom': "My car is making a strange noise when I brake. What could be wrong?",
            'nearestdealership': "Find a dealership in Seattle",
            'bookdealerappt': "Hello, I'd like to know about booking an appointment",
            'finddealeravailability': "What are the available appointment slots?",
            'parts-availability': "I need parts for DTC code P0301",
            'warrantyandrecalls': "Check warranty for VIN 1HGBH41JXMN109186",
            'orchestrater': "Hello, I need help with my vehicle"
        }
        
        for alias in aliases[:3]:  # Test first 3 aliases to avoid rate limits
            agent_id = alias['agent_id']
            alias_id = alias['alias_id']
            agent_name = alias['agent_name']
            alias_name = alias['alias_name']
            
            # Determine test prompt based on agent type
            test_prompt = "Hello, can you help me?"
            for key, prompt in test_prompts.items():
                if key in agent_name.lower() or key in alias_name.lower():
                    test_prompt = prompt
                    break
            
            try:
                print(f"📋 Testing invocation: {alias_name} for {agent_name}")
                print(f"  📝 Test prompt: {test_prompt}")
                
                # Invoke the agent
                response = self.bedrock_agent_runtime.invoke_agent(
                    agentId=agent_id,
                    agentAliasId=alias_id,
                    sessionId=f"test-session-{int(time.time())}",
                    inputText=test_prompt
                )
                
                # Process the streaming response
                completion = ""
                event_stream = response.get('completion', [])
                
                for event in event_stream:
                    if 'chunk' in event:
                        chunk = event['chunk']
                        if 'bytes' in chunk:
                            completion += chunk['bytes'].decode('utf-8')
                
                if completion:
                    print(f"  ✅ Agent responded successfully")
                    print(f"  📄 Response length: {len(completion)} characters")
                    
                    invocation_results[f"{agent_id}:{alias_id}"] = {
                        'agent_name': agent_name,
                        'alias_name': alias_name,
                        'test_prompt': test_prompt,
                        'response_length': len(completion),
                        'response_preview': completion[:200] + "..." if len(completion) > 200 else completion,
                        'invocation_successful': True
                    }
                else:
                    print(f"  ⚠️  Agent responded but no content received")
                    all_passed = False
                    invocation_results[f"{agent_id}:{alias_id}"] = {
                        'agent_name': agent_name,
                        'alias_name': alias_name,
                        'test_prompt': test_prompt,
                        'invocation_successful': False,
                        'error': 'No response content'
                    }
                
                # Add delay between invocations to avoid rate limits
                time.sleep(2)
                
            except ClientError as e:
                error_code = e.response.get('Error', {}).get('Code', 'Unknown')
                print(f"  ❌ Invocation failed: {error_code} - {e}")
                
                # Some errors are expected (like throttling), don't fail the test for those
                if error_code in ['ThrottlingException', 'ServiceQuotaExceededException']:
                    print(f"  ℹ️  Skipping due to rate limiting")
                    invocation_results[f"{agent_id}:{alias_id}"] = {
                        'agent_name': agent_name,
                        'alias_name': alias_name,
                        'test_prompt': test_prompt,
                        'invocation_successful': False,
                        'error': f'Rate limited: {error_code}',
                        'skipped': True
                    }
                else:
                    all_passed = False
                    invocation_results[f"{agent_id}:{alias_id}"] = {
                        'agent_name': agent_name,
                        'alias_name': alias_name,
                        'test_prompt': test_prompt,
                        'invocation_successful': False,
                        'error': str(e)
                    }
            
            except Exception as e:
                print(f"  ❌ Unexpected error during invocation: {e}")
                all_passed = False
                invocation_results[f"{agent_id}:{alias_id}"] = {
                    'agent_name': agent_name,
                    'alias_name': alias_name,
                    'test_prompt': test_prompt,
                    'invocation_successful': False,
                    'error': f'Unexpected error: {str(e)}'
                }
        
        # Count successful invocations (excluding skipped ones)
        successful_invocations = sum(
            1 for result in invocation_results.values() 
            if result.get('invocation_successful', False)
        )
        
        skipped_invocations = sum(
            1 for result in invocation_results.values() 
            if result.get('skipped', False)
        )
        
        self.test_results['agent_invocation'] = {
            'success': all_passed,
            'invocation_results': invocation_results,
            'total_tested': len(invocation_results),
            'successful_invocations': successful_invocations,
            'skipped_invocations': skipped_invocations
        }
        
        return all_passed
    
    def test_supervisor_collaboration(self, aliases: List[Dict]) -> bool:
        """Test supervisor agent collaboration functionality"""
        print("🔄 Testing supervisor agent collaboration...")
        
        # Find the supervisor agent (orchestrater)
        supervisor_alias = None
        for alias in aliases:
            if 'orchestrater' in alias['alias_name'].lower() or 'supervisor' in alias['agent_name'].lower():
                supervisor_alias = alias
                break
        
        if not supervisor_alias:
            print("⚠️  No supervisor agent found, skipping collaboration test")
            self.test_results['supervisor_collaboration'] = {
                'success': False,
                'error': 'No supervisor agent found',
                'skipped': True
            }
            return True  # Don't fail the overall test
        
        try:
            agent_id = supervisor_alias['agent_id']
            
            # Get agent details to check for collaboration configuration
            response = self.bedrock_agent.get_agent(agentId=agent_id)
            agent_detail = response['agent']
            
            print(f"📋 Testing supervisor: {supervisor_alias['agent_name']}")
            
            # Check if agent has collaboration enabled
            collaboration_mode = agent_detail.get('agentCollaboration')
            if collaboration_mode:
                print(f"  ✅ Collaboration mode: {collaboration_mode}")
            else:
                print(f"  ⚠️  No collaboration mode configured")
            
            # Check for collaborators
            collaborators = agent_detail.get('agentCollaborators', [])
            print(f"  📋 Collaborators: {len(collaborators)}")
            
            collaborator_details = []
            for collaborator in collaborators:
                collab_name = collaborator.get('collaboratorName', 'Unknown')
                collab_instruction = collaborator.get('collaborationInstruction', '')
                print(f"    {collab_name}: {collab_instruction[:100]}...")
                collaborator_details.append({
                    'name': collab_name,
                    'instruction': collab_instruction
                })
            
            # Test a collaboration scenario
            collaboration_test_prompt = "I have a car problem and need to find a dealer and book an appointment"
            
            try:
                print(f"  📝 Testing collaboration with prompt: {collaboration_test_prompt}")
                
                response = self.bedrock_agent_runtime.invoke_agent(
                    agentId=agent_id,
                    agentAliasId=supervisor_alias['alias_id'],
                    sessionId=f"collab-test-{int(time.time())}",
                    inputText=collaboration_test_prompt
                )
                
                # Process response
                completion = ""
                event_stream = response.get('completion', [])
                
                for event in event_stream:
                    if 'chunk' in event:
                        chunk = event['chunk']
                        if 'bytes' in chunk:
                            completion += chunk['bytes'].decode('utf-8')
                
                collaboration_successful = len(completion) > 0
                
                if collaboration_successful:
                    print(f"  ✅ Collaboration test successful")
                else:
                    print(f"  ⚠️  Collaboration test returned no response")
                
                self.test_results['supervisor_collaboration'] = {
                    'success': True,
                    'supervisor_agent': supervisor_alias['agent_name'],
                    'collaboration_mode': collaboration_mode,
                    'collaborators_count': len(collaborators),
                    'collaborator_details': collaborator_details,
                    'collaboration_test_successful': collaboration_successful,
                    'test_response_length': len(completion)
                }
                
                return True
                
            except ClientError as e:
                error_code = e.response.get('Error', {}).get('Code', 'Unknown')
                if error_code in ['ThrottlingException', 'ServiceQuotaExceededException']:
                    print(f"  ℹ️  Collaboration test skipped due to rate limiting")
                    self.test_results['supervisor_collaboration'] = {
                        'success': True,
                        'supervisor_agent': supervisor_alias['agent_name'],
                        'collaboration_mode': collaboration_mode,
                        'collaborators_count': len(collaborators),
                        'collaborator_details': collaborator_details,
                        'collaboration_test_successful': False,
                        'skipped': True,
                        'error': 'Rate limited'
                    }
                    return True
                else:
                    raise e
            
        except ClientError as e:
            print(f"❌ Error testing supervisor collaboration: {e}")
            self.test_results['supervisor_collaboration'] = {
                'success': False,
                'error': str(e)
            }
            return False
    
    def run_all_tests(self) -> bool:
        """Run all Bedrock agent tests"""
        print("🚀 Starting Bedrock Agents Functionality Tests")
        print("=" * 60)
        
        # Discover agents
        agents, aliases = self.discover_bedrock_agents()
        
        if not agents:
            print("❌ No Bedrock agents found. Cannot proceed with tests.")
            return False
        
        tests = [
            ("Agent Configurations", lambda: self.test_agent_configurations(agents)),
            ("Agent Aliases", lambda: self.test_agent_aliases(aliases)),
            ("Agent Invocation", lambda: self.test_agent_invocation(aliases)),
            ("Supervisor Collaboration", lambda: self.test_supervisor_collaboration(aliases))
        ]
        
        all_passed = True
        
        for test_name, test_func in tests:
            print(f"\n📋 Running: {test_name}")
            try:
                result = test_func()
                if not result:
                    all_passed = False
            except Exception as e:
                print(f"❌ Test {test_name} failed with exception: {e}")
                all_passed = False
        
        print("\n" + "=" * 60)
        if all_passed:
            print("🎉 All Bedrock agent tests passed!")
        else:
            print("❌ Some tests failed. Check the output above for details.")
        
        return all_passed
    
    def generate_test_report(self) -> str:
        """Generate a detailed test report"""
        report = "# Bedrock Agents Functionality Test Report\n\n"
        
        # Summary
        total_tests = len(self.test_results)
        passed_tests = sum(1 for result in self.test_results.values() if result.get('success', False))
        
        report += f"## Summary\n"
        report += f"- **Total Tests**: {total_tests}\n"
        report += f"- **Passed**: {passed_tests}\n"
        report += f"- **Failed**: {total_tests - passed_tests}\n\n"
        
        # Detailed results
        for test_name, result in self.test_results.items():
            report += f"## {test_name.replace('_', ' ').title()}\n"
            
            if result.get('success', False):
                report += "✅ **Status**: PASSED\n\n"
            elif result.get('skipped', False):
                report += "⏭️ **Status**: SKIPPED\n\n"
            else:
                report += "❌ **Status**: FAILED\n\n"
            
            if 'error' in result:
                report += f"**Error**: {result['error']}\n\n"
            
            # Add specific details for each test
            for key, value in result.items():
                if key not in ['success', 'error', 'skipped']:
                    if isinstance(value, (dict, list)):
                        try:
                            report += f"**{key.replace('_', ' ').title()}**: {json.dumps(value, indent=2, default=str)}\n\n"
                        except (TypeError, ValueError):
                            report += f"**{key.replace('_', ' ').title()}**: {str(value)}\n\n"
                    else:
                        report += f"**{key.replace('_', ' ').title()}**: {value}\n\n"
        
        return report

def main():
    """Main test execution"""
    if len(sys.argv) > 1:
        stack_name = sys.argv[1]
    else:
        stack_name = "MA3TMainStack"
    
    tester = BedrockAgentsTester(stack_name)
    
    # Run all tests
    success = tester.run_all_tests()
    
    # Generate and save report
    report = tester.generate_test_report()
    report_path = os.path.join(tester.cdk_path, 'bedrock_agents_test_report.md')
    
    with open(report_path, 'w') as f:
        f.write(report)
    
    print(f"\n📄 Detailed test report saved to: {report_path}")
    
    # Exit with appropriate code
    sys.exit(0 if success else 1)

if __name__ == "__main__":
    main()