from django import forms
from django.contrib.auth.forms import PasswordChangeForm, UserChangeForm, UserCreationForm
from django.contrib.auth.models import User
from datetime import date
from decimal import Decimal

from .models import AsignacionTurno, CajaMovimiento, CategoriaCaja, ConfiguracionInstitucional, Geriatrico, MedioPagoConfiguracion, ObraSocial, Pago, PagoParcial, PerfilUsuario, Personal, PorcentajeActualizacion, Residente, Tarea
from .moneda import decimal_importe


class ImporteDecimalField(forms.DecimalField):
    def to_python(self, value):
        if value in self.empty_values:
            return None
        try:
            return decimal_importe(value)
        except ValueError as error:
            raise forms.ValidationError(str(error))


class GeriatricoForm(forms.ModelForm):
    class Meta:
        model = Geriatrico
        fields = ("nombre", "codigo", "direccion", "capacidad_total", "activo", "observaciones")
        widgets = {"observaciones": forms.Textarea(attrs={"rows": 4})}


class PagoForm(forms.ModelForm):
    class Meta:
        model = Pago
        fields = ("residente", "periodo", "concepto", "monto", "fecha_vencimiento", "fecha_pago", "medio_pago", "observaciones")
        widgets = {
            "fecha_vencimiento": forms.DateInput(attrs={"type": "date"}),
            "fecha_pago": forms.DateInput(attrs={"type": "date"}),
            "observaciones": forms.Textarea(attrs={"rows": 3}),
        }

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.fields["monto"] = ImporteDecimalField(max_digits=12, decimal_places=2, label="Monto")
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

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.fields["monto"] = ImporteDecimalField(max_digits=12, decimal_places=2, label="Monto")


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

    def clean_fecha_vencimiento(self):
        fecha_vencimiento = self.cleaned_data["fecha_vencimiento"]
        if fecha_vencimiento < date.today():
            raise forms.ValidationError("La fecha de vencimiento no puede ser anterior a la fecha actual.")
        return fecha_vencimiento


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
        self.fields["importe"] = ImporteDecimalField(max_digits=12, decimal_places=2, label="Importe")


class CategoriaCajaForm(forms.ModelForm):
    class Meta:
        model = CategoriaCaja
        fields = ("nombre", "activa")


class ConfiguracionInstitucionalForm(forms.ModelForm):
    class Meta:
        model = ConfiguracionInstitucional
        fields = ("nombre_institucion", "direccion", "telefono", "email", "cuit", "logo", "dia_vencimiento_defecto", "concepto_cuota_defecto", "moneda", "smtp_servidor", "smtp_puerto", "smtp_usuario", "smtp_contrasena", "smtp_tls", "smtp_ssl", "smtp_remitente", "smtp_nombre_remitente")
        widgets = {"smtp_contrasena": forms.PasswordInput()}

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        if self.instance and self.instance.smtp_contrasena:
            self.fields["smtp_contrasena"].help_text = "Deje este campo vacío para conservar la contraseña actual."

    def clean(self):
        cleaned_data = super().clean()
        if cleaned_data.get("smtp_tls") and cleaned_data.get("smtp_ssl"):
            self.add_error("smtp_ssl", "TLS y SSL no pueden estar activos simultáneamente.")
        if not cleaned_data.get("smtp_contrasena") and self.instance and self.instance.pk:
            cleaned_data["smtp_contrasena"] = self.instance.smtp_contrasena
        return cleaned_data


class EnvioEmailForm(forms.Form):
    destinatario = forms.EmailField(label="Destinatario")
    asunto = forms.CharField(max_length=200, label="Asunto")
    mensaje = forms.CharField(label="Mensaje", widget=forms.Textarea(attrs={"rows": 4}))


class CompletarTareaForm(forms.Form):
    observacion = forms.CharField(label="Observación de finalización", required=False, widget=forms.Textarea(attrs={"rows": 4, "placeholder": "Detalle opcional sobre la tarea realizada."}))


class ActivarCuentaForm(UserCreationForm):
    email = forms.EmailField(label="Email")

    class Meta(UserCreationForm.Meta):
        model = User
        fields = ("username", "email", "password1", "password2")

    def clean_email(self):
        email = self.cleaned_data["email"].lower()
        if User.objects.filter(email__iexact=email).exists():
            raise forms.ValidationError("Ya existe una cuenta con este email.")
        return email

    def clean_password2(self):
        password = self.cleaned_data.get("password2")
        if password != self.cleaned_data.get("password1"):
            raise forms.ValidationError("Las contraseñas no coinciden.")
        if password and (len(password) < 8 or not any(char.isalpha() for char in password) or not any(char.isdigit() for char in password)):
            raise forms.ValidationError("La contraseña debe tener al menos 8 caracteres, letras y números.")
        return password


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


class ResidenteForm(forms.ModelForm):
    class Meta:
        model = Residente
        fields = ("geriatrico", "nombre", "apellido", "dni", "fecha_nacimiento", "fecha_ingreso", "habitacion", "obra_social", "obra_social_otra", "numero_afiliado", "contacto_familiar", "email_contacto", "telefono", "medico_tratante", "diagnostico_principal", "movilidad", "observaciones", "estado", "monto_mensual")
        widgets = {
            "fecha_nacimiento": forms.DateInput(attrs={"type": "date"}),
            "fecha_ingreso": forms.DateInput(attrs={"type": "date"}),
            "diagnostico_principal": forms.Textarea(attrs={"rows": 3}),
            "observaciones": forms.Textarea(attrs={"rows": 3}),
            "email_contacto": forms.EmailInput(attrs={"placeholder": "ejemplo@correo.com"}),
            "telefono": forms.TextInput(attrs={"placeholder": "3415123456"}),
            "contacto_familiar": forms.TextInput(attrs={"placeholder": "Nombre y apellido"}),
        }


class PerfilUsuarioForm(UserChangeForm):
    password = None

    class Meta:
        model = User
        fields = ("first_name", "last_name", "email")
        labels = {"first_name": "Nombre", "last_name": "Apellido", "email": "Email"}


class FotoPerfilForm(forms.ModelForm):
    class Meta:
        model = PerfilUsuario
        fields = ("foto",)


class CambioContrasenaForm(PasswordChangeForm):
    pass
