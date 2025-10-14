from django.core.management.base import BaseCommand
from django.contrib.auth.models import User
from accounts.models import UserProfile, UserSubscription, SubscriptionPlan
from audioDiagnostic.models import AudioProject
from datetime import datetime, timedelta
import logging

logger = logging.getLogger(__name__)

class Command(BaseCommand):
    help = 'Create an unlimited user profile and assign existing projects'

    def add_arguments(self, parser):
        parser.add_argument(
            '--username',
            type=str,
            default='unlimited_user',
            help='Username for the unlimited user (default: unlimited_user)'
        )
        parser.add_argument(
            '--email',
            type=str,
            default='unlimited@audiodetection.com',
            help='Email for the unlimited user'
        )
        parser.add_argument(
            '--password',
            type=str,
            default='AudioUnlimited2025!',
            help='Password for the unlimited user'
        )

    def handle(self, *args, **options):
        username = options['username']
        email = options['email']
        password = options['password']
        
        try:
            # Create or get the user
            user, created = User.objects.get_or_create(
                username=username,
                defaults={
                    'email': email,
                    'first_name': 'Unlimited',
                    'last_name': 'User',
                    'is_active': True,
                }
            )
            
            if created:
                user.set_password(password)
                user.save()
                self.stdout.write(
                    self.style.SUCCESS(f'✅ Created new user: {username}')
                )
            else:
                self.stdout.write(
                    self.style.WARNING(f'⚠️  User {username} already exists')
                )
            
            # Create or get unlimited subscription plan
            unlimited_plan, plan_created = SubscriptionPlan.objects.get_or_create(
                name='enterprise',
                defaults={
                    'display_name': 'Unlimited Enterprise Plan',
                    'description': 'Unlimited usage plan for audio duplicate detection - no restrictions',
                    'price_monthly': 100.00,
                    'price_yearly': 1000.00,
                    'max_projects_per_month': 0,  # 0 = unlimited
                    'max_audio_duration_minutes': 0,  # 0 = unlimited
                    'max_file_size_mb': 5000,  # 5GB files
                    'max_storage_gb': 1000.0,  # 1TB storage
                    'priority_processing': True,
                    'api_access': True,
                    'custom_branding': True,
                    'stripe_price_id_monthly': 'price_unlimited_monthly',
                    'stripe_price_id_yearly': 'price_unlimited_yearly',
                    'is_active': True
                }
            )
            
            if plan_created:
                self.stdout.write(
                    self.style.SUCCESS('✅ Created unlimited subscription plan')
                )
            
            # Create or update user profile
            user_profile, profile_created = UserProfile.objects.get_or_create(
                user=user,
                defaults={
                    'phone_number': '+44-UNLIMITED',
                    'company': 'Audio Detection System',
                    'usage_notes': 'Unlimited user - no usage restrictions'
                }
            )
            
            if profile_created:
                self.stdout.write(
                    self.style.SUCCESS('✅ Created user profile')
                )
            
            # Create or update user subscription
            user_subscription, sub_created = UserSubscription.objects.get_or_create(
                user=user,
                defaults={
                    'plan': unlimited_plan,
                    'status': 'active',
                    'current_period_start': datetime.now(),
                    'current_period_end': datetime.now() + timedelta(days=365),
                    'usage_count': 0,
                    'stripe_subscription_id': 'sub_unlimited_system',
                    'stripe_customer_id': 'cus_unlimited_system'
                }
            )
            
            if sub_created:
                self.stdout.write(
                    self.style.SUCCESS('✅ Created unlimited subscription')
                )
            else:
                # Update existing subscription to be unlimited
                user_subscription.plan = unlimited_plan
                user_subscription.status = 'active'
                user_subscription.current_period_end = datetime.now() + timedelta(days=365)
                user_subscription.save()
                self.stdout.write(
                    self.style.SUCCESS('✅ Updated subscription to unlimited')
                )
            
            # Assign existing projects to this user
            unassigned_projects = AudioProject.objects.filter(user__isnull=True)
            if unassigned_projects.exists():
                count = unassigned_projects.update(user=user)
                self.stdout.write(
                    self.style.SUCCESS(f'✅ Assigned {count} unassigned projects to {username}')
                )
            
            # Also assign projects from any testuser or similar
            test_projects = AudioProject.objects.filter(user__username__in=['testuser', 'test', 'admin'])
            if test_projects.exists():
                test_count = test_projects.count()
                test_projects.update(user=user)
                self.stdout.write(
                    self.style.SUCCESS(f'✅ Reassigned {test_count} test projects to {username}')
                )
            
            total_projects = AudioProject.objects.filter(user=user).count()
            
            self.stdout.write('')
            self.stdout.write(self.style.SUCCESS('🎉 UNLIMITED USER SETUP COMPLETE!'))
            self.stdout.write('')
            self.stdout.write(f'👤 Username: {username}')
            self.stdout.write(f'📧 Email: {email}')
            self.stdout.write(f'🔑 Password: {password}')
            self.stdout.write(f'💎 Plan: {unlimited_plan.name} (Unlimited usage)')
            self.stdout.write(f'📁 Projects: {total_projects} assigned')
            self.stdout.write('')
            self.stdout.write('🔐 LOGIN INSTRUCTIONS:')
            self.stdout.write('1. Go to http://localhost:3000/login')
            self.stdout.write(f'2. Enter username: {username}')
            self.stdout.write(f'3. Enter password: {password}')
            self.stdout.write('4. You now have unlimited access to create and process audio projects!')
            
        except Exception as e:
            logger.error(f"Error creating unlimited user: {str(e)}")
            self.stdout.write(
                self.style.ERROR(f'❌ Error: {str(e)}')
            )
            raise e