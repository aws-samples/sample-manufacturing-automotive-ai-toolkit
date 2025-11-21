# Quality Inspection CDK Infrastructure

This CDK stack creates all AWS resources needed for the Manufacturing Quality Inspection Multi-Agent System.

## Resources Created

- **6 DynamoDB Tables**: For storing agent data and workflow history
- **S3 Bucket**: `machinepartimages` with folder structure for image processing
- **SNS Topic**: `quality-inspection-alerts` for quality notifications

## Deployment

1. Install CDK dependencies:
```bash
cd cdk
pip install -r requirements.txt
```

2. Deploy with email address for notifications:
```bash
cdk deploy --context email=your-email@company.com
```

3. Confirm SNS subscription in your email

## Folder Structure Created in S3

- `inputimages/` - Images to be processed
- `cleanimages/` - Reference clean images  
- `defects/` - Defective images and reports
- `processedimages/` - Successfully processed clean images
- `scrap/` - Scrapped parts
- `rework/` - Parts requiring rework

## DynamoDB Tables

- `vision-inspection-data` - Vision analysis results
- `sop-decisions` - SOP compliance decisions
- `action-execution-log` - Physical action logs
- `erp-integration-log` - ERP system updates
- `historical-trends` - Quality trend data
- `sap-integration-log` - SAP integration logs