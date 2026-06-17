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


urlpatterns = [
    path('',               landing_view,                 name='landing'),
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
