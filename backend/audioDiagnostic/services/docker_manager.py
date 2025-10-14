"""
Docker and Celery Management Service
Automatically sets up and tears down Docker containers and Celery workers
"""
import os
import subprocess
import time
import logging
import threading
from django.conf import settings

logger = logging.getLogger(__name__)

class DockerCeleryManager:
    def __init__(self):
        self.backend_dir = os.path.join(settings.BASE_DIR)
        self.is_setup = False
        self.active_tasks = set()
        self.shutdown_timer = None
        
        # Check if containers are already running on startup
        self._check_existing_containers()
        
    def setup_infrastructure(self):
        """Set up Docker containers and Celery workers"""
        if self.is_setup:
            logger.info("Infrastructure already running")
            return True
            
        # Check if containers are already running
        if self._check_existing_containers():
            logger.info("Found existing containers, infrastructure is ready")
            self.is_setup = True
            return True
            
        # First check if Redis is accessible without Docker (external Redis)
        if self._wait_for_redis(max_attempts=3):
            logger.info("External Redis found, skipping Docker setup")
            self.is_setup = True
            return True
            
        try:
            logger.info("Starting Docker containers and Celery workers...")
            
            # Reset any stuck tasks before starting
            self._reset_stuck_tasks()
            
            # Change to backend directory
            original_dir = os.getcwd()
            os.chdir(self.backend_dir)
            
            # Start Docker Compose services
            result = subprocess.run([
                'docker', 'compose', 'up', '-d', '--build'
            ], capture_output=True, text=True)
            
            if result.returncode != 0:
                logger.error(f"Failed to start Docker services: {result.stderr}")
                # If port already allocated, check if Redis is still accessible
                if "port is already allocated" in result.stderr.lower():
                    logger.info("Port conflict detected, checking if Redis is accessible...")
                    if self._wait_for_redis(max_attempts=5):
                        logger.info("Redis is accessible despite Docker conflict, proceeding...")
                        self.is_setup = True
                        return True
                return False
            
            # Wait for services to be ready
            logger.info("Waiting for services to be ready...")
            time.sleep(10)
            
            # Check if Redis is accessible
            redis_ready = self._wait_for_redis()
            if not redis_ready:
                logger.error("Redis not accessible after setup")
                return False
            
            self.is_setup = True
            logger.info("Docker and Celery infrastructure ready")
            return True
            
        except Exception as e:
            logger.error(f"Failed to set up infrastructure: {str(e)}")
            # Try to continue if Redis is still accessible
            if self._wait_for_redis(max_attempts=3):
                logger.info("Redis accessible despite setup error, continuing...")
                self.is_setup = True
                return True
            return False
        finally:
            os.chdir(original_dir)
    
    def _wait_for_redis(self, max_attempts=30):
        """Wait for Redis to be ready"""
        from ..utils import get_redis_connection
        
        for attempt in range(max_attempts):
            try:
                r = get_redis_connection()
                return True
            except Exception:
                time.sleep(1)
        return False
    
    def _check_docker(self):
        """Check if Docker is available and running"""
        try:
            # Check if Docker command is available
            result = subprocess.run(['docker', '--version'], 
                                  capture_output=True, text=True, timeout=10)
            if result.returncode != 0:
                logger.error("Docker command not found")
                return False
            
            # Check if Docker daemon is running
            result = subprocess.run(['docker', 'info'], 
                                  capture_output=True, text=True, timeout=10)
            if result.returncode != 0:
                logger.error("Docker daemon not running")
                return False
            
            logger.info("Docker is available and running")
            return True
            
        except subprocess.TimeoutExpired:
            logger.error("Docker command timed out")
            return False
        except Exception as e:
            logger.error(f"Error checking Docker: {e}")
            return False
    
    def register_task(self, task_id):
        """Register a new active task"""
        self.active_tasks.add(task_id)
        
        # Cancel shutdown timer if it exists
        if self.shutdown_timer:
            self.shutdown_timer.cancel()
            self.shutdown_timer = None
        
        logger.info(f"Task {task_id} registered. Active tasks: {len(self.active_tasks)}")
    
    def unregister_task(self, task_id):
        """Unregister a completed task"""
        if task_id in self.active_tasks:
            self.active_tasks.remove(task_id)
        
        logger.info(f"Task {task_id} unregistered. Active tasks: {len(self.active_tasks)}")
        
        # If no more active tasks, start shutdown timer
        if not self.active_tasks and self.is_setup:
            self._start_shutdown_timer()
    
    def _start_shutdown_timer(self):
        """Start a timer to shutdown infrastructure after delay"""
        if self.shutdown_timer:
            self.shutdown_timer.cancel()
        
        logger.info("Starting shutdown timer (60 seconds)...")
        self.shutdown_timer = threading.Timer(60.0, self._shutdown_if_idle)
        self.shutdown_timer.start()
    
    def _shutdown_if_idle(self):
        """Shutdown infrastructure if no tasks are active"""
        if not self.active_tasks:
            logger.info("No active tasks, shutting down infrastructure...")
            self.shutdown_infrastructure()
        else:
            logger.info(f"Tasks still active ({len(self.active_tasks)}), keeping infrastructure running")
    
    def shutdown_infrastructure(self):
        """Shutdown Docker containers and Celery workers"""
        if not self.is_setup:
            return True
            
        try:
            logger.info("Shutting down Docker containers...")
            
            # Cancel shutdown timer
            if self.shutdown_timer:
                self.shutdown_timer.cancel()
                self.shutdown_timer = None
            
            # Change to backend directory
            original_dir = os.getcwd()
            os.chdir(self.backend_dir)
            
            # Shutdown Docker Compose services
            result = subprocess.run([
                'docker', 'compose', 'down'
            ], capture_output=True, text=True)
            
            if result.returncode != 0:
                logger.error(f"Failed to shutdown Docker services: {result.stderr}")
                return False
            
            self.is_setup = False
            self.active_tasks.clear()
            logger.info("Infrastructure shutdown completed")
            return True
            
        except Exception as e:
            logger.error(f"Failed to shutdown infrastructure: {str(e)}")
            return False
        finally:
            os.chdir(original_dir)
    
    def get_status(self):
        """Get current infrastructure status"""
        return {
            'docker_running': self.is_setup,
            'active_tasks': len(self.active_tasks),
            'task_list': list(self.active_tasks)
        }
    
    def force_shutdown(self):
        """Force immediate shutdown regardless of active tasks"""
        logger.info("Forcing infrastructure shutdown...")
        self.active_tasks.clear()
        return self.shutdown_infrastructure()
    
    def _reset_stuck_tasks(self):
        """Reset stuck audio processing tasks to prevent orphaned states"""
        try:
            from audioDiagnostic.models import AudioFile, AudioProject
            from celery.result import AsyncResult
            
            # Reset stuck audio files
            for af in AudioFile.objects.filter(status__in=['transcribing', 'processing']):
                if af.task_id:
                    result = AsyncResult(af.task_id)
                    if result.state == 'PENDING':  # Task never started or stuck
                        logger.info(f"Resetting stuck AudioFile {af.id} from {af.status} to pending")
                        af.status = 'pending'
                        af.task_id = None
                        af.save()
            
            # Reset stuck projects
            for project in AudioProject.objects.filter(status='processing'):
                logger.info(f"Resetting stuck Project {project.id} from processing to pending")
                project.status = 'pending' 
                project.save()
                
        except Exception as e:
            logger.error(f"Error resetting stuck tasks: {e}")

    def _check_existing_containers(self):
        """Check if Docker containers are already running"""
        try:
            result = subprocess.run([
                'docker', 'ps', '--filter', 'name=backend-', '--format', '{{.Names}}'
            ], capture_output=True, text=True)
            
            if result.returncode == 0:
                running_containers = result.stdout.strip().split('\n')
                # Check if key containers are running
                has_redis = any('redis' in container for container in running_containers if container)
                has_worker = any('celery_worker' in container for container in running_containers if container)
                
                if has_redis and has_worker:
                    logger.info("Detected existing Docker containers running")
                    self.is_setup = True
                    return True
                    
        except Exception as e:
            logger.debug(f"Could not check existing containers: {e}")
        
        return False

# Global instance
docker_celery_manager = DockerCeleryManager()