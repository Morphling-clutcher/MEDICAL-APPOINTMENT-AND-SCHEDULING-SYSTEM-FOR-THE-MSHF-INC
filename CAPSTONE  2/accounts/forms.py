from django import forms
from django.contrib.auth.forms import UserCreationForm
from .models import CustomUser, PatientProfile, DoctorProfile, SecretaryProfile


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
        fields = ['contact_number', 'gender', 'date_of_birth', 'place_of_birth', 'address', 'guardian']
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
        fields = ['specialization']


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
            )
        return user


class UserEditForm(forms.ModelForm):
    class Meta:
        model  = CustomUser
        fields = ['first_name', 'last_name', 'email', 'is_active']
