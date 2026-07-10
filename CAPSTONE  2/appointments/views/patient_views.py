from django.shortcuts import render, redirect, get_object_or_404
from django.urls import reverse
from django.contrib import messages
from django.db import transaction, models
from django.http import JsonResponse
from django.utils import timezone
from datetime import date, datetime, timedelta
import calendar as calendar_module
from accounts.decorators import role_required
from appointments.models import Appointment, Schedule, AppointmentPatientDetails
from appointments.forms import PatientDetailsForm
from accounts.models import CustomUser, PatientProfile, TERMS_VERSION
from notifications.email_utils import (
    send_booking_received_email, send_booking_confirmation_email, send_cancellation_email,
    send_reschedule_email, send_time_assigned_email
)
from notifications.models import Notification
from feedback.models import Feedback


def _notify(user, message):
    Notification.objects.create(user=user, message=message)


def _notify_assigned_secretaries_and_doctor(doctor, message):
    """A new pending-time appointment needs action from whoever gets to it
    first — the doctor or any secretary assigned to them — so both get
    notified rather than just one."""
    _notify(doctor, message)
    for secretary_profile in doctor.assigned_secretaries.select_related('user').all():
        if secretary_profile.user:
            _notify(secretary_profile.user, message)


def _compute_month_availability(doctor, year, month):
    """Build a day-by-day availability map for one calendar month, used to
    color the booking calendar green (the doctor works this day) or red
    (no schedule on this date), or past (unselectable).

    Patients only pick a DATE now — the actual time is assigned afterward
    by staff — so a date just needs at least one Schedule block to count
    as available. There's no slot-capacity check here anymore (that would
    require knowing time slots, which no longer exist on the booking
    side); double-booking is checked at time-assignment instead, where an
    actual time exists to compare against.

    Returns a list of week rows; each cell is either None (padding outside
    the month) or a dict: {day, date, status} where status is one of
    'available', 'unavailable', 'past'.
    """
    today = date.today()
    now_time = datetime.now().time()
    first_weekday, days_in_month = calendar_module.monthrange(year, month)
    month_start = date(year, month, 1)
    month_end   = date(year, month, days_in_month)

    working_dates = set(
        Schedule.objects.filter(
            doctor=doctor, specific_date__gte=month_start, specific_date__lte=month_end
        ).values_list('specific_date', flat=True)
    )
    # Today's own end times, so "today" can be marked unavailable once
    # the doctor's last working-hour block has already elapsed — e.g. a
    # patient browsing at 6 PM shouldn't be able to book "today" against
    # an 8 AM–12 PM schedule that's long over.
    today_end_times = list(
        Schedule.objects.filter(doctor=doctor, specific_date=today).values_list('end_time', flat=True)
    )

    weeks = []
    week = [None] * first_weekday
    for day_num in range(1, days_in_month + 1):
        current_date = date(year, month, day_num)
        if current_date < today:
            status = 'past'
        elif current_date == today:
            still_open = any(now_time < end for end in today_end_times)
            status = 'available' if (current_date in working_dates and still_open) else 'unavailable'
        elif current_date in working_dates:
            status = 'available'
        else:
            status = 'unavailable'
        week.append({'day': day_num, 'date': current_date.isoformat(), 'status': status})
        if len(week) == 7:
            weeks.append(week)
            week = []
    if week:
        week += [None] * (7 - len(week))
        weeks.append(week)

    return weeks


def _time_aware_greeting():
    hour = timezone.localtime().hour
    if hour < 12:
        return 'Good morning'
    if hour < 18:
        return 'Good afternoon'
    return 'Good evening'


def _build_patient_dashboard_data(request):
    upcoming = Appointment.objects.filter(
        patient=request.user,
        status__in=['Pending Assignment', 'Scheduled', 'Confirmed', 'Rescheduled', 'Pending Reschedule'],
        appointment_date__gte=date.today()
    ).select_related('doctor').order_by('appointment_date', 'appointment_time')[:5]
    past = Appointment.objects.filter(
        patient=request.user,
        status='Completed'
    ).select_related('doctor', 'results').order_by('-appointment_date')[:5]

    doctors_qs = CustomUser.objects.filter(role='doctor').select_related('doctor_profile')[:8]
    specializations = sorted({
        d.doctor_profile.specialization
        for d in doctors_qs
        if getattr(d, 'doctor_profile', None) and d.doctor_profile.specialization
    })

    # "Available Today / Tomorrow" pills on the featured doctor cards —
    # derived from real Schedule rows rather than hardcoded.
    today = date.today()
    tomorrow = today + timedelta(days=1)
    doctor_ids = [d.id for d in doctors_qs]
    available_today = set(
        Schedule.objects.filter(doctor_id__in=doctor_ids, specific_date=today)
        .values_list('doctor_id', flat=True)
    )
    available_tomorrow = set(
        Schedule.objects.filter(doctor_id__in=doctor_ids, specific_date=tomorrow)
        .values_list('doctor_id', flat=True)
    )

    def _availability(doctor_id):
        if doctor_id in available_today:
            return 'Available Today'
        if doctor_id in available_tomorrow:
            return 'Available Tomorrow'
        return None

    # The single highlighted "Upcoming Appointment" hero card.
    next_appt = upcoming[0] if upcoming else None
    hero_appointment = None
    if next_appt:
        doc_profile = getattr(next_appt.doctor, 'doctor_profile', None)
        hero_appointment = {
            'doctorName': f'Dr. {next_appt.doctor.get_full_name()}',
            'specialty': doc_profile.specialization if doc_profile else '',
            'photoUrl': next_appt.doctor.profile_picture.url if next_appt.doctor.profile_picture else None,
            'date': next_appt.appointment_date.isoformat(),
            'time': next_appt.appointment_time.strftime('%I:%M %p').lstrip('0') if next_appt.appointment_time else 'Time to be confirmed',
            'location': 'MSHFI Medical Clinic',
            'href': '/patient/appointments/?tab=upcoming',
        }

    return {
        'userName': request.user.get_full_name() or request.user.username,
        'userPhotoUrl': request.user.profile_picture.url if request.user.profile_picture else None,
        'unreadCount': Notification.objects.filter(user=request.user, is_read=False).count(),
        'greeting': _time_aware_greeting(),
        'heroAppointment': hero_appointment,
        'searchHref': '/patient/appointments/book/',
        'carouselSlides': [
            {
                'id': 'book',
                'title': 'Need to see a doctor?',
                'description': 'Book an appointment with our specialists in just a few taps.',
                'ctaLabel': 'Book Now',
                'href': '/patient/appointments/book/',
                'icon': 'calendar',
                'theme': 'navy',
            },
            {
                'id': 'doctors',
                'title': 'Meet our doctors',
                'description': f'{doctors_qs.count()} specialists ready to take care of you at MSHFI.',
                'ctaLabel': 'Browse Doctors',
                'href': '/patient/appointments/book/',
                'icon': 'doctors',
                'theme': 'teal',
            },
            {
                'id': 'records',
                'title': 'Your health, organized',
                'description': 'Keep track of past visits, results, and notes from your doctors.',
                'ctaLabel': 'View Records',
                'href': '/patient/records/',
                'icon': 'shield',
                'theme': 'violet',
            },
        ],
        'stats': [
            {'label': 'Upcoming Appointments', 'value': upcoming.count()},
            {'label': 'Completed Appointments', 'value': past.count()},
        ],
        'appointmentsTitle': 'Upcoming Appointments',
        'appointmentsHref': '/patient/appointments/?tab=upcoming',
        'appointments': [
            {
                'primary': f'Dr. {a.doctor.get_full_name()}',
                'secondary': a.reason or '',
                'date': a.appointment_date.isoformat(),
                'time': a.appointment_time.strftime('%H:%M') if a.appointment_time else None,
                'status': a.status,
            }
            for a in upcoming
        ],
        'pastAppointmentsTitle': 'Recent Completed Appointments',
        'pastAppointmentsHref': '/patient/appointments/?tab=completed',
        'pastAppointments': [
            {
                'primary': f'Dr. {a.doctor.get_full_name()}',
                'secondary': 'Completed' if a.status == 'Completed' else '',
                'date': a.appointment_date.isoformat(),
                'status': a.status,
            }
            for a in past
        ],
        'quickActions': [
            {'title': 'Book Appointment', 'description': 'Schedule a new visit', 'href': '/patient/appointments/book/'},
            {'title': 'My Appointments', 'description': 'View upcoming & past', 'href': '/patient/appointments/'},
            {'title': 'Medical Records', 'description': 'View your health history', 'href': '/patient/records/'},
        ],
        'categories': [
            {'name': spec, 'href': f'/patient/appointments/book/?q={spec}'}
            for spec in specializations
        ],
        'categoriesHref': '/patient/appointments/book/',
        'doctors': [
            {
                'id': str(d.id),
                'name': f'Dr. {d.get_full_name()}',
                'specialization': d.doctor_profile.specialization if getattr(d, 'doctor_profile', None) else '',
                'yearsExperience': d.doctor_profile.years_of_experience if getattr(d, 'doctor_profile', None) else None,
                'availability': _availability(d.id),
                'photoUrl': d.profile_picture.url if d.profile_picture else None,
                'href': f'/patient/doctors/{d.id}/',
            }
            for d in doctors_qs
        ],
        'doctorsHref': '/patient/appointments/book/',
    }


@role_required('patient')
def patient_dashboard(request):
    dashboard_data = _build_patient_dashboard_data(request)
    return render(request, 'patient/dashboard.html', {'dashboard_data': dashboard_data})


@role_required('patient')
def patient_dashboard_data(request):
    return JsonResponse(_build_patient_dashboard_data(request))


@role_required('patient')
def appointment_list(request):
    upcoming = Appointment.objects.filter(
        patient=request.user,
        status__in=['Pending Assignment', 'Scheduled', 'Confirmed', 'Rescheduled', 'Pending Reschedule']
    ).select_related('doctor', 'patient_details').order_by('appointment_date', 'appointment_time')
    completed = Appointment.objects.filter(
        patient=request.user,
        status='Completed'
    ).select_related('doctor', 'results', 'patient_details').order_by('-appointment_date')
    cancelled = Appointment.objects.filter(
        patient=request.user,
        status__in=['Cancelled', 'No-Show']
    ).select_related('doctor', 'patient_details').order_by('-appointment_date')
    completed_appointment_ids = set(completed.values_list('pk', flat=True))
    reviewed_appointment_ids = set(
        Feedback.objects.filter(
            patient=request.user, appointment_id__in=completed_appointment_ids
        ).values_list('appointment_id', flat=True)
    )
    return render(request, 'patient/appointment_list.html', {
        'upcoming': upcoming, 'completed': completed, 'cancelled': cancelled,
        'reviewed_appointment_ids': reviewed_appointment_ids,
    })


def _profile_incomplete_redirect(request):
    """Booking needs a complete patient record, but social-login (Google)
    signups arrive with an empty profile — the provider never supplies
    address or place of birth, which every other patient record here has.
    Rather than blocking these patients at login, booking is where the gap
    gets enforced: returns a redirect to the profile-edit page when either
    field is missing, or None when the profile is complete."""
    profile = getattr(request.user, 'patient_profile', None)
    if profile and profile.address.strip() and profile.place_of_birth.strip():
        return None
    messages.warning(
        request,
        'Please complete your profile (address and place of birth) before booking an appointment.'
    )
    return redirect('accounts:profile_edit')


@role_required('patient')
def book_step1(request):
    incomplete = _profile_incomplete_redirect(request)
    if incomplete:
        return incomplete
    doctors = CustomUser.objects.filter(role='doctor').select_related('doctor_profile').annotate(
        patient_count=models.Count('doctor_appointments__patient', distinct=True),
    )
    query = request.GET.get('q', '').strip()
    specialty = request.GET.get('specialty', '').strip()
    if query:
        doctors = doctors.filter(
            models.Q(first_name__icontains=query) |
            models.Q(last_name__icontains=query) |
            models.Q(doctor_profile__specialization__icontains=query)
        )
    if specialty:
        doctors = doctors.filter(doctor_profile__specialization=specialty)
    specializations = sorted({
        d.doctor_profile.specialization
        for d in CustomUser.objects.filter(role='doctor').select_related('doctor_profile')
        if getattr(d, 'doctor_profile', None) and d.doctor_profile.specialization
    })
    return render(request, 'patient/book_step1.html', {
        'doctors': doctors, 'query': query, 'specializations': specializations,
        'selected_specialty': specialty,
    })


@role_required('patient')
def doctor_profile_view(request, doctor_id):
    doctor = get_object_or_404(
        CustomUser.objects.annotate(
            patient_count=models.Count('doctor_appointments__patient', distinct=True),
        ),
        pk=doctor_id, role='doctor'
    )
    schedules = Schedule.objects.filter(
        doctor=doctor, specific_date__gte=date.today()
    ).order_by('specific_date', 'start_time')
    # Feedback (ratings/reviews) is intentionally not shown here — patients
    # and doctors don't see it; only admin does, via the admin feedback list.
    context = {'doctor': doctor, 'schedules': schedules, 'title': 'Doctor Profile'}
    if request.htmx:
        return render(request, 'patient/_doctor_profile_modal.html', context)
    return render(request, 'patient/doctor_profile.html', context)


def _format_date_str(selected_date_str):
    """Safely turn a 'YYYY-MM-DD' string into a display-friendly date, e.g.
    'Jun 29, 2026'. Django's |date template filter can't parse plain
    strings, so this is done in Python before reaching the template.
    Avoids the '%-d' / '%e' no-leading-zero strftime extensions since
    they aren't supported on Windows, which this project also runs on."""
    if not selected_date_str:
        return ''
    try:
        d = datetime.strptime(selected_date_str, '%Y-%m-%d').date()
        return f"{d.strftime('%b')} {d.day}, {d.year}"
    except ValueError:
        return selected_date_str


def _format_time_str(selected_time_str):
    """Same idea as _format_date_str but for a 'HH:MM:SS' time string,
    e.g. '09:00:00' -> '9:00 AM'."""
    if not selected_time_str:
        return ''
    try:
        t = datetime.strptime(selected_time_str, '%H:%M:%S').time()
        return t.strftime('%I:%M %p').lstrip('0')
    except ValueError:
        return selected_time_str


def _validate_booking_date(doctor, selected_date_str):
    """Patients pick a date only now — the time is assigned afterward by
    staff. This just confirms the date is choosable: not in the past, and
    the doctor actually has a Schedule block (working hours) that day."""
    error = None
    if selected_date_str:
        try:
            selected_date = datetime.strptime(selected_date_str, '%Y-%m-%d').date()
        except ValueError:
            return 'Invalid date format.', selected_date_str

        if selected_date < date.today():
            error = 'Cannot book an appointment in the past.'
        elif not Schedule.objects.filter(doctor=doctor, specific_date=selected_date).exists():
            error = 'The selected doctor has no schedule on this date.'

    return error, selected_date_str


def _resolve_calendar_month(request, selected_date_str):
    """Decide which year/month the calendar grid should show: an explicit
    ?year=&month= from month-navigation clicks takes priority, then the
    month containing the currently selected date, then today's month."""
    year_param  = request.GET.get('year')
    month_param = request.GET.get('month')
    if year_param and month_param:
        try:
            return int(year_param), int(month_param)
        except ValueError:
            pass
    if selected_date_str:
        try:
            d = datetime.strptime(selected_date_str, '%Y-%m-%d').date()
            return d.year, d.month
        except ValueError:
            pass
    today = date.today()
    return today.year, today.month


@role_required('patient')
def book_step2_slots(request, doctor_id):
    doctor = get_object_or_404(CustomUser, pk=doctor_id, role='doctor')
    selected_date_str = request.GET.get('date', '')
    error, selected_date_str = _validate_booking_date(doctor, selected_date_str)
    year, month = _resolve_calendar_month(request, selected_date_str)
    calendar_weeks = _compute_month_availability(doctor, year, month)

    context = {
        'doctor': doctor,
        'selected_date': selected_date_str,
        'selected_date_display': _format_date_str(selected_date_str),
        'error': error,
        'title': 'Choose a Date',
        'calendar_weeks': calendar_weeks,
        'calendar_year': year,
        'calendar_month': month,
        'calendar_month_name': calendar_module.month_name[month],
        'today_iso': date.today().isoformat(),
    }
    if request.htmx:
        return render(request, 'patient/_book_step2_modal.html', context)
    return render(request, 'patient/book_step2_slots.html', context)


@role_required('patient')
def book_step2_slots_partial(request, doctor_id):
    doctor = get_object_or_404(CustomUser, pk=doctor_id, role='doctor')
    selected_date_str = request.GET.get('date', '')
    error, selected_date_str = _validate_booking_date(doctor, selected_date_str)
    year, month = _resolve_calendar_month(request, selected_date_str)
    calendar_weeks = _compute_month_availability(doctor, year, month)
    return render(request, 'patient/_slot_grid_fragment.html', {
        'doctor': doctor, 'selected_date': selected_date_str,
        'selected_date_display': _format_date_str(selected_date_str),
        'error': error,
        'calendar_weeks': calendar_weeks,
        'calendar_year': year,
        'calendar_month': month,
        'calendar_month_name': calendar_module.month_name[month],
        'today_iso': date.today().isoformat(),
        'oob_calendar': True,
    })


@role_required('patient')
def book_step2_calendar_partial(request, doctor_id):
    """Re-renders just the calendar grid when the patient clicks the prev/next
    month arrows, without touching the (now stale) time-slot grid below it."""
    doctor = get_object_or_404(CustomUser, pk=doctor_id, role='doctor')
    year, month = _resolve_calendar_month(request, '')
    calendar_weeks = _compute_month_availability(doctor, year, month)
    return render(request, 'patient/_calendar_widget_fragment.html', {
        'doctor': doctor,
        'calendar_weeks': calendar_weeks,
        'calendar_year': year,
        'calendar_month': month,
        'calendar_month_name': calendar_module.month_name[month],
        'today_iso': date.today().isoformat(),
        'selected_date': request.GET.get('selected_date', ''),
    })


@role_required('patient')
def book_step3_who(request, doctor_id):
    """Step 3 of booking: 'Who is this for?'. Asks whether the patient is
    booking for themselves or someone else, shown right after the date
    selection and before the patient details form."""
    doctor = get_object_or_404(CustomUser, pk=doctor_id, role='doctor')
    # This step now runs right after "Book Now", BEFORE the date is chosen,
    # so appointment_date is normally empty here.
    appointment_date = request.GET.get('appointment_date') or ''

    if request.method == 'POST':
        for_whom = request.POST.get('for_whom', 'self')
        # Remember the choice for the rest of this booking flow.
        request.session['booking_for_whom'] = for_whom
        if appointment_date:
            # Backwards-compat: if a date was already picked (old deep links),
            # skip straight to the details step like before.
            return redirect(
                f"{reverse('patient:book_step4', kwargs={'doctor_id': doctor.pk})}"
                f"?appointment_date={appointment_date}&for_whom={for_whom}"
            )
        # Normal new flow: continue to date selection.
        return redirect('patient:book_step2', doctor_id=doctor.pk)

    context = {
        'doctor': doctor,
        'appointment_date': appointment_date,
        'title': 'Who is this for?',
    }
    if request.htmx:
        return render(request, 'patient/_book_step3_who_modal.html', context)
    return render(request, 'patient/book_step3_who.html', context)


def _patient_details_initial(user, for_whom='self'):
    """Builds initial form data for the Patient Details step.
    When for_whom='self' (default), pre-fills from the logged-in patient's
    account/profile. When for_whom='other', returns blank data since the
    person being booked is a different individual."""
    if for_whom != 'self':
        return {'relationship': 'Other'}
    profile = getattr(user, 'patient_profile', None)
    initial = {
        'first_name':  user.first_name,
        'last_name':   user.last_name,
        'email':       user.email,
        'relationship': 'Self',
    }
    if profile:
        initial.update({
            'middle_name':   profile.middle_name,
            'date_of_birth': profile.date_of_birth,
            'gender':        profile.gender,
            'address':       profile.address,
            'mobile_number': profile.contact_number,
        })
    return initial


# NOTE: _apply_patient_details_to_profile was intentionally removed.
# Appointment booking must NEVER overwrite the logged-in user's account
# data (first_name, last_name, email, PatientProfile fields), because a
# patient can book on behalf of a family member or dependent whose details
# are different from their own account. The appointment form data is
# captured exclusively in AppointmentPatientDetails (a durable per-
# appointment snapshot) and must not bleed back into CustomUser or
# PatientProfile. The logged-in account always remains unchanged.


def _patient_already_consented(user):
    profile = getattr(user, 'patient_profile', None)
    return bool(
        profile and profile.terms_accepted_at and profile.terms_accepted_version == TERMS_VERSION
    )


@role_required('patient')
def book_step4_details(request, doctor_id):
    """Step 4 of booking: Patient Details. Sits between the 'Who is this for?'
    step and the review/confirm step. Nothing is written to the database here
    — validated field values are carried forward as hidden form fields into
    the review step, where the actual Appointment row (and the permanent
    AppointmentPatientDetails snapshot) gets created on final confirm."""
    doctor = get_object_or_404(CustomUser, pk=doctor_id, role='doctor')
    appointment_date = request.POST.get('appointment_date') or request.GET.get('appointment_date', '')
    for_whom = (request.POST.get('for_whom') or request.GET.get('for_whom')
                or request.session.get('booking_for_whom', 'self'))

    if not appointment_date:
        # Can't proceed without knowing which date this is for.
        return redirect('patient:book_step2', doctor_id=doctor.pk)

    already_consented = _patient_already_consented(request.user)

    if request.method == 'POST':
        form = PatientDetailsForm(request.POST)
        # If the patient already has valid consent on file, don't force a
        # re-check on every booking — but if they're a first-time/legacy
        # patient or the policy version changed, the box is required.
        if already_consented:
            form.fields['terms_accepted'].required = False
        if for_whom != 'self':
            form.fields['relationship'].required = True
        if form.is_valid():
            context = {
                'doctor': doctor,
                'appointment_date': appointment_date,
                'appointment_date_display': _format_date_str(appointment_date),
                'details': form.cleaned_data,
                'already_consented': already_consented,
                'for_whom': for_whom,
                'title': 'Review Appointment',
            }
            if request.htmx:
                return render(request, 'patient/_book_step3_modal.html', context)
            return render(request, 'patient/book_step3_confirm.html', context)
        # Validation failed — redisplay with errors AND whatever the patient
        # already typed (Django forms keep submitted values automatically).
        messages.error(request, 'Please complete all required fields before continuing.')
    else:
        form = PatientDetailsForm(initial=_patient_details_initial(request.user, for_whom))
        if for_whom == 'self':
            form.fields['relationship'].required = False

    max_dob = (date.today() - timedelta(days=1)).isoformat()
    context = {
        'doctor': doctor,
        'appointment_date': appointment_date,
        'appointment_date_display': _format_date_str(appointment_date),
        'form': form,
        'already_consented': already_consented,
        'for_whom': for_whom,
        'max_dob': max_dob,
        'title': 'Patient Details',
    }
    if request.htmx:
        return render(request, 'patient/_book_step4_modal.html', context)
    return render(request, 'patient/book_step4_details.html', context)


@role_required('patient')
def book_step3_confirm(request):
    if request.method == 'POST':
        # Backstop for the profile-completion gate on book_step1 — a
        # bookmarked or hand-crafted confirm POST must not be able to
        # create an appointment for a patient with an incomplete profile.
        incomplete = _profile_incomplete_redirect(request)
        if incomplete:
            return incomplete

        doctor_id  = request.POST.get('doctor_id')
        date_str   = request.POST.get('appointment_date')

        try:
            doctor           = get_object_or_404(CustomUser, pk=doctor_id, role='doctor')
            appointment_date = datetime.strptime(date_str, '%Y-%m-%d').date()
        except (ValueError, TypeError):
            messages.error(request, 'Invalid booking data. Please try again.')
            return redirect('patient:book_step1')

        # Backstop for the calendar's own availability check — a tampered
        # or replayed POST must not be able to land on a date the doctor
        # doesn't actually work, a date already in the past, or "today"
        # after the doctor's last working-hour block for today has
        # already elapsed (nothing left to assign a time against).
        today = date.today()
        if appointment_date < today:
            messages.error(request, 'That date has already passed. Please pick another date.')
            return redirect('patient:book_step2', doctor_id=doctor.pk)
        day_blocks = list(
            Schedule.objects.filter(doctor=doctor, specific_date=appointment_date).values_list('end_time', flat=True)
        )
        if not day_blocks or (appointment_date == today and not any(datetime.now().time() < end for end in day_blocks)):
            messages.error(request, "That date is no longer available for this doctor. Please pick another date.")
            return redirect('patient:book_step2', doctor_id=doctor.pk)

        # Re-validate the patient-details fields here too, server-side —
        # the review screen only carries these as hidden inputs, so a
        # tampered or replayed POST must not be able to skip Step 4's
        # validation (required fields, DOB not in the future, mobile
        # number format, T&C checkbox).
        already_consented = _patient_already_consented(request.user)
        form = PatientDetailsForm(request.POST)
        if already_consented:
            form.fields['terms_accepted'].required = False
        if not form.is_valid():
            messages.error(request, 'Some patient details are missing or invalid. Please review and try again.')
            rel = request.POST.get('relationship', 'Self')
            for_whom = 'self' if rel == 'Self' else 'other'
            max_dob = (date.today() - timedelta(days=1)).isoformat()
            response_ctx = {
                'doctor': doctor,
                'appointment_date': date_str,
                'appointment_date_display': _format_date_str(date_str),
                'form': form,
                'already_consented': already_consented,
                'for_whom': for_whom,
                'max_dob': max_dob,
                'title': 'Patient Details',
            }
            if request.htmx:
                return render(request, 'patient/_book_step4_modal.html', response_ctx)
            return render(request, 'patient/book_step4_details.html', response_ctx)

        details = form.cleaned_data

        # No time-based conflict check here — there's no time yet. Staff
        # checks for double-booking when they assign the actual time
        # (see assign_appointment_time in doctor_views/secretary_views).
        with transaction.atomic():
            appointment = Appointment.objects.create(
                patient          = request.user,
                doctor           = doctor,
                appointment_date = appointment_date,
                appointment_time = None,
                status           = 'Pending Assignment',
                reason           = details['reason'],
            )

            terms_timestamp = timezone.now()
            AppointmentPatientDetails.objects.create(
                appointment      = appointment,
                first_name       = details['first_name'],
                middle_name      = details.get('middle_name', ''),
                last_name        = details['last_name'],
                date_of_birth    = details['date_of_birth'],
                gender           = details['gender'],
                address          = details['address'],
                mobile_number    = details['mobile_number'],
                email            = details.get('email', ''),
                chief_complaint  = details['reason'],
                relationship     = details.get('relationship', 'Self'),
                terms_accepted_at = terms_timestamp,
            )

            # IMPORTANT: Do NOT update CustomUser or PatientProfile here.
            # The details entered on the booking form belong to the *patient
            # being booked for* (which may be a family member, not the
            # account owner). Only the per-appointment snapshot above
            # (AppointmentPatientDetails) should receive that data.
            # The logged-in user's account information must remain unchanged.
            if not already_consented:
                profile, _created = PatientProfile.objects.get_or_create(user=request.user)
                profile.terms_accepted_at      = terms_timestamp
                profile.terms_accepted_version = TERMS_VERSION
                profile.save(update_fields=['terms_accepted_at', 'terms_accepted_version'])

        try:
            send_booking_received_email(appointment)
        except Exception:
            pass
        # Build a patient name for the notification. If the appointment is
        # for someone other than the account holder, mention both names so
        # staff know who the actual patient is.
        is_for_self = details.get('relationship', 'Self') == 'Self'
        patient_full_name = f"{details['first_name']} {details['last_name']}"
        if is_for_self:
            patient_identifier = request.user.get_full_name()
        else:
            patient_identifier = (
                f"{request.user.get_full_name()} (for {patient_full_name}"
                f" — {details.get('relationship', 'Other')})"
            )
        _notify_assigned_secretaries_and_doctor(
            doctor,
            f"{patient_identifier} requested an appointment with Dr. {doctor.get_full_name()} on "
            f"{appointment_date.strftime('%B %d, %Y')}. Awaiting time assignment."
        )
        _notify(request.user,
                f"Your appointment request with Dr. {doctor.get_full_name()} on "
                f"{appointment_date.strftime('%B %d, %Y')} has been received. "
                f"You'll be notified once the time is confirmed.")

        messages.success(request, 'Appointment request sent! You\'ll be notified once the time is confirmed.')
        if request.htmx:
            response = render(request, 'patient/_book_step3_modal.html', {
                'doctor': doctor, 'appointment_date': date_str,
                'title': 'Appointment Requested',
            })
            response['HX-Redirect'] = '/patient/appointments/'
            return response
        return redirect('patient:appointment_list')

    # GET: redirect back into the flow at Step 3 (Patient Details) — this
    # view no longer accepts a direct GET with just doctor/date, since
    # patient details must be collected first. Carries the date through
    # so the patient doesn't have to re-pick it.
    doctor_id  = request.GET.get('doctor_id')
    date_str   = request.GET.get('appointment_date')
    if not all([doctor_id, date_str]):
        return redirect('patient:book_step1')
    return redirect(
        f"{reverse('patient:book_step4', kwargs={'doctor_id': doctor_id})}"
        f"?appointment_date={date_str}"
    )


@role_required('patient')
def reschedule_appointment(request, pk):
    appointment = get_object_or_404(
        Appointment, pk=pk, patient=request.user, status__in=['Scheduled', 'Rescheduled']
    )
    if request.method == 'POST':
        date_str = request.POST.get('appointment_date')
        reason   = request.POST.get('reason', appointment.reason)
        try:
            new_date = datetime.strptime(date_str, '%Y-%m-%d').date()
        except (ValueError, TypeError):
            messages.error(request, 'Invalid date.')
            if request.htmx:
                return render(request, 'patient/_reschedule_modal.html', {'appointment': appointment, 'title': 'Reschedule Appointment'})
            return render(request, 'patient/reschedule.html', {'appointment': appointment})

        if new_date < date.today():
            messages.error(request, 'Cannot reschedule to a past date.')
            if request.htmx:
                return render(request, 'patient/_reschedule_modal.html', {'appointment': appointment, 'title': 'Reschedule Appointment'})
            return render(request, 'patient/reschedule.html', {'appointment': appointment})

        # No time-based conflict check here — the patient is only picking a
        # new date now. Whoever approves this (doctor or secretary) assigns
        # the actual time afterward, which is where double-booking against
        # other appointments actually gets checked.
        appointment.status            = 'Pending Reschedule'
        appointment.requested_date    = new_date
        appointment.requested_time    = None
        appointment.requested_reason  = reason
        appointment.save()

        _notify_assigned_secretaries_and_doctor(
            appointment.doctor,
            f"{appointment.patient.get_full_name()} requested to reschedule their appointment to "
            f"{new_date.strftime('%B %d, %Y')}. Awaiting approval."
        )
        _notify(request.user,
                f"Your reschedule request for {new_date.strftime('%B %d, %Y')} "
                f"has been sent to Dr. {appointment.doctor.get_full_name()}'s office for approval.")
        messages.success(request, 'Reschedule request sent. It will take effect once approved.')
        if request.htmx:
            response = render(request, 'patient/_reschedule_modal.html', {'appointment': appointment, 'title': 'Reschedule Appointment'})
            response['HX-Redirect'] = '/patient/appointments/'
            return response
        return redirect('patient:appointment_list')

    if request.htmx:
        return render(request, 'patient/_reschedule_modal.html', {'appointment': appointment, 'title': 'Reschedule Appointment'})
    return render(request, 'patient/reschedule.html', {'appointment': appointment})


@role_required('patient')
def appointment_detail(request, pk):
    appointment = get_object_or_404(
        Appointment.objects.select_related('doctor', 'doctor__doctor_profile', 'results', 'patient_details'), pk=pk, patient=request.user
    )
    medical_record = None
    if appointment.status == 'Completed':
        from records.models import ResultsConsultation
        try:
            medical_record = appointment.results.medical_records.first()
        except ResultsConsultation.DoesNotExist:
            medical_record = None
    return render(request, 'patient/_appointment_detail_modal.html', {
        'appointment': appointment, 'medical_record': medical_record, 'title': 'Appointment Details',
    })


@role_required('patient')
def cancel_appointment(request, pk):
    appointment = get_object_or_404(
        Appointment, pk=pk, patient=request.user,
        status__in=['Pending Assignment', 'Scheduled', 'Rescheduled']
    )
    if request.method == 'POST':
        appointment.status = 'Cancelled'
        appointment.save()
        try:
            send_cancellation_email(appointment)
        except Exception:
            pass
        _notify_assigned_secretaries_and_doctor(
            appointment.doctor,
            f"{appointment.patient.get_full_name()} cancelled their appointment on "
            f"{appointment.appointment_date.strftime('%B %d, %Y')}."
        )
        _notify(request.user,
                f"Your appointment with Dr. {appointment.doctor.get_full_name()} on "
                f"{appointment.appointment_date.strftime('%B %d, %Y')} has been cancelled.")
        messages.success(request, 'Appointment cancelled.')
        if request.htmx:
            response = render(request, 'patient/_cancel_confirm_modal.html', {'appointment': appointment})
            response['HX-Redirect'] = '/patient/appointments/'
            return response
        return redirect('patient:appointment_list')
    if request.htmx:
        return render(request, 'patient/_cancel_confirm_modal.html', {'appointment': appointment})
    return render(request, 'patient/cancel_confirm.html', {'appointment': appointment})


@role_required('patient')
def medical_records(request):
    from records.models import MedicalRecords, VitalSign
    records = MedicalRecords.objects.filter(
        patient=request.user
    ).select_related('doctor', 'results').order_by('-visit_date')
    vitals = VitalSign.objects.filter(patient=request.user).order_by('-date_taken')
    return render(request, 'patient/medical_records.html', {'records': records, 'vitals': vitals})


@role_required('patient')
def medical_record_detail(request, pk):
    from records.models import MedicalRecords
    record = get_object_or_404(
        MedicalRecords.objects.select_related('doctor', 'results').prefetch_related('results__prescriptions'),
        pk=pk, patient=request.user
    )
    return render(request, 'patient/_medical_record_detail_modal.html', {
        'record': record, 'title': 'Medical Record',
    })


@role_required('patient')
def patient_notifications(request):
    return redirect('/notifications/')
