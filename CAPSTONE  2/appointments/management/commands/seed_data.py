from django.core.management.base import BaseCommand
from django.contrib.auth.hashers import make_password
from datetime import date, timedelta
from accounts.models import CustomUser, PatientProfile, DoctorProfile, SecretaryProfile
from appointments.models import Schedule, Appointment
from feedback.models import Feedback


class Command(BaseCommand):
    help = 'Seed the database with demo data for testing'

    def handle(self, *args, **options):
        self.stdout.write('Seeding data...')

        if CustomUser.objects.filter(username='admin').exists():
            self.stdout.write(self.style.WARNING('Data already exists. Delete db.sqlite3 and re-migrate to re-seed.'))
            return

        # Admin
        admin = CustomUser.objects.create_superuser(
            username='admin', email='admin@mshfi.com', password='Admin1234!',
            first_name='System', last_name='Administrator', role='admin'
        )
        self.stdout.write('  Created admin: admin / Admin1234!')

        # Doctors
        specializations = [
            ('General Medicine', 'Jose', 'Reyes'),
            ('Cardiology',       'Maria', 'Santos'),
            ('Pediatrics',       'Carlos', 'Dela Cruz'),
        ]
        doctors = []
        for i, (spec, first, last) in enumerate(specializations, 1):
            doc = CustomUser.objects.create_user(
                username=f'doctor{i}', email=f'doctor{i}@mshfi.com',
                password='Doctor1234!', role='doctor',
                first_name=first, last_name=last
            )
            DoctorProfile.objects.create(user=doc, specialization=spec)
            # Mon, Wed, Fri 9am–12pm
            for day in [0, 2, 4]:
                Schedule.objects.create(
                    doctor=doc, day_of_week=day,
                    start_time='09:00', end_time='12:00'
                )
            doctors.append(doc)
            self.stdout.write(f'  Created doctor{i}: Dr. {first} {last} ({spec})')

        # Secretary
        sec = CustomUser.objects.create_user(
            username='secretary1', email='secretary1@mshfi.com',
            password='Sec1234!', role='secretary',
            first_name='Ana', last_name='Gomez'
        )
        SecretaryProfile.objects.create(
            user=sec, assigned_doctor=doctors[0], date_assigned=date.today()
        )
        self.stdout.write('  Created secretary1: Ana Gomez / Sec1234!')

        # Patients
        patient_data = [
            ('Juan', 'Cruz',      'M', '09171234567'),
            ('Rosa', 'Lim',       'F', '09181234567'),
            ('Pedro', 'Garcia',   'M', '09191234567'),
            ('Liza', 'Aquino',    'F', '09201234567'),
            ('Mario', 'Pascual',  'M', '09211234567'),
        ]
        patients = []
        for i, (first, last, gender, phone) in enumerate(patient_data, 1):
            pat = CustomUser.objects.create_user(
                username=f'patient{i}', email=f'patient{i}@mshfi.com',
                password='Patient1234!', role='patient',
                first_name=first, last_name=last
            )
            PatientProfile.objects.create(
                user=pat, contact_number=phone, gender=gender,
                date_of_birth=f'198{i}-0{i}-01',
                address='Sample Street, Marawi City'
            )
            patients.append(pat)
        self.stdout.write('  Created patient1–5 / Patient1234!')

        # Appointments — next available Monday
        days_ahead = (7 - date.today().weekday()) % 7
        if days_ahead == 0:
            days_ahead = 7
        next_monday = date.today() + timedelta(days=days_ahead)

        for i, patient in enumerate(patients[:3]):
            Appointment.objects.create(
                patient=patient,
                doctor=doctors[0],
                appointment_date=next_monday,
                appointment_time=f'{9+i:02d}:00',
                status='Scheduled',
                reason='Routine checkup'
            )
        self.stdout.write(f'  Created 3 appointments for next Monday ({next_monday})')

        # Sample feedback
        Feedback.objects.create(
            patient=patients[0],
            rating=5,
            comment='Excellent service! The doctor was very thorough and attentive.'
        )
        Feedback.objects.create(
            patient=patients[1],
            rating=4,
            comment='Good experience overall. The waiting area is comfortable.'
        )
        self.stdout.write('  Created sample feedback')

        self.stdout.write(self.style.SUCCESS('\n=== Seed complete ==='))
        self.stdout.write('Login credentials:')
        self.stdout.write('  admin       / Admin1234!')
        self.stdout.write('  doctor1–3   / Doctor1234!')
        self.stdout.write('  secretary1  / Sec1234!')
        self.stdout.write('  patient1–5  / Patient1234!')
