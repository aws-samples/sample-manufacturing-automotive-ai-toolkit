"""Cache service for DTO metrics."""
import json
import logging
import threading
from datetime import datetime
from botocore.exceptions import ClientError

logger = logging.getLogger(__name__)


class S3BackedMetricsCache:
    """
    Hybrid cache for DTO metrics: Fast local reads + S3 persistence.
    Solves Trust Bug between landing page (fast) and analytics page (accurate).
    """

    def __init__(self, s3_client=None, bucket=None):
        self.s3 = s3_client
        self.bucket = bucket
        self.s3_key = "config/latest_dto_metrics.json"
        self.local_cache = {
            "naive_cost_usd": 0,
            "intelligent_cost_usd": 0,
            "estimated_savings_usd": 0,
            "efficiency_gain_percent": 27.6,
            "last_updated": None,
            "analysis_method": "hardcoded_fallback",
            "source": "default"
        }
        self.lock = threading.Lock()

    def set_s3_client(self, s3_client, bucket):
        """Set S3 client after initialization."""
        self.s3 = s3_client
        self.bucket = bucket

    def load_from_s3_on_startup(self):
        """Load latest metrics from S3 on API startup (recovery path)"""
        try:
            if self.s3 is None:
                logger.warning("S3 client not initialized - using hardcoded DTO fallback")
                return

            logger.info("Loading latest DTO metrics from S3 on startup...")
            obj = self.s3.get_object(Bucket=self.bucket, Key=self.s3_key)
            s3_metrics = json.loads(obj['Body'].read())

            with self.lock:
                self.local_cache.update(s3_metrics)
                self.local_cache["source"] = "s3_recovery"

            logger.info(f"Loaded DTO metrics from S3: ${self.local_cache['estimated_savings_usd']} "
                       f"({self.local_cache['efficiency_gain_percent']:.1f}% efficiency)")

        except ClientError as e:
            if e.response['Error']['Code'] == 'NoSuchKey':
                logger.info("No cached DTO metrics found in S3 - using defaults")
            else:
                logger.warning(f"Failed to load DTO metrics from S3: {e}")
        except Exception as e:
            logger.error(f"Unexpected error loading DTO metrics from S3: {e}")

    def get_metrics(self):
        """Get current DTO metrics (sub-millisecond local read)"""
        with self.lock:
            return self.local_cache.copy()

    def update_metrics(self, naive_cost: int, intelligent_cost: int,
                      estimated_savings: int, efficiency_percent: float,
                      analysis_method: str = "vector_analysis"):
        """Update DTO metrics from analytics analysis (write-through pattern)"""

        new_metrics = {
            "naive_cost_usd": naive_cost,
            "intelligent_cost_usd": intelligent_cost,
            "estimated_savings_usd": estimated_savings,
            "efficiency_gain_percent": efficiency_percent,
            "last_updated": datetime.utcnow().isoformat(),
            "analysis_method": analysis_method,
            "source": "live_analysis"
        }

        with self.lock:
            self.local_cache.update(new_metrics)

        logger.info(f"Updated local DTO cache: ${estimated_savings} savings ({efficiency_percent:.1f}% efficiency)")
        self._write_to_s3_async(new_metrics)

    def _write_to_s3_async(self, metrics_data):
        """Write metrics to S3 in background thread (don't block API response)"""
        def s3_write_task():
            try:
                if self.s3 is None:
                    logger.warning("S3 client not available - DTO metrics not persisted")
                    return

                self.s3.put_object(
                    Bucket=self.bucket,
                    Key=self.s3_key,
                    Body=json.dumps(metrics_data, indent=2),
                    ContentType='application/json'
                )
                logger.info(f"Persisted DTO metrics to S3: {self.s3_key}")

            except Exception as e:
                logger.error(f"Failed to persist DTO metrics to S3: {e}")

        thread = threading.Thread(target=s3_write_task, daemon=True)
        thread.start()
