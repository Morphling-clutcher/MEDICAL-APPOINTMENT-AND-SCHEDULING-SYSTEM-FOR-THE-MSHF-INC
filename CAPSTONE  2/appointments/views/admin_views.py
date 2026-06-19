from django.shortcuts import render, redirect, get_object_or_404
from django.contrib import messages
from django.db.models import Count, Avg
from datetime import date, timedelta
from accounts.decorators import role_required
from accounts.models import CustomUser, PatientProfile, DoctorProfile, SecretaryProfile
from accounts.forms import DoctorCreationForm, SecretaryCreationForm, UserEditForm
from appointments.models import Appointment
from feedback.models import Feedback


@role_required('admin')
def admin_dashboard(request):
    total_patients    = CustomUser.objects.filter(role='patient').count()
    total_doctors     = CustomUser.objects.filter(role='doctor').count()
    total_secretaries = CustomUser.objects.filter(role='secretary').count()
    total_appts       = Appointment.objects.count()
    today_appts       = Appointment.objects.filter(
        appointment_date=date.today(), status__in=['Scheduled', 'Rescheduled']
    ).count()
    avg_rating        = Feedback.objects.aggregate(avg=Avg('rating'))['avg']
    recent_appts      = Appointment.objects.select_related('patient', 'doctor').order_by('-created_at')[:10]

    trend_start = date.today() - timedelta(days=13)
    counts_by_date = {
        row['appointment_date']: row['c']
        for row in Appointment.objects.filter(
            appointment_date__gte=trend_start, appointment_date__lte=date.today()
        ).values('appointment_date').annotate(c=Count('id'))
    }
    trend = [
        {'date': (trend_start + timedelta(days=i)).isoformat(),
         'value': counts_by_date.get(trend_start + timedelta(days=i), 0)}
        for i in range(14)
    ]

    dashboard_data = {
        'stats': [
            {'label': 'Patients', 'value': total_patients},
            {'label': 'Doctors', 'value': total_doctors},
            {'label': 'Secretaries', 'value': total_secretaries},
            {'label': 'Total Appointments', 'value': total_appts},
            {'label': "Today's Appointments", 'value': today_appts},
            {'label': 'Average Rating', 'value': round(avg_rating, 1) if avg_rating else None, 'hint': 'out of 5'},
        ],
        'trend': trend,
        'trendLabel': 'Appointments',
        'appointmentsTitle': 'Recent Appointments',
        'appointmentsHref': '/admin-panel/appointments/',
        'appointments': [
            {
                'primary': a.patient.get_full_name(),
                'secondary': f'Dr. {a.doctor.get_full_name()}',
                'date': a.appointment_date.isoformat(),
                'status': a.status,
            }
            for a in recent_appts
        ],
        'quickActions': [
            {'title': '+ Doctor', 'href': '/admin-panel/users/create/?role=doctor'},
            {'title': '+ Secretary', 'href': '/admin-panel/users/create/?role=secretary'},
            {'title': 'View Appointments', 'href': '/admin-panel/appointments/'},
            {'title': 'View Feedback', 'href': '/admin-panel/feedback/'},
        ],
    }
    return render(request, 'admin_panel/dashboard.html', {'dashboard_data': dashboard_data})


@role_required('admin')
def user_list(request):
    role_filter = request.GET.get('role', '')
    search      = request.GET.get('q', '')
    users = CustomUser.objects.exclude(role='admin')
    if role_filter:
        users = users.filter(role=role_filter)
    if search:
        users = users.filter(first_name__icontains=search) | \
                CustomUser.objects.exclude(role='admin').filter(last_name__icontains=search) | \
                CustomUser.objects.exclude(role='admin').filter(username__icontains=search)
    return render(request, 'admin_panel/user_list.html', {
        'users': users.distinct().order_by('role', 'last_name'),
        'role_filter': role_filter, 'search': search,
    })


@role_required('admin')
def user_create(request):
    role = request.GET.get('role', 'doctor')
    FormClass = DoctorCreationForm if role == 'doctor' else SecretaryCreationForm
    form = FormClass(request.POST or None)
    if request.method == 'POST' and form.is_valid():
        user = form.save()
        messages.success(request, f'{user.get_full_name()} ({user.role}) account created.')
        return redirect('admin_panel:user_list')
    return render(request, 'admin_panel/user_create.html', {
        'form': form, 'role': role
    })


@role_required('admin')
def user_edit(request, pk):
    user = get_object_or_404(CustomUser, pk=pk)
    form = UserEditForm(request.POST or None, instance=user)
    if request.method == 'POST' and form.is_valid():
        form.save()
        messages.success(request, 'User updated.')
        return redirect('admin_panel:user_list')
    return render(request, 'admin_panel/user_edit.html', {'form': form, 'edited_user': user})


@role_required('admin')
def user_delete(request, pk):
    user = get_object_or_404(CustomUser, pk=pk)
    if request.method == 'POST':
        name = user.get_full_name()
        user.delete()
        messages.success(request, f'User {name} deleted.')
        return redirect('admin_panel:user_list')
    return render(request, 'admin_panel/user_confirm_delete.html', {'edited_user': user})


@role_required('admin')
def admin_appointment_list(request):
    status_filter = request.GET.get('status', '')
    qs = Appointment.objects.all().select_related('patient', 'doctor', 'secretary')
    if status_filter:
        qs = qs.filter(status=status_filter)
    return render(request, 'admin_panel/appointment_list.html', {
        'appointments': qs.order_by('-appointment_date', 'appointment_time'),
        'status_filter': status_filter,
    })


@role_required('admin')
def admin_feedback_list(request):
    feedbacks = Feedback.objects.all().select_related('patient', 'appointment').order_by('-date_submitted')
    avg_rating = feedbacks.aggregate(avg=Avg('rating'))['avg']
    return render(request, 'admin_panel/feedback_list.html', {
        'feedbacks': feedbacks, 'avg_rating': avg_rating
    })
