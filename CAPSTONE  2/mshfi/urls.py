from django.conf import settings
from django.conf.urls.static import static
from django.contrib import admin
from django.urls import path, include
from django.shortcuts import render, redirect


def landing_view(request):
    if request.user.is_authenticated:
        role_redirects = {
            'patient': '/patient/',
            'doctor': '/doctor/',
            'secretary': '/secretary/',
            'admin': '/admin-panel/',
        }
        return redirect(role_redirects.get(request.user.role, '/accounts/login/'))
    return render(request, 'landing.html')


def terms_view(request):
    return render(request, 'terms.html')


def privacy_view(request):
    return render(request, 'privacy.html')


def custom_404_view(request, exception=None):
    return render(request, '404.html', status=404)


def custom_500_view(request):
    return render(request, '500.html', status=500)


urlpatterns = [
    path('',               landing_view,                 name='landing'),
    path('terms/',         terms_view,                   name='terms'),
    path('privacy/',       privacy_view,                 name='privacy'),
    path('django-admin/',  admin.site.urls),
    path('accounts/',      include('accounts.urls')),
    path('patient/',       include('appointments.urls.patient_urls')),
    path('doctor/',        include('appointments.urls.doctor_urls')),
    path('secretary/',     include('appointments.urls.secretary_urls')),
    path('admin-panel/',   include('appointments.urls.admin_urls')),
    path('records/',       include('records.urls')),
    path('notifications/', include('notifications.urls')),
    path('feedback/',      include('feedback.urls')),
]

if settings.DEBUG:
    urlpatterns += static(settings.MEDIA_URL, document_root=settings.MEDIA_ROOT)

handler404 = 'mshfi.urls.custom_404_view'
handler500 = 'mshfi.urls.custom_500_view'
