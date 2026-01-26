"""Forms for admin panel."""
from django import forms
from unfold.widgets import UnfoldAdminTextInputWidget, UnfoldAdminSelectWidget
from .models import Student, Test


class SendTestForm(forms.Form):
    """Form for sending tests with filters."""
    
    # Grade is automatically taken from test
    region = forms.ChoiceField(
        label="Viloyat",
        choices=[('', 'Barcha')] + list(Student.REGION_CHOICES),
        required=False,
        widget=UnfoldAdminSelectWidget
    )
    
    language = forms.ChoiceField(
        label="Til",
        choices=[('', 'Barcha')] + list(Student.LANGUAGE_CHOICES),
        required=False,
        widget=UnfoldAdminSelectWidget
    )
    
    school_search = forms.CharField(
        label="Maktab (qidiruv)",
        required=False,
        max_length=500,
        widget=UnfoldAdminTextInputWidget(attrs={
            'placeholder': 'Maktab nomini kiriting...'
        })
    )
    
    registration_date_from = forms.DateField(
        label="Ro'yxatdan o'tgan sana (dan)",
        required=False,
        widget=forms.DateInput(attrs={'type': 'date', 'class': 'form-control'})
    )
    
    registration_date_to = forms.DateField(
        label="Ro'yxatdan o'tgan sana (gacha)",
        required=False,
        widget=forms.DateInput(attrs={'type': 'date', 'class': 'form-control'})
    )
    
    def __init__(self, *args, **kwargs):
        test = kwargs.pop('test', None)
        super().__init__(*args, **kwargs)
        if test:
            self.test = test
            # Add grade info (read-only display)
            self.fields['grade_display'] = forms.CharField(
                label="Sinf (majburiy)",
                initial=f"{test.get_grade_display()}",
                required=False,
                widget=UnfoldAdminTextInputWidget(attrs={
                    'readonly': True,
                    'style': 'background-color: #f8f9fa;'
                })
            )
            # Move grade_display to the top
            field_order = ['grade_display'] + [f for f in self.fields.keys() if f != 'grade_display']
            self.order_fields(field_order)
