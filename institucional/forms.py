from django import forms
from datetime import date
from decimal import Decimal

from .models import AsignacionTurno, CajaMovimiento, CategoriaCaja, ConfiguracionInstitucional, Geriatrico, MedioPagoConfiguracion, ObraSocial, Pago, PagoParcial, Personal, PorcentajeActualizacion, Residente


class GeriatricoForm(forms.ModelForm):
    class Meta:
        model = Geriatrico
        fields = ("nombre", "codigo", "direccion", "capacidad_total", "activo", "observaciones")
        widgets = {"observaciones": forms.Textarea(attrs={"rows": 4})}


class PagoForm(forms.ModelForm):
    class Meta:
        model = Pago
        fields = ("residente", "periodo", "concepto", "monto", "fecha_vencimiento", "medio_pago", "observaciones")
        widgets = {
            "fecha_vencimiento": forms.DateInput(attrs={"type": "date"}),
            "observaciones": forms.Textarea(attrs={"rows": 3}),
        }

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        residente_id = self.data.get("residente") or self.initial.get("residente") or getattr(self.instance, "residente_id", None)
        if residente_id and not self.initial.get("monto"):
            try:
                monto = Residente.objects.only("monto_mensual").get(pk=residente_id).monto_mensual
                if monto:
                    self.initial["monto"] = monto
            except Residente.DoesNotExist:
                pass


class PagoParcialForm(forms.ModelForm):
    class Meta:
        model = PagoParcial
        fields = ("monto", "fecha_pago", "medio_pago", "observaciones")
        widgets = {
            "fecha_pago": forms.DateInput(attrs={"type": "date"}),
            "observaciones": forms.Textarea(attrs={"rows": 2}),
        }


class GenerarCuotasForm(forms.Form):
    periodo = forms.CharField(max_length=7, initial=date.today().strftime("%Y-%m"), help_text="Formato AAAA-MM")
    fecha_vencimiento = forms.DateField(initial=date.today, widget=forms.DateInput(attrs={"type": "date"}))
    geriatrico = forms.ModelChoiceField(queryset=Geriatrico.objects.all(), required=False, empty_label="Todos los geriátricos")

    def clean_periodo(self):
        periodo = self.cleaned_data["periodo"]
        import re
        if not re.fullmatch(r"\d{4}-(0[1-9]|1[0-2])", periodo):
            raise forms.ValidationError("El período debe tener el formato AAAA-MM.")
        return periodo


class AjusteMontoForm(forms.Form):
    porcentaje = forms.DecimalField(max_digits=6, decimal_places=2, required=False, help_text="Usá valores negativos para disminuir.")
    porcentaje_predefinido = forms.ModelChoiceField(queryset=PorcentajeActualizacion.objects.filter(activo=True), required=False, empty_label="Ingresar porcentaje manual")
    geriatrico = forms.ModelChoiceField(queryset=Geriatrico.objects.all(), required=False, empty_label="Todos los geriátricos")
    obra_social = forms.ChoiceField(required=False, choices=[("", "Todas las coberturas")] + list(Residente.ObraSocial.choices))

    def clean_porcentaje(self):
        porcentaje = self.cleaned_data["porcentaje"]
        if porcentaje is None:
            return porcentaje
        if porcentaje <= Decimal("-100"):
            raise forms.ValidationError("El porcentaje debe dejar un monto mayor que cero.")
        return porcentaje

    def clean(self):
        cleaned_data = super().clean()
        predefinido = cleaned_data.get("porcentaje_predefinido")
        if predefinido:
            cleaned_data["porcentaje"] = predefinido.porcentaje
        elif cleaned_data.get("porcentaje") is None:
            self.add_error("porcentaje", "Ingresá un porcentaje o elegí uno predefinido.")
        return cleaned_data


class EgresoCajaForm(forms.ModelForm):
    class Meta:
        model = CajaMovimiento
        fields = ("fecha", "geriatrico", "categoria", "proveedor_beneficiario", "descripcion", "importe", "medio_pago", "observaciones")
        widgets = {"fecha": forms.DateInput(attrs={"type": "date"}), "observaciones": forms.Textarea(attrs={"rows": 3})}

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.fields["categoria"].queryset = CategoriaCaja.objects.filter(activa=True)


class CategoriaCajaForm(forms.ModelForm):
    class Meta:
        model = CategoriaCaja
        fields = ("nombre", "activa")


class ConfiguracionInstitucionalForm(forms.ModelForm):
    class Meta:
        model = ConfiguracionInstitucional
        fields = ("nombre_institucion", "direccion", "telefono", "email", "cuit", "logo", "dia_vencimiento_defecto", "concepto_cuota_defecto", "moneda")


class ObraSocialForm(forms.ModelForm):
    class Meta:
        model = ObraSocial
        fields = ("nombre", "activa")


class MedioPagoConfiguracionForm(forms.ModelForm):
    class Meta:
        model = MedioPagoConfiguracion
        fields = ("nombre", "activo")


class PorcentajeActualizacionForm(forms.ModelForm):
    class Meta:
        model = PorcentajeActualizacion
        fields = ("porcentaje", "activo")


class PersonalForm(forms.ModelForm):
    class Meta:
        model = Personal
        fields = ("nombre_completo", "dni", "cargo", "turno_habitual", "telefono", "cuil", "inicio_contrato", "estado", "observaciones")
        widgets = {"inicio_contrato": forms.DateInput(attrs={"type": "date"}), "observaciones": forms.Textarea(attrs={"rows": 3})}
