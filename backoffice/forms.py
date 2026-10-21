from django import forms
from django.utils.translation import gettext_lazy as _


class LoginForm(forms.Form):
    email = forms.EmailField(max_length=254, label=_('Email address'))
    password = forms.CharField(
        max_length=256, strip=False, widget=forms.PasswordInput, label=_('Password'),
    )
