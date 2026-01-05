Tesla Fleet Discovery Platform - Demo Script

Platform Access

URL: https://tesla-discovery-studio.d9hvqx68eghv0.amplifyapp.com/
API: https://6kicn2wbzm.us-west-2.awsapprunner.com/
Authentication: None required

Current Dataset Status
- 716 total scenes processed
- 3 Critical, 134 Deviation, 578 Normal classifications
- Data from Tesla 6-camera configurations

Demo Walkthrough

1. Dashboard Overview
- Navigate to main dashboard
- Review traffic light statistics: Critical/Deviation/Normal counts
- Note DTO savings counter showing cost avoidance metrics

2. Filter System Testing
- Test Critical filter: Should show 3 scenes (recently fixed consistency bug)
- Test Deviation filter: Should show 134 scenes with proper pagination
- Test other filters: Weather, Construction, Night Ops, HIL Priority levels

3. Scene Analysis Architecture
- Click any scene to view detailed analysis
- Review multi-agent output:
  - Scene Understanding Agent results
  - Anomaly Detection Agent classification
  - Business Intelligence recommendations
- Check confidence scores and risk assessments

4. Multi-Camera Video System
- Play scene videos in the forensic view
- Switch between 6 camera angles: CAM_FRONT, CAM_FRONT_LEFT, CAM_FRONT_RIGHT, CAM_BACK, CAM_BACK_LEFT, CAM_BACK_RIGHT
- Note temporal synchronization across camera feeds

5. Search Capabilities
- Test behavioral search: "heavy rain driving"
- Test visual pattern search: specific driving scenarios
- Review Twin Engine results (behavioral + visual consensus)
- Check search result accuracy and relevance

6. Pagination and Data Consistency
- Navigate through multiple pages of results
- Verify filter counts match between stats and actual filtered results
- Test various page sizes and navigation

Technical Architecture Review

Processing Pipeline
- Phase 1-2: ROS bag extraction and video reconstruction (AWS ECS)
- Phase 3: AI behavioral analysis (InternVideo2.5 + Cosmos-Embed1)
- Phase 4-5: Vector embedding storage (AWS S3 Vectors, dual-index)
- Phase 6: Multi-agent analysis (AWS Bedrock AgentCore)

Infrastructure Components
- AWS ECS clusters: ARM64 Graviton (CPU) + NVIDIA A10G (GPU)
- AWS S3 Vectors: behavioral-vectors-index (1536-dim) + video-similarity-index (768-dim)
- AWS Step Functions: tesla-fleet-6phase-pipeline orchestration
- AWS App Runner: tesla-fleet-api auto-scaling backend
- AWS Bedrock AgentCore: 3 deployed agents for analysis

AI Models Integration
- InternVideo2.5: Behavioral pattern analysis
- NVIDIA Cosmos-Embed1: Visual temporal pattern recognition
- Cohere embed-v4: Semantic concept embedding
- Multi-agent consensus for classification decisions

Key Technical Validations

Data Processing Consistency
- Verify traffic light stats process complete dataset (716 scenes)
- Confirm all filters use same dataset scope (fixed batch processing bug)
- Check pagination accuracy with real filtered counts

Search Performance
- Sub-second similarity queries across high-dimensional embeddings
- Cross-modal search: text queries returning relevant video scenes
- Mathematical consensus between behavioral and visual engines

Agent Analysis Quality
- Quantified risk scoring (0.0-1.0 scale)
- HIL testing priority recommendations
- Environmental condition detection accuracy
- Anomaly classification consistency

Performance Metrics
- Pipeline processing: 45 minutes end-to-end per scene
- Search latency: <200ms for similarity queries
- Embedding accuracy: 95%+ semantic matching
- Concurrent processing: 10 threads for S3 operations

Recent Technical Fixes
- Fixed traffic light filter consistency (all filters now process complete dataset)
- Eliminated batch processing limitations (250-scene artificial caps removed)
- Implemented real pagination counts (removed estimation logic)
- Unified response architecture for maintainability

Testing Scenarios

Critical Path Testing
- Search for "construction zone" - verify relevant scenes returned
- Filter by Critical anomaly status - confirm 3 scenes displayed
- Navigate to scene detail - verify all 6 camera feeds load
- Test pagination on Deviation filter - should handle 134 scenes across multiple pages

Edge Case Validation
- Test empty search results handling
- Verify scene detail error handling for missing data
- Check filter combinations and reset functionality
- Validate multi-camera synchronization accuracy

Known Limitations
- Processing limited to 716 scenes currently (expanding)
- GPU processing sequential to avoid resource conflicts
- Cache timeout set to 5 minutes for real-time updates
- Some legacy datetime deprecation warnings (non-functional impact)

Questions to Investigate During Demo
- Processing scalability with larger datasets
- Integration points with existing ML pipelines
- Deployment requirements for production environments
- Data quality and validation processes