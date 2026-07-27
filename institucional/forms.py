from django import forms
from .models import Geriatrico


class GeriatricoForm(forms.ModelForm):
    class Meta:
        model = Geriatrico
        fields = ("nombre", "codigo", "direccion", "capacidad_total", "camas_ocupadas", "activo", "observaciones")
        widgets = {"observaciones": forms.Textarea(attrs={"rows": 4})}
