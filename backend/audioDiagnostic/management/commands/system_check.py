from django.core.management.base import BaseCommand
from django.core.management import call_command
from audioDiagnostic.models import AudioFile, AudioProject
import subprocess
import sys
import os


class Command(BaseCommand):
    help = 'Comprehensive system readiness check for Audio Duplicate Detection'

    def add_arguments(self, parser):
        parser.add_argument(
            '--fix',
            action='store_true',
            help='Automatically fix issues where possible',
        )
        parser.add_argument(
            '--verbose',
            action='store_true',
            help='Show detailed information about checks',
        )

    def handle(self, *args, **options):
        self.verbose = options['verbose']
        self.auto_fix = options['fix']
        
        self.stdout.write(self.style.SUCCESS('🔍 Audio Duplicate Detection - System Readiness Check'))
        self.stdout.write('=' * 60)
        
        all_checks_passed = True
        
        # Run all system checks
        checks = [
            ('Database Migrations', self.check_database),
            ('Stuck Tasks Reset', self.check_stuck_tasks),
            ('Docker Installation', self.check_docker),
            ('Python Dependencies', self.check_dependencies),
            ('File Permissions', self.check_file_permissions),
            ('Media Directories', self.check_media_directories),
        ]
        
        for check_name, check_func in checks:
            self.stdout.write(f'\n📋 {check_name}:')
            try:
                if not check_func():
                    all_checks_passed = False
            except Exception as e:
                self.stdout.write(self.style.ERROR(f'   ❌ Error during {check_name}: {e}'))
                all_checks_passed = False
        
        # Final summary
        self.stdout.write('\n' + '=' * 60)
        if all_checks_passed:
            self.stdout.write(self.style.SUCCESS('🎉 All system checks passed! Ready to start.'))
        else:
            self.stdout.write(self.style.WARNING('⚠️  Some issues found. Review and fix before starting.'))
            if not self.auto_fix:
                self.stdout.write('💡 Run with --fix to automatically resolve issues where possible.')
        
        # Return nothing for Django management command

    def check_database(self):
        """Check database status and migrations"""
        try:
            # Check if migrations are needed
            call_command('check', '--deploy', verbosity=0)
            
            # Count database objects
            project_count = AudioProject.objects.count()
            audio_file_count = AudioFile.objects.count()
            
            self.stdout.write(f'   ✅ Database accessible')
            self.stdout.write(f'   📊 {project_count} projects, {audio_file_count} audio files')
            
            if self.verbose:
                self.stdout.write(f'   📁 Database: {self.get_database_path()}')
            
            return True
            
        except Exception as e:
            self.stdout.write(self.style.ERROR(f'   ❌ Database issue: {e}'))
            if self.auto_fix:
                self.stdout.write('   🔧 Running migrations...')
                call_command('migrate', verbosity=0)
                self.stdout.write('   ✅ Migrations completed')
                return True
            else:
                self.stdout.write('   💡 Fix: python manage.py migrate')
            return False

    def check_stuck_tasks(self):
        """Check for and optionally reset stuck tasks"""
        try:
            from celery.result import AsyncResult
            
            stuck_audio_files = []
            stuck_projects = []
            
            # Find stuck audio files
            for af in AudioFile.objects.filter(status__in=['transcribing', 'processing']):
                if af.task_id:
                    try:
                        result = AsyncResult(af.task_id)
                        if result.state == 'PENDING':
                            stuck_audio_files.append(af)
                    except:
                        stuck_audio_files.append(af)
            
            # Find stuck projects
            stuck_projects = list(AudioProject.objects.filter(status='processing'))
            
            if not stuck_audio_files and not stuck_projects:
                self.stdout.write('   ✅ No stuck tasks found')
                return True
            
            self.stdout.write(f'   ⚠️  Found {len(stuck_audio_files)} stuck audio files, {len(stuck_projects)} stuck projects')
            
            if self.auto_fix:
                for af in stuck_audio_files:
                    af.status = 'pending'
                    af.task_id = None
                    af.save()
                    self.stdout.write(f'   🔧 Reset AudioFile {af.id} ({af.filename})')
                
                for project in stuck_projects:
                    project.status = 'pending'
                    project.save()
                    self.stdout.write(f'   🔧 Reset Project {project.id} ({project.title})')
                
                self.stdout.write('   ✅ All stuck tasks reset')
                return True
            else:
                self.stdout.write('   💡 Fix: python manage.py reset_stuck_tasks')
                return False
                
        except Exception as e:
            self.stdout.write(self.style.ERROR(f'   ❌ Error checking stuck tasks: {e}'))
            return False

    def check_docker(self):
        """Check Docker installation and status"""
        try:
            # Check if Docker command exists
            result = subprocess.run(['docker', '--version'], capture_output=True, text=True)
            if result.returncode != 0:
                self.stdout.write(self.style.ERROR('   ❌ Docker not installed'))
                self.stdout.write('   💡 Install Docker Desktop from https://www.docker.com/products/docker-desktop')
                return False
            
            docker_version = result.stdout.strip()
            self.stdout.write(f'   ✅ {docker_version}')
            
            # Check if Docker daemon is running
            result = subprocess.run(['docker', 'info'], capture_output=True, text=True)
            if result.returncode != 0:
                self.stdout.write(self.style.WARNING('   ⚠️  Docker Desktop not running'))
                self.stdout.write('   💡 Start Docker Desktop and wait for it to initialize')
                return False
            else:
                self.stdout.write('   ✅ Docker Desktop is running')
                return True
                
        except FileNotFoundError:
            self.stdout.write(self.style.ERROR('   ❌ Docker command not found'))
            self.stdout.write('   💡 Install Docker Desktop and add to PATH')
            return False

    def check_dependencies(self):
        """Check Python dependencies"""
        critical_packages = {
            'django': '5.2+',
            'celery': '5.5+',
            'redis': '6.0+',
            'whisper': 'OpenAI Whisper',
            'pydub': 'Audio processing',
        }
        
        all_good = True
        
        for package, description in critical_packages.items():
            try:
                module = __import__(package)
                version = getattr(module, '__version__', 'unknown')
                self.stdout.write(f'   ✅ {package} {version} ({description})')
            except ImportError:
                self.stdout.write(self.style.ERROR(f'   ❌ Missing: {package} ({description})'))
                all_good = False
        
        if not all_good:
            self.stdout.write('   💡 Fix: pip install -r requirements.txt')
        
        return all_good

    def check_file_permissions(self):
        """Check file permissions for media directories"""
        try:
            from django.conf import settings
            media_root = settings.MEDIA_ROOT
            
            # Test write permissions
            test_file = os.path.join(media_root, '.test_permissions')
            try:
                os.makedirs(media_root, exist_ok=True)
                with open(test_file, 'w') as f:
                    f.write('test')
                os.remove(test_file)
                self.stdout.write('   ✅ Media directory writable')
                return True
            except Exception as e:
                self.stdout.write(self.style.ERROR(f'   ❌ Cannot write to media directory: {e}'))
                return False
                
        except Exception as e:
            self.stdout.write(self.style.ERROR(f'   ❌ Permission check failed: {e}'))
            return False

    def check_media_directories(self):
        """Ensure required media directories exist"""
        try:
            from django.conf import settings
            media_root = settings.MEDIA_ROOT
            
            required_dirs = [
                'audio',
                'pdfs', 
                'processed',
                'logs',
                'chunks'
            ]
            
            created_dirs = []
            for dirname in required_dirs:
                dirpath = os.path.join(media_root, dirname)
                if not os.path.exists(dirpath):
                    if self.auto_fix:
                        os.makedirs(dirpath, exist_ok=True)
                        created_dirs.append(dirname)
                    else:
                        self.stdout.write(self.style.WARNING(f'   ⚠️  Missing directory: {dirname}'))
                        return False
            
            if created_dirs:
                self.stdout.write(f'   🔧 Created directories: {", ".join(created_dirs)}')
            
            self.stdout.write('   ✅ All required directories exist')
            return True
            
        except Exception as e:
            self.stdout.write(self.style.ERROR(f'   ❌ Directory check failed: {e}'))
            return False

    def get_database_path(self):
        """Get database file path for SQLite"""
        try:
            from django.conf import settings
            db_config = settings.DATABASES['default']
            if db_config['ENGINE'] == 'django.db.backends.sqlite3':
                return str(db_config['NAME'])
            else:
                return f"{db_config['ENGINE']} database"
        except:
            return "Unknown database"