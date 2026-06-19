from django.shortcuts import render, redirect, get_object_or_404
from django.contrib import messages
from django.db import transaction
from datetime import date, datetime, timedelta
from accounts.decorators import role_required
from appointments.models import Appointment, Schedule
from accounts.models import CustomUser
from notifications.email_utils import (
    send_booking_confirmation_email, send_cancellation_email, send_reschedule_email
)
from notifications.models import Notification


def _notify(user, message):
    Notification.objects.create(user=user, message=message)


@role_required('patient')
def patient_dashboard(request):
    upcoming = Appointment.objects.filter(
        patient=request.user,
        status__in=['Scheduled', 'Rescheduled'],
        appointment_date__gte=date.today()
    ).select_related('doctor')[:5]
    past = Appointment.objects.filter(
        patient=request.user,
        status__in=['Completed', 'Cancelled']
    ).select_related('doctor')[:5]

    dashboard_data = {
        'stats': [
            {'label': 'Upcoming Appointments', 'value': upcoming.count()},
            {'label': 'Past Appointments', 'value': past.count()},
        ],
        'appointmentsTitle': 'Upcoming Appointments',
        'appointmentsHref': '/patient/appointments/',
        'appointments': [
            {
                'primary': f'Dr. {a.doctor.get_full_name()}',
                'secondary': a.reason or '',
                'date': a.appointment_date.isoformat(),
                'time': a.appointment_time.strftime('%H:%M'),
                'status': a.status,
            }
            for a in upcoming
        ],
        'pastAppointmentsTitle': 'Recent Past Appointments',
        'pastAppointmentsHref': '/patient/appointments/',
        'pastAppointments': [
            {
                'primary': f'Dr. {a.doctor.get_full_name()}',
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
    }
    return render(request, 'patient/dashboard.html', {'dashboard_data': dashboard_data})


@role_required('patient')
def appointment_list(request):
    upcoming = Appointment.objects.filter(
        patient=request.user,
        appointment_date__gte=date.today()
    ).exclude(status='Cancelled').select_related('doctor').order_by('appointment_date', 'appointment_time')
    past = Appointment.objects.filter(
        patient=request.user,
        appointment_date__lt=date.today()
    ).select_related('doctor').order_by('-appointment_date')
    cancelled = Appointment.objects.filter(
        patient=request.user,
        status='Cancelled'
    ).select_related('doctor').order_by('-appointment_date')
    return render(request, 'patient/appointment_list.html', {
        'upcoming': upcoming, 'past': past, 'cancelled': cancelled
    })


@role_required('patient')
def book_step1(request):
    doctors = CustomUser.objects.filter(role='doctor').select_related('doctor_profile')
    return render(request, 'patient/book_step1.html', {'doctors': doctors})


@role_required('patient')
def book_step2_slots(request, doctor_id):
    doctor = get_object_or_404(CustomUser, pk=doctor_id, role='doctor')
    selected_date_str = request.GET.get('date', '')
    slots = []
    error = None

    if selected_date_str:
        try:
            selected_date = datetime.strptime(selected_date_str, '%Y-%m-%d').date()
        except ValueError:
            error = 'Invalid date format.'
            return render(request, 'patient/book_step2_slots.html', {
                'doctor': doctor, 'slots': [], 'error': error, 'selected_date': selected_date_str
            })

        if selected_date < date.today():
            error = 'Cannot book an appointment in the past.'
        else:
            day_of_week = selected_date.weekday()
            schedule_blocks = Schedule.objects.filter(doctor=doctor, day_of_week=day_of_week)
            if not schedule_blocks.exists():
                error = 'The selected doctor has no schedule on this day.'
            else:
                booked_times = set(
                    Appointment.objects.filter(
                        doctor=doctor,
                        appointment_date=selected_date,
                        status__in=['Scheduled', 'Rescheduled']
                    ).values_list('appointment_time', flat=True)
                )
                for block in schedule_blocks:
                    current = datetime.combine(selected_date, block.start_time)
                    end     = datetime.combine(selected_date, block.end_time)
                    while current < end:
                        t = current.time()
                        slots.append({'time': t, 'available': t not in booked_times})
                        current += timedelta(minutes=30)

    return render(request, 'patient/book_step2_slots.html', {
        'doctor': doctor,
        'slots': slots,
        'selected_date': selected_date_str,
        'error': error,
    })


@role_required('patient')
def book_step3_confirm(request):
    if request.method == 'POST':
        doctor_id  = request.POST.get('doctor_id')
        date_str   = request.POST.get('appointment_date')
        time_str   = request.POST.get('appointment_time')
        reason     = request.POST.get('reason', '')

        try:
            doctor           = get_object_or_404(CustomUser, pk=doctor_id, role='doctor')
            appointment_date = datetime.strptime(date_str, '%Y-%m-%d').date()
            appointment_time = datetime.strptime(time_str, '%H:%M:%S').time()
        except (ValueError, TypeError):
            messages.error(request, 'Invalid booking data. Please try again.')
            return redirect('patient:book_step1')

        with transaction.atomic():
            conflict = Appointment.objects.select_for_update().filter(
                doctor=doctor,
                appointment_date=appointment_date,
                appointment_time=appointment_time,
                status__in=['Scheduled', 'Rescheduled']
            ).exists()
            if conflict:
                messages.error(request, 'This time slot was just taken. Please choose another.')
                return redirect('patient:book_step2', doctor_id=doctor.pk)

            appointment = Appointment.objects.create(
                patient          = request.user,
                doctor           = doctor,
                appointment_date = appointment_date,
                appointment_time = appointment_time,
                status           = 'Scheduled',
                reason           = reason,
            )

        try:
            send_booking_confirmation_email(appointment)
        except Exception:
            pass
        _notify(request.user,
                f"Your appointment with Dr. {doctor.get_full_name()} on "
                f"{appointment_date.strftime('%B %d, %Y')} at "
                f"{appointment_time.strftime('%I:%M %p')} has been booked.")

        messages.success(request, 'Appointment booked successfully! A confirmation email has been sent.')
        return redirect('patient:appointment_list')

    # GET: show confirmation form with pre-filled fields
    doctor_id  = request.GET.get('doctor_id')
    date_str   = request.GET.get('appointment_date')
    time_str   = request.GET.get('appointment_time')
    if not all([doctor_id, date_str, time_str]):
        return redirect('patient:book_step1')
    doctor = get_object_or_404(CustomUser, pk=doctor_id, role='doctor')
    return render(request, 'patient/book_step3_confirm.html', {
        'doctor': doctor,
        'appointment_date': date_str,
        'appointment_time': time_str,
    })


@role_required('patient')
def reschedule_appointment(request, pk):
    appointment = get_object_or_404(
        Appointment, pk=pk, patient=request.user, status__in=['Scheduled', 'Rescheduled']
    )
    if request.method == 'POST':
        date_str = request.POST.get('appointment_date')
        time_str = request.POST.get('appointment_time')
        reason   = request.POST.get('reason', appointment.reason)
        try:
            new_date = datetime.strptime(date_str, '%Y-%m-%d').date()
            new_time = datetime.strptime(time_str, '%H:%M').time()
        except (ValueError, TypeError):
            messages.error(request, 'Invalid date/time.')
            return render(request, 'patient/reschedule.html', {'appointment': appointment})

        if new_date < date.today():
            messages.error(request, 'Cannot reschedule to a past date.')
            return render(request, 'patient/reschedule.html', {'appointment': appointment})

        with transaction.atomic():
            conflict = Appointment.objects.select_for_update().filter(
                doctor=appointment.doctor,
                appointment_date=new_date,
                appointment_time=new_time,
                status__in=['Scheduled', 'Rescheduled']
            ).exclude(pk=appointment.pk).exists()
            if conflict:
                messages.error(request, 'That slot is already taken. Choose another time.')
                return render(request, 'patient/reschedule.html', {'appointment': appointment})

            appointment.status = 'Rescheduled'
            appointment.save()
            new_appt = Appointment.objects.create(
                patient          = appointment.patient,
                doctor           = appointment.doctor,
                appointment_date = new_date,
                appointment_time = new_time,
                status           = 'Scheduled',
                reason           = reason,
            )

        try:
            send_reschedule_email(new_appt)
        except Exception:
            pass
        _notify(request.user,
                f"Your appointment with Dr. {appointment.doctor.get_full_name()} has been rescheduled to "
                f"{new_date.strftime('%B %d, %Y')} at {new_time.strftime('%I:%M %p')}.")
        messages.success(request, 'Appointment rescheduled successfully.')
        return redirect('patient:appointment_list')

    return render(request, 'patient/reschedule.html', {'appointment': appointment})


@role_required('patient')
def cancel_appointment(request, pk):
    appointment = get_object_or_404(
        Appointment, pk=pk, patient=request.user, status__in=['Scheduled', 'Rescheduled']
    )
    if request.method == 'POST':
        appointment.status = 'Cancelled'
        appointment.save()
        try:
            send_cancellation_email(appointment)
        except Exception:
            pass
        _notify(request.user,
                f"Your appointment with Dr. {appointment.doctor.get_full_name()} on "
                f"{appointment.appointment_date.strftime('%B %d, %Y')} has been cancelled.")
        messages.success(request, 'Appointment cancelled.')
        return redirect('patient:appointment_list')
    return render(request, 'patient/cancel_confirm.html', {'appointment': appointment})


@role_required('patient')
def medical_records(request):
    from records.models import MedicalRecords
    records = MedicalRecords.objects.filter(
        patient=request.user
    ).select_related('doctor', 'results').order_by('-visit_date')
    return render(request, 'patient/medical_records.html', {'records': records})


@role_required('patient')
def patient_notifications(request):
    return redirect('/notifications/')
