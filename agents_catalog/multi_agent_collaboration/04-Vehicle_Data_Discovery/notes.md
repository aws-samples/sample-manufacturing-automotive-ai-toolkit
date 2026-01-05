Scene Search Notes
- Agents are in sep. runtimes (using project cdk for agentcore deployment)
- # IAM ROLE for ECS instances - FULL ADMIN PERMISSIONS FOR TESTING
- ], apply_to_nested_stacks=True) on TeslaFleetDiscoveryCdkStack
- rename all tesla resources
    - ECS Clusters: `tesla-fleet-cpu-cluster-<unique-id>`, `tesla-fleet-gpu-cluster`
    - Step Functions: `tesla-fleet-6phase-pipeline` (main orchestrator)
    - Lambda: `tesla-s3-trigger-us-west-2` (pipeline trigger)
    - S3 Buckets: `tesla-fleet-discovery-<unique-id>`, `tesla-fleet-vectors-<unique-id>`