from django.contrib import admin
from django.urls import path, include

urlpatterns = [
    path('admin/', admin.site.urls),
    path('api/audio/', include('audioDiagnostic.urls')),
    path('', include('audioDiagnostic.urls')), 

]