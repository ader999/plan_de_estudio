from django import forms
from multiselectfield import MultiSelectFormField
from .models import Silabo

class SilaboForm(forms.ModelForm):
    tipo_tercer_momento = MultiSelectFormField(
            flat_choices=Silabo.TIPO_TERCER_MOMENTO_LIST,
            choices=Silabo.TIPO_TERCER_MOMENTO_LIST,
            required=False
        )

    class Meta:
        model = Silabo
        fields = '__all__'
        widgets = {
            'fecha': forms.DateInput(attrs={'type': 'date'}),
        }
