# Engineering Fixes: 04-Vehicle_Data_Discovery

## Critical Issues 🔴

### 1. AdministratorAccess IAM Policy (Security)
- [x] **Location**: `fleet_discovery_cdk_stack.py:99, 312`
- **Issue**: ECS instance roles have full admin access
- **Fix**: Replaced with scoped policies for S3, Bedrock, Step Functions, ECR, CloudWatch, S3Vectors

### 2. Hardcoded AWS Account IDs and Resource Names (Portability)
- [x] **Location**: `dashboard_api.py:408-410`, `embedding_retrieval.py:15-16`
- **Issue**: Hardcoded account IDs and bucket names
- **Fix**: Changed to environment variables (FLEET_BUCKET, VECTOR_BUCKET, STATE_MACHINE_ARN, CORS_ALLOWED_ORIGINS)

### 3. Overly Permissive CORS (Security)
- [x] **Location**: `dashboard_api.py:403`
- **Issue**: `allow_origins=["*"]` enables CSRF attacks
- **Fix**: Now reads from CORS_ALLOWED_ORIGINS env var (defaults to "*" for dev)

### 4. No S3 Bucket Versioning (Data Protection)
- [x] **Location**: `fleet_discovery_cdk_stack.py` - S3 bucket definitions
- **Issue**: No versioning, risking data loss
- **Fix**: Added `versioned=True` to discovery and vector buckets

---

## High Priority Issues 🟠

### 5. RemovalPolicy.DESTROY on All Resources (Data Loss Risk)
- [x] **Location**: `fleet_discovery_cdk_stack.py:52, 251, 263, 276, 290, 964`
- **Issue**: All resources deleted on stack destroy
- **Fix**: Changed to `RemovalPolicy.RETAIN` for discovery and vector buckets

### 6. Monolithic Files (Maintainability)
- [ ] `dashboard_api.py`: 5,020 lines
- [ ] `microservice_orchestrator.py`: 4,429 lines
- **Fix**: Split into modules (deferred - large refactor)

### 7. No Unit Tests
- [ ] **Issue**: No test directory
- **Fix**: Add pytest tests (deferred - requires test design)

### 8. Broad Exception Handling
- [ ] **Location**: Multiple files with `except Exception`
- **Fix**: Catch specific exceptions (deferred - many locations)

---

## Medium Priority Issues 🟡

### 9. S3-Managed Encryption Instead of KMS
- [ ] **Location**: `fleet_discovery_cdk_stack.py:255, 267, 280`
- **Fix**: Use KMS CMK for sensitive data (deferred - requires KMS key setup)

### 10. Duplicate Helper Functions
- [x] **Status**: Consolidated into `shared/` directory (renamed from `lib/` due to gitignore)
- **Fix**: Files moved to `repo/shared/`, imports updated to `from shared.xxx`

### 11. Missing Input Validation
- [x] **Location**: `dashboard_api.py` API endpoints
- **Fix**: Added Pydantic validators for scene_id (regex pattern) and limit (1-100 range)

### 12. No Rate Limiting on API
- [x] **Location**: `dashboard_api.py`
- **Fix**: Added in-memory rate limiter middleware (configurable via RATE_LIMIT_PER_MINUTE env var)
