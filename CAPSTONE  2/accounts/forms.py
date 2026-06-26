from django import forms
from django.contrib.auth.forms import UserCreationForm
import re
from .models import CustomUser, PatientProfile, DoctorProfile, SecretaryProfile
from .validators import validate_ph_mobile_number, normalize_ph_mobile_number


def _slugify_name_part(value):
    """Lowercases and strips a name down to safe username characters."""
    value = value.lower().strip()
    value = re.sub(r'[^a-z0-9]+', '', value)
    return value or 'patient'


def _generate_walkin_username(first_name, last_name):
    """Builds a readable, unique username like 'walkin-juan-delacruz' (with
    a numeric suffix if that's already taken) — walk-in patients never log
    in with it, but it still shows up in admin/secretary patient lists, so
    it should be recognizable rather than a random string."""
    base = f"walkin-{_slugify_name_part(first_name)}-{_slugify_name_part(last_name)}"
    username = base
    suffix = 1
    while CustomUser.objects.filter(username=username).exists():
        suffix += 1
        username = f"{base}-{suffix}"
    return username


class WalkInPatientForm(forms.Form):
    """Registers a walk-in patient who will never log in themselves — the
    secretary is entering their details in person, on the spot. No
    username or password is collected; both are generated automatically.
    Email is optional since many walk-ins won't have one handy, but a
    mobile number is required so the clinic has a way to reach them.

    Field set intentionally matches PatientProfileEditForm so a walk-in's
    profile ends up just as complete as a self-registered patient's —
    the only difference is who's typing it in.
    """
    first_name      = forms.CharField(max_length=150, required=True, label='First Name')
    middle_name     = forms.CharField(max_length=150, required=False, label='Middle Name')
    last_name       = forms.CharField(max_length=150, required=True, label='Last Name')
    contact_number  = forms.CharField(max_length=20, required=True, label='Mobile Number')
    email           = forms.EmailField(required=False, label='Email Address')
    gender          = forms.ChoiceField(
        choices=[('', '-- Select --')] + PatientProfile.GENDER_CHOICES, required=False, label='Sex'
    )
    date_of_birth   = forms.DateField(required=False, widget=forms.DateInput(attrs={'type': 'date'}))
    place_of_birth  = forms.CharField(max_length=150, required=False)
    address         = forms.CharField(widget=forms.Textarea(attrs={'rows': 2}), required=False)
    guardian        = forms.CharField(max_length=150, required=False, label='Guardian (optional)')
    emergency_contact_name   = forms.CharField(max_length=150, required=False)
    emergency_contact_number = forms.CharField(max_length=20, required=False)
    blood_type      = forms.ChoiceField(
        choices=[('', '-- Select --')] + PatientProfile.BLOOD_TYPE_CHOICES, required=False
    )
    reason          = forms.CharField(
        widget=forms.Textarea(attrs={'rows': 2}), required=True,
        label='Reason for Visit', help_text='Shown to the doctor on the appointment.'
    )

    def clean_contact_number(self):
        value = self.cleaned_data['contact_number']
        validate_ph_mobile_number(value)
        return normalize_ph_mobile_number(value)

    def clean_emergency_contact_number(self):
        value = self.cleaned_data.get('emergency_contact_number', '')
        if value:
            validate_ph_mobile_number(value)
            return normalize_ph_mobile_number(value)
        return value

    def save(self):
        username = _generate_walkin_username(self.cleaned_data['first_name'], self.cleaned_data['last_name'])
        user = CustomUser(
            username=username,
            first_name=self.cleaned_data['first_name'],
            last_name=self.cleaned_data['last_name'],
            email=self.cleaned_data.get('email', ''),
            role='patient',
        )
        # Walk-in patients never log in with this account, so it should
        # be impossible to authenticate as them even if someone later
        # learned or guessed the auto-generated username.
        user.set_unusable_password()
        user.save()
        PatientProfile.objects.create(
            user=user,
            middle_name=self.cleaned_data.get('middle_name', ''),
            contact_number=self.cleaned_data['contact_number'],
            gender=self.cleaned_data.get('gender', ''),
            date_of_birth=self.cleaned_data.get('date_of_birth'),
            place_of_birth=self.cleaned_data.get('place_of_birth', ''),
            address=self.cleaned_data.get('address', ''),
            guardian=self.cleaned_data.get('guardian', ''),
            emergency_contact_name=self.cleaned_data.get('emergency_contact_name', ''),
            emergency_contact_number=self.cleaned_data.get('emergency_contact_number', ''),
            blood_type=self.cleaned_data.get('blood_type', ''),
        )
        return user


class PatientRegistrationForm(UserCreationForm):
    first_name     = forms.CharField(max_length=150, required=True, label='First Name')
    last_name      = forms.CharField(max_length=150, required=True, label='Last Name')
    email          = forms.EmailField(required=True, label='Email Address')
    contact_number = forms.CharField(max_length=20, required=False, label='Contact Number')
    gender         = forms.ChoiceField(choices=[('', '-- Select --')] + PatientProfile.GENDER_CHOICES, required=False)
    date_of_birth  = forms.DateField(required=False, widget=forms.DateInput(attrs={'type': 'date'}))
    place_of_birth = forms.CharField(max_length=150, required=False)
    address        = forms.CharField(widget=forms.Textarea(attrs={'rows': 3}), required=False)
    guardian       = forms.CharField(max_length=150, required=False, label='Guardian (optional)')

    class Meta:
        model  = CustomUser
        fields = ['username', 'first_name', 'last_name', 'email', 'password1', 'password2']

    def save(self, commit=True):
        user = super().save(commit=False)
        user.role       = 'patient'
        user.first_name = self.cleaned_data['first_name']
        user.last_name  = self.cleaned_data['last_name']
        user.email      = self.cleaned_data['email']
        if commit:
            user.save()
            PatientProfile.objects.create(
                user           = user,
                contact_number = self.cleaned_data.get('contact_number', ''),
                gender         = self.cleaned_data.get('gender', ''),
                date_of_birth  = self.cleaned_data.get('date_of_birth'),
                place_of_birth = self.cleaned_data.get('place_of_birth', ''),
                address        = self.cleaned_data.get('address', ''),
                guardian       = self.cleaned_data.get('guardian', ''),
            )
        return user


class PatientProfileEditForm(forms.ModelForm):
    first_name     = forms.CharField(max_length=150, required=False)
    last_name      = forms.CharField(max_length=150, required=False)

    class Meta:
        model  = PatientProfile
        fields = [
            'contact_number', 'gender', 'date_of_birth', 'place_of_birth', 'address', 'guardian',
            'emergency_contact_name', 'emergency_contact_number', 'blood_type',
        ]
        widgets = {
            'date_of_birth': forms.DateInput(attrs={'type': 'date'}),
            'address': forms.Textarea(attrs={'rows': 3}),
        }

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        if self.instance and self.instance.user_id:
            self.fields['first_name'].initial = self.instance.user.first_name
            self.fields['last_name'].initial  = self.instance.user.last_name


class DoctorProfileEditForm(forms.ModelForm):
    class Meta:
        model  = DoctorProfile
        fields = ['specialization', 'years_of_experience', 'license_number']


class SecretaryProfileEditForm(forms.ModelForm):
    class Meta:
        model  = SecretaryProfile
        fields = ['contact_number', 'employee_id']


class DoctorCreationForm(UserCreationForm):
    first_name     = forms.CharField(max_length=150, required=True)
    last_name      = forms.CharField(max_length=150, required=True)
    email          = forms.EmailField(required=True)
    specialization = forms.CharField(max_length=150, required=False)

    class Meta:
        model  = CustomUser
        fields = ['username', 'first_name', 'last_name', 'email', 'password1', 'password2']

    def save(self, commit=True):
        user = super().save(commit=False)
        user.role       = 'doctor'
        user.first_name = self.cleaned_data['first_name']
        user.last_name  = self.cleaned_data['last_name']
        user.email      = self.cleaned_data['email']
        if commit:
            user.save()
            DoctorProfile.objects.create(
                user=user,
                specialization=self.cleaned_data.get('specialization', '')
            )
        return user


class SecretaryCreationForm(UserCreationForm):
    first_name      = forms.CharField(max_length=150, required=True)
    last_name       = forms.CharField(max_length=150, required=True)
    email           = forms.EmailField(required=True)
    contact_number  = forms.CharField(max_length=20, required=False, label='Contact Number')
    employee_id     = forms.CharField(max_length=30, required=False, label='Employee/Staff ID')
    assigned_doctor = forms.ModelChoiceField(
        queryset=CustomUser.objects.filter(role='doctor'),
        required=False, label='Assigned Doctor'
    )
    date_assigned   = forms.DateField(required=False, widget=forms.DateInput(attrs={'type': 'date'}))

    class Meta:
        model  = CustomUser
        fields = ['username', 'first_name', 'last_name', 'email', 'password1', 'password2']

    def save(self, commit=True):
        user = super().save(commit=False)
        user.role       = 'secretary'
        user.first_name = self.cleaned_data['first_name']
        user.last_name  = self.cleaned_data['last_name']
        user.email      = self.cleaned_data['email']
        if commit:
            user.save()
            SecretaryProfile.objects.create(
                user            = user,
                assigned_doctor = self.cleaned_data.get('assigned_doctor'),
                date_assigned   = self.cleaned_data.get('date_assigned'),
                contact_number  = self.cleaned_data.get('contact_number', ''),
                employee_id     = self.cleaned_data.get('employee_id', ''),
            )
        return user


class UserEditForm(forms.ModelForm):
    class Meta:
        model  = CustomUser
        fields = ['first_name', 'last_name', 'email', 'is_active']


class EmailNotificationSettingsForm(forms.ModelForm):
    class Meta:
        model  = CustomUser
        fields = ['email_notifications_enabled']


class ProfilePictureWidget(forms.ClearableFileInput):
    template_name = 'accounts/widgets/profile_picture_input.html'


class ProfilePictureForm(forms.ModelForm):
    class Meta:
        model  = CustomUser
        fields = ['profile_picture']
        widgets = {
            'profile_picture': ProfilePictureWidget(attrs={
                'class': 'block text-sm text-gray-600',
                'accept': 'image/*',
            }),
        }
