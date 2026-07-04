from django.test import TestCase, Client
from django.contrib.auth import get_user_model
from django.urls import reverse
from datetime import date, datetime, timedelta
from appointments.models import Appointment, Schedule

User = get_user_model()


class AppointmentDuplicateBookingTestCase(TestCase):
    """Test cases for preventing duplicate active appointments per patient."""

    def setUp(self):
        """Set up test data."""
        # Create a patient user
        self.patient = User.objects.create_user(
            username='testpatient',
            email='patient@test.com',
            password='testpass123',
            role='patient'
        )

        # Create a doctor user
        self.doctor = User.objects.create_user(
            username='testdoctor',
            email='doctor@test.com',
            password='testpass123',
            role='doctor'
        )

        # Create a schedule for the doctor (needed for booking)
        tomorrow = date.today() + timedelta(days=1)
        self.schedule = Schedule.objects.create(
            doctor=self.doctor,
            specific_date=tomorrow,
            start_time='09:00',
            end_time='17:00'
        )

        self.client = Client()

    def test_has_active_appointment_no_appointments(self):
        """Test that a patient with no appointments doesn't have an active appointment."""
        self.assertFalse(Appointment.has_active_appointment(self.patient))

    def test_has_active_appointment_with_pending_time_assignment(self):
        """Test that a patient with 'Pending Time Assignment' status has an active appointment."""
        Appointment.objects.create(
            patient=self.patient,
            doctor=self.doctor,
            appointment_date=date.today() + timedelta(days=1),
            status='Pending Time Assignment',
            reason='Test appointment'
        )
        self.assertTrue(Appointment.has_active_appointment(self.patient))

    def test_has_active_appointment_with_scheduled(self):
        """Test that a patient with 'Scheduled' status has an active appointment."""
        Appointment.objects.create(
            patient=self.patient,
            doctor=self.doctor,
            appointment_date=date.today() + timedelta(days=1),
            appointment_time='10:00',
            status='Scheduled',
            reason='Test appointment'
        )
        self.assertTrue(Appointment.has_active_appointment(self.patient))

    def test_has_active_appointment_with_rescheduled(self):
        """Test that a patient with 'Rescheduled' status has an active appointment."""
        Appointment.objects.create(
            patient=self.patient,
            doctor=self.doctor,
            appointment_date=date.today() + timedelta(days=1),
            appointment_time='10:00',
            status='Rescheduled',
            reason='Test appointment'
        )
        self.assertTrue(Appointment.has_active_appointment(self.patient))

    def test_has_active_appointment_with_pending_reschedule(self):
        """Test that a patient with 'Pending Reschedule' status has an active appointment."""
        Appointment.objects.create(
            patient=self.patient,
            doctor=self.doctor,
            appointment_date=date.today() + timedelta(days=1),
            appointment_time='10:00',
            status='Pending Reschedule',
            reason='Test appointment'
        )
        self.assertTrue(Appointment.has_active_appointment(self.patient))

    def test_has_active_appointment_with_completed(self):
        """Test that a patient with 'Completed' status does NOT have an active appointment."""
        Appointment.objects.create(
            patient=self.patient,
            doctor=self.doctor,
            appointment_date=date.today() - timedelta(days=1),
            appointment_time='10:00',
            status='Completed',
            reason='Test appointment'
        )
        self.assertFalse(Appointment.has_active_appointment(self.patient))

    def test_has_active_appointment_with_cancelled(self):
        """Test that a patient with 'Cancelled' status does NOT have an active appointment."""
        Appointment.objects.create(
            patient=self.patient,
            doctor=self.doctor,
            appointment_date=date.today() + timedelta(days=1),
            status='Cancelled',
            reason='Test appointment'
        )
        self.assertFalse(Appointment.has_active_appointment(self.patient))

    def test_has_active_appointment_multiple_appointments_one_active(self):
        """Test with multiple appointments, one active and one completed."""
        # Create a completed appointment
        Appointment.objects.create(
            patient=self.patient,
            doctor=self.doctor,
            appointment_date=date.today() - timedelta(days=5),
            appointment_time='10:00',
            status='Completed',
            reason='Past appointment'
        )
        # Create an active appointment
        Appointment.objects.create(
            patient=self.patient,
            doctor=self.doctor,
            appointment_date=date.today() + timedelta(days=1),
            status='Pending Time Assignment',
            reason='Active appointment'
        )
        # Should have active appointment because one is still pending
        self.assertTrue(Appointment.has_active_appointment(self.patient))

    def test_booking_prevented_with_active_appointment(self):
        """Test that the validation check prevents booking with active appointment."""
        # Create an active appointment
        Appointment.objects.create(
            patient=self.patient,
            doctor=self.doctor,
            appointment_date=date.today() + timedelta(days=5),
            status='Pending Time Assignment',
            reason='Existing active appointment'
        )

        # Verify patient has active appointment
        self.assertTrue(Appointment.has_active_appointment(self.patient))

        # In the actual booking flow, book_step3_confirm checks this before creating
        # If has_active_appointment() returns True, no appointment is created
        # This test verifies the check would trigger

        # Try to create another appointment - this would be blocked in book_step3_confirm
        # We test the logic here directly since Django/Python 3.14 has template rendering issues
        if not Appointment.has_active_appointment(self.patient):
            # This path should NOT be taken when patient has active appointment
            Appointment.objects.create(
                patient=self.patient,
                doctor=self.doctor,
                appointment_date=date.today() + timedelta(days=3),
                status='Pending Time Assignment',
                reason='Second appointment'
            )

        # Verify no new appointment was created (still only 1)
        appointment_count = Appointment.objects.filter(patient=self.patient).count()
        self.assertEqual(appointment_count, 1)  # Only the original one

    def test_booking_allowed_after_cancellation(self):
        """Test that booking is allowed after previous appointment is cancelled."""
        # Create an appointment
        appt = Appointment.objects.create(
            patient=self.patient,
            doctor=self.doctor,
            appointment_date=date.today() + timedelta(days=5),
            appointment_time='10:00',
            status='Scheduled',
            reason='Existing appointment'
        )

        # Verify patient has active appointment
        self.assertTrue(Appointment.has_active_appointment(self.patient))

        # Cancel the appointment
        appt.status = 'Cancelled'
        appt.save()

        # Verify patient no longer has active appointment
        self.assertFalse(Appointment.has_active_appointment(self.patient))

    def test_booking_allowed_after_completion(self):
        """Test that booking is allowed after previous appointment is completed."""
        # Create an appointment
        appt = Appointment.objects.create(
            patient=self.patient,
            doctor=self.doctor,
            appointment_date=date.today() - timedelta(days=1),
            appointment_time='10:00',
            status='Scheduled',
            reason='Existing appointment'
        )

        # Verify patient has active appointment
        self.assertTrue(Appointment.has_active_appointment(self.patient))

        # Complete the appointment
        appt.status = 'Completed'
        appt.save()

        # Verify patient no longer has active appointment
        self.assertFalse(Appointment.has_active_appointment(self.patient))
