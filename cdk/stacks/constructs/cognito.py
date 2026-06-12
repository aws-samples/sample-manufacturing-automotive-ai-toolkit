"""
Cognito Construct for AgentCore JWT authorization
"""

from aws_cdk import (
    aws_cognito as cognito,
    aws_iam as iam,
    aws_lambda as lambda_,
    custom_resources as cr,
    CustomResource,
    Duration,
    RemovalPolicy,
    Stack,
)
from cdk_nag import NagSuppressions
from constructs import Construct


class CognitoConstruct(Construct):
    """Cognito User Pool and App Client for AgentCore agent authorization."""

    def __init__(self, scope: Construct, construct_id: str,
                 username: str = "testuser",
                 password: str = "ChangeMe123!",
                 **kwargs) -> None:
        super().__init__(scope, construct_id)

        self.user_pool = cognito.UserPool(
            self, "AgentCoreUserPool",
            user_pool_name=f"{Stack.of(self).stack_name}-agentcore-pool",
            self_sign_up_enabled=False,
            removal_policy=RemovalPolicy.DESTROY,
            password_policy=cognito.PasswordPolicy(
                min_length=8,
                require_uppercase=True,
                require_digits=True,
                require_symbols=True,
            ),
        )

        self.app_client = self.user_pool.add_client(
            "AgentCoreClient",
            auth_flows=cognito.AuthFlow(user_password=True, user_srp=True),
            generate_secret=False,
        )

        # Create default user via custom resource
        create_user_fn = lambda_.Function(
            self, "CreateUserFunction",
            runtime=lambda_.Runtime.PYTHON_3_9,
            handler="index.handler",
            timeout=Duration.seconds(30),
            code=lambda_.Code.from_inline("""
import boto3
import json

def handler(event, context):
    props = event['ResourceProperties']
    pool_id = props['UserPoolId']
    username = props['Username']
    password = props['Password']
    cognito = boto3.client('cognito-idp')

    if event['RequestType'] in ('Create', 'Update'):
        try:
            cognito.admin_get_user(UserPoolId=pool_id, Username=username)
        except cognito.exceptions.UserNotFoundException:
            cognito.admin_create_user(
                UserPoolId=pool_id, Username=username,
                TemporaryPassword='Temp123!', MessageAction='SUPPRESS')
            cognito.admin_set_user_password(
                UserPoolId=pool_id, Username=username,
                Password=password, Permanent=True)
    return {'PhysicalResourceId': f'{pool_id}/{username}'}
"""),
        )

        create_user_fn.add_to_role_policy(iam.PolicyStatement(
            actions=[
                "cognito-idp:AdminCreateUser",
                "cognito-idp:AdminSetUserPassword",
                "cognito-idp:AdminGetUser",
            ],
            resources=[self.user_pool.user_pool_arn],
        ))

        provider = cr.Provider(self, "CreateUserProvider", on_event_handler=create_user_fn)

        CustomResource(self, "DefaultUser",
            service_token=provider.service_token,
            properties={
                "UserPoolId": self.user_pool.user_pool_id,
                "Username": username,
                "Password": password,
            },
        )

        NagSuppressions.add_resource_suppressions(
            self.user_pool,
            [
                {"id": "AwsSolutions-COG2", "reason": "MFA not required for demo/toolkit environment"},
                {"id": "AwsSolutions-COG8", "reason": "Plus tier not required for demo/toolkit environment"},
            ],
        )

    @property
    def discovery_url(self) -> str:
        """OIDC discovery URL for the Cognito User Pool."""
        region = Stack.of(self).region
        return f"https://cognito-idp.{region}.amazonaws.com/{self.user_pool.user_pool_id}/.well-known/openid-configuration"

    @property
    def client_id(self) -> str:
        return self.app_client.user_pool_client_id


class GatewayCognitoConstruct(Construct):
    """Cognito User Pool with OAuth M2M client for AgentCore Gateway authentication."""

    def __init__(self, scope: Construct, construct_id: str,
                 resource_server_id: str = "AutomotiveGatewayResId",
                 **kwargs) -> None:
        super().__init__(scope, construct_id)

        self.resource_server_id = resource_server_id
        stack = Stack.of(self)

        self.user_pool = cognito.UserPool(
            self, "GatewayUserPool",
            user_pool_name=f"{stack.stack_name}-gateway-pool",
            self_sign_up_enabled=False,
            removal_policy=RemovalPolicy.DESTROY,
            password_policy=cognito.PasswordPolicy(
                min_length=8, require_uppercase=True,
                require_digits=True, require_symbols=True,
            ),
        )

        # Domain is created by the custom resource below (must match pool_id without underscores, lowercased)
        # because mcp_agent.py constructs the token URL as: pool_id.replace("_", "").auth.REGION.amazoncognito.com

        # Resource server + M2M client via custom resource (CDK L2 doesn't support GenerateSecret with OAuth)
        setup_fn = lambda_.Function(
            self, "SetupGatewayOAuth",
            runtime=lambda_.Runtime.PYTHON_3_9,
            handler="index.handler",
            timeout=Duration.seconds(30),
            code=lambda_.Code.from_inline("""
import boto3, json

def handler(event, context):
    props = event['ResourceProperties']
    pool_id = props['UserPoolId']
    res_id = props['ResourceServerId']
    cognito = boto3.client('cognito-idp')

    if event['RequestType'] == 'Delete':
        return {'PhysicalResourceId': event.get('PhysicalResourceId', 'gw-oauth')}

    # Ensure domain (pool_id without underscores, lowercased - required by mcp_agent.py)
    domain = pool_id.replace('_', '').lower()
    try:
        cognito.describe_user_pool(UserPoolId=pool_id)
        try:
            cognito.create_user_pool_domain(UserPoolId=pool_id, Domain=domain)
        except Exception:
            pass  # domain may already exist

    except Exception:
        pass

    # Ensure resource server
    try:
        cognito.describe_resource_server(UserPoolId=pool_id, Identifier=res_id)
    except cognito.exceptions.ResourceNotFoundException:
        cognito.create_resource_server(
            UserPoolId=pool_id, Identifier=res_id,
            Name='GatewayResourceServer',
            Scopes=[
                {'ScopeName': 'gateway:read', 'ScopeDescription': 'Read'},
                {'ScopeName': 'gateway:write', 'ScopeDescription': 'Write'},
            ])

    # Ensure M2M client
    client_name = 'GatewayM2MClient'
    clients = cognito.list_user_pool_clients(UserPoolId=pool_id, MaxResults=60)
    for c in clients['UserPoolClients']:
        if c['ClientName'] == client_name:
            desc = cognito.describe_user_pool_client(UserPoolId=pool_id, ClientId=c['ClientId'])
            return {
                'PhysicalResourceId': f'{pool_id}/{c["ClientId"]}',
                'Data': {'ClientId': c['ClientId'], 'ClientSecret': desc['UserPoolClient']['ClientSecret']}
            }

    resp = cognito.create_user_pool_client(
        UserPoolId=pool_id, ClientName=client_name, GenerateSecret=True,
        AllowedOAuthFlows=['client_credentials'],
        AllowedOAuthScopes=[f'{res_id}/gateway:read', f'{res_id}/gateway:write'],
        AllowedOAuthFlowsUserPoolClient=True,
        SupportedIdentityProviders=['COGNITO'],
        ExplicitAuthFlows=['ALLOW_REFRESH_TOKEN_AUTH'])
    return {
        'PhysicalResourceId': f'{pool_id}/{resp["UserPoolClient"]["ClientId"]}',
        'Data': {'ClientId': resp['UserPoolClient']['ClientId'], 'ClientSecret': resp['UserPoolClient']['ClientSecret']}
    }
"""),
        )

        setup_fn.add_to_role_policy(iam.PolicyStatement(
            actions=[
                "cognito-idp:CreateResourceServer",
                "cognito-idp:DescribeResourceServer",
                "cognito-idp:CreateUserPoolClient",
                "cognito-idp:DescribeUserPoolClient",
                "cognito-idp:ListUserPoolClients",
                "cognito-idp:DescribeUserPool",
                "cognito-idp:CreateUserPoolDomain",
            ],
            resources=[self.user_pool.user_pool_arn],
        ))

        provider = cr.Provider(self, "GatewayOAuthProvider", on_event_handler=setup_fn)

        self._oauth_resource = CustomResource(self, "GatewayOAuthSetup",
            service_token=provider.service_token,
            properties={
                "UserPoolId": self.user_pool.user_pool_id,
                "ResourceServerId": resource_server_id,
            },
        )

        NagSuppressions.add_resource_suppressions(
            self.user_pool,
            [
                {"id": "AwsSolutions-COG2", "reason": "MFA not required for M2M OAuth pool"},
                {"id": "AwsSolutions-COG8", "reason": "Plus tier not required for demo"},
            ],
        )

    @property
    def gateway_user_pool_id(self) -> str:
        return self.user_pool.user_pool_id

    @property
    def gateway_client_id(self) -> str:
        return self._oauth_resource.get_att_string("ClientId")

    @property
    def gateway_client_secret(self) -> str:
        return self._oauth_resource.get_att_string("ClientSecret")
