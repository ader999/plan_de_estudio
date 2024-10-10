from django import forms
from .models import Silabo

class SilaboForm(forms.ModelForm):
    class Meta:
        model = Silabo
        fields = '__all__'

    def __init__(self, *args, **kwargs):
        super(SilaboForm, self).__init__(*args, **kwargs)
        # Aplicar clases de Bootstrap a todos los campos visibles
        for visible in self.visible_fields():
            visible.field.widget.attrs['class'] = 'form-control'


