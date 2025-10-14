from django.contrib import admin
from .models import SubscriptionPlan, UserSubscription, UsageTracking, BillingHistory, UserProfile


@admin.register(SubscriptionPlan)
class SubscriptionPlanAdmin(admin.ModelAdmin):
    list_display = (
        'display_name', 'name', 'price_monthly', 'price_yearly',
        'max_projects_per_month', 'max_audio_duration_minutes', 'is_active'
    )
    list_filter = ('is_active', 'priority_processing', 'api_access')
    search_fields = ('name', 'display_name')
    ordering = ('price_monthly',)


@admin.register(UserSubscription)
class UserSubscriptionAdmin(admin.ModelAdmin):
    list_display = (
        'user', 'plan', 'status', 'billing_cycle',
        'current_period_end', 'is_trial', 'created_at'
    )
    list_filter = ('status', 'billing_cycle', 'plan__name')
    search_fields = ('user__username', 'user__email', 'stripe_customer_id')
    readonly_fields = ('stripe_customer_id', 'stripe_subscription_id', 'created_at', 'updated_at')
    ordering = ('-created_at',)


@admin.register(UsageTracking)
class UsageTrackingAdmin(admin.ModelAdmin):
    list_display = (
        'user', 'period_start', 'projects_created',
        'audio_minutes_processed', 'storage_used_mb', 'api_calls_made'
    )
    list_filter = ('period_start',)
    search_fields = ('user__username', 'user__email')
    readonly_fields = ('created_at', 'updated_at')
    ordering = ('-period_start', 'user__username')


@admin.register(BillingHistory)
class BillingHistoryAdmin(admin.ModelAdmin):
    list_display = (
        'user', 'transaction_type', 'amount', 'currency',
        'description', 'created_at'
    )
    list_filter = ('transaction_type', 'currency', 'created_at')
    search_fields = ('user__username', 'user__email', 'stripe_payment_intent_id')
    readonly_fields = ('created_at',)
    ordering = ('-created_at',)


@admin.register(UserProfile)
class UserProfileAdmin(admin.ModelAdmin):
    list_display = (
        'user', 'company_name', 'phone_number',
        'email_notifications', 'marketing_emails', 'created_at'
    )
    list_filter = ('email_notifications', 'marketing_emails', 'created_at')
    search_fields = ('user__username', 'user__email', 'company_name')
    readonly_fields = ('created_at', 'updated_at')
    ordering = ('-created_at',)