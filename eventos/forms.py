from django import forms
from django.contrib.auth.models import User
from .models import Evento, CriterioEvaluacion, Participante, Evaluacion

class EventoForm(forms.ModelForm):
    class Meta:
        model = Evento
        fields = ['nombre', 'descripcion', 'fecha_inicio', 'fecha_fin', 'requiere_jurado']
        widgets = {
            'nombre': forms.TextInput(attrs={'class': 'form-control', 'placeholder': 'Ej. Hackathon 2026'}),
            'descripcion': forms.Textarea(attrs={'class': 'form-control', 'rows': 4, 'placeholder': 'Descripción del evento...'}),
            'fecha_inicio': forms.DateTimeInput(attrs={'class': 'form-control', 'type': 'datetime-local'}),
            'fecha_fin': forms.DateTimeInput(attrs={'class': 'form-control', 'type': 'datetime-local'}),
            'requiere_jurado': forms.CheckboxInput(attrs={'class': 'form-check-input'}),
        }

    def clean(self):
        cleaned_data = super().clean()
        fecha_inicio = cleaned_data.get('fecha_inicio')
        fecha_fin = cleaned_data.get('fecha_fin')

        if fecha_inicio and fecha_fin and fecha_fin <= fecha_inicio:
            self.add_error('fecha_fin', 'La fecha de cierre debe ser posterior a la fecha de inicio.')
        return cleaned_data


class CriterioEvaluacionForm(forms.ModelForm):
    class Meta:
        model = CriterioEvaluacion
        fields = ['nombre', 'descripcion', 'puntaje_maximo']
        widgets = {
            'nombre': forms.TextInput(attrs={'class': 'form-control', 'placeholder': 'Ej. Creatividad, Innovación'}),
            'descripcion': forms.Textarea(attrs={'class': 'form-control', 'rows': 2, 'placeholder': 'Breve descripción del criterio...'}),
            'puntaje_maximo': forms.NumberInput(attrs={'class': 'form-control', 'min': 1, 'placeholder': 'Ej. 20'}),
        }


class ParticipanteForm(forms.ModelForm):
    class Meta:
        model = Participante
        fields = ['nombre', 'descripcion', 'integrantes']
        widgets = {
            'nombre': forms.TextInput(attrs={'class': 'form-control', 'placeholder': 'Ej. Proyecto Alfa o Equipo Dinamita'}),
            'descripcion': forms.Textarea(attrs={'class': 'form-control', 'rows': 2, 'placeholder': 'Descripción del proyecto...'}),
            'integrantes': forms.Textarea(attrs={'class': 'form-control', 'rows': 3, 'placeholder': 'Ej. Juan Pérez, María Gómez, Carlos Rojas...'}),
        }


class EvaluacionForm(forms.Form):
    def __init__(self, *args, **kwargs):
        criterios = kwargs.pop('criterios', [])
        evaluaciones_existentes = kwargs.pop('evaluaciones_existentes', {})
        super().__init__(*args, **kwargs)
        
        for criterio in criterios:
            field_name = f'criterio_{criterio.id}'
            initial_val = evaluaciones_existentes.get(criterio.id, None)
            self.fields[field_name] = forms.IntegerField(
                label=criterio.nombre,
                min_value=0,
                max_value=criterio.puntaje_maximo,
                initial=initial_val,
                widget=forms.NumberInput(attrs={
                    'class': 'form-control scoring-input',
                    'placeholder': f'Máx. {criterio.puntaje_maximo}',
                    'data-max': criterio.puntaje_maximo
                }),
                help_text=criterio.descripcion or f"Puntaje máximo: {criterio.puntaje_maximo} puntos."
            )
