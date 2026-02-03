# Fleet Discovery Pricing Estimates

## Fixed Monthly Costs

The Fleet Discovery platform has a baseline infrastructure cost of approximately $80 per month. This includes App Runner for the web UI ($30-50), a NAT Gateway ($32 plus data transfer), VPC Flow Logs ($5-10), and CloudWatch Logs ($5-10). S3 storage costs vary based on data volume.

## Compute Costs

Compute costs depend on instance usage. ARM64 instances (c7g.16xlarge) cost $2.32 per hour, or approximately $1,670 per month if running continuously. GPU instances vary: g5.2xlarge costs $1.21 per hour ($870/month), g5.4xlarge costs $2.42 per hour ($1,740/month), and g4dn.4xlarge costs $1.20 per hour ($864/month).

With scale-to-zero configuration, instances only run when processing jobs, significantly reducing costs.

## Per Job Costs

Processing a 500MB ROS bag file costs approximately $0.40-0.70 and takes 15-20 minutes across six phases. Phase 1 (ROS Extraction) runs on ARM64 for 1-2 minutes ($0.04-0.08). Phase 2 (Video Reconstruction) uses ARM64 for 2-5 minutes ($0.08-0.19). Phase 3 (InternVideo2.5 Analysis) requires GPU compute for 5-10 minutes ($0.10-0.20). Phases 4-5 (Embeddings) run on ARM64 for 2-3 minutes ($0.08-0.12). Phase 6 (Clustering) completes on ARM64 in about 1 minute ($0.04).

S3 request costs and Step Functions execution fees are negligible at approximately $0.01 per job.

## Scalability

The platform scales cost-effectively with volume. Processing 100 bags per day costs approximately $130 per month ($50 compute plus $80 fixed). At 500 bags per day, costs reach approximately $330 per month. Processing 1,000 bags per day costs approximately $580 per month, and 10,000 bags per day costs approximately $5,080 per month.

## Notes

These estimates assume scale-to-zero configuration where ASG minimum capacity is set to zero. The first job after an idle period incurs a 2-5 minute cold start while instances spin up. GPU instance availability varies by region; the platform uses mixed instance types (g5.2xlarge, g5.4xlarge, g4dn.4xlarge) to improve reliability and availability.
