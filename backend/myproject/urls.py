from django.contrib import admin
from django.urls import path, include

urlpatterns = [
    path('admin/', admin.site.urls),
    path('api/', include('audioDiagnostic.urls')),  # Changed to /api/ to match frontend expectations
    path('api/auth/', include('accounts.urls')),   # User authentication and billing
    path('', include('audioDiagnostic.urls')),     # Legacy support

]