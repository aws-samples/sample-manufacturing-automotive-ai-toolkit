# CDK Deployment Test Report

## Node Version
✅ **Status**: PASSED

**Version**: v18.20.2

**Major Version**: 18

## Aws Environment
✅ **Status**: PASSED

**Account Id**: 149536462911

**User Arn**: arn:aws:iam::149536462911:user/cliuser

## Cdk Bootstrap
✅ **Status**: PASSED

**Status**: UPDATE_COMPLETE

## Synthesis
✅ **Status**: PASSED

**Template Path**: /Users/agweber/code/old-amazon-bedrock-agents-healthcare-lifesciences/cdk/cdk.out/MA3TMainStack.template.json

**Resource Count**: 40

**Missing Sections**: []

## Template Validation
✅ **Status**: PASSED

**Found Types**: ['AWS::CDK::Metadata', 'AWS::CloudFormation::CustomResource', 'AWS::CloudFormation::Stack', 'AWS::CodeBuild::Project', 'AWS::DynamoDB::Table', 'AWS::IAM::Policy', 'AWS::IAM::Role', 'AWS::Lambda::Function', 'AWS::S3::Bucket', 'AWS::S3::BucketPolicy']

**Missing Types**: []

**Resource Details**: {'AWS::S3::Bucket': ['StorageResourceBucketD8B2FEFB'], 'AWS::S3::BucketPolicy': ['StorageResourceBucketPolicyD82FEAA9'], 'AWS::DynamoDB::Table': ['StorageTabledealerdataD75C50ED', 'StorageTabledealerappointmentdata7682AA7C', 'StorageTablecustomeruserprofile6AF7F7BD', 'StorageTabledtcpartslookupCBA658FD', 'StorageTabledealerpartsstockAF3FF571', 'StorageTabledealerpartsorder511E3F95', 'StorageTablewarrantyinfoC34BBF0B'], 'AWS::IAM::Role': ['IAMAgentRole10CD547C', 'IAMLambdaExecutionRole95EEC9C4', 'IAMCodeBuildServiceRoleEBCCBD55', 'ComputeProviderPopulateDataframeworkonEventServiceRole8B24C26D', 'ComputeProviderPopulateWarrantyDataframeworkonEventServiceRole1C781A10'], 'AWS::IAM::Policy': ['IAMAgentRoleDefaultPolicy9AF22938', 'IAMLambdaExecutionRoleDefaultPolicyEA1132FD', 'IAMCodeBuildServiceRoleDefaultPolicy854E083B', 'ComputeProviderPopulateDataframeworkonEventServiceRoleDefaultPolicy5D0030C0', 'ComputeProviderPopulateWarrantyDataframeworkonEventServiceRoleDefaultPolicy481216CD'], 'AWS::Lambda::Function': ['ComputeFunctiongetdealerdataBE5F9EE9', 'ComputeFunctiongetdealerappointmentslots72FA591F', 'ComputeFunctionBookAppointment2C93F04C', 'ComputeFunctionBookAppointmentStar09EA1E6D', 'ComputeFunctiongetpartsfordtcD222FB46', 'ComputeFunctionplacepartsorderB8A76F64', 'ComputeFunctiongetdealerstock92E44342', 'ComputeFunctionGetWarrantyData17583A9A', 'ComputeDataFunctionSampleDataFunction61BAB4CF', 'ComputeDataFunctionInsertCustomerProfilesE91E3C97', 'ComputeDataFunctiondtcpartsdataloader80613DBE', 'ComputeDataFunctionInsertWarrantyInfoC97420F8', 'ComputeProviderPopulateDataframeworkonEvent6EF30C7D', 'ComputeProviderPopulateWarrantyDataframeworkonEvent830959AB'], 'AWS::CloudFormation::CustomResource': ['ComputeCustomResourcePopulateData380DBDC7', 'ComputeCustomResourcePopulateWarrantyData57203226'], 'AWS::CodeBuild::Project': ['CodeBuildCDKSynthesisProjectB99C29D3', 'CodeBuildAgentCoreDeploymentProject2690D280', 'CodeBuildAgentProject00productsagent3B717AA4'], 'AWS::CloudFormation::Stack': ['NestedStack00vistaagentsNestedStackNestedStack00vistaagentsNestedStackResource33AF62D3'], 'AWS::CDK::Metadata': ['CDKMetadata']}

## Deployment Validation
✅ **Status**: PASSED

**Diff Output**: Loaded template: dealer-data
Loaded template: find-dealer-appointment-slots
Loaded template: book-appointment
Loaded template: parts
Loaded template: warranty
Loaded template: dealer-data
Loaded template: find-dealer-appointment-slots
Loaded template: book-appointment
Loaded template: parts
Loaded template: warranty
Starting agent discovery in /Users/agweber/code/old-amazon-bedrock-agents-healthcare-lifesciences/agents_catalog
Scanning category: standalone_agents
  Examining agent: 00-products-agent
    Found AgentCore agent: AgentCoreConfig(name='00-products-agent', path='/Users/agweber/code/old-amazon-bedrock-agents-healthcare-lifesciences/agents_catalog/standalone_agents/00-products-agent', category='standalone_agents')
Scanning category: multi_agent_collaboration
  Examining agent: 00-vista-agents
    Found CDK stack: CDKStackConfig(name='00-vista-agents', path='/Users/agweber/code/old-amazon-bedrock-agents-healthcare-lifesciences/agents_catalog/multi_agent_collaboration/00-vista-agents/cdk', stack_class='VistaServiceStack')
Discovery complete: 1 CDK stacks, 1 AgentCore agents
Registering CDK stack: 00-vista-agents
Using foundation model: ${Token[TOKEN.311]}
Using shared S3 bucket: ${Token[TOKEN.44]}
Using shared agent role: ${Token[TOKEN.110]}
Available shared tables: ['dealer-data', 'dealer-appointment-data', 'customer-user-profile', 'dtc-parts-lookup', 'dealer-parts-stock', 'dealer-parts-order', 'warranty-info']
Available shared Lambda functions: ['get-dealer-data', 'get-dealer-appointment-slots', 'BookAppointment', 'BookAppointmentStar', 'get-parts-for-dtc', 'place-parts-order', 'get-dealer-stock', 'GetWarrantyData', 'SampleDataFunction', 'InsertCustomerProfiles', 'dtc-parts-data-loader', 'InsertWarrantyInfo']
Loading Lambda templates from lambda-layer directory...
Loaded template: dealer-data
Loaded template: find-dealer-appointment-slots
Loaded template: book-appointment
Loaded template: parts
Loaded template: warranty
Template summary:
  dealer-data: {'AWS::DynamoDB::Table': 1, 'AWS::IAM::Role': 2, 'AWS::Lambda::Function': 2, 'AWS::Lambda::Permission': 1, 'Custom::PopulateData': 1}
  find-dealer-appointment-slots: {'AWS::DynamoDB::Table': 1, 'AWS::IAM::Role': 1, 'AWS::Lambda::Function': 1, 'AWS::Lambda::Permission': 1}
  book-appointment: {'AWS::DynamoDB::Table': 1, 'AWS::IAM::Role': 3, 'AWS::Lambda::Function': 3, 'Custom::PopulateCustomerData': 1}
  parts: {'AWS::DynamoDB::Table': 3, 'AWS::IAM::Role': 4, 'AWS::Lambda::Function': 4, 'Custom::DataLoader': 1}
  warranty: {'AWS::DynamoDB::Table': 1, 'AWS::IAM::Role': 2, 'AWS::Lambda::Function': 2, 'Custom::PopulateWarrantyData': 1}
Set table references:
  dealer_table: ${Token[TOKEN.56]}
  parts_table: ${Token[TOKEN.77]}
  warranty_table: ${Token[TOKEN.98]}
  appointment_table: ${Token[TOKEN.63]}
  customer_table: ${Token[TOKEN.70]}
Set Lambda function references:
  dealer_lambda: ${Token[TOKEN.157]}
  parts_lambda: ${Token[TOKEN.189]}
  warranty_lambda: ${Token[TOKEN.213]}
  appointment_lambda: ${Token[TOKEN.181]}
Registered collaborator: vehicle-symptom-analysis
Registered collaborator: dealer-lookup
Registered collaborator: appointment-booking
Registered collaborator: dealer-availability
Registered collaborator: parts-availability
Registered collaborator: warranty-recalls
Created supervisor agent with multi-agent collaboration
Configured supervisor agent with 6 collaborators
Successfully registered CDK nested stack: 00-vista-agents
Registering AgentCore agent: 00-products-agent
Successfully registered AgentCore agent: 00-products-agent


