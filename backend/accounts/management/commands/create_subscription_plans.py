from django.core.management.base import BaseCommand
from accounts.models import SubscriptionPlan


class Command(BaseCommand):
    help = 'Create default subscription plans'

    def handle(self, *args, **options):
        """Create default subscription plans for the SaaS service"""
        
        plans = [
            {
                'name': 'free',
                'display_name': 'Free Trial',
                'description': 'Try our service free for 7 days',
                'price_monthly': 0.00,
                'price_yearly': 0.00,
                'max_projects_per_month': 0,  # Trial uses only
                'max_audio_duration_minutes': 60,  # 1 hour for trial
                'max_file_size_mb': 100,
                'max_storage_gb': 1.0,
                'priority_processing': False,
                'api_access': False,
                'custom_branding': False,
            },
            {
                'name': 'basic',
                'display_name': 'Basic Plan',
                'description': 'Perfect for occasional use - 1 processing job per month',
                'price_monthly': 10.00,  # £10
                'price_yearly': 120.00,  # £120 (no discount for consistency)
                'max_projects_per_month': 1,  # 1 use per month
                'max_audio_duration_minutes': 0,  # Unlimited duration per use
                'max_file_size_mb': 500,
                'max_storage_gb': 2.0,
                'priority_processing': False,
                'api_access': False,
                'custom_branding': False,
            },
            {
                'name': 'pro',
                'display_name': 'Professional',
                'description': 'For regular users - 10 processing jobs per month',
                'price_monthly': 50.00,  # £50
                'price_yearly': 600.00,  # £600 (no discount for consistency)
                'max_projects_per_month': 10,  # 10 uses per month
                'max_audio_duration_minutes': 0,  # Unlimited duration per use
                'max_file_size_mb': 1000,  # 1GB files
                'max_storage_gb': 10.0,
                'priority_processing': True,
                'api_access': True,
                'custom_branding': False,
            },
            {
                'name': 'enterprise',
                'display_name': 'Unlimited Annual',
                'description': 'Unlimited processing jobs for the entire year',
                'price_monthly': 0.00,  # Not available monthly
                'price_yearly': 100.00,  # £100 per year
                'max_projects_per_month': 0,  # Unlimited
                'max_audio_duration_minutes': 0,  # Unlimited
                'max_file_size_mb': 2000,  # 2GB files
                'max_storage_gb': 50.0,
                'priority_processing': True,
                'api_access': True,
                'custom_branding': True,
            },
        ]
        
        created_count = 0
        updated_count = 0
        
        for plan_data in plans:
            plan, created = SubscriptionPlan.objects.update_or_create(
                name=plan_data['name'],
                defaults=plan_data
            )
            
            if created:
                created_count += 1
                self.stdout.write(
                    self.style.SUCCESS(f'Created plan: {plan.display_name}')
                )
            else:
                updated_count += 1
                self.stdout.write(
                    self.style.WARNING(f'Updated plan: {plan.display_name}')
                )
        
        self.stdout.write(
            self.style.SUCCESS(
                f'\nCompleted! Created {created_count} new plans, updated {updated_count} existing plans.'
            )
        )
        
        # Display pricing summary
        self.stdout.write('\n=== PRICING SUMMARY (GBP) ===')
        for plan in SubscriptionPlan.objects.filter(is_active=True).order_by('price_monthly', 'price_yearly'):
            self.stdout.write(f'{plan.display_name}:')
            
            if plan.name == 'free':
                self.stdout.write(f'  Price: Free (7-day trial)')
            elif plan.name == 'enterprise':
                self.stdout.write(f'  Price: £{plan.price_yearly}/year (annual only)')
            else:
                self.stdout.write(f'  Monthly: £{plan.price_monthly}')
                if plan.price_yearly > 0:
                    self.stdout.write(f'  Yearly: £{plan.price_yearly}')
            
            if plan.max_projects_per_month == 0:
                uses_text = "Unlimited uses"
            else:
                uses_text = f"{plan.max_projects_per_month} use{'s' if plan.max_projects_per_month != 1 else ''}"
                
            self.stdout.write(f'  Usage: {uses_text}/month')
            self.stdout.write(f'  Audio Duration: {"Unlimited" if plan.max_audio_duration_minutes == 0 else str(plan.max_audio_duration_minutes) + " minutes"} per use')
            self.stdout.write(f'  Max File Size: {plan.max_file_size_mb}MB')
            self.stdout.write(f'  Storage: {plan.max_storage_gb}GB')
            self.stdout.write('')