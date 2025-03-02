from django import forms
from .models import Silabo, Guia


class SilaboForm(forms.ModelForm):
    guia = forms.ModelChoiceField(
        queryset=Guia.objects.all(),  # Ajusta según necesites filtrar
        required=False,
        empty_label="Selecciona una Guía de Estudio"
    )

    class Meta:
        model = Silabo
        fields = '__all__'

    def __init__(self, *args, **kwargs):
        super(SilaboForm, self).__init__(*args, **kwargs)
        for visible in self.visible_fields():
            visible.field.widget.attrs['class'] = 'form-control'

        # Asegurarse de que el campo de fecha tenga el tipo adecuado
        if 'fecha' in self.fields:
            self.fields['fecha'].widget = forms.DateInput(attrs={'class': 'form-control', 'type': 'date'})
