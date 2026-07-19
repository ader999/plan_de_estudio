from django import forms
from multiselectfield import MultiSelectFormField
from .models import Silabo, Carrera, NUMEROS_ROMANOS, TRIMESTRES_ROMANOS

class SilaboForm(forms.ModelForm):
    sin_evaluacion_dinamica = forms.BooleanField(required=False, label="No se realizará una evaluación dinámica en esta clase")

    class Meta:
        model = Silabo
        fields = '__all__'
        widgets = {
            'fecha': forms.DateInput(attrs={'type': 'date'}),
        }

    def clean(self):
        cleaned_data = super().clean()
        sin_evaluacion = cleaned_data.get('sin_evaluacion_dinamica') or self.data.get('sin_evaluacion_dinamica') == 'on'
        
        if sin_evaluacion:
            cleaned_data['actividad_aprendizaje'] = "No se realizará evaluación en clase"
            cleaned_data['tecnica_evaluacion'] = []
            cleaned_data['tipo_evaluacion'] = []
            cleaned_data['periodo_tiempo_programado'] = ""
            cleaned_data['tiempo_minutos'] = 0
            cleaned_data['agente_evaluador'] = []
            cleaned_data['instrumento_evaluacion'] = ""
            cleaned_data['criterios_evaluacion'] = "No se realizará evaluación en clase"
            cleaned_data['puntaje'] = 0

            # Limpiar posibles errores de campos de evaluación dinámica
            campos_evaluacion = [
                'actividad_aprendizaje', 'tecnica_evaluacion', 'tipo_evaluacion',
                'periodo_tiempo_programado', 'tiempo_minutos', 'agente_evaluador',
                'instrumento_evaluacion', 'criterios_evaluacion', 'puntaje'
            ]
            for campo in campos_evaluacion:
                if campo in self._errors:
                    del self._errors[campo]

        return cleaned_data

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
