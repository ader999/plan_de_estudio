from django import forms
from multiselectfield import MultiSelectFormField
from .models import Silabo

class SilaboForm(forms.ModelForm):
    class Meta:
        model = Silabo
        fields = '__all__'
        widgets = {
            'fecha': forms.DateInput(attrs={'type': 'date'}),
        }
