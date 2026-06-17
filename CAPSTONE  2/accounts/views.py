from django.shortcuts import render, redirect, get_object_or_404
from django.contrib.auth import authenticate, login, logout
from django.contrib import messages
from .forms import PatientRegistrationForm, PatientProfileEditForm, DoctorProfileEditForm
from .models import PatientProfile, DoctorProfile, SecretaryProfile
from .decorators import role_required


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
    return render(request, 'accounts/login.html')


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
        messages.success(request, 'Account created! Welcome to MSHFI.')
        return redirect('patient:dashboard')
    return render(request, 'accounts/register.html', {'form': form})


@role_required('patient', 'doctor', 'secretary', 'admin')
def profile_view(request):
    profile = _get_profile(request.user)
    return render(request, 'accounts/profile_view.html', {'profile': profile})


@role_required('patient', 'doctor', 'secretary', 'admin')
def profile_edit_view(request):
    profile = _get_profile(request.user)
    FormClass = _get_profile_form(request.user)
    if FormClass is None:
        messages.info(request, 'Profile editing is not available for your role.')
        return redirect('accounts:profile_view')
    form = FormClass(request.POST or None, instance=profile)
    if request.method == 'POST' and form.is_valid():
        # Also update first/last name on the user object
        first = request.POST.get('first_name', '').strip()
        last  = request.POST.get('last_name', '').strip()
        if first:
            request.user.first_name = first
        if last:
            request.user.last_name = last
        request.user.save()
        form.save()
        messages.success(request, 'Profile updated.')
        return redirect('accounts:profile_view')
    return render(request, 'accounts/profile_edit.html', {'form': form})


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
    return None
