#!/usr/bin/env python3
import time
import logging
from typing import Dict, List, Optional, Any
from datetime import datetime, timedelta
from dataclasses import dataclass, asdict
from enum import Enum

# Configure logging (following dashboard_api.py pattern)
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

class JobStatus(Enum):
    """Job status enumeration"""
    RUNNING = "running"
    COMPLETED = "completed"
    FAILED = "failed"

@dataclass
class DiscoveryJob:
    """Data structure for discovery job tracking"""
    job_id: str
    status: JobStatus
    started_at: datetime
    completed_at: Optional[datetime] = None
    progress: int = 0  # 0-100
    total_scenes: Optional[int] = None
    clusters_discovered: Optional[int] = None
    discovered_categories: Optional[List[Dict]] = None
    error_message: Optional[str] = None
    current_step: Optional[str] = None

class DiscoveryStatusManager:
    """
    Manager for tracking async discovery job status
    In-memory implementation suitable for single-instance API
    Following patterns from dashboard_api.py for error handling and logging
    """

    def __init__(self):
        """Initialize status manager with empty job tracking"""
        self.jobs: Dict[str, DiscoveryJob] = {}
        self.job_cleanup_hours = 24  # Clean up completed jobs after 24 hours

    def start_discovery_job(self) -> str:
        """
        Start a new discovery job and return job ID
        Creates unique job ID and initializes tracking
        """
        try:
            # Generate unique job ID using timestamp
            job_id = f"discovery_{int(time.time() * 1000)}"

            # Create new job record
            job = DiscoveryJob(
                job_id=job_id,
                status=JobStatus.RUNNING,
                started_at=datetime.utcnow(),
                progress=0,
                current_step="Initializing discovery process"
            )

            # Store job
            self.jobs[job_id] = job

            logger.info(f"Started discovery job: {job_id}")

            # Clean up old jobs periodically
            self._cleanup_old_jobs()

            return job_id

        except Exception as e:
            logger.error(f"Failed to start discovery job: {str(e)}")
            raise

    def update_job_progress(self, job_id: str, progress: int,
                          current_step: Optional[str] = None,
                          total_scenes: Optional[int] = None) -> bool:
        """
        Update job progress and current step
        Returns True if job exists and was updated, False otherwise
        """
        try:
            if job_id not in self.jobs:
                logger.error(f"Job {job_id} not found for progress update")
                return False

            job = self.jobs[job_id]

            # Only update if job is still running
            if job.status != JobStatus.RUNNING:
                logger.warning(f"Cannot update progress for job {job_id} - status is {job.status}")
                return False

            # Update progress (clamp to 0-100)
            job.progress = max(0, min(100, progress))

            if current_step:
                job.current_step = current_step

            if total_scenes:
                job.total_scenes = total_scenes

            logger.debug(f"Updated job {job_id}: {job.progress}% - {job.current_step}")
            return True

        except Exception as e:
            logger.error(f"Failed to update job progress: {str(e)}")
            return False

    def complete_discovery_job(self, job_id: str, discovered_categories: List[Dict]) -> bool:
        """
        Mark discovery job as completed with results
        Returns True if job exists and was completed, False otherwise
        """
        try:
            if job_id not in self.jobs:
                logger.error(f"Job {job_id} not found for completion")
                return False

            job = self.jobs[job_id]

            # Update job to completed status
            job.status = JobStatus.COMPLETED
            job.completed_at = datetime.utcnow()
            job.progress = 100
            job.current_step = "Discovery completed successfully"
            job.discovered_categories = discovered_categories

            # FIXED: Extract actual category count from nested structure
            if isinstance(discovered_categories, dict):
                # Handle new discovery_results format
                if "analysis_summary" in discovered_categories:
                    job.clusters_discovered = discovered_categories["analysis_summary"].get("total_categories", 0)
                elif "uniqueness_results" in discovered_categories:
                    job.clusters_discovered = len(discovered_categories["uniqueness_results"])
                else:
                    job.clusters_discovered = len(discovered_categories)  # Fallback
            else:
                # Handle legacy list format
                job.clusters_discovered = len(discovered_categories)

            duration = (job.completed_at - job.started_at).total_seconds()
            logger.info(f"Completed discovery job {job_id}: {job.clusters_discovered} categories found in {duration:.1f}s")

            return True

        except Exception as e:
            logger.error(f"Failed to complete discovery job: {str(e)}")
            return False

    def fail_discovery_job(self, job_id: str, error_message: str) -> bool:
        """
        Mark discovery job as failed with error message
        Returns True if job exists and was marked as failed, False otherwise
        """
        try:
            if job_id not in self.jobs:
                logger.error(f"Job {job_id} not found for failure")
                return False

            job = self.jobs[job_id]

            # Update job to failed status
            job.status = JobStatus.FAILED
            job.completed_at = datetime.utcnow()
            job.current_step = "Discovery failed"
            job.error_message = error_message

            logger.error(f"Failed discovery job {job_id}: {error_message}")

            return True

        except Exception as e:
            logger.error(f"Failed to mark job as failed: {str(e)}")
            return False

    def get_job_status(self, job_id: str) -> Optional[Dict]:
        """
        Get current status of a discovery job
        Returns job status dict or None if job not found
        """
        try:
            if job_id not in self.jobs:
                return None

            job = self.jobs[job_id]

            # Calculate duration
            if job.completed_at:
                duration_seconds = (job.completed_at - job.started_at).total_seconds()
            else:
                duration_seconds = (datetime.utcnow() - job.started_at).total_seconds()

            # Convert to serializable dict
            status_dict = {
                "job_id": job.job_id,
                "status": job.status.value,
                "started_at": job.started_at.isoformat(),
                "completed_at": job.completed_at.isoformat() if job.completed_at else None,
                "duration_seconds": round(duration_seconds, 1),
                "progress": job.progress,
                "current_step": job.current_step,
                "total_scenes": job.total_scenes,
                "clusters_discovered": job.clusters_discovered,
                "discovered_categories": job.discovered_categories,
                "error_message": job.error_message
            }

            return status_dict

        except Exception as e:
            logger.error(f"Failed to get job status: {str(e)}")
            return None

    def list_jobs(self, limit: int = 10) -> List[Dict]:
        """
        List recent discovery jobs
        Returns list of job status dicts, newest first
        """
        try:
            # Sort jobs by start time, newest first
            sorted_jobs = sorted(
                self.jobs.values(),
                key=lambda j: j.started_at,
                reverse=True
            )

            # Get status for each job (limited)
            job_list = []
            for job in sorted_jobs[:limit]:
                status_dict = self.get_job_status(job.job_id)
                if status_dict:
                    job_list.append(status_dict)

            return job_list

        except Exception as e:
            logger.error(f"Failed to list jobs: {str(e)}")
            return []

    def _cleanup_old_jobs(self) -> None:
        """
        Clean up completed/failed jobs older than cleanup threshold
        Keeps memory usage bounded for long-running API instances
        """
        try:
            cutoff_time = datetime.utcnow() - timedelta(hours=self.job_cleanup_hours)
            jobs_to_remove = []

            for job_id, job in self.jobs.items():
                # Remove jobs that are completed/failed and old enough
                if job.status in [JobStatus.COMPLETED, JobStatus.FAILED]:
                    check_time = job.completed_at or job.started_at
                    if check_time < cutoff_time:
                        jobs_to_remove.append(job_id)

            # Remove old jobs
            for job_id in jobs_to_remove:
                del self.jobs[job_id]
                logger.debug(f"Cleaned up old job: {job_id}")

            if jobs_to_remove:
                logger.info(f"Cleaned up {len(jobs_to_remove)} old discovery jobs")

        except Exception as e:
            logger.error(f"Failed to clean up old jobs: {str(e)}")

    def get_manager_stats(self) -> Dict:
        """
        Get manager statistics for health monitoring
        """
        try:
            total_jobs = len(self.jobs)
            running_jobs = sum(1 for job in self.jobs.values() if job.status == JobStatus.RUNNING)
            completed_jobs = sum(1 for job in self.jobs.values() if job.status == JobStatus.COMPLETED)
            failed_jobs = sum(1 for job in self.jobs.values() if job.status == JobStatus.FAILED)

            return {
                "total_jobs": total_jobs,
                "running_jobs": running_jobs,
                "completed_jobs": completed_jobs,
                "failed_jobs": failed_jobs,
                "cleanup_threshold_hours": self.job_cleanup_hours,
                "manager_uptime": datetime.utcnow().isoformat()
            }

        except Exception as e:
            logger.error(f"Failed to get manager stats: {str(e)}")
            return {"error": str(e)}

# Global instance for use across API endpoints
# Following dashboard_api.py pattern of global client variables
discovery_status_manager = DiscoveryStatusManager()