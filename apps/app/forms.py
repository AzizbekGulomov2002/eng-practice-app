from django import forms
from django.contrib.auth.forms import UserCreationForm, UserChangeForm
from django.core.exceptions import ValidationError
from .models import Users
import re


class CustomUserCreationForm(UserCreationForm):
    first_name = forms.CharField(
        max_length=50,
        required=True,
        widget=forms.TextInput(attrs={'class': 'form-control', 'placeholder': 'Enter first name'}),
        label="First Name"
    )
    last_name = forms.CharField(
        max_length=50,
        required=True,
        widget=forms.TextInput(attrs={'class': 'form-control', 'placeholder': 'Enter last name'}),
        label="Last Name"
    )
    phone = forms.CharField(
        max_length=15,
        required=True,
        widget=forms.TextInput(attrs={
            'class': 'form-control',
            'placeholder': '+998901234567',
            'pattern': r'^\+?[0-9]{9,15}$'
        }),
        label="Phone Number"
    )
    role = forms.ChoiceField(
        choices=Users.ROLE_CHOICES,
        required=True,
        widget=forms.Select(attrs={'class': 'form-control'}),
        label="Role"
    )

    class Meta(UserCreationForm.Meta):
        model = Users
        fields = ('first_name', 'last_name', 'phone', 'role')

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.fields['password1'].required = False
        self.fields['password2'].required = False
        self.fields['password1'].help_text = (
            "Optional. If empty, an 8-digit password is generated. "
            "Username will be the phone number digits."
        )
        self.fields['password1'].widget = forms.PasswordInput(attrs={'class': 'form-control', 'autocomplete': 'new-password'})
        self.fields['password2'].widget = forms.PasswordInput(attrs={'class': 'form-control', 'autocomplete': 'new-password'})

    def clean_phone(self):
        phone = self.cleaned_data.get('phone')
        if not re.match(r'^\+?[0-9]{9,15}$', phone):
            raise ValidationError("Invalid phone number format. Example: +998901234567")
        if Users.objects.filter(phone=phone).exists():
            raise ValidationError("This phone number is already registered.")
        return phone

    def save(self, commit=True):
        user = super().save(commit=False)
        phone_digits = ''.join(filter(str.isdigit, user.phone or ''))
        user.username = phone_digits
        raw_password = self.cleaned_data.get('password1')
        if not raw_password:
            raw_password = user.generate_password()
        user.set_password(raw_password)
        user._generated_password = raw_password
        if commit:
            user.save()
        return user


class CustomUserChangeForm(UserChangeForm):
    first_name = forms.CharField(
        max_length=50,
        required=True,
        widget=forms.TextInput(attrs={'class': 'form-control'}),
        label="First Name"
    )
    last_name = forms.CharField(
        max_length=50,
        required=True,
        widget=forms.TextInput(attrs={'class': 'form-control'}),
        label="Last Name"
    )
    phone = forms.CharField(
        max_length=15,
        required=True,
        widget=forms.TextInput(attrs={'class': 'form-control'}),
        label="Phone Number"
    )
    role = forms.ChoiceField(
        choices=Users.ROLE_CHOICES,
        required=True,
        widget=forms.Select(attrs={'class': 'form-control'}),
        label="Role"
    )

    class Meta(UserChangeForm.Meta):
        model = Users
        fields = ('username', 'first_name', 'last_name', 'phone', 'role', 'is_active', 'is_staff')

    def clean_phone(self):
        phone = self.cleaned_data.get('phone')
        if not re.match(r'^\+?[0-9]{9,15}$', phone):
            raise ValidationError("Invalid phone number format.")
        existing_user = Users.objects.filter(phone=phone).exclude(pk=self.instance.pk)
        if existing_user.exists():
            raise ValidationError("This phone number is used by another user.")
        return phone
