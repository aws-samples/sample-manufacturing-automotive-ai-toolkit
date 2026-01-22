Scene Search Notes
- Agents are in sep. runtimes (using project cdk for agentcore deployment)
- # IAM ROLE for ECS instances - FULL ADMIN PERMISSIONS FOR TESTING
- ], apply_to_nested_stacks=True) on FleetDiscoveryCdkStack
- rename all resources
    - ECS Clusters: `fleet-cpu-cluster-<unique-id>`, `fleet-gpu-cluster`
    - Step Functions: `fleet-6phase-pipeline` (main orchestrator)
    - Lambda: `fleet-s3-trigger-us-west-2` (pipeline trigger)
    - S3 Buckets: `fleet-discovery-<unique-id>`, `fleet-vectors-<unique-id>`