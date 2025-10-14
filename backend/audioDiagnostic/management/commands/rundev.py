import subprocess
import signal
import sys
import time
import os
import platform
from django.core.management.base import BaseCommand
from django.core.management import call_command


class Command(BaseCommand):
    help = 'Starts Docker, Redis, Celery, and Django development server'
    
    def __init__(self):
        super().__init__()
        self.processes = []
        self.redis_container_id = None
    
    def add_arguments(self, parser):
        parser.add_argument(
            '--port',
            type=str,
            default='8000',
            help='Port for Django development server (default: 8000)',
        )
        parser.add_argument(
            '--skip-docker',
            action='store_true',
            help='Skip starting Docker/Redis (assume already running)',
        )
        parser.add_argument(
            '--skip-celery',
            action='store_true',
            help='Skip starting Celery worker',
        )
        parser.add_argument(
            '--frontend',
            action='store_true',
            help='Also start React frontend (npm start)',
        )
        parser.add_argument(
            '--celery-verbose',
            action='store_true',
            help='Show Celery worker output in console',
        )
        parser.add_argument(
            '--skip-cleanup',
            action='store_true',
            help='Skip automatic cleanup of existing Celery processes',
        )

    def handle(self, *args, **options):
        self.stdout.write(
            self.style.SUCCESS('🚀 Starting Audio Repetitive Detection Development Environment')
        )
        
        # Setup signal handlers for cleanup
        signal.signal(signal.SIGINT, self.signal_handler)
        signal.signal(signal.SIGTERM, self.signal_handler)
        
        try:
            # Run system readiness checks
            self.run_system_checks()
            
            if not options['skip_docker']:
                self.start_redis()
            
            # Store verbose celery option for start_celery method
            self._verbose_celery = options.get('celery_verbose', False)
            
            if not options['skip_celery']:
                # Clean up existing Celery processes before starting new one (unless skipped)
                if not options.get('skip_cleanup', False):
                    self.cleanup_existing_celery()
                self.start_celery()
            
            if options['frontend']:
                self.start_frontend()
            
            self.start_django(options['port'])
            
        except KeyboardInterrupt:
            self.cleanup()
        except Exception as e:
            self.stdout.write(
                self.style.ERROR(f'Error: {e}')
            )
            self.cleanup()
    
    def start_redis(self):
        """Start Redis in Docker container"""
        self.stdout.write('🔧 Checking Docker...')
        
        # Check if Docker is running
        try:
            subprocess.run(['docker', '--version'], check=True, capture_output=True)
        except (subprocess.CalledProcessError, FileNotFoundError):
            self.stdout.write(
                self.style.ERROR('❌ Docker is not installed or not running. Please install Docker first.')
            )
            sys.exit(1)
        
        # Check if Redis container is already running
        try:
            result = subprocess.run(
                ['docker', 'ps', '--filter', 'ancestor=redis', '--filter', 'publish=6379', '--format', '{{.ID}}'],
                capture_output=True, text=True, check=True
            )
            if result.stdout.strip():
                self.stdout.write(
                    self.style.WARNING('⚠️  Redis container already running, skipping...')
                )
                return
        except subprocess.CalledProcessError:
            pass
        
        # Start Redis container
        self.stdout.write('🚀 Starting Redis in Docker...')
        try:
            redis_process = subprocess.Popen(
                ['docker', 'run', '--rm', '-p', '6379:6379', 'redis'],
                stdout=subprocess.PIPE,
                stderr=subprocess.PIPE
            )
            self.processes.append(('redis', redis_process))
            
            # Wait a moment for Redis to start
            time.sleep(3)
            
            # Check if Redis is responding
            if redis_process.poll() is None:  # Still running
                self.stdout.write(
                    self.style.SUCCESS('✅ Redis started successfully on port 6379')
                )
            else:
                raise Exception('Redis container failed to start')
                
        except Exception as e:
            self.stdout.write(
                self.style.ERROR(f'❌ Failed to start Redis: {e}')
            )
            sys.exit(1)
    
    def cleanup_existing_celery(self):
        """Clean up any existing Celery processes to prevent conflicts"""
        self.stdout.write('🧹 Cleaning up existing Celery processes...')
        
        try:
            if platform.system() == 'Windows':
                # Kill existing celery processes on Windows
                subprocess.run(
                    ['taskkill', '/f', '/im', 'celery.exe'], 
                    capture_output=True, 
                    check=False  # Don't fail if no processes found
                )
                
                # Also try to kill any Python processes with celery in the title
                subprocess.run([
                    'taskkill', '/f', '/im', 'python.exe', 
                    '/fi', 'WINDOWTITLE eq *celery*'
                ], capture_output=True, check=False)
                
            else:
                # For Unix-like systems (Mac, Linux)
                subprocess.run([
                    'pkill', '-f', 'celery.*worker'
                ], capture_output=True, check=False)
            
            self.stdout.write('   ✅ Celery cleanup completed')
            
        except Exception as e:
            # Don't fail startup if cleanup fails
            self.stdout.write(
                self.style.WARNING(f'   ⚠️  Cleanup warning: {e}')
            )
    
    def start_celery(self):
        """Start Celery worker"""
        self.stdout.write('🚀 Starting Celery worker...')
        
        try:
            # Generate unique worker name to avoid conflicts
            import time
            worker_name = f"worker-{int(time.time())}"
            
            celery_cmd = ['celery', '-A', 'myproject', 'worker', '--loglevel=info', '-n', worker_name]
            
            # Add pool=solo for Windows
            if platform.system() == 'Windows':
                celery_cmd.append('--pool=solo')
            
            # Check if verbose mode is requested
            verbose_celery = getattr(self, '_verbose_celery', False)
            
            if verbose_celery:
                # Don't capture output - let it show in console
                celery_process = subprocess.Popen(celery_cmd)
                self.stdout.write(
                    self.style.SUCCESS(f'✅ Celery worker started in verbose mode (name: {worker_name})')
                )
            else:
                # Capture output as before
                celery_process = subprocess.Popen(
                    celery_cmd,
                    stdout=subprocess.PIPE,
                    stderr=subprocess.PIPE
                )
                self.stdout.write(
                    self.style.SUCCESS(f'✅ Celery worker started successfully (name: {worker_name})')
                )
            
            self.processes.append(('celery', celery_process))
            
            # Wait a moment for Celery to start
            time.sleep(2)
            
            if celery_process.poll() is not None:  # Process ended unexpectedly
                raise Exception('Celery worker failed to start')
                
        except Exception as e:
            self.stdout.write(
                self.style.ERROR(f'❌ Failed to start Celery: {e}')
            )
            sys.exit(1)
    
    def start_frontend(self):
        """Start React frontend development server"""
        self.stdout.write('🚀 Starting React frontend...')
        
        # Use the exact path you confirmed works
        frontend_path = r"C:\Users\user\Documents\GitHub\Audio repetative detection\frontend\audio-waveform-visualizer"
        
        self.stdout.write(f'   Looking for frontend at: {frontend_path}')
        
        if not os.path.exists(frontend_path):
            self.stdout.write(
                self.style.ERROR(f'❌ Frontend directory not found: {frontend_path}')
            )
            return
        
        # Check if package.json exists
        package_json = os.path.join(frontend_path, 'package.json')
        if not os.path.exists(package_json):
            self.stdout.write(
                self.style.ERROR(f'❌ package.json not found in: {frontend_path}')
            )
            return
        
        try:
            # Try multiple ways to find npm
            npm_cmd = 'npm'
            
            # First try to find npm in common locations
            possible_npm_paths = [
                'npm',
                'npm.cmd',
                r'C:\Program Files\nodejs\npm.cmd',
                r'C:\Program Files (x86)\nodejs\npm.cmd',
                os.path.expandvars(r'%APPDATA%\npm\npm.cmd')
            ]
            
            npm_found = False
            for npm_path in possible_npm_paths:
                try:
                    subprocess.run([npm_path, '--version'], check=True, capture_output=True, timeout=5)
                    npm_cmd = npm_path
                    npm_found = True
                    self.stdout.write(f'   Found npm at: {npm_cmd}')
                    break
                except (subprocess.CalledProcessError, FileNotFoundError, subprocess.TimeoutExpired):
                    continue
            
            if not npm_found:
                self.stdout.write(
                    self.style.WARNING('⚠️  npm not found in PATH. Opening frontend directory instead...')
                )
                # Fallback: just open the directory for manual start
                if platform.system() == 'Windows':
                    subprocess.Popen(['explorer', frontend_path])
                    self.stdout.write(
                        self.style.SUCCESS(f'📂 Opened frontend directory. Please run "npm start" manually in: {frontend_path}')
                    )
                return
            
            # Try to start npm
            self.stdout.write(f'   Starting npm with command: {npm_cmd}')
            
            frontend_process = subprocess.Popen(
                [npm_cmd, 'start'],
                cwd=frontend_path,
                stdout=subprocess.PIPE,
                stderr=subprocess.PIPE
            )
            self.processes.append(('frontend', frontend_process))
            
            # Wait a moment for frontend to start
            time.sleep(3)
            
            if frontend_process.poll() is None:  # Still running
                self.stdout.write(
                    self.style.SUCCESS('✅ React frontend started successfully')
                )
            else:
                # Get error output
                _, stderr = frontend_process.communicate(timeout=5)
                error_msg = stderr.decode() if stderr else "Unknown error"
                raise Exception(f'Frontend failed to start: {error_msg}')
                
        except Exception as e:
            self.stdout.write(
                self.style.ERROR(f'❌ Failed to start frontend: {e}')
            )
            self.stdout.write(
                self.style.WARNING(f'💡 Try starting manually: cd "{frontend_path}" && npm start')
            )
    
    def start_django(self, port):
        """Start Django development server"""
        self.stdout.write(f'🚀 Starting Django development server on port {port}...')
        
        # Set up Docker/Celery infrastructure immediately
        self.setup_infrastructure_on_startup()
        
        try:
            # Run Django development server in the foreground
            frontend_msg = '\n⚛️  React frontend: http://localhost:3000' if any(name == 'frontend' for name, _ in self.processes) else ''
            
            self.stdout.write(
                self.style.SUCCESS(
                    f'\n✅ All services started successfully!\n'
                    f'🌐 Django server: http://127.0.0.1:{port}\n'
                    f'📊 Redis: localhost:6379\n'
                    f'⚡ Celery worker: Running{frontend_msg}\n'
                    f'🐳 Docker/Celery: Ready for tasks\n'
                    f'\nPress Ctrl+C to stop all services\n'
                )
            )
            
            call_command('runserver', f'127.0.0.1:{port}')
            
        except KeyboardInterrupt:
            self.cleanup()
        except Exception as e:
            self.stdout.write(
                self.style.ERROR(f'❌ Failed to start Django server: {e}')
            )
            self.cleanup()
    
    def cleanup(self):
        """Clean up all started processes"""
        self.stdout.write('\n🛑 Stopping all services...')
        
        for name, process in self.processes:
            if process.poll() is None:  # Still running
                self.stdout.write(f'   Stopping {name}...')
                process.terminate()
                try:
                    process.wait(timeout=5)
                except subprocess.TimeoutExpired:
                    process.kill()
        
        # Stop any Redis containers we might have started
        try:
            subprocess.run(
                ['docker', 'stop', '$(docker', 'ps', '-q', '--filter', 'ancestor=redis)'],
                shell=True, capture_output=True
            )
        except:
            pass
        
        self.stdout.write(
            self.style.SUCCESS('✅ All services stopped')
        )
    
    def run_system_checks(self):
        """Run comprehensive system readiness checks"""
        self.stdout.write(self.style.WARNING('🔍 Running system readiness checks...'))
        
        # Check 1: Reset stuck tasks
        self.reset_stuck_tasks()
        
        # Check 2: Verify database migrations
        self.check_database_migrations()
        
        # Check 3: Verify Docker availability
        self.check_docker_status()
        
        # Check 4: Validate system requirements
        self.validate_system_requirements()
        
        self.stdout.write(self.style.SUCCESS('✅ System checks complete - Ready to start!'))
    
    def reset_stuck_tasks(self):
        """Reset any stuck audio processing tasks"""
        try:
            from audioDiagnostic.models import AudioFile, AudioProject
            from celery.result import AsyncResult
            
            stuck_audio_files = 0
            stuck_projects = 0
            
            # Reset stuck audio files
            for af in AudioFile.objects.filter(status__in=['transcribing', 'processing']):
                if af.task_id:
                    try:
                        result = AsyncResult(af.task_id)
                        if result.state == 'PENDING':  # Task never started or stuck
                            stuck_audio_files += 1
                            self.stdout.write(f'   📄 Resetting AudioFile {af.id} ({af.filename}): {af.status} → pending')
                            af.status = 'pending'
                            af.task_id = None
                            af.save()
                    except Exception:
                        # If we can't check the task, assume it's stuck
                        stuck_audio_files += 1
                        self.stdout.write(f'   📄 Resetting AudioFile {af.id} ({af.filename}): {af.status} → pending')
                        af.status = 'pending' 
                        af.task_id = None
                        af.save()
            
            # Reset stuck projects
            for project in AudioProject.objects.filter(status='processing'):
                stuck_projects += 1
                self.stdout.write(f'   📁 Resetting Project {project.id} ({project.title}): processing → pending')
                project.status = 'pending'
                project.save()
            
            if stuck_audio_files > 0 or stuck_projects > 0:
                self.stdout.write(f'   ✅ Reset {stuck_audio_files} audio files and {stuck_projects} projects')
            else:
                self.stdout.write(f'   ✅ No stuck tasks found')
                
        except Exception as e:
            self.stdout.write(self.style.ERROR(f'   ❌ Error resetting stuck tasks: {e}'))
    
    def check_database_migrations(self):
        """Verify database is up to date"""
        try:
            call_command('check', '--deploy', verbosity=0)
            self.stdout.write('   ✅ Database migrations are up to date')
        except Exception as e:
            self.stdout.write(self.style.ERROR(f'   ❌ Database migration issues: {e}'))
            self.stdout.write(self.style.WARNING('   💡 Run: python manage.py migrate'))
    
    def check_docker_status(self):
        """Check if Docker Desktop is running"""
        try:
            result = subprocess.run(['docker', 'info'], capture_output=True, text=True)
            if result.returncode == 0:
                self.stdout.write('   ✅ Docker Desktop is running')
            else:
                self.stdout.write(self.style.WARNING('   ⚠️  Docker Desktop may not be running'))
                self.stdout.write('   💡 Audio processing requires Docker Desktop')
        except FileNotFoundError:
            self.stdout.write(self.style.ERROR('   ❌ Docker not installed'))
            self.stdout.write('   💡 Install Docker Desktop for audio processing')
    
    def validate_system_requirements(self):
        """Check system requirements and dependencies"""
        try:
            # Check Python version
            python_version = f"{sys.version_info.major}.{sys.version_info.minor}"
            if sys.version_info >= (3, 12):
                self.stdout.write(f'   ✅ Python {python_version} (compatible)')
            else:
                self.stdout.write(self.style.WARNING(f'   ⚠️  Python {python_version} (recommend 3.12+)'))
            
            # Check critical packages
            critical_packages = ['django', 'celery', 'whisper', 'redis']
            for package in critical_packages:
                try:
                    __import__(package)
                    self.stdout.write(f'   ✅ {package} package available')
                except ImportError:
                    self.stdout.write(self.style.ERROR(f'   ❌ Missing package: {package}'))
                    self.stdout.write('   💡 Run: pip install -r requirements.txt')
                    
        except Exception as e:
            self.stdout.write(self.style.ERROR(f'   ❌ System validation error: {e}'))
    
    def setup_infrastructure_on_startup(self):
        """Set up Docker/Celery infrastructure during startup"""
        self.stdout.write('🐳 Setting up Docker/Celery infrastructure...')
        
        try:
            from ...services.docker_manager import docker_celery_manager
            
            # Check if Docker is available first
            if not docker_celery_manager._check_docker():
                self.stdout.write(
                    self.style.WARNING(
                        '⚠️ Docker Desktop not running - infrastructure will start when you transcribe audio'
                    )
                )
                return
            
            # Set up infrastructure
            if docker_celery_manager.setup_infrastructure():
                self.stdout.write(
                    self.style.SUCCESS('✅ Docker/Celery infrastructure ready')
                )
            else:
                self.stdout.write(
                    self.style.WARNING(
                        '⚠️ Infrastructure setup incomplete - will retry when you transcribe audio'
                    )
                )
                
        except Exception as e:
            self.stdout.write(
                self.style.WARNING(
                    f'⚠️ Infrastructure setup failed: {e}\n'
                    '   Infrastructure will start automatically when you transcribe audio'
                )
            )
    
    def signal_handler(self, signum, frame):
        """Handle Ctrl+C and other signals"""
        self.cleanup()
        sys.exit(0)