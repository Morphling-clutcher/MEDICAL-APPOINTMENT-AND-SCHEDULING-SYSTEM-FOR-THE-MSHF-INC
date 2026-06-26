from django.shortcuts import render, redirect, get_object_or_404
from django.contrib import messages
from django.http import JsonResponse
from datetime import date
from django.db.models import Q
from accounts.decorators import role_required
from appointments.models import Appointment, Schedule
from accounts.models import CustomUser, PatientProfile
from notifications.email_utils import send_cancellation_email
from notifications.models import Notification


def _notify(user, message):
    Notification.objects.create(user=user, message=message)


def _assigned_doctor(user):
    profile = getattr(user, 'secretary_profile', None)
    return profile.assigned_doctor if profile else None


def _build_secretary_dashboard_data(request):
    doctor = _assigned_doctor(request.user)
    today_appts = Appointment.objects.filter(
        doctor=doctor,
        appointment_date=date.today(),
        status__in=['Scheduled', 'Rescheduled', 'Pending Reschedule']
    ).select_related('patient', 'doctor').order_by('appointment_time') if doctor else Appointment.objects.none()
    total_today = today_appts.count()

    return {
        'userName': request.user.get_full_name() or request.user.username,
        'stats': [
            {'label': "Today's Appointments", 'value': total_today},
        ],
        'appointmentsTitle': "Today's Appointments",
        'appointmentsHref': '/secretary/appointments/',
        'appointments': [
            {
                'primary': a.patient.get_full_name(),
                'secondary': f'Dr. {a.doctor.get_full_name()}',
                'date': a.appointment_date.isoformat(),
                'time': a.appointment_time.strftime('%H:%M'),
                'status': a.status,
            }
            for a in today_appts
        ],
        'quickActions': [
            {'title': 'Appointments', 'description': 'Approve or cancel requests', 'href': '/secretary/appointments/'},
            {'title': 'Walk-In Registration', 'description': 'Register a walk-in patient', 'href': '/secretary/walk-in/register/'},
            {'title': 'Doctor Profile', 'description': "View your doctor's info & availability", 'href': '/secretary/schedules/'},
            {'title': 'Patients', 'description': 'View patient list', 'href': '/secretary/patients/'},
        ],
    }


@role_required('secretary')
def secretary_dashboard(request):
    dashboard_data = _build_secretary_dashboard_data(request)
    return render(request, 'secretary/dashboard.html', {'dashboard_data': dashboard_data})


@role_required('secretary')
def secretary_dashboard_data(request):
    return JsonResponse(_build_secretary_dashboard_data(request))


@role_required('secretary')
def secretary_appointment_list(request):
    doctor = _assigned_doctor(request.user)
    status_filter = request.GET.get('status', '')
    date_filter   = request.GET.get('date', '')
    qs = Appointment.objects.filter(doctor=doctor).select_related('patient', 'doctor') if doctor else Appointment.objects.none()
    if status_filter:
        qs = qs.filter(status=status_filter)
    if date_filter:
        qs = qs.filter(appointment_date=date_filter)
    return render(request, 'secretary/appointment_list.html', {
        'appointments': qs.order_by('appointment_date', 'appointment_time'),
        'status_filter': status_filter, 'date_filter': date_filter,
        'assigned_doctor': doctor,
    })


@role_required('secretary')
def appointment_detail(request, pk):
    doctor = _assigned_doctor(request.user)
    appt = get_object_or_404(Appointment.objects.select_related('patient', 'doctor'), pk=pk, doctor=doctor)
    return render(request, 'secretary/_appointment_detail_modal.html', {
        'appt': appt, 'title': 'Appointment Details',
    })


@role_required('secretary')
def appointment_approve(request, pk):
    doctor = _assigned_doctor(request.user)
    appt = get_object_or_404(Appointment, pk=pk, status='Scheduled', doctor=doctor)
    if request.method == 'POST':
        appt.secretary = request.user
        appt.save()
        _notify(appt.patient,
                f"Your appointment with Dr. {appt.doctor.get_full_name()} on "
                f"{appt.appointment_date.strftime('%B %d, %Y')} has been confirmed by the secretary.")
        messages.success(request, 'Appointment approved.')
        if request.htmx:
            response = render(request, 'secretary/_appointment_action_modal.html', {'appointment': appt, 'action': 'approve'})
            response['HX-Redirect'] = '/secretary/appointments/'
            return response
        return redirect('secretary:appointment_list')
    if request.htmx:
        return render(request, 'secretary/_appointment_action_modal.html', {'appointment': appt, 'action': 'approve'})
    return render(request, 'secretary/appointment_confirm_action.html', {
        'appointment': appt, 'action': 'approve'
    })


@role_required('secretary')
def appointment_cancel(request, pk):
    doctor = _assigned_doctor(request.user)
    appt = get_object_or_404(Appointment, pk=pk, status__in=['Scheduled', 'Rescheduled'], doctor=doctor)
    if request.method == 'POST':
        reason = request.POST.get('reason', '')
        appt.status = 'Cancelled'
        appt.secretary = request.user
        appt.save()
        try:
            send_cancellation_email(appt, reason)
        except Exception:
            pass
        _notify(appt.patient,
                f"Your appointment with Dr. {appt.doctor.get_full_name()} on "
                f"{appt.appointment_date.strftime('%B %d, %Y')} was cancelled.")
        messages.success(request, 'Appointment cancelled and patient notified.')
        if request.htmx:
            response = render(request, 'secretary/_appointment_action_modal.html', {'appointment': appt, 'action': 'cancel'})
            response['HX-Redirect'] = '/secretary/appointments/'
            return response
        return redirect('secretary:appointment_list')
    if request.htmx:
        return render(request, 'secretary/_appointment_action_modal.html', {'appointment': appt, 'action': 'cancel'})
    return render(request, 'secretary/appointment_confirm_action.html', {
        'appointment': appt, 'action': 'cancel'
    })


@role_required('secretary')
def walkin_register(request):
    from accounts.forms import PatientRegistrationForm
    form = PatientRegistrationForm(request.POST or None)
    if request.method == 'POST' and form.is_valid():
        user = form.save()
        messages.success(request, f'Walk-in patient {user.get_full_name()} registered.')
        if request.htmx:
            response = render(request, 'secretary/_walkin_register_modal.html', {'form': form})
            response['HX-Redirect'] = f'/secretary/vitals/add/{user.pk}/'
            return response
        return redirect('secretary:vitals_add', patient_id=user.pk)
    if request.htmx:
        return render(request, 'secretary/_walkin_register_modal.html', {'form': form})
    return render(request, 'secretary/walkin_register.html', {'form': form})


@role_required('secretary')
def vitals_add(request, patient_id):
    patient = get_object_or_404(CustomUser, pk=patient_id, role='patient')
    from records.forms import VitalSignForm
    from records.models import VitalSign
    form = VitalSignForm(request.POST or None)
    if request.method == 'POST' and form.is_valid():
        vital = form.save(commit=False)
        vital.patient   = patient
        vital.secretary = request.user
        vital.save()
        messages.success(request, 'Vital signs recorded.')
        return redirect('secretary:patient_records', patient_id=patient.pk)
    vitals = VitalSign.objects.filter(patient=patient).order_by('-date_taken')
    return render(request, 'secretary/vitals_form.html', {
        'form': form, 'patient': patient, 'vitals': vitals
    })


@role_required('secretary')
def view_all_schedules(request):
    doctor = _assigned_doctor(request.user)
    schedules = Schedule.objects.filter(doctor=doctor).order_by('day_of_week', 'start_time') if doctor else Schedule.objects.none()
    return render(request, 'secretary/schedules.html', {
        'schedules': schedules, 'doctor': doctor
    })


@role_required('secretary')
def secretary_patient_list(request):
    search = request.GET.get('q', '')
    patients = CustomUser.objects.filter(role='patient')
    if search:
        patients = patients.filter(
            Q(first_name__icontains=search) | Q(last_name__icontains=search)
        )
    return render(request, 'secretary/patient_list.html', {
        'patients': patients.distinct(), 'search': search
    })


@role_required('secretary')
def patient_quickview(request, patient_id):
    patient = get_object_or_404(CustomUser, pk=patient_id, role='patient')
    profile = getattr(patient, 'patient_profile', None)
    last_visit = Appointment.objects.filter(patient=patient).order_by('-appointment_date').first()
    return render(request, 'secretary/_patient_quickview_modal.html', {
        'patient': patient, 'profile': profile, 'last_visit': last_visit, 'title': 'Patient Summary',
    })


@role_required('secretary')
def secretary_patient_records(request, patient_id):
    patient = get_object_or_404(CustomUser, pk=patient_id, role='patient')
    from records.models import MedicalRecords, VitalSign
    records = MedicalRecords.objects.filter(patient=patient).select_related('results', 'doctor')
    vitals  = VitalSign.objects.filter(patient=patient).order_by('-date_taken')
    appts   = Appointment.objects.filter(patient=patient).select_related('doctor').order_by('-appointment_date')
    return render(request, 'secretary/patient_records.html', {
        'patient': patient, 'records': records, 'vitals': vitals, 'appts': appts
    })


@role_required('secretary')
def secretary_notifications(request):
    return redirect('/notifications/')
