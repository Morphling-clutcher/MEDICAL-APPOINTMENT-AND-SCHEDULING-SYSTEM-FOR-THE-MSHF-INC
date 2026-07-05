from django.shortcuts import render, redirect, get_object_or_404
from django.contrib import messages
from django.db.models import Count, Avg, Q
from django.http import JsonResponse, HttpResponse
from datetime import date, timedelta
from accounts.decorators import role_required
from accounts.models import CustomUser, PatientProfile, DoctorProfile, SecretaryProfile
from accounts.forms import DoctorCreationForm, SecretaryCreationForm, UserEditForm
from appointments.models import Appointment
from appointments.forms import AdminAppointmentEditForm
from feedback.models import Feedback


def _build_admin_dashboard_data(request):
    total_patients    = CustomUser.objects.filter(role='patient').count()
    total_doctors     = CustomUser.objects.filter(role='doctor').count()
    total_secretaries = CustomUser.objects.filter(role='secretary').count()
    total_appts       = Appointment.objects.count()
    today_appts       = Appointment.objects.filter(
        appointment_date=date.today(), status__in=['Pending Assignment', 'Scheduled', 'Confirmed', 'Rescheduled']
    ).count()
    avg_rating        = Feedback.objects.aggregate(avg=Avg('rating'))['avg']
    recent_appts      = Appointment.objects.select_related('patient', 'doctor').order_by('-created_at')[:10]

    trend_start = date.today() - timedelta(days=29)
    counts_by_date = {
        row['appointment_date']: row['c']
        for row in Appointment.objects.filter(
            appointment_date__gte=trend_start, appointment_date__lte=date.today()
        ).values('appointment_date').annotate(c=Count('id'))
    }
    trend = [
        {'date': (trend_start + timedelta(days=i)).isoformat(),
         'value': counts_by_date.get(trend_start + timedelta(days=i), 0)}
        for i in range(30)
    ]

    return {
        'userName': request.user.get_full_name() or request.user.username,
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
                'time': a.appointment_time.strftime('%H:%M') if a.appointment_time else None,
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


@role_required('admin')
def admin_dashboard(request):
    dashboard_data = _build_admin_dashboard_data(request)
    return render(request, 'admin_panel/dashboard.html', {'dashboard_data': dashboard_data})


@role_required('admin')
def admin_dashboard_data(request):
    return JsonResponse(_build_admin_dashboard_data(request))


@role_required('admin')
def user_list(request):
    role_filter = request.GET.get('role', '')
    search      = request.GET.get('q', '')
    users = CustomUser.objects.exclude(role='admin')
    if role_filter:
        users = users.filter(role=role_filter)
    if search:
        # Apply the search as an OR *within* the already role-filtered
        # queryset (via Q objects), instead of rebuilding fresh querysets
        # per field — the old version only re-applied exclude(role='admin')
        # on the 2nd/3rd clauses, silently dropping any role_filter.
        users = users.filter(
            Q(first_name__icontains=search) |
            Q(last_name__icontains=search) |
            Q(username__icontains=search)
        )
    return render(request, 'admin_panel/user_list.html', {
        'users': users.distinct().order_by('role', 'last_name'),
        'role_filter': role_filter, 'search': search,
    })


@role_required('admin')
def user_detail(request, pk):
    from accounts.views import _get_profile
    detail_user = get_object_or_404(CustomUser, pk=pk)
    profile = _get_profile(detail_user)
    return render(request, 'admin_panel/_user_detail_modal.html', {
        'detail_user': detail_user, 'profile': profile, 'title': 'User Details',
    })


@role_required('admin')
def user_create(request):
    role = request.GET.get('role', 'doctor')
    FormClass = DoctorCreationForm if role == 'doctor' else SecretaryCreationForm
    form = FormClass(request.POST or None)
    if request.method == 'POST' and form.is_valid():
        user = form.save()
        messages.success(request, f'{user.get_full_name()} ({user.role}) account created.')
        if request.htmx:
            response = render(request, 'admin_panel/_user_create_modal.html', {'form': form, 'role': role})
            response['HX-Redirect'] = '/admin-panel/users/'
            return response
        return redirect('admin_panel:user_list')
    if request.htmx:
        return render(request, 'admin_panel/_user_create_modal.html', {'form': form, 'role': role})
    return render(request, 'admin_panel/user_create.html', {'form': form, 'role': role})


@role_required('admin')
def user_edit(request, pk):
    user = get_object_or_404(CustomUser, pk=pk)
    form = UserEditForm(request.POST or None, instance=user)
    if request.method == 'POST' and form.is_valid():
        form.save()
        messages.success(request, 'User updated.')
        if request.htmx:
            response = render(request, 'admin_panel/_user_edit_modal.html', {'form': form, 'edited_user': user})
            response['HX-Redirect'] = '/admin-panel/users/'
            return response
        return redirect('admin_panel:user_list')
    if request.htmx:
        return render(request, 'admin_panel/_user_edit_modal.html', {'form': form, 'edited_user': user})
    return render(request, 'admin_panel/user_edit.html', {'form': form, 'edited_user': user})


@role_required('admin')
def user_delete(request, pk):
    user = get_object_or_404(CustomUser, pk=pk)
    if request.method == 'POST':
        name = user.get_full_name()
        user.delete()
        messages.success(request, f'User {name} deleted.')
        if request.htmx:
            # Don't re-render _user_delete_modal.html here: it builds a URL
            # from edited_user.pk, but Django sets pk to None on an instance
            # right after .delete() succeeds, which would throw a
            # NoReverseMatch. HX-Redirect makes htmx navigate away
            # immediately anyway, so the response body just needs to be
            # valid HTML — its content is never shown to the user.
            response = HttpResponse('')
            response['HX-Redirect'] = '/admin-panel/users/'
            return response
        return redirect('admin_panel:user_list')
    if request.htmx:
        return render(request, 'admin_panel/_user_delete_modal.html', {'edited_user': user})
    return render(request, 'admin_panel/user_confirm_delete.html', {'edited_user': user})


@role_required('admin')
def admin_appointment_list(request):
    qs = Appointment.objects.all().select_related('patient', 'doctor', 'secretary').order_by('-appointment_date', 'appointment_time')
    return render(request, 'admin_panel/appointment_list.html', {
        # "Scheduled" bucket covers every appointment that hasn't finished or
        # been cancelled yet (Pending Assignment, Scheduled, Confirmed,
        # Rescheduled, Pending Reschedule) — mirrors the patient-facing
        # "Upcoming" tab.
        'scheduled': qs.exclude(status__in=['Completed', 'Cancelled']),
        'completed': qs.filter(status='Completed'),
        'cancelled': qs.filter(status='Cancelled'),
    })


@role_required('admin')
def admin_appointment_detail(request, pk):
    appt = get_object_or_404(Appointment.objects.select_related('patient', 'doctor', 'secretary'), pk=pk)
    return render(request, 'admin_panel/_appointment_detail_modal.html', {
        'appt': appt, 'title': 'Appointment Details',
    })


@role_required('admin')
def admin_appointment_edit(request, pk):
    appt = get_object_or_404(Appointment, pk=pk)
    form = AdminAppointmentEditForm(request.POST or None, instance=appt)
    if request.method == 'POST' and form.is_valid():
        form.save()
        messages.success(request, 'Appointment updated.')
        if request.htmx:
            response = render(request, 'admin_panel/_appointment_edit_modal.html', {'form': form, 'appt': appt, 'title': 'Edit Appointment'})
            response['HX-Redirect'] = '/admin-panel/appointments/'
            return response
        return redirect('admin_panel:appointment_list')
    return render(request, 'admin_panel/_appointment_edit_modal.html', {
        'form': form, 'appt': appt, 'title': 'Edit Appointment',
    })


@role_required('admin')
def admin_feedback_list(request):
    feedbacks = Feedback.objects.all().select_related('patient', 'appointment').order_by('-date_submitted')
    avg_rating = feedbacks.aggregate(avg=Avg('rating'))['avg']
    return render(request, 'admin_panel/feedback_list.html', {
        'feedbacks': feedbacks, 'avg_rating': avg_rating
    })


@role_required('admin')
def admin_feedback_detail(request, pk):
    fb = get_object_or_404(Feedback.objects.select_related('patient', 'appointment', 'appointment__doctor'), pk=pk)
    return render(request, 'admin_panel/_feedback_detail_modal.html', {
        'fb': fb, 'title': 'Feedback Details',
    })
