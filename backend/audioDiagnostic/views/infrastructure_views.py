"""
Infrastructure Views for audioDiagnostic app.
"""
from ._base import *

class InfrastructureStatusView(APIView):
    """
    GET: Get Docker and Celery infrastructure status
    POST: Force shutdown infrastructure
    """
    authentication_classes = [SessionAuthentication, TokenAuthentication, BasicAuthentication]
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
    authentication_classes = [SessionAuthentication, TokenAuthentication, BasicAuthentication]
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


