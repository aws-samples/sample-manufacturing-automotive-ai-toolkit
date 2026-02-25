SFC Control Plane Requirements
==============================

The CDK backend already provides infra to store sfc configs created by the sfc agent in s3 and ddb. 

# I want to extend the existing CDK stack and provide infra for a modern webapp & backend that can: 

## 1/ Browse, Visualize & Edit that configs in a nice json editor with a easy to use file-browser (to select a "sfc config in focus") 
    - a/ Config in Focus means that this SFC config is editable and that the UI offers to create a "Launch Package" 

## 2/ Create so called "Launch packages" from "sfc configs in focus" as bundled zip for download, containing:
    - a/ The sfc config in focus - it shall be modified to use the AWS IoT Cred Provider (AwsIotCredentialProviderClients) config, using/linking assets from c/
    - b/ A runner python app, using uv package mgmnt, that can immediately be executed on a host having python uv & java installed;
        That script also shall be able to bootstrap a SFC env, download the required sfc binaries from github based on the config in focus, and optionally install java;
        The runner shall execute SFC with the config in focus in a separate thread
        The runner shall feed back otel logs to cloudwatch, so that sfc logs are stored for a dedicated Launch package; 
        The runner shall also use the Iot cert from c/ to authenticate against cloudwatch using the aws iot cred provider capability;
    - c/ An AWS IoT X.509 cert with the respective aws iot thing created in AWS IoT service; The Amazon RootCA cert; 
        The AWS IoT cert's role alias and the respective IAM permissions (for the IAM role to be created) shall be derived from the SFC Config in focus and created dynamically by a Backend Lambda 
    - d/ A lean documentation, how to use that launch package.
    - e/ A Dockerfile with a docker build shell script - linking all artifacts (runner app, sfc config, iot certs,..), to create a docker image locally if required. 

## 3/ Manage "Launch packages" in UI
    - a/ Key part are the otel cloudwatch logs of the respective Launch package - make sure to vizualize tht logs properly. SFC process info is key.
    - b/ In case of SFC log errors, the UI shall offer an automation to feed back the error log section (root cause) to the agentcore sfc agent and create a new version of the Launch package (fixed) sfc config
    - c/ Once Launch packages are working (no errors in logs), offer an automation to create a AWS IoT Greengrass Component. The GG component shall use the zip file as main artifact.


## 4/ Design Tenets
    - a/ Use Serverless services like API GW & AWS Lambda
    - b/ Use DDB for UI state, SFC Config management & Launch package mgmnt.
    - c/ UI shall be lean and functional, no cheap icons, professional look
    - d/ UI's main purpose is to bring a "SFC config in focus" to life, that means SFC runs with that config on an edge or cloud based host, and collects data from industrial equipment, and sends data to AWS Services


## 5/ Tech
    - a/ UI shall use vitejs
    - b/ Backend HTTP API (based on openapi spec) shall be built using Amazon API gateway with AWS Lambdas (python based) behind (all synchronous)
    - c/ HTTP API shall be usable from localhost webapp
    - d/ API resources shall reflect all aspects from points 1/ to 3/


