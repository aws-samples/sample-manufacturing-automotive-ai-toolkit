#!/usr/bin/env python3
import os
import json
import re
from datetime import datetime
import inquirer
from typing import Dict, List, Optional

def sanitize_id(name: str) -> str:
    """Convert a name to a valid ID format that matches [a-zA-Z][a-zA-Z0-9_]{0,47}."""
    original = name
    # Start with first letter, replace invalid chars with underscore
    sanitized = re.sub(r'[^a-zA-Z0-9_]', '_', name)
    
    # Ensure it starts with a letter
    if not sanitized or not sanitized[0].isalpha():
        sanitized = 'agent_' + sanitized
    
    # Truncate to 48 characters max
    sanitized = sanitized[:48]
    
    # Remove trailing underscores
    sanitized = sanitized.rstrip('_')
    
    # Notify user if changed
    if sanitized != original:
        print(f"📝 Agent name updated to meet requirements: '{original}' → '{sanitized}'")
    
    return sanitized

def get_next_folder_number(base_path: str) -> str:
    """Get the next available folder number in the sequence."""
    try:
        existing = [d for d in os.listdir(base_path) if os.path.isdir(os.path.join(base_path, d))]
        numbers = [int(d.split('-')[0]) for d in existing if d[:2].isdigit()]
        next_num = max(numbers + [-1]) + 1
        return f"{next_num:02d}"
    except Exception:
        return "00"

def prompt_basic_info() -> Dict:
    """Prompt for basic agent information."""
    questions = [
        inquirer.Text('name', message="What is the name of your agent?"),
        inquirer.Text('description', message="Provide a description of your agent"),
        inquirer.List('agent_type',
                     message="What type of agent is this?",
                     choices=['bedrock', 'agentcore']),
        inquirer.List('deployment_type',
                     message="Is this a standalone agent or part of a multi-agent collaboration?",
                     choices=['standalone', 'collaboration']),
        inquirer.Text('entrypoint',
                     message="What is the main entry point file? (e.g., agent.py)",
                     default="agent.py"),
        inquirer.Text('version',
                     message="What is the version of your agent?",
                     default="1.0.0"),
    ]
    answers = inquirer.prompt(questions)
    
    # Sanitize the agent name and notify user if changed
    agent_id = sanitize_id(answers['name'])
    answers['agent_id'] = agent_id
    
    return answers

def prompt_infrastructure() -> Optional[Dict]:
    """Prompt for CDK infrastructure needs."""
    print("\nLet's check if you need custom AWS infrastructure.")
    print("This is useful if your agent needs resources like Lambda functions, DynamoDB tables, etc.")
    print("If yes, we'll set up CDK (AWS Cloud Development Kit) for you.")
    
    needs_cdk = inquirer.confirm("Does this agent need custom AWS infrastructure (Lambda, DynamoDB, etc.)?", default=False)
    
    if not needs_cdk:
        return None
    
    questions = [
        inquirer.Text('stack_class',
                     message="CDK Stack class name",
                     default="AgentStack"),
        inquirer.Text('stack_path',
                     message="CDK Stack file path",
                     default="cdk/stack.py"),
        inquirer.Confirm('create_example',
                        message="Create a CDK example stack?",
                        default=True)
    ]
    
    answers = inquirer.prompt(questions)
    
    return {
        'cdk': True,
        'stack_class': answers['stack_class'],
        'stack_path': answers['stack_path'],
        'create_example': answers['create_example']
    }

def create_manifest(info: Dict, infrastructure: Optional[Dict] = None) -> Dict:
    """Create the manifest JSON structure."""
    manifest = {
        "agents": [{
            "id": info['agent_id'],
            "name": info['name'],
            "version": info['version'],
            "description": info['description'],
            "type": info['agent_type'],
            "entrypoint": info['entrypoint'],
            "metadata": {
                "authors": [
                    {
                        "name": os.getenv('USER', 'Unknown'),
                        "organization": "AWS"
                    }
                ],
                "created_date": datetime.now().strftime("%Y-%m-%d"),
                "last_updated": datetime.now().strftime("%Y-%m-%d"),
                "maturity": "development"
            }
        }]
    }
    
    if infrastructure:
        manifest["infrastructure"] = {
            "cdk": infrastructure['cdk'],
            "stack_class": infrastructure['stack_class'],
            "stack_path": infrastructure['stack_path']
        }
    
    return manifest

def create_folder_structure(base_path: str, agent_id: str, manifest: Dict, infrastructure: Optional[Dict] = None) -> None:
    """Create the folder structure and files for the agent."""
    folder_num = get_next_folder_number(base_path)
    agent_folder = os.path.join(base_path, f"{folder_num}-{agent_id}")

    # Create main folder
    os.makedirs(agent_folder, exist_ok=True)

    # Create manifest file
    with open(os.path.join(agent_folder, 'manifest.json'), 'w') as f:
        json.dump(manifest, f, indent=2)

    # Create basic file structure
    os.makedirs(os.path.join(agent_folder, 'src'), exist_ok=True)
    os.makedirs(os.path.join(agent_folder, 'tests'), exist_ok=True)

    # Create CDK structure if needed
    if infrastructure and infrastructure.get('create_example'):
        cdk_folder = os.path.join(agent_folder, 'cdk')
        os.makedirs(cdk_folder, exist_ok=True)
        
        # Create example CDK stack
        stack_content = f'''"""
CDK Stack for {manifest['agents'][0]['name']}
"""

from aws_cdk import (
    Stack,
    aws_lambda as _lambda,
    aws_dynamodb as dynamodb,
    RemovalPolicy,
)
from constructs import Construct

class {infrastructure['stack_class']}(Stack):
    """CDK Stack for {manifest['agents'][0]['name']} infrastructure"""
    
    def __init__(self, scope: Construct, construct_id: str, **kwargs) -> None:
        super().__init__(scope, construct_id, **kwargs)
        
        # Example DynamoDB table
        self.table = dynamodb.Table(
            self, "AgentTable",
            table_name=f"{agent_id}-data",
            partition_key=dynamodb.Attribute(
                name="id",
                type=dynamodb.AttributeType.STRING
            ),
            removal_policy=RemovalPolicy.DESTROY
        )
        
        # Example Lambda function
        self.lambda_function = _lambda.Function(
            self, "AgentFunction",
            function_name=f"{agent_id}-function",
            runtime=_lambda.Runtime.PYTHON_3_11,
            handler="index.handler",
            code=_lambda.Code.from_inline("""
def handler(event, context):
    return {{"statusCode": 200, "body": "Hello from {manifest['agents'][0]['name']}!"}}
            """),
            environment={{
                "TABLE_NAME": self.table.table_name
            }}
        )
        
        # Grant Lambda permissions to access DynamoDB
        self.table.grant_read_write_data(self.lambda_function)
'''
        
        with open(os.path.join(cdk_folder, 'stack.py'), 'w') as f:
            f.write(stack_content)
        
        # Create CDK requirements
        with open(os.path.join(cdk_folder, 'requirements.txt'), 'w') as f:
            f.write("aws-cdk-lib>=2.0.0\nconstructs>=10.0.0\n")

    # Create entry point file
    with open(os.path.join(agent_folder, 'src', manifest['agents'][0]['entrypoint']), 'w') as f:
        f.write(f"""#!/usr/bin/env python3
\"\"\"
{manifest['agents'][0]['name']}
{manifest['agents'][0]['description']}
\"\"\"

def main():
    pass

if __name__ == "__main__":
    main()
""")

    # Create README
    readme_content = f"""# {manifest['agents'][0]['name']}

{manifest['agents'][0]['description']}

## Setup

1. Install dependencies:
   ```bash
   pip install -r requirements.txt
   ```
"""

    if infrastructure and infrastructure.get('create_example'):
        readme_content += """
## Infrastructure

This agent includes CDK infrastructure. To deploy:

1. Install CDK dependencies:
   ```bash
   cd cdk
   pip install -r requirements.txt
   ```

2. Deploy the stack:
   ```bash
   cdk deploy
   ```
"""

    readme_content += """
## Running Tests

```bash
python -m pytest tests/
```
"""

    with open(os.path.join(agent_folder, 'README.md'), 'w') as f:
        f.write(readme_content)

    # Create requirements.txt
    with open(os.path.join(agent_folder, 'requirements.txt'), 'w') as f:
        f.write("# Add your dependencies here\n")

    # Create basic test file
    with open(os.path.join(agent_folder, 'tests', 'test_agent.py'), 'w') as f:
        f.write(f"""#!/usr/bin/env python3
\"\"\"
Tests for {manifest['agents'][0]['name']}
\"\"\"

def test_basic():
    assert True  # Add your tests here
""")

def main():
    print("🤖 Welcome to the Agent Creation Wizard! 🧙‍♂️")
    print("This wizard will help you set up a new agent in the catalog.")
    print()

    # Get basic information
    info = prompt_basic_info()

    # Get infrastructure details
    infrastructure = prompt_infrastructure()

    # Create manifest
    manifest = create_manifest(info, infrastructure)

    # Determine base path based on deployment type
    base_dir = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
    if info['deployment_type'] == 'standalone':
        base_path = os.path.join(base_dir, 'agents_catalog', 'standalone_agents')
    else:
        base_path = os.path.join(base_dir, 'agents_catalog', 'multi_agent_collaboration')

    # Create folder structure
    create_folder_structure(base_path, info['agent_id'], manifest, infrastructure)

    print(f"\n✨ Agent {info['name']} has been created successfully!")
    print(f"You can find your agent in: {base_path}")
    print("\nNext steps:")
    print("1. Review and update the generated manifest.json")
    print("2. Implement your agent logic in the src directory")
    print("3. Add tests in the tests directory")
    print("4. Update the README.md with additional information")
    print("5. Add your dependencies to requirements.txt")

if __name__ == "__main__":
    main()
