"""
Infrastructure Views for audioDiagnostic app.
"""
from ._base import *

class InfrastructureStatusView(APIView):
    """
    GET: Get Docker and Celery infrastructure status
    POST: Force shutdown infrastructure
    """
    authentication_classes = [SessionAuthentication, ExpiringTokenAuthentication]
    permission_classes = [IsAuthenticated]
    
    def get(self, request):
        from audioDiagnostic.services.docker_manager import docker_celery_manager
        from audioDiagnostic.utils import get_redis_connection
        from celery import current_app
        
        # Check Docker/Redis status
        status = docker_celery_manager.get_status()
        
        # Check Redis connectivity
        redis_running = False
        try:
            r = get_redis_connection()
            r.ping()
            redis_running = True
        except Exception:
            pass
        
        # Check Celery connectivity
        celery_running = False
        try:
            inspect = current_app.control.inspect()
            stats = inspect.stats()
            celery_running = stats is not None and len(stats) > 0
        except Exception:
            pass
        
        return Response({
            'infrastructure_running': status['docker_running'],
            'redis_running': redis_running,
            'celery_running': celery_running,
            'active_tasks': status['active_tasks'],
            'task_ids': status['task_list']
        })
    
    def post(self, request):
        from audioDiagnostic.services.docker_manager import docker_celery_manager
        action = request.data.get('action', '')
        
        if action == 'force_shutdown':
            docker_celery_manager.force_shutdown()
            return Response({'message': 'Infrastructure forcefully shut down'})
        elif action == 'start':
            if docker_celery_manager.setup_infrastructure():
                return Response({'message': 'Infrastructure started successfully'})
            else:
                return Response({'error': 'Failed to start infrastructure'}, 
                              status=status.HTTP_500_INTERNAL_SERVER_ERROR)
        else:
            return Response({'error': 'Invalid action'}, 
                          status=status.HTTP_400_BAD_REQUEST)



class TaskStatusView(APIView):
    """
    GET: Check status of background tasks to prevent frontend timeouts
    """
    authentication_classes = [SessionAuthentication, ExpiringTokenAuthentication]
    permission_classes = [IsAuthenticated]

    def get(self, request, task_id):
        try:
            from audioDiagnostic.utils import get_redis_connection
            
            # Get task result from Celery
            task_result = AsyncResult(task_id)
            
            # Get progress from Redis
            r = get_redis_connection()
            progress = r.get(f"progress:{task_id}")
            
            if progress is not None:
                progress = int(progress)
            else:
                progress = 0
            
            # Determine task status
            if task_result.state == 'PENDING':
                status_info = {
                    'status': 'pending',
                    'progress': progress,
                    'message': 'Task is waiting to be processed'
                }
            elif task_result.state == 'PROGRESS':
                status_info = {
                    'status': 'in_progress', 
                    'progress': progress,
                    'message': 'Task is currently running'
                }
            elif task_result.state == 'SUCCESS':
                status_info = {
                    'status': 'completed',
                    'progress': 100,
                    'result': task_result.result,
                    'message': 'Task completed successfully'
                }
            elif task_result.state == 'FAILURE':
                status_info = {
                    'status': 'failed',
                    'progress': -1,
                    'error': str(task_result.info),
                    'message': 'Task failed with an error'
                }
            else:
                # Handle other states (RETRY, REVOKED, etc.)
                status_info = {
                    'status': task_result.state.lower(),
                    'progress': progress,
                    'message': f'Task is in {task_result.state} state'
                }
            
            # Add task metadata
            status_info.update({
                'task_id': task_id,
                'task_state': task_result.state
            })
            
            return Response(status_info)
            
        except Exception as e:
            logger.error(f"Error checking task status {task_id}: {str(e)}")
            return Response({
                'status': 'error',
                'error': f'Failed to check task status: {str(e)}',
                'task_id': task_id
            }, status=status.HTTP_500_INTERNAL_SERVER_ERROR)


class SystemVersionView(APIView):
    """
    GET: Get system version information (no auth required for front page display)
    Returns: git commit, build info, service status
    """
    authentication_classes = []
    permission_classes = []
    
    def get(self, request):
        import subprocess
        import os
        from django.conf import settings
        from audioDiagnostic.utils import get_redis_connection
        from celery import current_app
        
        version_info = {
            'backend': {
                'git_commit': 'unknown',
                'git_branch': 'unknown',
                'last_updated': 'unknown',
                'status': 'unknown'
            },
            'frontend': {
                'build_file': 'unknown',
                'status': 'unknown'
            },
            'services': {
                'celery': 'offline',
                'redis': 'offline',
                'docker': 'offline'
            },
            'environment': os.getenv('ENVIRONMENT', 'production')
        }
        
        # Get backend git info
        try:
            os.chdir(settings.BASE_DIR)
            
            # Get current commit hash
            git_commit = subprocess.check_output(
                ['git', 'rev-parse', '--short', 'HEAD'],
                stderr=subprocess.DEVNULL
            ).decode('utf-8').strip()
            version_info['backend']['git_commit'] = git_commit
            
            # Get current branch
            git_branch = subprocess.check_output(
                ['git', 'rev-parse', '--abbrev-ref', 'HEAD'],
                stderr=subprocess.DEVNULL
            ).decode('utf-8').strip()
            version_info['backend']['git_branch'] = git_branch
            
            # Get last commit date
            last_updated = subprocess.check_output(
                ['git', 'log', '-1', '--format=%cd', '--date=short'],
                stderr=subprocess.DEVNULL
            ).decode('utf-8').strip()
            version_info['backend']['last_updated'] = last_updated
            
            version_info['backend']['status'] = 'online'
            
        except Exception as e:
            logger.warning(f"Could not get git info: {str(e)}")
        
        # Check Redis status
        try:
            r = get_redis_connection()
            r.ping()
            version_info['services']['redis'] = 'online'
        except Exception:
            version_info['services']['redis'] = 'offline'
        
        # Check Celery status
        try:
            inspect = current_app.control.inspect()
            stats = inspect.stats()
            if stats is not None and len(stats) > 0:
                version_info['services']['celery'] = 'online'
                # Get worker count
                version_info['services']['celery_workers'] = len(stats)
            else:
                version_info['services']['celery'] = 'offline'
        except Exception:
            version_info['services']['celery'] = 'offline'
        
        # Check Docker (simplified - just check if we can connect to services)
        if version_info['services']['celery'] == 'online' or version_info['services']['redis'] == 'online':
            version_info['services']['docker'] = 'online'
        else:
            version_info['services']['docker'] = 'offline'
        
        # Frontend build info - read from static files if available
        try:
            # Try to find main.*.js file in static directory
            static_dir = os.path.join(settings.BASE_DIR.parent, 'frontend', 'audio-waveform-visualizer', 'build', 'static', 'js')
            if os.path.exists(static_dir):
                js_files = [f for f in os.listdir(static_dir) if f.startswith('main.') and f.endswith('.js')]
                if js_files:
                    version_info['frontend']['build_file'] = js_files[0]
                    version_info['frontend']['status'] = 'deployed'
        except Exception as e:
            logger.warning(f"Could not get frontend build info: {str(e)}")
        
        # Overall system status
        all_online = all([
            version_info['backend']['status'] == 'online',
            version_info['services']['celery'] == 'online',
            version_info['services']['redis'] == 'online'
        ])
        
        version_info['overall_status'] = 'all_systems_operational' if all_online else 'some_services_degraded'
        
        return Response(version_info)


