from django import forms
from multiselectfield import MultiSelectFormField
from .models import (
    AsignacionPlanEstudio,
    Carrera,
    NUMEROS_ROMANOS,
    Silabo,
    TRIMESTRES_ROMANOS,
)
from .trimestre_utils import generar_opciones_trimestre_lectivo

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

class AsignacionPlanEstudioAdminForm(forms.ModelForm):
    """Formulario del Admin que exige seleccionar explícitamente el trimestre lectivo."""

    trimestre_lectivo = forms.ChoiceField(
        choices=[],
        required=True,
        label="Trimestre lectivo",
        help_text=(
            "Seleccione el trimestre y año lectivo exacto al que pertenece esta asignación "
            "(I: Mar–May, II: Jun–Ago, III: Sep–Nov, IV: Dic–Feb)."
        ),
    )

    class Meta:
        model = AsignacionPlanEstudio
        fields = '__all__'

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        extra = (
            [self.instance.trimestre_lectivo]
            if getattr(self.instance, "trimestre_lectivo", None)
            else None
        )
        self.fields['trimestre_lectivo'].choices = generar_opciones_trimestre_lectivo(
            incluir_vacio=True,
            detallado=True,
            extra_values=extra,
        )
        if not (self.instance and self.instance.pk):
            self.initial['trimestre_lectivo'] = ''

    def _post_clean(self):
        tuvo_error_form = 'trimestre_lectivo' in self._errors
        super()._post_clean()
        if tuvo_error_form and 'trimestre_lectivo' in self._errors:
            filtrados = [
                err for err in self._errors['trimestre_lectivo']
                if err != "Debes seleccionar un trimestre lectivo."
            ]
            if filtrados:
                self._errors['trimestre_lectivo'][:] = filtrados


class ExportarAsignacionesForm(forms.Form):
    trimestre_lectivo = forms.ChoiceField(
        choices=[],
        required=False,
        widget=forms.Select,
        label="Trimestre lectivo"
    )
    trimestre = forms.ChoiceField(
        choices=TRIMESTRES_ROMANOS,
        widget=forms.Select,
        label="Trimestre del plan"
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

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.fields['trimestre_lectivo'].choices = generar_opciones_trimestre_lectivo(
            incluir_vacio=True,
            etiqueta_vacio="Todos los trimestres lectivos",
            detallado=True,
        )
