from django.contrib import admin
from django.contrib import messages
from django import forms
from django.http import JsonResponse
from django.shortcuts import get_object_or_404, redirect
from django.urls import path, reverse
from django.utils.html import format_html
from django.utils.http import url_has_allowed_host_and_scheme
from .models import AdelantoSueldo, CajaCierre, CajaMovimiento, CategoriaCaja, Comunicado, ConfiguracionInstitucional, GastoRecurrente, GastoRecurrenteMensual, Geriatrico, HistorialEnvioEmail, InvitacionPersonal, LecturaComunicado, LecturaNormaPolitica, NormaPolitica, Pago, PagoParcial, Personal, Residente, Tarea


@admin.register(Geriatrico)
class GeriatricoAdmin(admin.ModelAdmin):
    list_display = ("nombre", "capacidad_total", "camas_ocupadas", "camas_disponibles", "activo")
    list_filter = ("activo",)
    search_fields = ("nombre", "codigo", "direccion")


@admin.register(Residente)
class ResidenteAdmin(admin.ModelAdmin):
    class ResidenteAdminForm(forms.ModelForm):
        class Meta:
            model = Residente
            fields = "__all__"

        def __init__(self, *args, **kwargs):
            super().__init__(*args, **kwargs)
            self.fields["email_contacto"].widget.attrs["placeholder"] = "ejemplo@correo.com"
            self.fields["telefono"].widget.attrs["placeholder"] = "3415123456"
            geriatrico_id = self.data.get(self.add_prefix("geriatrico")) or getattr(self.instance, "geriatrico_id", None)
            self.fields["habitacion"] = forms.ChoiceField(
                required=False,
                choices=ResidenteAdmin.habitaciones_disponibles(geriatrico_id, self.instance.pk),
            )
            self.fields["habitacion"].widget.attrs["data-habitaciones-url"] = reverse(
                "admin:institucional_residente_habitaciones_disponibles", args=[0]
            )

    form = ResidenteAdminForm
    list_display = ("apellido", "nombre", "dni", "geriatrico", "estado")
    list_filter = ("geriatrico", "estado")
    search_fields = ("nombre", "apellido", "dni")

    @staticmethod
    def habitaciones_disponibles(geriatrico_id, residente_id=None):
        if not geriatrico_id:
            return [("", "Seleccioná primero un geriátrico")]
        try:
            geriatrico = Geriatrico.objects.get(pk=geriatrico_id)
        except (Geriatrico.DoesNotExist, ValueError):
            return [("", "Seleccioná primero un geriátrico")]
        ocupadas = Residente.objects.filter(
            geriatrico=geriatrico,
            estado=Residente.Estado.ACTIVO,
        ).exclude(habitacion="")
        if residente_id:
            ocupadas = ocupadas.exclude(pk=residente_id)
        habitaciones_ocupadas = set(ocupadas.values_list("habitacion", flat=True))
        return [("", "---------")] + [
            (str(numero), f"Habitación {numero}")
            for numero in range(1, geriatrico.capacidad_total + 1)
            if str(numero) not in habitaciones_ocupadas
        ]

    def get_urls(self):
        urls = super().get_urls()
        personalizados = [
            path(
                "habitaciones-disponibles/<int:geriatrico_id>/",
                self.admin_site.admin_view(self.habitaciones_disponibles_view),
                name="institucional_residente_habitaciones_disponibles",
            ),
        ]
        return personalizados + urls

    def habitaciones_disponibles_view(self, request, geriatrico_id):
        residente_id = request.GET.get("residente_id")
        return JsonResponse({"habitaciones": self.habitaciones_disponibles(geriatrico_id, residente_id)})

    class Media:
        js = ("institucional/js/residente_admin.js", "institucional/js/residente_habitaciones_admin.js")


@admin.register(Pago)
class PagoAdmin(admin.ModelAdmin):
    list_filter = ("residente__geriatrico", "estado", "periodo")
    search_fields = ("residente__nombre", "residente__apellido", "residente__dni")
    readonly_fields = ("estado",)
    list_display = ("residente", "geriatrico", "periodo", "concepto", "monto", "total_abonado", "saldo_pendiente", "fecha_vencimiento", "estado")

    @admin.display(description="Geriátrico", ordering="residente__geriatrico__nombre")
    def geriatrico(self, pago):
        return pago.residente.geriatrico

    def get_queryset(self, request):
        Pago.actualizar_vencidos()
        return super().get_queryset(request).select_related("residente__geriatrico")


@admin.register(PagoParcial)
class PagoParcialAdmin(admin.ModelAdmin):
    list_display = ("pago", "monto", "fecha_pago", "medio_pago")
    search_fields = ("pago__residente__nombre", "pago__residente__apellido", "pago__residente__dni")

    def save_model(self, request, obj, form, change):
        if not obj.usuario_id:
            obj.usuario = request.user
        super().save_model(request, obj, form, change)


@admin.register(CajaMovimiento)
class CajaMovimientoAdmin(admin.ModelAdmin):
    list_display = ("fecha", "tipo", "nombre_geriatrico", "residente", "importe", "medio_pago", "usuario")
    list_filter = ("tipo", "geriatrico", "fecha")
    search_fields = ("residente__nombre", "residente__apellido", "descripcion", "proveedor_beneficiario")
    readonly_fields = ("tipo", "residente", "pago", "abono", "usuario")


@admin.register(CategoriaCaja)
class CategoriaCajaAdmin(admin.ModelAdmin):
    list_display = ("nombre", "activa")
    list_filter = ("activa",)
    search_fields = ("nombre",)


@admin.register(GastoRecurrente)
class GastoRecurrenteAdmin(admin.ModelAdmin):
    list_display = ("concepto", "importe_estimado", "dia_vencimiento", "nombre_geriatrico", "categoria", "activo")
    list_filter = ("activo", "geriatrico", "categoria")
    search_fields = ("concepto", "observaciones")


@admin.register(GastoRecurrenteMensual)
class GastoRecurrenteMensualAdmin(admin.ModelAdmin):
    list_display = ("periodo", "concepto", "importe_real", "fecha_pago", "nombre_geriatrico", "usuario")
    list_filter = ("periodo", "geriatrico", "categoria")
    search_fields = ("concepto",)
    readonly_fields = ("gasto_recurrente", "periodo", "concepto", "importe_estimado", "importe_real", "dia_vencimiento", "geriatrico", "categoria", "observaciones", "fecha_pago", "movimiento_caja", "usuario", "creado_en")


@admin.register(CajaCierre)
class CajaCierreAdmin(admin.ModelAdmin):
    list_display = ("fecha", "saldo_inicial", "ingresos", "egresos", "saldo_final", "cantidad_cobros", "cantidad_egresos")
    readonly_fields = ("fecha", "saldo_inicial", "ingresos", "egresos", "saldo_final", "cantidad_cobros", "cantidad_egresos", "cerrado_por", "cerrado_en")


@admin.register(ConfiguracionInstitucional)
class ConfiguracionInstitucionalAdmin(admin.ModelAdmin):
    list_display = ("nombre_institucion", "actualizado_en")


@admin.register(HistorialEnvioEmail)
class HistorialEnvioEmailAdmin(admin.ModelAdmin):
    list_display = ("fecha", "usuario", "destinatario", "documento", "resultado", "error")
    list_filter = ("resultado", "documento", "fecha")
    search_fields = ("destinatario", "documento", "error")
    readonly_fields = ("fecha", "usuario", "destinatario", "documento", "resultado", "error")


@admin.register(Personal)
class PersonalAdmin(admin.ModelAdmin):
    list_display = ("nombre_completo", "usuario", "estado_acceso", "cargo", "turno_habitual", "estado", "acciones_invitacion")
    list_filter = ("cargo", "turno_habitual", "estado")
    search_fields = ("nombre_completo", "dni", "cuil", "usuario__username")

    @admin.display(description="Acceso")
    def estado_acceso(self, personal):
        if personal.usuario_id:
            return "Cuenta activa"
        try:
            invitacion = personal.invitacion
        except InvitacionPersonal.DoesNotExist:
            return "Sin usuario"
        return "Invitación pendiente" if invitacion.vigente else "Sin usuario"

    @admin.display(description="Invitación")
    def acciones_invitacion(self, personal):
        if personal.usuario_id:
            return "—"
        generar = reverse("admin:institucional_personal_generar_invitacion", args=[personal.pk])
        try:
            invitacion = personal.invitacion
        except InvitacionPersonal.DoesNotExist:
            invitacion = None
        etiqueta = "Regenerar invitación" if invitacion else "Generar invitación"
        enlace = format_html('<a class="button" href="{}">{}</a>', generar, etiqueta)
        if invitacion and invitacion.vigente:
            activacion = reverse("activar_cuenta", args=[invitacion.token])
            copiar = format_html(' <button type="button" class="button" onclick="navigator.clipboard.writeText(window.location.origin + \'{}\')">Copiar enlace</button>', activacion)
            return format_html("{}{}", enlace, copiar)
        return enlace

    def get_urls(self):
        urls = super().get_urls()
        personalizados = [
            path("<int:personal_id>/generar-invitacion/", self.admin_site.admin_view(self.generar_invitacion), name="institucional_personal_generar_invitacion"),
        ]
        return personalizados + urls

    def generar_invitacion(self, request, personal_id):
        personal = get_object_or_404(Personal, pk=personal_id)
        if personal.usuario_id:
            messages.error(request, "La empleada ya tiene una cuenta activa.")
        else:
            invitacion, creada = InvitacionPersonal.objects.get_or_create(personal=personal)
            if not creada:
                invitacion.regenerar()
            messages.success(request, "Invitación generada. Copiá el enlace desde la columna Invitación.")
        siguiente = request.GET.get("next", "")
        if siguiente and url_has_allowed_host_and_scheme(siguiente, {request.get_host()}):
            return redirect(siguiente)
        return redirect("admin:institucional_personal_changelist")


@admin.register(AdelantoSueldo)
class AdelantoSueldoAdmin(admin.ModelAdmin):
    list_display = ("personal", "fecha", "importe", "mes", "anio", "usuario")
    list_filter = ("anio", "mes", "personal")
    search_fields = ("personal__nombre_completo", "personal__dni", "observaciones")
    readonly_fields = ("usuario", "creado_en")

    def save_model(self, request, obj, form, change):
        if not obj.usuario_id:
            obj.usuario = request.user
        super().save_model(request, obj, form, change)


@admin.register(Tarea)
class TareaAdmin(admin.ModelAdmin):
    list_display = ("titulo", "asignada_a", "fecha", "turno", "estado", "vencida", "completada_en")
    list_filter = ("estado", "turno", "fecha", "asignada_a")
    search_fields = ("titulo", "descripcion", "asignada_a__nombre_completo")
    readonly_fields = ("creada_en", "completada_en", "completada_por", "observacion_completado")


@admin.register(NormaPolitica)
class NormaPoliticaAdmin(admin.ModelAdmin):
    list_display = ("titulo", "activa", "publicada_en")
    list_filter = ("activa", "publicada_en")
    search_fields = ("titulo", "contenido")
    readonly_fields = ("publicada_en",)


@admin.register(Comunicado)
class ComunicadoAdmin(admin.ModelAdmin):
    list_display = ("titulo", "fecha", "nombre_geriatrico", "prioridad", "activo", "usuario")
    list_filter = ("prioridad", "activo", "geriatrico", "fecha")
    search_fields = ("titulo", "mensaje")
    readonly_fields = ("usuario", "creado_en")

    def save_model(self, request, obj, form, change):
        if not obj.usuario_id:
            obj.usuario = request.user
        super().save_model(request, obj, form, change)


@admin.register(LecturaComunicado)
class LecturaComunicadoAdmin(admin.ModelAdmin):
    list_display = ("comunicado", "personal", "leido_en")
    list_filter = ("comunicado", "leido_en")
    search_fields = ("comunicado__titulo", "personal__nombre_completo")
    readonly_fields = ("comunicado", "personal", "leido_en")


@admin.register(LecturaNormaPolitica)
class LecturaNormaPoliticaAdmin(admin.ModelAdmin):
    list_display = ("norma", "personal", "leido_en")
    list_filter = ("norma", "leido_en")
    search_fields = ("norma__titulo", "personal__nombre_completo")
    readonly_fields = ("norma", "personal", "leido_en")
