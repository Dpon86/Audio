from rest_framework import serializers
from django.contrib.auth.models import User
from django.contrib.auth.password_validation import validate_password
from .models import SubscriptionPlan, UserSubscription, UsageTracking, BillingHistory, UserProfile, UserAPIKey


class UserRegistrationSerializer(serializers.ModelSerializer):
    """
    Serializer for user registration
    """
    password = serializers.CharField(write_only=True, validators=[validate_password])
    password_confirm = serializers.CharField(write_only=True)
    
    class Meta:
        model = User
        fields = ('username', 'email', 'first_name', 'last_name', 'password', 'password_confirm')
        extra_kwargs = {
            'email': {'required': True},
        }
    
    def validate(self, attrs):
        if attrs['password'] != attrs['password_confirm']:
            raise serializers.ValidationError("Passwords don't match")
        return attrs
    
    def validate_email(self, value):
        if User.objects.filter(email=value).exists():
            raise serializers.ValidationError("Email already registered")
        return value
    
    def create(self, validated_data):
        validated_data.pop('password_confirm')
        user = User.objects.create_user(**validated_data)
        return user


class UserProfileSerializer(serializers.ModelSerializer):
    """
    Serializer for user profile
    """
    username = serializers.CharField(source='user.username', read_only=True)
    email = serializers.EmailField(source='user.email', read_only=True)
    first_name = serializers.CharField(source='user.first_name')
    last_name = serializers.CharField(source='user.last_name')
    
    class Meta:
        model = UserProfile
        fields = (
            'username', 'email', 'first_name', 'last_name',
            'company_name', 'phone_number', 'email_notifications', 
            'marketing_emails', 'created_at'
        )
        read_only_fields = ('created_at',)
    
    def update(self, instance, validated_data):
        # Update User fields
        user_data = {}
        if 'user' in validated_data:
            user_data = validated_data.pop('user')
        
        for attr, value in user_data.items():
            setattr(instance.user, attr, value)
        instance.user.save()
        
        # Update Profile fields
        for attr, value in validated_data.items():
            setattr(instance, attr, value)
        instance.save()
        
        return instance


class SubscriptionPlanSerializer(serializers.ModelSerializer):
    """
    Serializer for subscription plans
    """
    features = serializers.SerializerMethodField()
    
    class Meta:
        model = SubscriptionPlan
        fields = (
            'id', 'name', 'display_name', 'description',
            'price_monthly', 'price_yearly', 'max_projects_per_month',
            'max_audio_duration_minutes', 'max_file_size_mb', 'max_storage_gb',
            'features'
        )
    
    def get_features(self, obj):
        """Return list of features for this plan"""
        features = []
        
        if obj.max_projects_per_month == 0:
            features.append("Unlimited projects")
        else:
            features.append(f"{obj.max_projects_per_month} projects per month")
        
        if obj.max_audio_duration_minutes == 0:
            features.append("Unlimited audio processing")
        else:
            features.append(f"{obj.max_audio_duration_minutes} minutes of audio per month")
        
        features.append(f"Up to {obj.max_file_size_mb}MB file size")
        features.append(f"{obj.max_storage_gb}GB storage")
        
        if obj.priority_processing:
            features.append("Priority processing")
        
        if obj.api_access:
            features.append("API access")
        
        if obj.custom_branding:
            features.append("Custom branding")
        
        return features


class UserSubscriptionSerializer(serializers.ModelSerializer):
    """
    Serializer for user subscriptions
    """
    plan = SubscriptionPlanSerializer(read_only=True)
    plan_name = serializers.CharField(source='plan.display_name', read_only=True)
    days_until_renewal = serializers.ReadOnlyField()
    is_trial = serializers.ReadOnlyField()
    is_active = serializers.ReadOnlyField()
    
    class Meta:
        model = UserSubscription
        fields = (
            'id', 'plan', 'plan_name', 'status', 'billing_cycle',
            'current_period_start', 'current_period_end', 'trial_end',
            'days_until_renewal', 'is_trial', 'is_active', 'created_at'
        )
        read_only_fields = ('created_at',)


class UsageTrackingSerializer(serializers.ModelSerializer):
    """
    Serializer for usage tracking
    """
    period_month = serializers.SerializerMethodField()
    
    class Meta:
        model = UsageTracking
        fields = (
            'id', 'projects_created', 'audio_minutes_processed',
            'storage_used_mb', 'api_calls_made', 'period_start',
            'period_end', 'period_month', 'created_at'
        )
        read_only_fields = ('created_at',)
    
    def get_period_month(self, obj):
        return obj.period_start.strftime('%B %Y')


class BillingHistorySerializer(serializers.ModelSerializer):
    """
    Serializer for billing history
    """
    formatted_amount = serializers.SerializerMethodField()
    
    class Meta:
        model = BillingHistory
        fields = (
            'id', 'transaction_type', 'amount', 'formatted_amount',
            'currency', 'description', 'created_at'
        )
        read_only_fields = ('created_at',)
    
    def get_formatted_amount(self, obj):
        currency_symbols = {'GBP': '£', 'USD': '$', 'EUR': '€'}
        symbol = currency_symbols.get(obj.currency, obj.currency)
        return f"{symbol}{obj.amount:.2f}"


class UserAPIKeySerializer(serializers.ModelSerializer):
    """
    Serializer for saving a user's AI provider API key.

    The raw key is write-only and is encrypted before being saved - it is
    never included in any serialized response, only a masked preview
    (`key_last_four`) is returned.
    """
    api_key = serializers.CharField(write_only=True, required=True, min_length=8, max_length=200, trim_whitespace=True)

    class Meta:
        model = UserAPIKey
        fields = ('provider', 'api_key', 'key_last_four', 'is_active', 'updated_at')
        read_only_fields = ('key_last_four', 'updated_at')

    def create(self, validated_data):
        raw_key = validated_data.pop('api_key')
        user = self.context['request'].user
        provider = validated_data.get('provider', 'deepseek')

        instance, _ = UserAPIKey.objects.update_or_create(
            user=user,
            provider=provider,
            defaults={'is_active': True},
        )
        instance.set_key(raw_key)
        instance.save()
        return instance