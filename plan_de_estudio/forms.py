from django import forms
from multiselectfield import MultiSelectFormField
from .models import Silabo, Carrera, NUMEROS_ROMANOS, TRIMESTRES_ROMANOS

class SilaboForm(forms.ModelForm):
    class Meta:
        model = Silabo
        fields = '__all__'
        widgets = {
            'fecha': forms.DateInput(attrs={'type': 'date'}),
        }

class ExportarAsignacionesForm(forms.Form):
    trimestre = forms.ChoiceField(
        choices=TRIMESTRES_ROMANOS,
        widget=forms.Select,
        label="Trimestre"
    )
    carreras = forms.ModelMultipleChoiceField(
        queryset=Carrera.objects.all(),
        widget=forms.CheckboxSelectMultiple,
        label="Carreras"
    )
    años = forms.MultipleChoiceField(
        choices=NUMEROS_ROMANOS,
        widget=forms.CheckboxSelectMultiple,
        label="Años"
    )
