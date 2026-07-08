from django.shortcuts import render, redirect, get_object_or_404
from django.template.loader import render_to_string
from django.urls import reverse
from django.contrib import messages
from django.db import transaction
from django.db.models import Count
from django.http import JsonResponse, HttpResponse
from datetime import date, datetime, timedelta
import calendar as calendar_module
from accounts.decorators import role_required
from appointments.models import Appointment, Schedule
from appointments.forms import ScheduleForm, RescheduleForm, AssignTimeForm, MultiDateScheduleForm
from accounts.models import CustomUser
from notifications.email_utils import (
    send_cancellation_email, send_reschedule_email, send_booking_received_email, send_time_assigned_email
)
from notifications.models import Notification


def _notify(user, message):
    Notification.objects.create(user=user, message=message)


def _notify_assigned_secretaries(doctor, message):
    """Notifies every secretary assigned to this doctor — a doctor can in
    principle have more than one, so this fans out to all of them rather
    than assuming a single secretary."""
    for secretary_profile in doctor.assigned_secretaries.select_related('user').all():
        if secretary_profile.user:
            _notify(secretary_profile.user, message)


def _format_date_str(selected_date_str):
    """Safely turn a 'YYYY-MM-DD' string into a display-friendly date, e.g.
    'Jun 29, 2026'. Mirrors the same helper on the patient booking side."""
    if not selected_date_str:
        return ''
    try:
        d = datetime.strptime(selected_date_str, '%Y-%m-%d').date()
        return f"{d.strftime('%b')} {d.day}, {d.year}"
    except ValueError:
        return selected_date_str


def _resolve_calendar_month(request, selected_date_str):
    """Decide which year/month the schedule calendar grid should show: an
    explicit ?year=&month= from month-navigation clicks takes priority,
    then the month containing the currently selected date, then today's
    month. Mirrors the same helper on the patient booking side."""
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


def _compute_schedule_month(doctor, year, month):
    """Build a day-by-day map for one calendar month, used to color the
    doctor's own 'Add Slot' calendar:
      has_slots = doctor already has one or more Schedule rows that day
      open      = no slot yet, but still a valid day to add one
      past      = before today, not selectable

    Returns a list of week rows; each cell is either None (padding outside
    the month) or a dict: {day, date, status}.
    """
    today = date.today()
    first_weekday, days_in_month = calendar_module.monthrange(year, month)
    month_start = date(year, month, 1)
    month_end   = date(year, month, days_in_month)

    dates_with_slots = set(
        Schedule.objects.filter(
            doctor=doctor,
            specific_date__gte=month_start,
            specific_date__lte=month_end,
        ).values_list('specific_date', flat=True)
    )

    weeks = []
    week = [None] * first_weekday
    for day in range(1, days_in_month + 1):
        d = date(year, month, day)
        if d < today:
            status = 'past'
        elif d in dates_with_slots:
            status = 'has_slots'
        else:
            status = 'open'
        week.append({'day': day, 'date': d.isoformat(), 'status': status})
        if len(week) == 7:
            weeks.append(week)
            week = []
    if week:
        week += [None] * (7 - len(week))
        weeks.append(week)
    return weeks


def _compute_schedule_month_with_slots(doctor, year, month):
    """Same grid as _compute_schedule_month, but each cell also carries its
    own actual Schedule rows (up to 3, plus a remaining count) so the
    desktop grid can show every day's time slots inline, always visible,
    without needing a click to reveal them."""
    today = date.today()
    first_weekday, days_in_month = calendar_module.monthrange(year, month)
    month_start = date(year, month, 1)
    month_end   = date(year, month, days_in_month)

    month_slots = Schedule.objects.filter(
        doctor=doctor,
        specific_date__gte=month_start,
        specific_date__lte=month_end,
    ).order_by('specific_date', 'start_time')

    slots_by_date = {}
    for s in month_slots:
        slots_by_date.setdefault(s.specific_date, []).append(s)

    PREVIEW_LIMIT = 3
    weeks = []
    week = [None] * first_weekday
    for day in range(1, days_in_month + 1):
        d = date(year, month, day)
        day_slots = slots_by_date.get(d, [])
        if d < today:
            status = 'past'
        elif day_slots:
            status = 'has_slots'
        else:
            status = 'open'
        week.append({
            'day': day, 'date': d.isoformat(), 'status': status,
            'slots': day_slots[:PREVIEW_LIMIT],
            'more_count': max(0, len(day_slots) - PREVIEW_LIMIT),
        })
        if len(week) == 7:
            weeks.append(week)
            week = []
    if week:
        week += [None] * (7 - len(week))
        weeks.append(week)
    return weeks


def _build_doctor_dashboard_data(request):
    today_appts = Appointment.objects.filter(
        doctor=request.user,
        appointment_date=date.today(),
        status__in=['Scheduled', 'Rescheduled', 'Pending Reschedule']
    ).select_related('patient').order_by('appointment_time')
    upcoming = Appointment.objects.filter(
        doctor=request.user,
        appointment_date__gt=date.today(),
        status__in=['Scheduled', 'Rescheduled']
    ).count()
    pending_reschedules = Appointment.objects.filter(
        doctor=request.user, status='Pending Reschedule'
    ).count()

    trend_start = date.today() - timedelta(days=29)
    counts_by_date = {
        row['appointment_date']: row['c']
        for row in Appointment.objects.filter(
            doctor=request.user, appointment_date__gte=trend_start, appointment_date__lte=date.today()
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
            {'label': "Today's Appointments", 'value': today_appts.count()},
            {'label': 'Upcoming Appointments', 'value': upcoming},
            {'label': 'Pending Reschedules', 'value': pending_reschedules},
        ],
        'trend': trend,
        'trendLabel': 'Appointments',
        'appointmentsTitle': "Today's Appointments",
        'appointmentsHref': '/doctor/appointments/',
        'appointments': [
            {
                'primary': a.patient.get_full_name(),
                'date': a.appointment_date.isoformat(),
                'time': a.appointment_time.strftime('%H:%M'),
                'status': a.status,
            }
            for a in today_appts
        ],
        'quickActions': [
            {'title': 'View Schedule', 'description': 'Manage your weekly hours', 'href': '/doctor/schedule/'},
            {'title': 'Appointment Requests', 'description': 'Accept, decline, or reschedule', 'href': '/doctor/appointments/'},
            {'title': 'My Patients', 'description': 'View patient records', 'href': '/doctor/patients/'},
        ],
    }


@role_required('doctor')
def doctor_dashboard(request):
    dashboard_data = _build_doctor_dashboard_data(request)
    return render(request, 'doctor/dashboard.html', {'dashboard_data': dashboard_data})


@role_required('doctor')
def doctor_dashboard_data(request):
    return JsonResponse(_build_doctor_dashboard_data(request))


@role_required('doctor')
def schedule_list(request):
    """Main 'My Schedule' page. Mobile shows a circle calendar with a
    separate day-detail panel below; desktop shows a full grid with every
    day's slots always visible inline, plus a sidebar that shows today's
    schedule by default and switches to show whichever day is clicked."""
    selected_date_str = request.GET.get('date') or date.today().isoformat()
    year, month = _resolve_calendar_month(request, selected_date_str)
    calendar_weeks = _compute_schedule_month(request.user, year, month)
    calendar_weeks_with_slots = _compute_schedule_month_with_slots(request.user, year, month)

    selected_slots = []
    try:
        the_date = datetime.strptime(selected_date_str, '%Y-%m-%d').date()
        selected_slots = list(
            Schedule.objects.filter(doctor=request.user, specific_date=the_date).order_by('start_time')
        )
    except ValueError:
        pass

    context = {
        'calendar_weeks': calendar_weeks,
        'calendar_weeks_with_slots': calendar_weeks_with_slots,
        'calendar_year': year, 'calendar_month': month,
        'calendar_month_name': calendar_module.month_name[month],
        'today_iso': date.today().isoformat(),
        'selected_date': selected_date_str,
        'selected_date_display': _format_date_str(selected_date_str),
        'selected_slots': selected_slots,
    }
    context.update(_panel_context_for_date(request.user, selected_date_str))
    return render(request, 'doctor/schedule_list.html', context)


@role_required('doctor')
def schedule_calendar_partial(request):
    """Re-renders just the calendar grid on the main schedule page when the
    doctor clicks the prev/next month arrows. The day-detail panel below
    is untouched by this — it's a separate htmx target."""
    selected_date_str = request.GET.get('date', '')
    year, month = _resolve_calendar_month(request, selected_date_str)
    calendar_weeks = _compute_schedule_month(request.user, year, month)
    return render(request, 'doctor/_schedule_main_calendar_fragment.html', {
        'calendar_weeks': calendar_weeks,
        'calendar_year': year, 'calendar_month': month,
        'calendar_month_name': calendar_module.month_name[month],
        'today_iso': date.today().isoformat(),
        'selected_date': selected_date_str,
    })


def _panel_context_for_date(doctor, date_str):
    """Builds the context the sidebar panel needs for a given date: its
    slots, a friendly display string, whether it's today, and the plain
    iso string used for the Add/Edit/Delete links."""
    today = date.today()
    the_date = today
    if date_str:
        try:
            the_date = datetime.strptime(date_str, '%Y-%m-%d').date()
        except ValueError:
            the_date = today
    slots = list(
        Schedule.objects.filter(doctor=doctor, specific_date=the_date).order_by('start_time')
    )
    return {
        'panel_date_iso': the_date.isoformat(),
        'panel_date_display': _format_date_str(the_date.isoformat()),
        'panel_slots': slots,
        'panel_is_today': the_date == today,
    }


@role_required('doctor')
def schedule_grid_partial(request):
    """Desktop-only rectangular grid calendar (see _schedule_grid_desktop.html).
    Every day's time slots are always visible right inside that day's own
    cell. Clicking a day re-renders this grid (so the clicked day shows as
    selected) AND rides an out-of-band swap along in the same response to
    update the 'Today's Schedule' sidebar with that day's full detail
    (add/edit/delete) instead — no modal, matching the old below-the-
    calendar panel's behavior but positioned on the right."""
    selected_date_str = request.GET.get('date') or date.today().isoformat()
    year, month = _resolve_calendar_month(request, selected_date_str)
    calendar_weeks = _compute_schedule_month_with_slots(request.user, year, month)

    grid_html = render_to_string('doctor/_schedule_grid_desktop.html', {
        'calendar_weeks': calendar_weeks,
        'calendar_year': year, 'calendar_month': month,
        'calendar_month_name': calendar_module.month_name[month],
        'today_iso': date.today().isoformat(),
        'selected_date': selected_date_str,
    }, request=request)
    panel_html = render_to_string('doctor/_schedule_selected_day_panel.html', {
        'oob': True,
        **_panel_context_for_date(request.user, selected_date_str),
    }, request=request)
    return HttpResponse(grid_html + panel_html)


@role_required('doctor')
def schedule_day_detail(request):
    """Action-capable version of the day-info panel: fetched whenever the
    doctor clicks a date on the main schedule calendar. Unlike
    _schedule_day_info.html (read-only, used inside the Add Slot modal),
    this one lets the doctor edit or remove each slot right from the
    panel, and add a new one already scoped to this date."""
    date_str = request.GET.get('date', '')
    slots = []
    if date_str:
        try:
            the_date = datetime.strptime(date_str, '%Y-%m-%d').date()
            slots = list(
                Schedule.objects.filter(doctor=request.user, specific_date=the_date).order_by('start_time')
            )
        except ValueError:
            pass
    return render(request, 'doctor/_schedule_day_detail.html', {
        'date_str': date_str,
        'date_display': _format_date_str(date_str),
        'slots': slots,
    })


@role_required('doctor')
def schedule_day_info(request):
    """Returns just the 'existing slots on this date' info panel, fetched
    whenever the doctor clicks a day on the Add Slot calendar. Kept
    separate from the multi-select toggle itself (which is pure
    client-side JS) so clicking a day never re-renders the whole modal or
    loses whatever other days are already selected."""
    date_str = request.GET.get('date', '')
    existing = []
    if date_str:
        try:
            the_date = datetime.strptime(date_str, '%Y-%m-%d').date()
            existing = list(
                Schedule.objects.filter(doctor=request.user, specific_date=the_date)
                .order_by('start_time')
            )
        except ValueError:
            pass
    return render(request, 'doctor/_schedule_day_info.html', {
        'date_str': date_str,
        'date_display': _format_date_str(date_str),
        'existing_slots': existing,
    })


@role_required('doctor')
def schedule_add(request):
    """Add Slot now accepts MULTIPLE dates at once — the doctor multi-selects
    days on the calendar (pure client-side toggle, see the JS in
    _schedule_calendar_fragment.html) and applies one start/end time to
    all of them in a single submit. Each date is checked for overlap
    independently: a date that already has a conflicting slot is skipped
    (not saved) while every other selected date still gets its slot, and
    the doctor sees exactly which ones succeeded vs were skipped and why."""
    selected_dates_str = request.POST.get('dates') or request.GET.get('date', '')
    # GET (just opening the modal) only ever carries one date so far, from
    # a single calendar click — that's fine, it seeds the multi-select
    # with one day already toggled on.
    year, month = _resolve_calendar_month(request, selected_dates_str.split(',')[0] if selected_dates_str else '')
    calendar_weeks = _compute_schedule_month(request.user, year, month)

    if request.method == 'POST':
        form = MultiDateScheduleForm(request.POST)
        if form.is_valid():
            target_dates = form.cleaned_data['dates']
            start_time   = form.cleaned_data['start_time']
            end_time     = form.cleaned_data['end_time']

            saved_dates  = []
            skipped      = []  # list of (date, reason) tuples
            with transaction.atomic():
                for d in target_dates:
                    overlap = Schedule.objects.filter(
                        doctor=request.user, specific_date=d,
                        start_time__lt=end_time, end_time__gt=start_time,
                    ).exists()
                    if overlap:
                        skipped.append((d, 'overlaps with an existing slot on that date'))
                        continue
                    Schedule.objects.create(
                        doctor=request.user, specific_date=d,
                        start_time=start_time, end_time=end_time,
                    )
                    saved_dates.append(d)

            if saved_dates:
                dates_display = ', '.join(d.strftime('%b %d') for d in saved_dates)
                _notify_assigned_secretaries(
                    request.user,
                    f"Dr. {request.user.get_full_name()} added schedule slots on "
                    f"{dates_display} ({start_time.strftime('%I:%M %p')}–{end_time.strftime('%I:%M %p')})."
                )
            if saved_dates and not skipped:
                messages.success(request, f"Added the slot to {len(saved_dates)} date(s).")
            elif saved_dates and skipped:
                skipped_display = ', '.join(d.strftime('%b %d') for d, _r in skipped)
                messages.success(
                    request,
                    f"Added the slot to {len(saved_dates)} date(s). "
                    f"Skipped {len(skipped)} that already had an overlapping slot: {skipped_display}."
                )
            elif not saved_dates:
                skipped_display = ', '.join(d.strftime('%b %d') for d, _r in skipped)
                conflict_msg = f"This schedule conflicts with an existing time slot on {skipped_display}. Please choose a different time."
                form.add_error(None, conflict_msg)
                messages.error(request, f"No slots were added — every selected date already has an overlapping slot ({skipped_display}).")

            if saved_dates:
                if request.htmx:
                    response = render(request, 'doctor/_schedule_modal.html', {'form': MultiDateScheduleForm(), 'action': 'Add'})
                    response['HX-Redirect'] = f'/doctor/schedule/?date={saved_dates[-1].isoformat()}'
                    return response
                return redirect(f"{reverse('doctor:schedule_list')}?date={saved_dates[-1].isoformat()}")
            # Nothing saved at all — fall through and re-show the form
            # with the same dates still selected so the doctor can pick a
            # different time without having to re-select every day.
    else:
        form = MultiDateScheduleForm(initial={'dates': selected_dates_str})

    context = {
        'form': form, 'action': 'Add',
        'selected_dates': selected_dates_str,
        'selected_dates_list': [s for s in selected_dates_str.split(',') if s],
        'calendar_weeks': calendar_weeks,
        'calendar_year': year, 'calendar_month': month,
        'calendar_month_name': calendar_module.month_name[month],
        'today_iso': date.today().isoformat(),
    }
    if request.htmx:
        return render(request, 'doctor/_schedule_modal.html', context)
    return render(request, 'doctor/schedule_form.html', context)


@role_required('doctor')
def schedule_add_calendar_partial(request):
    """Re-renders just the calendar grid inside the Add Slot modal when the
    doctor clicks the prev/next month arrows. The full multi-select set
    (selected_dates, comma-joined) is carried through via querystring so
    navigating months never loses days already picked in another month —
    the selection itself lives in the page via a hidden input the JS
    toggle maintains, this param just lets the freshly-rendered grid know
    which days (if any, in the now-visible month) to paint as selected."""
    selected_dates_str = request.GET.get('selected_dates', '')
    first_date = selected_dates_str.split(',')[0] if selected_dates_str else ''
    year, month = _resolve_calendar_month(request, first_date)
    calendar_weeks = _compute_schedule_month(request.user, year, month)
    return render(request, 'doctor/_schedule_calendar_fragment.html', {
        'calendar_weeks': calendar_weeks,
        'calendar_year': year, 'calendar_month': month,
        'calendar_month_name': calendar_module.month_name[month],
        'today_iso': date.today().isoformat(),
        'selected_dates_list': [s for s in selected_dates_str.split(',') if s],
        'multi_select': True,
    })


@role_required('doctor')
def schedule_edit(request, pk):
    schedule = get_object_or_404(Schedule, pk=pk, doctor=request.user)
    selected_date_str = (
        request.POST.get('specific_date')
        or request.GET.get('date')
        or schedule.specific_date.isoformat()
    )
    year, month = _resolve_calendar_month(request, selected_date_str)
    calendar_weeks = _compute_schedule_month(request.user, year, month)

    form = ScheduleForm(request.POST or None, instance=schedule, initial={'specific_date': selected_date_str})
    if request.method == 'POST' and form.is_valid():
        updated = form.save(commit=False)
        overlap = Schedule.objects.filter(
            doctor=request.user,
            specific_date=updated.specific_date,
            start_time__lt=updated.end_time,
            end_time__gt=updated.start_time,
        ).exclude(pk=pk).exists()
        if overlap:
            form.add_error(None, 'This schedule conflicts with an existing time slot on that date. Please choose a different time.')
            messages.error(request, 'This schedule overlaps with an existing one on that date.')
            if request.htmx:
                return render(request, 'doctor/_schedule_modal.html', {
                    'form': form, 'action': 'Edit', 'schedule': schedule,
                    'selected_date': selected_date_str,
                    'selected_date_display': _format_date_str(selected_date_str),
                    'calendar_weeks': calendar_weeks,
                    'calendar_year': year, 'calendar_month': month,
                    'calendar_month_name': calendar_module.month_name[month],
                    'today_iso': date.today().isoformat(),
                })
        else:
            old_date, old_start, old_end = schedule.specific_date, schedule.start_time, schedule.end_time
            updated.save()
            _notify_assigned_secretaries(
                request.user,
                f"Dr. {request.user.get_full_name()} updated a schedule slot: "
                f"{old_date.strftime('%b %d, %Y')} {old_start.strftime('%I:%M %p')}–{old_end.strftime('%I:%M %p')} "
                f"is now {updated.specific_date.strftime('%b %d, %Y')} "
                f"{updated.start_time.strftime('%I:%M %p')}–{updated.end_time.strftime('%I:%M %p')}."
            )
            messages.success(request, 'Schedule updated.')
            if request.htmx:
                response = render(request, 'doctor/_schedule_modal.html', {'form': form, 'action': 'Edit'})
                response['HX-Redirect'] = f'/doctor/schedule/?date={updated.specific_date.isoformat()}'
                return response
            return redirect(f"{reverse('doctor:schedule_list')}?date={updated.specific_date.isoformat()}")

    context = {
        'form': form, 'action': 'Edit', 'schedule': schedule,
        'selected_date': selected_date_str,
        'selected_date_display': _format_date_str(selected_date_str),
        'calendar_weeks': calendar_weeks,
        'calendar_year': year, 'calendar_month': month,
        'calendar_month_name': calendar_module.month_name[month],
        'today_iso': date.today().isoformat(),
    }
    if request.htmx:
        return render(request, 'doctor/_schedule_modal.html', context)
    return render(request, 'doctor/schedule_form.html', context)


@role_required('doctor')
def schedule_edit_calendar_partial(request, pk):
    """Re-renders just the calendar grid inside the Edit Slot modal when the
    doctor clicks the prev/next month arrows."""
    schedule = get_object_or_404(Schedule, pk=pk, doctor=request.user)
    selected_date_str = request.GET.get('selected_date', '')
    year, month = _resolve_calendar_month(request, '')
    calendar_weeks = _compute_schedule_month(request.user, year, month)
    return render(request, 'doctor/_schedule_calendar_fragment.html', {
        'calendar_weeks': calendar_weeks,
        'calendar_year': year, 'calendar_month': month,
        'calendar_month_name': calendar_module.month_name[month],
        'today_iso': date.today().isoformat(),
        'selected_date': selected_date_str,
        'schedule': schedule,
    })


@role_required('doctor')
def schedule_delete(request, pk):
    schedule = get_object_or_404(Schedule, pk=pk, doctor=request.user)
    if request.method == 'POST':
        removed_date, removed_start, removed_end = (
            schedule.specific_date, schedule.start_time, schedule.end_time
        )
        schedule.delete()
        _notify_assigned_secretaries(
            request.user,
            f"Dr. {request.user.get_full_name()} removed the schedule slot on "
            f"{removed_date.strftime('%B %d, %Y')} "
            f"({removed_start.strftime('%I:%M %p')}–{removed_end.strftime('%I:%M %p')})."
        )
        messages.success(request, 'Schedule slot removed.')
        if request.htmx:
            # Don't re-render _schedule_delete_modal.html here: it now builds
            # a URL from schedule.pk, but Django sets pk to None on an
            # instance right after .delete() succeeds, which would throw a
            # NoReverseMatch. HX-Redirect makes htmx navigate away
            # immediately anyway, so the response body just needs to be
            # valid HTML — its content is never shown to the user.
            from django.http import HttpResponse
            response = HttpResponse('')
            response['HX-Redirect'] = f'/doctor/schedule/?date={removed_date.isoformat()}'
            return response
        return redirect(f"{reverse('doctor:schedule_list')}?date={removed_date.isoformat()}")
    
    if request.htmx:
        return render(request, 'doctor/_schedule_delete_modal.html', {'schedule': schedule})
    return render(request, 'doctor/schedule_confirm_delete.html', {'schedule': schedule})


@role_required('doctor')
def doctor_appointment_list(request):
    status_filter = request.GET.get('status', '')
    qs = Appointment.objects.filter(doctor=request.user).select_related('patient', 'patient_details')
    if status_filter:
        qs = qs.filter(status=status_filter)
    else:
        # Doctors only need to see their active/upcoming and completed
        # appointments here. Pending assignment, pending reschedule, and
        # cancelled appointments are the secretary's responsibility and
        # are handled on the secretary's own appointments page instead.
        qs = qs.filter(status__in=['Scheduled', 'Confirmed', 'Rescheduled', 'Completed'])
    return render(request, 'doctor/appointment_list.html', {
        'appointments': qs, 'status_filter': status_filter
    })


@role_required('doctor')
def appointment_detail(request, pk):
    appt = get_object_or_404(Appointment.objects.select_related('patient', 'patient_details'), pk=pk, doctor=request.user)
    return render(request, 'doctor/_appointment_detail_modal.html', {
        'appt': appt, 'title': 'Appointment Details',
    })


def _working_hours_for_date(doctor, the_date):
    """Returns the doctor's Schedule blocks for that date as (start, end)
    tuples, used to validate a staff-assigned time falls within them."""
    return list(
        Schedule.objects.filter(doctor=doctor, specific_date=the_date)
        .values_list('start_time', 'end_time')
    )


def _time_within_working_hours(the_time, blocks):
    return any(start <= the_time < end for start, end in blocks)


@role_required('doctor')
def assign_appointment_time(request, pk):
    """Doctor sets the actual time on one of their own appointments that's
    awaiting time assignment. Mirrors secretary_views' version of this
    action — both roles can do this, whichever gets to it first."""
    appt = get_object_or_404(Appointment, pk=pk, doctor=request.user, status='Pending Assignment')
    blocks = _working_hours_for_date(appt.doctor, appt.appointment_date)

    if request.method == 'POST':
        form = AssignTimeForm(request.POST)
        if form.is_valid():
            new_time = form.cleaned_data['appointment_time']
            if not blocks:
                messages.error(request, "You have no working hours set for this date.")
            elif not _time_within_working_hours(new_time, blocks):
                hours_display = ', '.join(
                    f"{s.strftime('%I:%M %p')}–{e.strftime('%I:%M %p')}" for s, e in blocks
                )
                messages.error(request, f"That time is outside your working hours ({hours_display}).")
            else:
                with transaction.atomic():
                    conflict = Appointment.objects.select_for_update().filter(
                        doctor=appt.doctor,
                        appointment_date=appt.appointment_date,
                        appointment_time=new_time,
                        status__in=['Scheduled', 'Rescheduled'],
                    ).exclude(pk=appt.pk).exists()
                    if conflict:
                        messages.error(request, 'You already have another appointment at that time. Choose a different time.')
                    else:
                        appt.appointment_time = new_time
                        appt.status = 'Scheduled'
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
                        response = render(request, 'doctor/_assign_time_modal.html', {
                            'appt': appt, 'form': form, 'blocks': blocks,
                        })
                        response['HX-Redirect'] = '/doctor/appointments/'
                        return response
                    return redirect('doctor:appointment_list')
    else:
        form = AssignTimeForm()

    context = {'appt': appt, 'form': form, 'blocks': blocks, 'title': 'Assign Appointment Time'}
    if request.htmx:
        return render(request, 'doctor/_assign_time_modal.html', context)
    return render(request, 'doctor/assign_time.html', context)


@role_required('doctor')
def get_occupied_times(request, pk):
    """API endpoint — occupied appointment times for a doctor's appointment date.
    Returns JSON: {'occupied_times': [{'time', 'time_display', 'patient', 'status'}]}"""
    appt = get_object_or_404(
        Appointment, pk=pk, doctor=request.user,
        status__in=['Pending Assignment', 'Scheduled', 'Rescheduled']
    )
    occupied = Appointment.objects.filter(
        doctor=request.user,
        appointment_date=appt.appointment_date,
        appointment_time__isnull=False,
        status__in=['Scheduled', 'Rescheduled', 'Confirmed'],
    ).exclude(pk=appt.pk).select_related('patient').values_list(
        'appointment_time', 'patient__first_name', 'patient__last_name', 'status'
    ).order_by('appointment_time')

    occupied_list = [
        {
            'time':         t.strftime('%H:%M'),
            'time_display': t.strftime('%I:%M %p'),
            'patient':      f"{fn} {ln}",
            'status':       st,
        }
        for t, fn, ln, st in occupied
    ]
    return JsonResponse({'occupied_times': occupied_list, 'appointment_id': pk})


@role_required('doctor')
def appointment_accept(request, pk):
    appt = get_object_or_404(Appointment, pk=pk, doctor=request.user, status__in=['Scheduled', 'Rescheduled'])
    if request.method == 'POST':
        appt.status = 'Confirmed'
        appt.save()
        _notify(appt.patient,
                f"Dr. {request.user.get_full_name()} has confirmed your appointment on "
                f"{appt.appointment_date.strftime('%B %d, %Y')} at {appt.appointment_time.strftime('%I:%M %p')}.")
        messages.success(request, 'Appointment confirmed.')
        if request.htmx:
            response = render(request, 'doctor/_appointment_action_modal.html', {'appointment': appt, 'action': 'accept'})
            response['HX-Redirect'] = '/doctor/appointments/'
            return response
        return redirect('doctor:appointment_list')
    if request.htmx:
        return render(request, 'doctor/_appointment_action_modal.html', {'appointment': appt, 'action': 'accept'})
    return render(request, 'doctor/appointment_confirm_action.html', {
        'appointment': appt, 'action': 'accept'
    })


@role_required('doctor')
def appointment_decline(request, pk):
    appt = get_object_or_404(Appointment, pk=pk, doctor=request.user, status__in=['Scheduled', 'Rescheduled'])
    if request.method == 'POST':
        reason = request.POST.get('reason', '')
        appt.status = 'Cancelled'
        appt.save()
        try:
            send_cancellation_email(appt, reason)
        except Exception:
            pass
        _notify(appt.patient,
                f"Dr. {request.user.get_full_name()} has cancelled your appointment on "
                f"{appt.appointment_date.strftime('%B %d, %Y')}.")
        messages.success(request, 'Appointment declined and patient notified.')
        if request.htmx:
            response = render(request, 'doctor/_appointment_action_modal.html', {'appointment': appt, 'action': 'decline'})
            response['HX-Redirect'] = '/doctor/appointments/'
            return response
        return redirect('doctor:appointment_list')
    if request.htmx:
        return render(request, 'doctor/_appointment_action_modal.html', {'appointment': appt, 'action': 'decline'})
    return render(request, 'doctor/appointment_confirm_action.html', {
        'appointment': appt, 'action': 'decline'
    })


@role_required('doctor')
def appointment_reschedule_approve(request, pk):
    """Doctor approves a patient's pending reschedule request: the new
    date becomes the appointment's date and the status moves to
    'Pending Assignment' so the doctor or secretary can assign the
    actual time next (same as a fresh booking)."""
    appt = get_object_or_404(Appointment, pk=pk, status='Pending Reschedule', doctor=request.user)
    if request.method == 'POST':
        appt.appointment_date    = appt.requested_date
        appt.appointment_time    = None
        if appt.requested_reason:
            appt.reason = appt.requested_reason
        appt.requested_date      = None
        appt.requested_time      = None
        appt.requested_reason    = ''
        appt.status              = 'Pending Assignment'
        appt.save()

        try:
            send_booking_received_email(appt)
        except Exception:
            pass
        _notify_assigned_secretaries(
            appt.doctor,
            f"Dr. {appt.doctor.get_full_name()} approved {appt.patient.get_full_name()}'s reschedule request to "
            f"{appt.appointment_date.strftime('%B %d, %Y')}. Awaiting time assignment."
        )
        _notify(appt.patient,
                f"Dr. {appt.doctor.get_full_name()} approved your reschedule request. New date: "
                f"{appt.appointment_date.strftime('%B %d, %Y')}. You'll be notified once the time is confirmed.")
        messages.success(request, 'Reschedule approved. Assign a time once ready.')
        if request.htmx:
            response = render(request, 'doctor/_reschedule_action_modal.html', {'appointment': appt, 'action': 'approve'})
            response['HX-Redirect'] = '/doctor/appointments/'
            return response
        return redirect('doctor:appointment_list')
    if request.htmx:
        return render(request, 'doctor/_reschedule_action_modal.html', {'appointment': appt, 'action': 'approve'})
    return render(request, 'doctor/reschedule_confirm_action.html', {'appointment': appt, 'action': 'approve'})


@role_required('doctor')
def appointment_reschedule_reject(request, pk):
    """Doctor rejects a patient's pending reschedule request: the
    appointment reverts to its original date/time/status, unchanged."""
    appt = get_object_or_404(Appointment, pk=pk, status='Pending Reschedule', doctor=request.user)
    if request.method == 'POST':
        reason = request.POST.get('reason', '')
        requested_date = appt.requested_date
        appt.requested_date   = None
        appt.requested_time   = None
        appt.requested_reason = ''
        appt.status           = 'Scheduled'
        appt.save()
        original_time_display = (
            f" at {appt.appointment_time.strftime('%I:%M %p')}" if appt.appointment_time else ''
        )
        _notify(appt.patient,
                f"Dr. {appt.doctor.get_full_name()} declined your request to reschedule your appointment to "
                f"{requested_date.strftime('%B %d, %Y') if requested_date else ''}. "
                f"{('Reason: ' + reason) if reason else ''} Your original appointment on "
                f"{appt.appointment_date.strftime('%B %d, %Y')}{original_time_display} stays as is.")
        messages.success(request, 'Reschedule request declined. Patient notified, original appointment kept.')
        if request.htmx:
            response = render(request, 'doctor/_reschedule_action_modal.html', {'appointment': appt, 'action': 'reject'})
            response['HX-Redirect'] = '/doctor/appointments/'
            return response
        return redirect('doctor:appointment_list')
    if request.htmx:
        return render(request, 'doctor/_reschedule_action_modal.html', {'appointment': appt, 'action': 'reject'})
    return render(request, 'doctor/reschedule_confirm_action.html', {'appointment': appt, 'action': 'reject'})


@role_required('doctor')
def appointment_reschedule(request, pk):
    """Doctor directly moves one of their own appointments to a new date
    (separate from approving a patient's reschedule *request*). Date-only
    — the new appointment lands in 'Pending Assignment' just like a
    fresh booking, since RescheduleForm's clean_appointment_date already
    rejects past dates."""
    appt = get_object_or_404(Appointment, pk=pk, doctor=request.user, status__in=['Scheduled', 'Rescheduled'])
    form = RescheduleForm(request.POST or None)
    if request.method == 'POST' and form.is_valid():
        new_date = form.cleaned_data['appointment_date']
        new_reason = form.cleaned_data.get('reason') or appt.reason

        appt.status = 'Rescheduled'
        appt.save()
        new_appt = Appointment.objects.create(
            patient=appt.patient, doctor=request.user,
            appointment_date=new_date, appointment_time=None,
            status='Pending Assignment', reason=new_reason
        )
        try:
            send_booking_received_email(new_appt)
        except Exception:
            pass
        _notify_assigned_secretaries(
            request.user,
            f"Dr. {request.user.get_full_name()} rescheduled {appt.patient.get_full_name()}'s appointment to "
            f"{new_date.strftime('%B %d, %Y')}. Awaiting time assignment."
        )
        _notify(appt.patient,
                f"Dr. {request.user.get_full_name()} rescheduled your appointment to "
                f"{new_date.strftime('%B %d, %Y')}. You'll be notified once the time is confirmed.")
        messages.success(request, 'Appointment rescheduled. Assign a time once ready.')
        return redirect('doctor:appointment_list')
    return render(request, 'doctor/appointment_reschedule.html', {'form': form, 'appointment': appt})


@role_required('doctor')
def appointment_complete(request, pk):
    appt = get_object_or_404(Appointment, pk=pk, doctor=request.user, status__in=['Scheduled', 'Rescheduled', 'Confirmed'])
    if request.method == 'POST':
        appt.status = 'Completed'
        appt.save()
        messages.success(request, 'Appointment marked as completed.')
        return redirect('doctor:add_results', pk=appt.pk)
    return render(request, 'doctor/appointment_confirm_action.html', {
        'appointment': appt, 'action': 'complete'
    })


@role_required('doctor')
def add_consultation_results(request, pk):
    appt = get_object_or_404(Appointment, pk=pk, doctor=request.user, status='Completed')
    from records.models import ResultsConsultation, MedicalRecords
    from records.forms import ResultsConsultationForm
    existing = getattr(appt, 'results', None)
    form = ResultsConsultationForm(request.POST or None, instance=existing)
    if request.method == 'POST' and form.is_valid():
        result = form.save(commit=False)
        result.appointment = appt
        result.save()
        MedicalRecords.objects.get_or_create(
            doctor=request.user, patient=appt.patient,
            results=result, defaults={'visit_date': appt.appointment_date}
        )
        messages.success(request, 'Consultation results saved.')
        return redirect('doctor:add_prescription', pk=appt.pk)
    return render(request, 'doctor/consultation_form.html', {
        'form': form, 'appointment': appt, 'existing': existing
    })


@role_required('doctor')
def add_prescription(request, pk):
    appt = get_object_or_404(Appointment, pk=pk, doctor=request.user)
    from records.models import ResultsConsultation, Prescription
    from records.forms import PrescriptionForm
    try:
        results = appt.results
    except ResultsConsultation.DoesNotExist:
        messages.error(request, 'Please add consultation results first.')
        return redirect('doctor:add_results', pk=pk)
    form = PrescriptionForm(request.POST or None, request.FILES or None)
    if request.method == 'POST' and form.is_valid():
        prescription = form.save(commit=False)
        prescription.results_consultation = results
        prescription.save()
        messages.success(request, 'Prescription saved.')
        return redirect('doctor:appointment_list')
    prescriptions = results.prescriptions.all()
    return render(request, 'doctor/prescription_form.html', {
        'form': form, 'appointment': appt, 'prescriptions': prescriptions
    })


@role_required('doctor')
def doctor_patient_list(request):
    from django.db.models import Max
    patient_ids = Appointment.objects.filter(
        doctor=request.user
    ).values_list('patient_id', flat=True).distinct()
    patients = CustomUser.objects.filter(pk__in=patient_ids)
    return render(request, 'doctor/patient_list.html', {'patients': patients})


@role_required('doctor')
def patient_quickview(request, patient_id):
    patient = get_object_or_404(CustomUser, pk=patient_id, role='patient')
    has_appt = Appointment.objects.filter(doctor=request.user, patient=patient).exists()
    if not has_appt:
        messages.error(request, 'You do not have access to this patient.')
        return redirect('doctor:patient_list')
    profile = getattr(patient, 'patient_profile', None)
    last_visit = Appointment.objects.filter(doctor=request.user, patient=patient).order_by('-appointment_date').first()
    return render(request, 'doctor/_patient_quickview_modal.html', {
        'patient': patient, 'profile': profile, 'last_visit': last_visit, 'title': 'Patient Summary',
    })


@role_required('doctor')
def doctor_patient_records(request, patient_id):
    # Doctor may only view records for patients who have had appointments with them
    patient = get_object_or_404(CustomUser, pk=patient_id, role='patient')
    has_appt = Appointment.objects.filter(doctor=request.user, patient=patient).exists()
    if not has_appt:
        messages.error(request, 'You do not have access to this patient.')
        return redirect('doctor:patient_list')
    from records.models import MedicalRecords, VitalSign
    records   = MedicalRecords.objects.filter(patient=patient).select_related('results', 'doctor')
    vitals    = VitalSign.objects.filter(patient=patient)
    return render(request, 'doctor/patient_records.html', {
        'patient': patient, 'records': records, 'vitals': vitals
    })


@role_required('doctor')
def doctor_notifications(request):
    return redirect('/notifications/')
