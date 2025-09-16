"""
URL configuration for WBF project.

The `urlpatterns` list routes URLs to views. For more information please see:
    https://docs.djangoproject.com/en/5.2/topics/http/urls/
Examples:
Function views
    1. Add an import:  from my_app import views
    2. Add a URL to urlpatterns:  path('', views.home, name='home')
Class-based views
    1. Add an import:  from other_app.views import Home
    2. Add a URL to urlpatterns:  path('', Home.as_view(), name='home')
Including another URLconf
    1. Import the include() function: from django.urls import include, path
    2. Add a URL to urlpatterns:  path('blog/', include('blog.urls'))
"""
from django.contrib import admin
from django.urls import path, include
from django.conf import settings
from django.conf.urls.static import static
from accounts.views import post_login_redirect

urlpatterns = [
    path('admin/', admin.site.urls),
    path('accounts/', include('allauth.urls')),
    path('accounts/', include(('accounts.urls', 'benevoles'), namespace='benevoles')),
    path('notifications/', include(('notifications.urls', 'notifications'), namespace='notifications')),
    path('', include(('core.urls', 'core'), namespace='core')),
    path('staff/', include(('staff.urls', 'staff'), namespace='staff')),
    path("accounts/redirect/", post_login_redirect, name="post_login_redirect"),
    path("", include("legal.urls", namespace="legal")),
    path("pay/", include("payments.urls", namespace="payments")),

]

if settings.DEBUG:
    urlpatterns += static(settings.MEDIA_URL, document_root=settings.MEDIA_ROOT)
    
if settings.DEBUG:
    urlpatterns += [
        path("__reload__/", include("django_browser_reload.urls")),
    ]