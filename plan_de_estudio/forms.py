from django import forms
from .models import Silabo


class SilaboForm(forms.ModelForm):
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




