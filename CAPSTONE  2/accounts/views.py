from django.shortcuts import render, redirect, get_object_or_404
from django.contrib.auth import authenticate, login, logout
from django.contrib import messages
from .forms import (
    PatientRegistrationForm, PatientProfileEditForm, DoctorProfileEditForm, SecretaryProfileEditForm,
    ProfilePictureForm, EmailNotificationSettingsForm,
)
from .models import CustomUser, PatientProfile, DoctorProfile, SecretaryProfile
from .decorators import role_required
from notifications.models import Notification


def _notify_admins(message):
    """New patient self-registrations happen with nobody on staff in the
    loop, unlike doctor/secretary accounts which admins create themselves.
    Let every admin account know one landed."""
    for admin_user in CustomUser.objects.filter(role='admin'):
        Notification.objects.create(user=admin_user, message=message)


def login_view(request):
    if request.user.is_authenticated:
        return _role_redirect(request.user)
    if request.method == 'POST':
        username = request.POST.get('username', '').strip()
        password = request.POST.get('password', '')
        user = authenticate(request, username=username, password=password)
        if user is not None:
            login(request, user)
            return _role_redirect(user)
        messages.error(request, 'Invalid username or password.')
    return render(request, 'accounts/login.html', {
        'register_form': PatientRegistrationForm(),
        'active_panel': 'login',
    })


def logout_view(request):
    if request.method == 'POST':
        logout(request)
    return redirect('accounts:login')


def register_view(request):
    if request.user.is_authenticated:
        return _role_redirect(request.user)
    form = PatientRegistrationForm(request.POST or None)
    if request.method == 'POST' and form.is_valid():
        user = form.save()
        login(request, user)
        _notify_admins(f"New patient account created: {user.get_full_name()} ({user.username}).")
        messages.success(request, 'Account created! Welcome to MSHFI.')
        return redirect('patient:dashboard')
    return render(request, 'accounts/register.html', {
        'register_form': form,
        'active_panel': 'register',
    })


PROFILE_VIEW_TEMPLATES = {
    'patient': 'accounts/profile_view_patient.html',
    'doctor': 'accounts/profile_view_doctor.html',
    'secretary': 'accounts/profile_view_secretary.html',
    'admin': 'accounts/profile_view_admin.html',
}

PROFILE_EDIT_TEMPLATES = {
    'patient': 'accounts/profile_edit_patient.html',
    'doctor': 'accounts/profile_edit_doctor.html',
    'secretary': 'accounts/profile_edit_secretary.html',
    'admin': 'accounts/profile_edit_admin.html',
}


@role_required('patient', 'doctor', 'secretary', 'admin')
def profile_view(request):
    profile = _get_profile(request.user)
    template = PROFILE_VIEW_TEMPLATES.get(request.user.role, 'accounts/profile_view_patient.html')
    return render(request, template, {'profile': profile})


@role_required('patient', 'doctor', 'secretary', 'admin')
def profile_edit_view(request):
    profile = _get_profile(request.user)
    FormClass = _get_profile_form(request.user)
    pic_form = ProfilePictureForm(request.POST or None, request.FILES or None, instance=request.user)
    template = PROFILE_EDIT_TEMPLATES.get(request.user.role, 'accounts/profile_edit_patient.html')
    modal_template = 'accounts/_profile_edit_modal.html'
    if FormClass is None:
        if request.method == 'POST' and pic_form.is_valid():
            pic_form.save()
            messages.success(request, 'Profile picture updated.')
            if request.htmx:
                response = render(request, modal_template, {'form': None, 'pic_form': pic_form, 'title': 'Edit Profile'})
                response['HX-Redirect'] = '/accounts/profile/'
                return response
            return redirect('accounts:profile_view')
        if request.htmx:
            return render(request, modal_template, {'form': None, 'pic_form': pic_form, 'title': 'Edit Profile'})
        return render(request, template, {'form': None, 'pic_form': pic_form})
    form = FormClass(request.POST or None, instance=profile)
    if request.method == 'POST' and form.is_valid() and pic_form.is_valid():
        # Also update first/last name on the user object
        first = request.POST.get('first_name', '').strip()
        last  = request.POST.get('last_name', '').strip()
        if first:
            request.user.first_name = first
        if last:
            request.user.last_name = last
        request.user.save()
        form.save()
        pic_form.save()
        messages.success(request, 'Profile updated.')
        if request.htmx:
            response = render(request, modal_template, {'form': form, 'pic_form': pic_form, 'title': 'Edit Profile'})
            response['HX-Redirect'] = '/accounts/profile/'
            return response
        return redirect('accounts:profile_view')
    if request.htmx:
        return render(request, modal_template, {'form': form, 'pic_form': pic_form, 'title': 'Edit Profile'})
    return render(request, template, {'form': form, 'pic_form': pic_form})


SETTINGS_TEMPLATES = {
    'patient': 'accounts/settings_patient.html',
    'doctor': 'accounts/settings_doctor.html',
    'secretary': 'accounts/settings_secretary.html',
    'admin': 'accounts/settings_admin.html',
}

HELP_TEMPLATES = {
    'patient': 'accounts/help_patient.html',
    'doctor': 'accounts/help_doctor.html',
    'secretary': 'accounts/help_secretary.html',
    'admin': 'accounts/help_admin.html',
}


@role_required('patient', 'doctor', 'secretary', 'admin')
def settings_view(request):
    if request.method == 'POST':
        form = EmailNotificationSettingsForm(request.POST, instance=request.user)
        if form.is_valid():
            form.save()
            messages.success(request, 'Settings updated.')
            return redirect('accounts:settings')
    else:
        form = EmailNotificationSettingsForm(instance=request.user)
    template = SETTINGS_TEMPLATES.get(request.user.role, 'accounts/settings_patient.html')
    return render(request, template, {'form': form})


@role_required('patient', 'doctor', 'secretary', 'admin')
def help_view(request):
    template = HELP_TEMPLATES.get(request.user.role, 'accounts/help_patient.html')
    return render(request, template)


def _role_redirect(user):
    mapping = {
        'patient':   '/patient/',
        'doctor':    '/doctor/',
        'secretary': '/secretary/',
        'admin':     '/admin-panel/',
    }
    from django.shortcuts import redirect as _redirect
    return _redirect(mapping.get(user.role, '/'))


def _get_profile(user):
    if user.role == 'patient':
        return getattr(user, 'patient_profile', None)
    if user.role == 'doctor':
        return getattr(user, 'doctor_profile', None)
    if user.role == 'secretary':
        return getattr(user, 'secretary_profile', None)
    return None


def _get_profile_form(user):
    if user.role == 'patient':
        return PatientProfileEditForm
    if user.role == 'doctor':
        return DoctorProfileEditForm
    if user.role == 'secretary':
        return SecretaryProfileEditForm
    return None
