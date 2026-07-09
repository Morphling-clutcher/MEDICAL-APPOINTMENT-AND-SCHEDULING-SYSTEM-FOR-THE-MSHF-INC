from django.shortcuts import render, redirect, get_object_or_404
from django.urls import reverse
from django.contrib import messages
from django.http import JsonResponse
from django.db import transaction
from datetime import date, datetime, timedelta
from django.db.models import Q, Count
from accounts.decorators import role_required
from appointments.models import Appointment, Schedule
from appointments.forms import AssignTimeForm
from accounts.models import CustomUser, PatientProfile
from notifications.email_utils import (
    send_cancellation_email, send_time_assigned_email, send_booking_confirmation_email
)
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
        status__in=['Pending Assignment', 'Scheduled', 'Confirmed', 'Rescheduled', 'Pending Reschedule']
    ).select_related('patient', 'doctor').order_by('appointment_time') if doctor else Appointment.objects.none()
    total_today = today_appts.count()
    pending_time_count = today_appts.filter(status='Pending Assignment').count() if doctor else 0

    trend_start = date.today() - timedelta(days=29)
    counts_by_date = {
        row['appointment_date']: row['c']
        for row in Appointment.objects.filter(
            doctor=doctor,
            appointment_date__gte=trend_start,
            appointment_date__lte=date.today(),
            status__in=['Scheduled', 'Confirmed', 'Rescheduled']
        ).values('appointment_date').annotate(c=Count('id'))
    } if doctor else {}
    trend = [
        {'date': (trend_start + timedelta(days=i)).isoformat(),
         'value': counts_by_date.get(trend_start + timedelta(days=i), 0)}
        for i in range(30)
    ]

    return {
        'userName': request.user.get_full_name() or request.user.username,
        'stats': [
            {'label': "Today's Appointments", 'value': total_today},
            {'label': "Awaiting Time Assignment", 'value': pending_time_count},
        ],
        'trend': trend,
        'trendLabel': 'Appointments',
        'appointmentsTitle': "Today's Appointments",
        'appointmentsHref': '/secretary/appointments/',
        'appointments': [
            {
                'primary': a.patient.get_full_name(),
                'secondary': f'Dr. {a.doctor.get_full_name()}',
                'date': a.appointment_date.isoformat(),
                'time': a.appointment_time.strftime('%H:%M') if a.appointment_time else None,
                'status': a.status,
            }
            for a in today_appts
        ],
        'quickActions': [
            {'title': 'Appointments', 'description': 'Approve or cancel requests', 'href': '/secretary/appointments/'},
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
    qs = Appointment.objects.filter(doctor=doctor).select_related('patient', 'doctor', 'patient_details') if doctor else Appointment.objects.none()
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
    appt = get_object_or_404(Appointment.objects.select_related('patient', 'doctor', 'patient_details'), pk=pk, doctor=doctor)
    return render(request, 'secretary/_appointment_detail_modal.html', {
        'appt': appt, 'title': 'Appointment Details', 'today': date.today(),
    })


def _working_hours_for_date(doctor, the_date):
    """Returns a list of (start_time, end_time) tuples — the doctor's
    Schedule blocks for that date — used to validate a staff-assigned time
    actually falls within working hours."""
    return list(
        Schedule.objects.filter(doctor=doctor, specific_date=the_date)
        .values_list('start_time', 'end_time')
    )


def _time_within_working_hours(the_time, blocks):
    return any(start <= the_time < end for start, end in blocks)


@role_required('secretary')
def assign_appointment_time(request, pk):
    """Secretary sets the actual time on an appointment that's either
    awaiting its first time assignment or had a reschedule date approved
    (both land in 'Pending Time Assignment'). Validates the chosen time
    falls within the doctor's working hours that day and doesn't conflict
    with another appointment, the same two things doctor_views' version of
    this action checks — both staff roles can do this."""
    doctor = _assigned_doctor(request.user)
    appt = get_object_or_404(
        Appointment, pk=pk, doctor=doctor, status__in=['Pending Assignment', 'Scheduled', 'Rescheduled']
    )
    blocks = _working_hours_for_date(appt.doctor, appt.appointment_date)

    if request.method == 'POST':
        form = AssignTimeForm(request.POST)
        if form.is_valid():
            new_time = form.cleaned_data['appointment_time']
            if not blocks:
                messages.error(request, "The doctor has no working hours set for this date.")
            elif not _time_within_working_hours(new_time, blocks):
                hours_display = ', '.join(
                    f"{s.strftime('%I:%M %p')}–{e.strftime('%I:%M %p')}" for s, e in blocks
                )
                messages.error(request, f"That time is outside the doctor's working hours ({hours_display}).")
            else:
                with transaction.atomic():
                    doctor_conflict = Appointment.objects.select_for_update().filter(
                        doctor=appt.doctor,
                        appointment_date=appt.appointment_date,
                        appointment_time=new_time,
                        status__in=['Scheduled', 'Rescheduled'],
                    ).exclude(pk=appt.pk).exists()
                    # A patient is free to have appointments with several
                    # different doctors — that's expected and allowed.
                    # What must never happen is the SAME patient ending up
                    # double-booked at the same date/time, even across two
                    # different doctors.
                    patient_conflict = Appointment.objects.select_for_update().filter(
                        patient=appt.patient,
                        appointment_date=appt.appointment_date,
                        appointment_time=new_time,
                        status__in=['Scheduled', 'Rescheduled'],
                    ).exclude(pk=appt.pk).exists()
                    conflict = doctor_conflict or patient_conflict
                    if doctor_conflict:
                        messages.error(request, 'The doctor already has another appointment at that time. Choose a different time.')
                    elif patient_conflict:
                        messages.error(request, 'This patient already has another appointment at that time with a different doctor. Choose a different time.')
                    else:
                        appt.appointment_time = new_time
                        appt.status = 'Scheduled'
                        appt.secretary = request.user
                        appt.save()

                if not conflict:
                    try:
                        send_time_assigned_email(appt)
                    except Exception:
                        pass
                    _notify(appt.patient,
                            f"Your appointment with Dr. {appt.doctor.get_full_name()} on "
                            f"{appt.appointment_date.strftime('%B %d, %Y')} is confirmed for "
                            f"{new_time.strftime('%I:%M %p')}.")
                    messages.success(request, 'Appointment time assigned. Patient notified.')
                    if request.htmx:
                        response = render(request, 'secretary/_assign_time_modal.html', {
                            'appt': appt, 'form': form, 'blocks': blocks,
                        })
                        response['HX-Redirect'] = '/secretary/appointments/'
                        return response
                    return redirect('secretary:appointment_list')
    else:
        form = AssignTimeForm()

    context = {'appt': appt, 'form': form, 'blocks': blocks, 'title': 'Assign Appointment Time'}
    if request.htmx:
        return render(request, 'secretary/_assign_time_modal.html', context)
    return render(request, 'secretary/assign_time.html', context)


@role_required('secretary')
def appointment_reschedule(request, pk):
    """Secretary reschedules a Scheduled appointment to a new date.
    This proactively changes the appointment date/time without requiring
    patient approval, different from patient-initiated reschedule requests."""
    doctor = _assigned_doctor(request.user)
    appt = get_object_or_404(
        Appointment, pk=pk, status__in=['Scheduled', 'Rescheduled'], doctor=doctor
    )
    blocks = _working_hours_for_date(appt.doctor, appt.appointment_date)

    if request.method == 'POST':
        new_date_str = request.POST.get('new_date')
        new_time_str = request.POST.get('new_time')
        if not new_date_str:
            messages.error(request, 'Please select a new date.')
        else:
            from datetime import datetime
            try:
                new_date = datetime.strptime(new_date_str, '%Y-%m-%d').date()
            except (ValueError, TypeError):
                messages.error(request, 'Invalid date format.')
                new_date = None

            if new_date:
                new_blocks = _working_hours_for_date(appt.doctor, new_date)
                if not new_blocks:
                    messages.error(request, f"Doctor has no working hours set for {new_date.strftime('%B %d, %Y')}.")
                elif new_time_str:
                    new_time = datetime.strptime(new_time_str, '%H:%M').time()
                    if not _time_within_working_hours(new_time, new_blocks):
                        hours_display = ', '.join(
                            f"{s.strftime('%I:%M %p')}–{e.strftime('%I:%M %p')}" for s, e in new_blocks
                        )
                        messages.error(request, f"That time is outside working hours ({hours_display}).")
                    else:
                        with transaction.atomic():
                            doctor_conflict = Appointment.objects.select_for_update().filter(
                                doctor=appt.doctor,
                                appointment_date=new_date,
                                appointment_time=new_time,
                                status__in=['Scheduled', 'Rescheduled'],
                            ).exclude(pk=appt.pk).exists()
                            patient_conflict = Appointment.objects.select_for_update().filter(
                                patient=appt.patient,
                                appointment_date=new_date,
                                appointment_time=new_time,
                                status__in=['Scheduled', 'Rescheduled'],
                            ).exclude(pk=appt.pk).exists()
                            conflict = doctor_conflict or patient_conflict
                            if doctor_conflict:
                                messages.error(request, 'Doctor already has an appointment at that time.')
                            elif patient_conflict:
                                messages.error(request, 'This patient already has another appointment at that time with a different doctor.')
                            else:
                                appt.appointment_date = new_date
                                appt.appointment_time = new_time
                                appt.status = 'Rescheduled'
                                appt.secretary = request.user
                                appt.save()
                                try:
                                    send_time_assigned_email(appt)
                                except Exception:
                                    pass
                                _notify(appt.patient,
                                        f"Your appointment with Dr. {appt.doctor.get_full_name()} has been rescheduled to "
                                        f"{appt.appointment_date.strftime('%B %d, %Y')} at {appt.appointment_time.strftime('%I:%M %p')}.")
                                messages.success(request, 'Appointment rescheduled. Patient notified.')
                                if request.htmx:
                                    response = render(request, 'secretary/_appointment_action_modal.html', {'appointment': appt, 'action': 'reschedule'})
                                    response['HX-Redirect'] = '/secretary/appointments/'
                                    return response
                                return redirect('secretary:appointment_list')
                else:
                    messages.error(request, 'Please select a time.')

    context = {'appt': appt, 'title': 'Reschedule Appointment'}
    if request.htmx:
        return render(request, 'secretary/_appointment_reschedule_modal.html', context)
    return render(request, 'secretary/appointment_reschedule.html', context)


@role_required('secretary')
def appointment_confirm(request, pk):
    """Secretary confirms the patient has arrived at the hospital.
    This action is only available for 'Scheduled' appointments and moves
    the status to 'Confirmed', signalling that the patient is present,
    vital signs assessment can begin, and the doctor consultation can proceed."""
    doctor = _assigned_doctor(request.user)
    appt = get_object_or_404(Appointment, pk=pk, status='Scheduled', doctor=doctor)
    if request.method == 'POST':
        appt.status = 'Confirmed'
        appt.secretary = request.user
        appt.save()
        _notify(appt.patient,
                f"You have been checked in for your appointment with Dr. {appt.doctor.get_full_name()} on "
                f"{appt.appointment_date.strftime('%B %d, %Y')} at "
                f"{appt.appointment_time.strftime('%I:%M %p') if appt.appointment_time else 'the scheduled time'}. "
                f"Please proceed for vital signs assessment.")
        messages.success(request, 'Patient confirmed as arrived. Vital signs assessment can now begin.')
        if request.htmx:
            response = render(request, 'secretary/_appointment_confirm_modal.html', {'appt': appt, 'action': 'confirm'})
            response['HX-Redirect'] = reverse('secretary:vitals_add', kwargs={'patient_id': appt.patient.pk})
            return response
        return redirect('secretary:vitals_add', patient_id=appt.patient.pk)
    if request.htmx:
        return render(request, 'secretary/_appointment_confirm_modal.html', {'appt': appt, 'action': 'confirm'})
    return render(request, 'secretary/appointment_confirm_action.html', {
        'appointment': appt, 'action': 'confirm'
    })


@role_required('secretary')
def appointment_cancel(request, pk):
    doctor = _assigned_doctor(request.user)
    appt = get_object_or_404(
        Appointment, pk=pk, status__in=['Pending Assignment', 'Scheduled'], doctor=doctor
    )
    mode = request.POST.get('mode') or request.GET.get('mode') or 'cancel'
    if request.method == 'POST':
        reason = request.POST.get('reason', '')
        # "Cancelled" = called off before the date; "No-Show" = the patient
        # simply didn't arrive for the appointment.
        appt.status = 'No-Show' if mode == 'no_show' else 'Cancelled'
        appt.secretary = request.user
        appt.save()
        try:
            send_cancellation_email(appt, reason)
        except Exception:
            pass
        if mode == 'no_show':
            _notify(appt.patient,
                    f"Your appointment with Dr. {appt.doctor.get_full_name()} on "
                    f"{appt.appointment_date.strftime('%B %d, %Y')} was marked as No-Show.")
            messages.success(request, 'Appointment marked as No-Show.')
        else:
            _notify(appt.patient,
                    f"Your appointment with Dr. {appt.doctor.get_full_name()} on "
                    f"{appt.appointment_date.strftime('%B %d, %Y')} was cancelled.")
            messages.success(request, 'Appointment cancelled and patient notified.')
        if request.htmx:
            response = render(request, 'secretary/_appointment_action_modal.html', {'appointment': appt, 'action': 'cancel', 'mode': mode})
            response['HX-Redirect'] = '/secretary/appointments/'
            return response
        return redirect('secretary:appointment_list')
    if request.htmx:
        return render(request, 'secretary/_appointment_action_modal.html', {'appointment': appt, 'action': 'cancel', 'mode': mode})
    return render(request, 'secretary/appointment_confirm_action.html', {
        'appointment': appt, 'action': 'cancel', 'mode': mode
    })


@role_required('secretary')
def appointment_complete(request, pk):
    """Secretary marks a Confirmed appointment as Completed after the
    consultation has finished. Only valid from 'Confirmed' status."""
    doctor = _assigned_doctor(request.user)
    appt = get_object_or_404(Appointment, pk=pk, status='Confirmed', doctor=doctor)
    if request.method == 'POST':
        appt.status = 'Completed'
        appt.secretary = request.user
        appt.save()
        _notify(appt.patient,
                f"Your appointment with Dr. {appt.doctor.get_full_name()} on "
                f"{appt.appointment_date.strftime('%B %d, %Y')} has been completed. "
                f"Thank you for visiting MSHFI Medical Clinic.")
        messages.success(request, 'Appointment marked as completed.')
        if request.htmx:
            response = render(request, 'secretary/_appointment_complete_modal.html', {'appt': appt})
            response['HX-Redirect'] = '/secretary/appointments/'
            return response
        return redirect('secretary:appointment_list')
    if request.htmx:
        return render(request, 'secretary/_appointment_complete_modal.html', {'appt': appt})
    return render(request, 'secretary/appointment_confirm_action.html', {
        'appointment': appt, 'action': 'complete'
    })


@role_required('secretary')
def appointment_reschedule_approve(request, pk):
    """Secretary approves a patient's pending reschedule request, scoped to
    their assigned doctor. Mirrors doctor_views' version: the new date
    becomes the appointment's date and status moves to
    'Pending Assignment' for someone to assign a time next."""

    doctor = _assigned_doctor(request.user)
    appt = get_object_or_404(Appointment, pk=pk, status='Pending Reschedule', doctor=doctor)
    if request.method == 'POST':
        appt.appointment_date = appt.requested_date
        appt.appointment_time = None
        if appt.requested_reason:
            appt.reason = appt.requested_reason
        appt.requested_date   = None
        appt.requested_time   = None
        appt.requested_reason = ''
        appt.status           = 'Pending Assignment'
        appt.secretary         = request.user
        appt.save()

        try:
            send_booking_received_email(appt)
        except Exception:
            pass
        _notify(appt.doctor,
                f"{request.user.get_full_name()} approved {appt.patient.get_full_name()}'s reschedule request to "
                f"{appt.appointment_date.strftime('%B %d, %Y')}. Awaiting time assignment.")
        _notify(appt.patient,
                f"Your reschedule request has been approved. New date: "
                f"{appt.appointment_date.strftime('%B %d, %Y')}. You'll be notified once the time is confirmed.")
        messages.success(request, 'Reschedule approved. Assign a time once ready.')
        if request.htmx:
            response = render(request, 'secretary/_reschedule_action_modal.html', {'appointment': appt, 'action': 'approve'})
            response['HX-Redirect'] = '/secretary/appointments/'
            return response
        return redirect('secretary:appointment_list')
    if request.htmx:
        return render(request, 'secretary/_reschedule_action_modal.html', {'appointment': appt, 'action': 'approve'})
    return render(request, 'secretary/reschedule_confirm_action.html', {'appointment': appt, 'action': 'approve'})


@role_required('secretary')
def appointment_reschedule_reject(request, pk):
    """Secretary rejects a patient's pending reschedule request: the
    appointment reverts to its original date/time/status, unchanged."""
    doctor = _assigned_doctor(request.user)
    appt = get_object_or_404(Appointment, pk=pk, status='Pending Reschedule', doctor=doctor)
    if request.method == 'POST':
        reason = request.POST.get('reason', '')
        requested_date = appt.requested_date
        appt.requested_date   = None
        appt.requested_time   = None
        appt.requested_reason = ''
        appt.status           = 'Scheduled'
        appt.secretary         = request.user
        appt.save()
        original_time_display = (
            f" at {appt.appointment_time.strftime('%I:%M %p')}" if appt.appointment_time else ''
        )
        _notify(appt.patient,
                f"Your request to reschedule your appointment to "
                f"{requested_date.strftime('%B %d, %Y') if requested_date else ''} was declined. "
                f"{('Reason: ' + reason) if reason else ''} Your original appointment on "
                f"{appt.appointment_date.strftime('%B %d, %Y')}{original_time_display} stays as is.")
        messages.success(request, 'Reschedule request declined. Patient notified, original appointment kept.')
        if request.htmx:
            response = render(request, 'secretary/_reschedule_action_modal.html', {'appointment': appt, 'action': 'reject'})
            response['HX-Redirect'] = '/secretary/appointments/'
            return response
        return redirect('secretary:appointment_list')
    if request.htmx:
        return render(request, 'secretary/_reschedule_action_modal.html', {'appointment': appt, 'action': 'reject'})
    return render(request, 'secretary/reschedule_confirm_action.html', {'appointment': appt, 'action': 'reject'})


@role_required('secretary')
def vitals_add(request, patient_id):
    patient = _get_accessible_patient_or_deny(request, patient_id)
    if patient is None:
        return redirect('secretary:patient_list')
    from records.forms import VitalSignForm
    from records.models import VitalSign
    form = VitalSignForm(request.POST or None, initial={'date_taken': date.today()})
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


def _schedule_calendar_context(doctor, year=None, month=None):
    """Build the same month-grid (with inline slots) that the doctor's
    'My Schedule' calendar uses, but read-only for the secretary."""
    from calendar import month_name
    from appointments.views.doctor_views import _compute_schedule_month_with_slots
    today = date.today()
    year = year or today.year
    month = month or today.month
    return {
        'calendar_weeks': _compute_schedule_month_with_slots(doctor, year, month) if doctor else [],
        'calendar_year': year,
        'calendar_month': month,
        'calendar_month_name': month_name[month],
        'today_iso': today.isoformat(),
    }


@role_required('secretary')
def view_all_schedules(request):
    doctor = _assigned_doctor(request.user)
    schedules = Schedule.objects.filter(doctor=doctor).order_by('specific_date', 'start_time') if doctor else Schedule.objects.none()
    context = {'schedules': schedules, 'doctor': doctor}
    context.update(_schedule_calendar_context(doctor))
    return render(request, 'secretary/schedules.html', context)


@role_required('secretary')
def schedule_grid_partial(request):
    """htmx endpoint: re-render the read-only availability calendar for
    a different month (Prev / Next navigation)."""
    doctor = _assigned_doctor(request.user)
    try:
        year = int(request.GET.get('year'))
        month = int(request.GET.get('month'))
    except (TypeError, ValueError):
        today = date.today()
        year, month = today.year, today.month
    context = {'doctor': doctor}
    context.update(_schedule_calendar_context(doctor, year, month))
    return render(request, 'secretary/_schedule_grid_readonly.html', context)


def _accessible_patient_ids(secretary):
    """Patients the secretary may see: only those who have (or had) an
    appointment with the secretary's assigned doctor."""
    doctor = _assigned_doctor(secretary)
    if not doctor:
        return Appointment.objects.none().values_list('patient_id', flat=True)
    return Appointment.objects.filter(doctor=doctor).values_list('patient_id', flat=True).distinct()


def _get_accessible_patient_or_deny(request, patient_id):
    """Fetch a patient only if they belong to the secretary's assigned
    doctor; otherwise return None (caller redirects with an error)."""
    patient = get_object_or_404(CustomUser, pk=patient_id, role='patient')
    if patient.pk not in set(_accessible_patient_ids(request.user)):
        messages.error(request, 'You do not have access to this patient.')
        return None
    return patient


@role_required('secretary')
def secretary_patient_list(request):
    search = request.GET.get('q', '')
    patients = CustomUser.objects.filter(role='patient', pk__in=_accessible_patient_ids(request.user))
    if search:
        patients = patients.filter(
            Q(first_name__icontains=search) | Q(last_name__icontains=search)
        )
    return render(request, 'secretary/patient_list.html', {
        'patients': patients.distinct(), 'search': search
    })


@role_required('secretary')
def patient_quickview(request, patient_id):
    patient = _get_accessible_patient_or_deny(request, patient_id)
    if patient is None:
        return redirect('secretary:patient_list')
    profile = getattr(patient, 'patient_profile', None)
    last_visit = Appointment.objects.filter(patient=patient).order_by('-appointment_date').first()
    return render(request, 'secretary/_patient_quickview_modal.html', {
        'patient': patient, 'profile': profile, 'last_visit': last_visit, 'title': 'Patient Summary',
    })


@role_required('secretary')
def secretary_patient_records(request, patient_id):
    patient = _get_accessible_patient_or_deny(request, patient_id)
    if patient is None:
        return redirect('secretary:patient_list')
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


@role_required('secretary')
def get_occupied_times(request, pk):
    """API endpoint returning occupied appointment times for a doctor on a specific date.
    Returns JSON with: {'occupied_times': [{'time': 'HH:MM', 'patient': 'Name', 'status': 'Scheduled'}], ...}"""
    doctor = _assigned_doctor(request.user)
    appt = get_object_or_404(
        Appointment, pk=pk, doctor=doctor, status__in=['Pending Assignment', 'Scheduled', 'Rescheduled']
    )

    occupied = Appointment.objects.filter(
        doctor=appt.doctor,
        appointment_date=appt.appointment_date,
        appointment_time__isnull=False,
        status__in=['Scheduled', 'Rescheduled', 'Confirmed'],
    ).exclude(pk=appt.pk).select_related('patient').values_list(
        'appointment_time', 'patient__first_name', 'patient__last_name', 'status'
    ).order_by('appointment_time')

    occupied_list = [
        {
            'time': time.strftime('%H:%M'),
            'time_display': time.strftime('%I:%M %p'),
            'patient': f"{first_name} {last_name}",
            'status': status,
        }
        for time, first_name, last_name, status in occupied
    ]

    return JsonResponse({
        'occupied_times': occupied_list,
        'appointment_id': pk,
    })
