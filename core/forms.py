import datetime

from django import forms
from django.contrib.auth.forms import AuthenticationForm, UserCreationForm
from django.core.validators import RegexValidator
from .models import ServiceUser, CareHome, CustomUser, ABCForm, IncidentReport, LogEntry, Mapping
# forms.py
from django import forms
from .models import CareHome
import datetime

# AM time choices: 12:00 AM to 11:00 AM
AM_TIMES = [
    (datetime.time(hour=h), f"{(h % 12 or 12)}:00 AM")
    for h in range(0, 12)
]


def coerce_to_time(val):
    if isinstance(val, datetime.time):
        return val
    if isinstance(val, str):
        h, m = map(int, val.split(":"))
        return datetime.time(h, m)
    return None


class CareHomeForm(forms.ModelForm):
    class Meta:
        model = CareHome
        fields = ['name', 'postcode', 'details', 'picture', 'morning_shift_start', 'night_shift_start']
        widgets = {
            'morning_shift_start': forms.TimeInput(format='%H:%M', attrs={'type': 'time'}),
            'night_shift_start': forms.TimeInput(format='%H:%M', attrs={'type': 'time'}),
        }

class LoginForm(AuthenticationForm):
    username = forms.CharField(widget=forms.TextInput(attrs={'class': 'form-control'}))
    password = forms.CharField(widget=forms.PasswordInput(attrs={'class': 'form-control'}))


class ServiceUserForm(forms.ModelForm):
    class Meta:
        model = ServiceUser
        fields = '__all__'
        widgets = {
            'carehome': forms.Select(attrs={'class': 'form-control'}),
            'first_name': forms.TextInput(attrs={'class': 'form-control'}),
            'last_name': forms.TextInput(attrs={'class': 'form-control'}),
            'phone': forms.TextInput(attrs={
                'class': 'form-control',
                'placeholder': '+44 7123 456789 or 07123 456789'
            }),
            'email': forms.EmailInput(attrs={'class': 'form-control'}),
            'emergency_contact': forms.TextInput(attrs={'class': 'form-control'}),
            'address': forms.Textarea(attrs={'class': 'form-control', 'rows': 3}),
            'notes': forms.Textarea(attrs={'class': 'form-control', 'rows': 3}),
        }


class StaffCreationForm(UserCreationForm):
    role = forms.ChoiceField(
        choices=CustomUser.ROLE_CHOICES,
        widget=forms.RadioSelect
    )
    carehome = forms.ModelChoiceField(
        queryset=CareHome.objects.none(),  # Start with empty queryset
        required=False,
        widget=forms.Select(attrs={'class': 'form-control'})
    )

    class Meta:
        model = CustomUser
        fields = (
            'image', 'first_name', 'last_name', 'email',
            'phone', 'address', 'role', 'carehome', 'additional_info',
            'password1', 'password2'
        )
        widgets = {
            'image': forms.FileInput(attrs={'class': 'form-control-file'}),
            'address': forms.Textarea(attrs={'rows': 3, 'class': 'form-control'}),
            'additional_info': forms.Textarea(attrs={'rows': 3, 'class': 'form-control'}),
            'email': forms.EmailInput(attrs={'class': 'form-control'}),
            'first_name': forms.TextInput(attrs={'class': 'form-control'}),
            'last_name': forms.TextInput(attrs={'class': 'form-control'}),
            'phone': forms.TextInput(attrs={'class': 'custom-file-input'}),
        }

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)

        # Populate carehome dropdown safely at runtime
        self.fields['carehome'].queryset = CareHome.objects.all()

        # Optional: add Bootstrap classes to role choices for consistency
        self.fields['role'].widget.attrs.update({'class': 'form-check-input'})

    def clean(self):
        cleaned_data = super().clean()
        role = cleaned_data.get('role')
        carehome = cleaned_data.get('carehome')

        if role == CustomUser.TEAM_LEAD and not carehome:
            self.add_error('carehome', "Care Home is required for Team Leads.")

        return cleaned_data


class ABCFormForm(forms.ModelForm):
    TARGET_BEHAVIOUR_CHOICES = [
        ('physical_aggression', 'Physical aggressive behaviour towards other people'),
        ('property_destruction', 'Property destruction e.g., ripping clothes'),
        ('self_injury', 'Self-injurious behaviours e.g., hitting the wall'),
        ('verbal_aggression', 'Verbal aggression'),
        ('other', 'Other / stereotyped behaviours e.g., screaming'),
    ]

    target_behaviours = forms.MultipleChoiceField(
        choices=TARGET_BEHAVIOUR_CHOICES,
        widget=forms.CheckboxSelectMultiple(attrs={'class': 'checkbox-list'}),
        required=False,
        label='Target Behaviours (select all that apply)'
    )

    class Meta:
        model = ABCForm
        fields = '__all__'
        widgets = {
            'service_user': forms.Select(attrs={
                'class': 'form-control select2',
                'data-placeholder': 'Select a service user'
            }),
            'date_time': forms.DateTimeInput(attrs={
                'type': 'datetime-local',
                'class': 'form-control'
            }),
            'date_of_birth': forms.DateInput(attrs={
                'type': 'date',
                'class': 'form-control'
            }),
            'staff': forms.TextInput(attrs={
                'class': 'form-control'
            }),
            'setting': forms.Textarea(attrs={
                'rows': 3,
                'class': 'form-control',
                'placeholder': 'Where? Who was present? What was happening?'
            }),
            'antecedent': forms.Textarea(attrs={
                'rows': 3,
                'class': 'form-control',
                'placeholder': 'What happened just before the behaviour started?'
            }),
            'behaviour': forms.Textarea(attrs={
                'rows': 5,
                'class': 'form-control',
                'placeholder': 'Describe exactly what the client did'
            }),
            'consequences': forms.Textarea(attrs={
                'rows': 3,
                'class': 'form-control',
                'placeholder': 'What happened after the behaviour took place?'
            }),
            'reflection': forms.Textarea(attrs={
                'rows': 3,
                'class': 'form-control',
                'placeholder': 'What can we learn from this situation?'
            }),
        }

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)

        # Order service users by last name
        self.fields['service_user'].label_from_instance = lambda obj: obj.get_formatted_name()

    # Make staff field regular text input (not autofilled)
        self.fields['staff'].initial = ''  # Clear auto-population
        self.fields['staff'].widget.attrs.update({
            'placeholder': 'Enter staff name manually'
        })

class IncidentReportForm(forms.ModelForm):
    class Meta:
        model = IncidentReport
        fields = '__all__'
        exclude = ['staff', 'carehome', 'pdf_file', 'created_at']


class LogEntryForm(forms.ModelForm):
    class Meta:
        model = LogEntry
        fields = ['content']
        widgets = {
            'content': forms.Textarea(attrs={'rows': 2}),
        }


class MappingForm(forms.ModelForm):
    class Meta:
        model = Mapping
        fields = ['staff', 'carehomes', 'service_users']
        widgets = {
            'carehomes': forms.SelectMultiple(attrs={'class': 'form-control'}),
            'service_users': forms.SelectMultiple(attrs={'class': 'form-control'}),
            'staff': forms.Select(attrs={'class': 'form-control'}),
        }


def __init__(self, *args, **kwargs):
    super().__init__(*args, **kwargs)

    # Only show users with staff role
    self.fields['staff'].queryset = CustomUser.objects.filter(role='staff')

    self.fields['carehomes'].queryset = CareHome.objects.all()
    self.fields['service_users'].queryset = ServiceUser.objects.none()

    self.fields['carehomes'].widget.attrs.update({'id': 'id_carehomes'})
    self.fields['service_users'].widget.attrs.update({'id': 'id_service_users'})

    if 'carehomes' in self.data:
        try:
            carehome_ids = self.data.getlist('carehomes')
            self.fields['service_users'].queryset = ServiceUser.objects.filter(carehome_id__in=carehome_ids)
        except (ValueError, TypeError):
            pass
    elif self.instance.pk:
        self.fields['service_users'].queryset = self.instance.service_users.all()
