"""Shared dependencies for Fleet Discovery API."""
import os
import re
import logging
import threading
import time
import boto3
from botocore.config import Config
from botocore.exceptions import UnknownServiceError

logger = logging.getLogger(__name__)

# Configuration from environment
BUCKET = os.getenv("S3_BUCKET", "")
VECTOR_BUCKET = os.getenv("VECTOR_BUCKET_NAME", "")
STATE_MACHINE_ARN = os.getenv("STATE_MACHINE_ARN", "")
AWS_REGION = os.environ.get('AWS_REGION', os.environ.get('AWS_DEFAULT_REGION', 'us-west-2'))

# Scene ID validation
SCENE_ID_PATTERN = re.compile(r'^scene[-_]\d{1,6}(_CAM_[A-Z_]+)?$')

# Twin Engine Configuration
INDICES_CONFIG = {
    "visual": {
        "name": "video-similarity-index",
        "dimensions": 768,
        "embedding_model": "endpoint-cosmos-embed1-text",
        "type": "visual",
        "source": "sagemaker",
        "description": "Visual pattern matching"
    },
    "behavioral": {
        "name": "behavioral-metadata-index",
        "dimensions": 1536,
        "embedding_model": "us.cohere.embed-v4:0",
        "type": "behavioral",
        "source": "bedrock",
        "description": "Concept & behavior matching"
    }
}

DEFAULT_ANALYTICS_ENGINE = "behavioral"

# Fleet overview cache (bounded to prevent memory growth)
CACHE_MAX_ENTRIES = 50
fleet_overview_cache = {}


class RateLimiter:
    def __init__(self, requests_per_minute: int = 60):
        self.requests_per_minute = requests_per_minute
        self.requests = {}
        self.lock = threading.Lock()

    def is_allowed(self, client_ip: str) -> bool:
        now = time.time()
        with self.lock:
            self.requests = {k: v for k, v in self.requests.items() if now - v[-1] < 60}
            if client_ip in self.requests:
                recent = [t for t in self.requests[client_ip] if now - t < 60]
                if len(recent) >= self.requests_per_minute:
                    return False
                self.requests[client_ip] = recent + [now]
            else:
                self.requests[client_ip] = [now]
            return True


rate_limiter = RateLimiter(requests_per_minute=int(os.getenv("RATE_LIMIT_PER_MINUTE", "60")))


# Initialize AWS clients at module load time
def _init_aws_clients():
    """Initialize AWS clients at module load."""
    clients = {
        's3': None,
        's3vectors': None,
        'sfn': None,
        'bedrock': None,
        's3vectors_available': False,
        'initialization_error': None
    }
    
    try:
        logger.info(f"Initializing AWS clients for region: {AWS_REGION}")

        config = Config(signature_version='s3v4', max_pool_connections=50)
        clients['s3'] = boto3.client('s3', region_name=AWS_REGION, config=config,
                                      endpoint_url=f'https://s3.{AWS_REGION}.amazonaws.com')
        logger.info("S3 client initialized")

        clients['sfn'] = boto3.client('stepfunctions', region_name=AWS_REGION)
        logger.info("Step Functions client initialized")

        clients['bedrock'] = boto3.client('bedrock-runtime', region_name=AWS_REGION)
        logger.info("Bedrock client initialized")

        try:
            clients['s3vectors'] = boto3.client('s3vectors', region_name=AWS_REGION)
            clients['s3vectors_available'] = True
            logger.info("S3 Vectors client initialized")
        except (UnknownServiceError, Exception) as e:
            logger.warning(f"S3 Vectors not available: {e}")

    except Exception as e:
        logger.error(f"Failed to initialize AWS clients: {e}")
        clients['initialization_error'] = str(e)
    
    return clients


# Initialize clients at import time
_clients = _init_aws_clients()

# Export clients as module-level variables
s3 = _clients['s3']
s3vectors = _clients['s3vectors']
sfn = _clients['sfn']
bedrock = _clients['bedrock']
s3vectors_available = _clients['s3vectors_available']
initialization_error = _clients['initialization_error']


def init_aws_clients():
    """Re-initialize AWS clients if needed. Called during app lifespan startup."""
    global s3, s3vectors, sfn, bedrock, s3vectors_available, initialization_error, _clients
    
    # Only re-initialize if there was an error or clients are None
    if initialization_error or s3 is None:
        _clients = _init_aws_clients()
        s3 = _clients['s3']
        s3vectors = _clients['s3vectors']
        sfn = _clients['sfn']
        bedrock = _clients['bedrock']
        s3vectors_available = _clients['s3vectors_available']
        initialization_error = _clients['initialization_error']
    else:
        # Verify S3 connection
        try:
            s3.list_buckets()
            logger.info("AWS clients verified")
        except Exception as e:
            logger.warning(f"S3 verification failed, re-initializing: {e}")
            _clients = _init_aws_clients()
            s3 = _clients['s3']
            s3vectors = _clients['s3vectors']
            sfn = _clients['sfn']
            bedrock = _clients['bedrock']
            s3vectors_available = _clients['s3vectors_available']
            initialization_error = _clients['initialization_error']


def get_s3():
    return s3

def get_sfn():
    return sfn

def get_bedrock():
    return bedrock

def get_s3vectors():
    return s3vectors
