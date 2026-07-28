from django.contrib.auth.mixins import LoginRequiredMixin, PermissionRequiredMixin, UserPassesTestMixin
from datetime import date, timedelta
import calendar
import json
from decimal import Decimal, ROUND_HALF_UP

from django.contrib import messages
from django.core.exceptions import ValidationError
from django.db import IntegrityError, transaction
from django.db.models import Count, Q, Sum
from django.shortcuts import get_object_or_404, redirect
from django.urls import reverse, reverse_lazy
from django.utils import timezone
from django.views import View
from django.views.generic import CreateView, DeleteView, DetailView, ListView, TemplateView, UpdateView
from .forms import AjusteMontoForm, CategoriaCajaForm, CompletarTareaForm, ConfiguracionInstitucionalForm, EgresoCajaForm, EnvioEmailForm, GenerarCuotasForm, GeriatricoForm, MedioPagoConfiguracionForm, ObraSocialForm, PagoForm, PagoParcialForm, PersonalForm, PorcentajeActualizacionForm
from .models import AsignacionTurno, CajaCierre, CajaMovimiento, CategoriaCaja, ConfiguracionInstitucional, Geriatrico, GrillaTurnos, HistorialEnvioEmail, LecturaNormaPolitica, MedioPagoConfiguracion, NormaPolitica, ObraSocial, Pago, PagoParcial, Personal, PorcentajeActualizacion, Residente, Tarea
from .reportes import enviar_pdf, excel_response, pdf_response


class InicioView(LoginRequiredMixin, TemplateView):
    template_name = "institucional/inicio.html"

    nombres_meses = ("", "Enero", "Febrero", "Marzo", "Abril", "Mayo", "Junio", "Julio", "Agosto", "Septiembre", "Octubre", "Noviembre", "Diciembre")

    def filtro_fecha(self):
        hoy = date.today()
        try:
            mes = int(self.request.GET.get("mes", hoy.month))
            anio = int(self.request.GET.get("anio", hoy.year))
            if mes not in range(1, 13):
                raise ValueError
        except (TypeError, ValueError):
            mes, anio = hoy.month, hoy.year
        return mes, anio

    def rango_mes(self, mes, anio):
        return date(anio, mes, 1), date(anio, mes, calendar.monthrange(anio, mes)[1])

    def meses_recientes(self, mes, anio):
        resultado = []
        for desplazamiento in range(5, -1, -1):
            indice = anio * 12 + mes - 1 - desplazamiento
            anio_mes, mes_mes = divmod(indice, 12)
            resultado.append((mes_mes + 1, anio_mes))
        return resultado

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        Pago.actualizar_vencidos()
        mes, anio = self.filtro_fecha()
        inicio_mes, fin_mes = self.rango_mes(mes, anio)
        geriatrico_id = self.request.GET.get("geriatrico", "")
        geriatrico_qs = Geriatrico.objects.all()
        if geriatrico_id:
            geriatrico_qs = geriatrico_qs.filter(pk=geriatrico_id)
        geriatrico_qs = geriatrico_qs.annotate(
            residentes_activos=Count(
                "residentes",
                filter=Q(residentes__estado=Residente.Estado.ACTIVO),
            )
        )
        geriatrico_estadisticas = []
        for geriatrico in geriatrico_qs:
            disponibles = geriatrico.capacidad_total - geriatrico.residentes_activos
            geriatrico_estadisticas.append({
                "geriatrico": geriatrico,
                "ocupadas": geriatrico.residentes_activos,
                "disponibles": disponibles,
                "ocupacion": (geriatrico.residentes_activos / geriatrico.capacidad_total * 100),
            })
        capacidad_total = geriatrico_qs.aggregate(total=Sum("capacidad_total"))["total"] or 0
        residentes_activos = sum(item["ocupadas"] for item in geriatrico_estadisticas)
        pagos = Pago.objects.select_related("residente__geriatrico").all()
        movimientos = CajaMovimiento.objects.select_related("geriatrico", "categoria", "residente").all()
        if geriatrico_id:
            pagos = pagos.filter(residente__geriatrico_id=geriatrico_id)
            movimientos = movimientos.filter(geriatrico_id=geriatrico_id)
        pagos_pendientes = pagos.exclude(estado=Pago.Estado.PAGADO)
        pagos_mes = pagos.filter(periodo=f"{anio}-{mes:02d}")
        abonos_mes = PagoParcial.objects.filter(fecha_pago__range=(inicio_mes, fin_mes))
        if geriatrico_id:
            abonos_mes = abonos_mes.filter(pago__residente__geriatrico_id=geriatrico_id)
        movimientos_mes = movimientos.filter(fecha__range=(inicio_mes, fin_mes))
        ingresos_mes = movimientos_mes.filter(tipo=CajaMovimiento.Tipo.INGRESO).aggregate(total=Sum("importe"))["total"] or Decimal("0.00")
        egresos_mes = movimientos_mes.filter(tipo=CajaMovimiento.Tipo.EGRESO).aggregate(total=Sum("importe"))["total"] or Decimal("0.00")
        ingresos_total = movimientos.filter(tipo=CajaMovimiento.Tipo.INGRESO).aggregate(total=Sum("importe"))["total"] or Decimal("0.00")
        egresos_total = movimientos.filter(tipo=CajaMovimiento.Tipo.EGRESO).aggregate(total=Sum("importe"))["total"] or Decimal("0.00")
        pagos_deuda = list(pagos_pendientes.prefetch_related("abonos").order_by("fecha_vencimiento"))
        deuda_por_residente = {}
        for pago in pagos_deuda:
            item = deuda_por_residente.setdefault(pago.residente_id, {"residente": pago.residente, "deuda": Decimal("0.00")})
            item["deuda"] += pago.saldo_pendiente
        meses = self.meses_recientes(mes, anio)
        etiquetas_meses = [f"{self.nombres_meses[m][:3]} {a}" for m, a in meses]
        ingresos_serie, egresos_serie, facturado_serie, cobrado_serie = [], [], [], []
        for mes_serie, anio_serie in meses:
            desde, hasta = self.rango_mes(mes_serie, anio_serie)
            movimientos_serie = movimientos.filter(fecha__range=(desde, hasta))
            ingresos_serie.append(float(movimientos_serie.filter(tipo=CajaMovimiento.Tipo.INGRESO).aggregate(total=Sum("importe"))["total"] or 0))
            egresos_serie.append(float(movimientos_serie.filter(tipo=CajaMovimiento.Tipo.EGRESO).aggregate(total=Sum("importe"))["total"] or 0))
            pagos_serie = pagos.filter(periodo=f"{anio_serie}-{mes_serie:02d}")
            facturado_serie.append(float(pagos_serie.aggregate(total=Sum("monto"))["total"] or 0))
            abonos_serie = PagoParcial.objects.filter(fecha_pago__range=(desde, hasta))
            if geriatrico_id:
                abonos_serie = abonos_serie.filter(pago__residente__geriatrico_id=geriatrico_id)
            cobrado_serie.append(float(abonos_serie.aggregate(total=Sum("monto"))["total"] or 0))
        estados_pago = [(estado, pagos.filter(estado=estado).count()) for estado, _ in Pago.Estado.choices]
        egresos_categoria = movimientos_mes.filter(tipo=CajaMovimiento.Tipo.EGRESO, categoria__isnull=False).values("categoria__nombre").annotate(total=Sum("importe")).order_by("categoria__nombre")
        obras_sociales = Residente.objects.filter(estado=Residente.Estado.ACTIVO)
        if geriatrico_id:
            obras_sociales = obras_sociales.filter(geriatrico_id=geriatrico_id)
        obras_sociales = obras_sociales.values("obra_social").annotate(total=Count("id")).order_by("obra_social")
        context.update({
            "residentes_activos": residentes_activos,
            "camas_ocupadas": residentes_activos,
            "camas_disponibles": capacidad_total - residentes_activos,
            "capacidad_total": capacidad_total,
            "porcentaje_ocupacion": (residentes_activos / capacidad_total * 100) if capacidad_total else 0,
            "pagos_pendientes": pagos.filter(estado__in=(Pago.Estado.PENDIENTE, Pago.Estado.PARCIAL)).count(),
            "pagos_vencidos": pagos.filter(estado=Pago.Estado.VENCIDO).count(),
            "total_facturado_mes": pagos_mes.aggregate(total=Sum("monto"))["total"] or Decimal("0.00"),
            "total_cobrado_mes": abonos_mes.aggregate(total=Sum("monto"))["total"] or Decimal("0.00"),
            "deuda_pendiente": sum((item["deuda"] for item in deuda_por_residente.values()), Decimal("0.00")),
            "ingresos_mes": ingresos_mes,
            "egresos_mes": egresos_mes,
            "resultado_mes": ingresos_mes - egresos_mes,
            "saldo_actual_caja": ingresos_total - egresos_total,
            "personal_activo": Personal.objects.filter(estado=Personal.Estado.ACTIVO).count(),
            "geriatrico_estadisticas": geriatrico_estadisticas,
            "ultimos_pagos": pagos.order_by("-periodo", "-pk")[:5],
            "ultimos_egresos": movimientos.filter(tipo=CajaMovimiento.Tipo.EGRESO).order_by("-fecha", "-pk")[:5],
            "residentes_con_deuda": sorted(deuda_por_residente.values(), key=lambda item: item["deuda"], reverse=True)[:5],
            "lista_pagos_vencidos": pagos.filter(estado=Pago.Estado.VENCIDO).order_by("fecha_vencimiento")[:5],
            "geriatrico_opciones": Geriatrico.objects.all(),
            "filtros": {"geriatrico": geriatrico_id, "mes": mes, "anio": anio},
            "meses_opciones": list(enumerate(self.nombres_meses))[1:],
            "anios_opciones": range(anio - 2, anio + 3),
            "grafico_ocupacion": json.dumps({"labels": [item["geriatrico"].nombre for item in geriatrico_estadisticas], "data": [item["ocupacion"] for item in geriatrico_estadisticas]}),
            "grafico_caja": json.dumps({"labels": etiquetas_meses, "ingresos": ingresos_serie, "egresos": egresos_serie}),
            "grafico_pagos": json.dumps({"labels": [estado for estado, total in estados_pago if total], "data": [total for estado, total in estados_pago if total]}),
            "grafico_egresos": json.dumps({"labels": [item["categoria__nombre"] for item in egresos_categoria], "data": [float(item["total"]) for item in egresos_categoria]}),
            "grafico_facturacion": json.dumps({"labels": etiquetas_meses, "facturado": facturado_serie, "cobrado": cobrado_serie}),
            "grafico_obras": json.dumps({"labels": [item["obra_social"] or "Sin cobertura" for item in obras_sociales], "data": [item["total"] for item in obras_sociales]}),
        })
        return context


class PersonalActualMixin:
    def personal_actual(self):
        try:
            return self.request.user.perfil_personal
        except Personal.DoesNotExist:
            return None


class TareasListView(LoginRequiredMixin, PersonalActualMixin, ListView):
    model = Tarea
    template_name = "institucional/tarea_list.html"

    def get_queryset(self):
        queryset = Tarea.objects.select_related("asignada_a", "completada_por")
        if self.request.user.is_staff:
            return queryset
        personal = self.personal_actual()
        return queryset.filter(asignada_a=personal) if personal else queryset.none()

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        personal = self.personal_actual()
        context.update({
            "personal_actual": personal,
            "tareas_pendientes": self.get_queryset().exclude(estado=Tarea.Estado.COMPLETADA).count(),
            "tareas_vencidas": self.get_queryset().exclude(estado=Tarea.Estado.COMPLETADA, fecha__gte=date.today()).count(),
        })
        return context


class TareaEnProcesoView(LoginRequiredMixin, PersonalActualMixin, View):
    def post(self, request, pk):
        personal = self.personal_actual()
        tarea = get_object_or_404(Tarea, pk=pk, asignada_a=personal)
        if tarea.estado == Tarea.Estado.PENDIENTE:
            tarea.estado = Tarea.Estado.EN_PROCESO
            tarea.save(update_fields=("estado",))
            messages.success(request, "Tarea marcada como en proceso.")
        return redirect("tarea_list")


class TareaCompletarView(LoginRequiredMixin, PersonalActualMixin, TemplateView):
    template_name = "institucional/tarea_completar.html"

    def get_tarea(self):
        return get_object_or_404(Tarea, pk=self.kwargs["pk"], asignada_a=self.personal_actual())

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context.update({"tarea": self.get_tarea(), "form": kwargs.get("form", CompletarTareaForm())})
        return context

    def post(self, request, *args, **kwargs):
        tarea = self.get_tarea()
        form = CompletarTareaForm(request.POST)
        if form.is_valid():
            tarea.completar(request.user, form.cleaned_data["observacion"])
            messages.success(request, "Tarea completada y registrada correctamente.")
            return redirect("tarea_list")
        return self.render_to_response(self.get_context_data(form=form))


class NormasListView(LoginRequiredMixin, PersonalActualMixin, ListView):
    model = NormaPolitica
    template_name = "institucional/norma_list.html"

    def get_queryset(self):
        queryset = NormaPolitica.objects.prefetch_related("lecturas")
        return queryset if self.request.user.is_staff else queryset.filter(activa=True)

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        personal = self.personal_actual()
        leidas = set()
        if personal:
            leidas = set(LecturaNormaPolitica.objects.filter(personal=personal).values_list("norma_id", flat=True))
        context.update({"personal_actual": personal, "normas_leidas": leidas})
        return context


class NormaMarcarLeidaView(LoginRequiredMixin, PersonalActualMixin, View):
    def post(self, request, pk):
        personal = self.personal_actual()
        norma = get_object_or_404(NormaPolitica, pk=pk, activa=True)
        if not personal:
            messages.error(request, "Tu usuario no está vinculado a una ficha de personal.")
        else:
            LecturaNormaPolitica.objects.get_or_create(norma=norma, personal=personal)
            messages.success(request, "Norma marcada como leída.")
        return redirect("norma_list")


class PanelTareasAdminView(LoginRequiredMixin, UserPassesTestMixin, TemplateView):
    template_name = "institucional/tarea_panel.html"

    def test_func(self):
        return self.request.user.is_staff

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        tareas = Tarea.objects.select_related("asignada_a")
        cumplimiento = []
        for persona in Personal.objects.filter(estado=Personal.Estado.ACTIVO):
            total = tareas.filter(asignada_a=persona).count()
            completadas = tareas.filter(asignada_a=persona, estado=Tarea.Estado.COMPLETADA).count()
            cumplimiento.append({"personal": persona, "total": total, "completadas": completadas, "porcentaje": (completadas / total * 100) if total else 0})
        context.update({
            "pendientes": tareas.filter(estado=Tarea.Estado.PENDIENTE).count(),
            "completadas": tareas.filter(estado=Tarea.Estado.COMPLETADA).count(),
            "vencidas": tareas.exclude(estado=Tarea.Estado.COMPLETADA, fecha__gte=date.today()).count(),
            "cumplimiento": cumplimiento,
            "ultimas_tareas": tareas.order_by("fecha", "turno")[:10],
        })
        return context


class GeriatricoListView(LoginRequiredMixin, PermissionRequiredMixin, ListView):
    model = Geriatrico
    template_name = "institucional/geriatrico_list.html"
    permission_required = "institucional.view_geriatrico"


class GeriatricoCreateView(LoginRequiredMixin, PermissionRequiredMixin, CreateView):
    model = Geriatrico
    form_class = GeriatricoForm
    template_name = "institucional/geriatrico_form.html"
    permission_required = "institucional.add_geriatrico"
    success_url = reverse_lazy("geriatrico_list")


class GeriatricoUpdateView(LoginRequiredMixin, PermissionRequiredMixin, UpdateView):
    model = Geriatrico
    form_class = GeriatricoForm
    template_name = "institucional/geriatrico_form.html"
    permission_required = "institucional.change_geriatrico"
    success_url = reverse_lazy("geriatrico_list")


class GeriatricoDeleteView(LoginRequiredMixin, PermissionRequiredMixin, DeleteView):
    model = Geriatrico
    template_name = "institucional/geriatrico_confirm_delete.html"
    permission_required = "institucional.delete_geriatrico"
    success_url = reverse_lazy("geriatrico_list")


class ResidenteListView(LoginRequiredMixin, ListView):
    model = Residente
    template_name = "institucional/residente_list.html"

    def get_queryset(self):
        queryset = Residente.objects.select_related("geriatrico")
        busqueda = self.request.GET.get("q", "").strip()
        geriatrico = self.request.GET.get("geriatrico", "")
        estado = self.request.GET.get("estado", "")
        if busqueda:
            queryset = queryset.filter(
                Q(nombre__icontains=busqueda)
                | Q(apellido__icontains=busqueda)
                | Q(dni__icontains=busqueda)
            )
        if geriatrico:
            queryset = queryset.filter(geriatrico_id=geriatrico)
        if estado:
            queryset = queryset.filter(estado=estado)
        return queryset

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context.update({
            "geriatrico_opciones": Geriatrico.objects.all(),
            "estado_opciones": Residente.Estado.choices,
            "filtros": self.request.GET,
        })
        return context


class ExportarResidentesView(ResidenteListView):
    def get(self, request, formato):
        filas = [(r.apellido + ", " + r.nombre, r.dni, r.geriatrico.nombre, r.habitacion, r.estado, r.obra_social) for r in self.get_queryset()]
        columnas = ["Apellido y nombre", "DNI", "Geriátrico", "Habitación", "Estado", "Obra social"]
        institucion, _ = ConfiguracionInstitucional.objects.get_or_create(pk=1)
        return excel_response("residentes", columnas, filas) if formato == "excel" else pdf_response("Reporte de residentes", columnas, filas, institucion, request.user)


class ResidenteDetailView(LoginRequiredMixin, DetailView):
    model = Residente
    template_name = "institucional/residente_detail.html"
    queryset = Residente.objects.select_related("geriatrico")

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        pagos = self.object.pagos.prefetch_related("abonos").all()
        context.update({
            "cuenta_pagos": pagos,
            "total_facturado": sum((pago.monto for pago in pagos), Decimal("0.00")),
            "total_abonado": sum((pago.total_abonado for pago in pagos), Decimal("0.00")),
            "deuda_total": sum((pago.saldo_pendiente for pago in pagos), Decimal("0.00")),
        })
        return context


class PagoListView(LoginRequiredMixin, ListView):
    model = Pago
    template_name = "institucional/pago_list.html"

    def get_queryset(self):
        Pago.actualizar_vencidos()
        queryset = Pago.objects.select_related("residente__geriatrico")
        busqueda = self.request.GET.get("q", "").strip()
        geriatrico = self.request.GET.get("geriatrico", "")
        estado = self.request.GET.get("estado", "")
        periodo = self.request.GET.get("periodo", "").strip()
        if busqueda:
            queryset = queryset.filter(
                Q(residente__nombre__icontains=busqueda)
                | Q(residente__apellido__icontains=busqueda)
                | Q(residente__dni__icontains=busqueda)
            )
        if geriatrico:
            queryset = queryset.filter(residente__geriatrico_id=geriatrico)
        if estado:
            queryset = queryset.filter(estado=estado)
        if periodo:
            queryset = queryset.filter(periodo=periodo)
        return queryset

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context.update({
            "geriatrico_opciones": Geriatrico.objects.all(),
            "estado_opciones": Pago.Estado.choices,
            "periodo_opciones": Pago.objects.order_by("-periodo").values_list("periodo", flat=True).distinct(),
            "filtros": self.request.GET,
        })
        return context


class ExportarPagosView(PagoListView):
    def get(self, request, formato):
        filas = [(p.residente, p.residente.geriatrico.nombre, p.periodo, p.concepto, p.monto, p.total_abonado, p.saldo_pendiente, p.fecha_vencimiento, p.estado) for p in self.get_queryset()]
        columnas = ["Residente", "Geriátrico", "Período", "Concepto", "Monto", "Abonado", "Saldo", "Vencimiento", "Estado"]
        institucion, _ = ConfiguracionInstitucional.objects.get_or_create(pk=1)
        return excel_response("pagos", columnas, filas) if formato == "excel" else pdf_response("Reporte de pagos", columnas, filas, institucion, request.user)


class PagoCreateView(LoginRequiredMixin, CreateView):
    model = Pago
    form_class = PagoForm
    template_name = "institucional/pago_form.html"

    def get_initial(self):
        initial = super().get_initial()
        residente = self.request.GET.get("residente")
        if residente:
            initial["residente"] = residente
        return initial

    def get_success_url(self):
        return reverse("pago_detail", kwargs={"pk": self.object.pk})

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context["montos_residentes"] = {
            str(residente.pk): str(residente.monto_mensual or "")
            for residente in Residente.objects.only("pk", "monto_mensual")
        }
        return context


class PagoUpdateView(LoginRequiredMixin, UpdateView):
    model = Pago
    form_class = PagoForm
    template_name = "institucional/pago_form.html"

    def get_success_url(self):
        return reverse("pago_detail", kwargs={"pk": self.object.pk})


class PagoDetailView(LoginRequiredMixin, DetailView):
    model = Pago
    template_name = "institucional/pago_detail.html"
    queryset = Pago.objects.select_related("residente__geriatrico").prefetch_related("abonos")

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context["abono_form"] = kwargs.get("abono_form", PagoParcialForm())
        return context

    def post(self, request, *args, **kwargs):
        self.object = self.get_object()
        form = PagoParcialForm(request.POST)
        if form.is_valid():
            abono = form.save(commit=False)
            abono.pago = self.object
            abono.usuario = request.user
            try:
                abono.save()
            except ValidationError as error:
                form.add_error("monto", error.message_dict.get("monto", ["No se pudo registrar el abono."])[0])
            else:
                messages.success(request, "Abono registrado correctamente.")
                return redirect("pago_detail", pk=self.object.pk)
        return self.render_to_response(self.get_context_data(abono_form=form))


class EnviarComprobanteLegacyView(LoginRequiredMixin, View):
    def post(self, request, pk):
        pago = get_object_or_404(Pago.objects.select_related("residente__geriatrico"), pk=pk); destino = pago.residente.email_contacto; institucion, _ = ConfiguracionInstitucional.objects.get_or_create(pk=1)
        try:
            if not destino: raise ValueError("El residente no tiene email de contacto.")
            pdf = pdf_response("Comprobante", ["Residente","Período","Concepto","Monto","Abonado","Saldo"], [(pago.residente,pago.periodo,pago.concepto,pago.monto,pago.total_abonado,pago.saldo_pendiente)], institucion, request.user).content
            enviar_pdf(institucion, destino, "Comprobante de pago", pdf, "comprobante.pdf"); HistorialEnvioEmail.objects.create(usuario=request.user,destinatario=destino,documento="Comprobante",resultado="Enviado"); messages.success(request,"Comprobante enviado.")
        except Exception as error:
            HistorialEnvioEmail.objects.create(usuario=request.user,destinatario=destino or "sin-email@example.invalid",documento="Comprobante",resultado="Error",error=str(error)); messages.error(request,f"No se pudo enviar: {error}")
        return redirect("pago_detail",pk=pk)


class EnviarEstadoCuentaLegacyView(LoginRequiredMixin, View):
    def post(self, request, pk):
        residente=get_object_or_404(Residente,pk=pk); institucion,_=ConfiguracionInstitucional.objects.get_or_create(pk=1); destino=residente.email_contacto
        try:
            if not destino: raise ValueError("El residente no tiene email de contacto.")
            filas=[(p.periodo,p.concepto,p.monto,p.total_abonado,p.saldo_pendiente,p.estado) for p in residente.pagos.all()]
            pdf=pdf_response("Estado de cuenta",["Período","Concepto","Monto","Abonado","Saldo","Estado"],filas,institucion,request.user).content
            enviar_pdf(institucion,destino,"Estado de cuenta",pdf,"estado_cuenta.pdf"); HistorialEnvioEmail.objects.create(usuario=request.user,destinatario=destino,documento="Estado de cuenta",resultado="Enviado"); messages.success(request,"Estado de cuenta enviado.")
        except Exception as error:
            HistorialEnvioEmail.objects.create(usuario=request.user,destinatario=destino or "sin-email@example.invalid",documento="Estado de cuenta",resultado="Error",error=str(error)); messages.error(request,f"No se pudo enviar: {error}")
        return redirect("residente_detail",pk=pk)


class EnvioDocumentoView(LoginRequiredMixin, View):
    template_name = "institucional/confirmar_envio_email.html"
    documento = ""
    nombre_pdf = ""

    def get_objeto(self, pk):
        raise NotImplementedError

    def asunto_predeterminado(self, objeto):
        raise NotImplementedError

    def generar_pdf(self, objeto, institucion, usuario):
        raise NotImplementedError

    def url_volver(self, objeto):
        raise NotImplementedError

    def get(self, request, pk):
        objeto = self.get_objeto(pk)
        destinatario = objeto.residente.email_contacto if hasattr(objeto, "residente") else objeto.email_contacto
        form = EnvioEmailForm(initial={"destinatario": destinatario, "asunto": self.asunto_predeterminado(objeto), "mensaje": "Adjuntamos el documento solicitado."})
        return self.render_to_response(request, objeto, form)

    def post(self, request, pk):
        objeto = self.get_objeto(pk)
        form = EnvioEmailForm(request.POST)
        if not form.is_valid():
            return self.render_to_response(request, objeto, form)
        destinatario = form.cleaned_data["destinatario"]
        try:
            institucion, _ = ConfiguracionInstitucional.objects.get_or_create(pk=1)
            pdf = self.generar_pdf(objeto, institucion, request.user)
            enviar_pdf(institucion, destinatario, form.cleaned_data["asunto"], pdf, self.nombre_pdf, form.cleaned_data["mensaje"])
            HistorialEnvioEmail.objects.create(usuario=request.user, destinatario=destinatario, documento=self.documento, resultado="Enviado")
            messages.success(request, f"{self.documento} enviado correctamente.")
        except Exception as error:
            detalle = str(error) if isinstance(error, ValueError) else "No se pudo conectar o autenticar con el servidor SMTP."
            HistorialEnvioEmail.objects.create(usuario=request.user, destinatario=destinatario, documento=self.documento, resultado="Error", error=detalle)
            messages.error(request, f"No se pudo enviar el email: {detalle}")
        return redirect(self.url_volver(objeto))

    def render_to_response(self, request, objeto, form):
        from django.shortcuts import render
        return render(request, self.template_name, {"form": form, "objeto": objeto, "documento": self.documento, "nombre_pdf": self.nombre_pdf, "url_volver": self.url_volver(objeto)})


class EnviarComprobanteView(EnvioDocumentoView):
    documento = "Comprobante"
    nombre_pdf = "comprobante.pdf"

    def get_objeto(self, pk): return get_object_or_404(Pago.objects.select_related("residente__geriatrico"), pk=pk)
    def asunto_predeterminado(self, objeto): return f"Comprobante de pago - {objeto.periodo}"
    def url_volver(self, objeto): return reverse("pago_detail", kwargs={"pk": objeto.pk})
    def generar_pdf(self, objeto, institucion, usuario):
        return pdf_response("Comprobante", ["Residente", "Período", "Concepto", "Monto", "Abonado", "Saldo"], [(objeto.residente, objeto.periodo, objeto.concepto, objeto.monto, objeto.total_abonado, objeto.saldo_pendiente)], institucion, usuario).content


class EnviarEstadoCuentaView(EnvioDocumentoView):
    documento = "Estado de cuenta"
    nombre_pdf = "estado_cuenta.pdf"

    def get_objeto(self, pk): return get_object_or_404(Residente, pk=pk)
    def asunto_predeterminado(self, objeto): return "Estado de cuenta"
    def url_volver(self, objeto): return reverse("residente_detail", kwargs={"pk": objeto.pk})
    def generar_pdf(self, objeto, institucion, usuario):
        filas = [(p.periodo, p.concepto, p.monto, p.total_abonado, p.saldo_pendiente, p.estado) for p in objeto.pagos.all()]
        return pdf_response("Estado de cuenta", ["Período", "Concepto", "Monto", "Abonado", "Saldo", "Estado"], filas, institucion, usuario).content


class GenerarCuotasView(LoginRequiredMixin, TemplateView):
    template_name = "institucional/generar_cuotas.html"

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context["form"] = kwargs.get("form", GenerarCuotasForm())
        return context

    def post(self, request, *args, **kwargs):
        form = GenerarCuotasForm(request.POST)
        if not form.is_valid():
            return self.render_to_response(self.get_context_data(form=form))
        residentes = Residente.objects.filter(estado=Residente.Estado.ACTIVO)
        if form.cleaned_data["geriatrico"]:
            residentes = residentes.filter(geriatrico=form.cleaned_data["geriatrico"])
        creados = existentes = sin_monto = 0
        configuracion, _ = ConfiguracionInstitucional.objects.get_or_create(pk=1)
        for residente in residentes:
            if not residente.monto_mensual:
                sin_monto += 1
                continue
            try:
                _, creado = Pago.objects.get_or_create(
                    residente=residente,
                    periodo=form.cleaned_data["periodo"],
                    defaults={"concepto": configuracion.concepto_cuota_defecto, "monto": residente.monto_mensual, "fecha_vencimiento": form.cleaned_data["fecha_vencimiento"]},
                )
                if creado:
                    creados += 1
                else:
                    existentes += 1
            except IntegrityError:
                existentes += 1
        messages.success(request, f"Cuotas creadas: {creados}. Ya existentes: {existentes}. Sin monto configurado: {sin_monto}.")
        return redirect("pago_list")


class AjusteMontoView(LoginRequiredMixin, TemplateView):
    template_name = "institucional/ajuste_montos.html"

    def residentes_filtrados(self, data):
        residentes = Residente.objects.filter(estado=Residente.Estado.ACTIVO, monto_mensual__isnull=False)
        if data.get("geriatrico"):
            residentes = residentes.filter(geriatrico=data["geriatrico"])
        if data.get("obra_social"):
            residentes = residentes.filter(obra_social=data["obra_social"])
        return residentes

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context.update({"form": kwargs.get("form", AjusteMontoForm()), "vista_previa": kwargs.get("vista_previa", [])})
        return context

    def post(self, request, *args, **kwargs):
        form = AjusteMontoForm(request.POST)
        if not form.is_valid():
            return self.render_to_response(self.get_context_data(form=form))
        residentes = self.residentes_filtrados(form.cleaned_data)
        factor = Decimal("1") + form.cleaned_data["porcentaje"] / Decimal("100")
        vista_previa = [(residente, (residente.monto_mensual * factor).quantize(Decimal("0.01"), rounding=ROUND_HALF_UP)) for residente in residentes]
        if request.POST.get("accion") == "confirmar":
            for residente, nuevo_monto in vista_previa:
                residente.monto_mensual = nuevo_monto
                residente.save(update_fields=["monto_mensual"])
            messages.success(request, f"Se actualizaron {len(vista_previa)} montos mensuales.")
            return redirect("pago_list")
        return self.render_to_response(self.get_context_data(form=form, vista_previa=vista_previa))


class CajaListView(LoginRequiredMixin, ListView):
    model = CajaMovimiento
    template_name = "institucional/caja_list.html"

    def get_queryset(self):
        queryset = CajaMovimiento.objects.select_related("geriatrico", "residente", "pago", "usuario", "categoria")
        fecha = self.request.GET.get("fecha", "")
        geriatrico = self.request.GET.get("geriatrico", "")
        categoria = self.request.GET.get("categoria", "")
        proveedor = self.request.GET.get("proveedor", "").strip()
        medio_pago = self.request.GET.get("medio_pago", "")
        if fecha:
            queryset = queryset.filter(fecha=fecha)
        if geriatrico:
            queryset = queryset.filter(geriatrico_id=geriatrico)
        if categoria:
            queryset = queryset.filter(categoria_id=categoria)
        if proveedor:
            queryset = queryset.filter(proveedor_beneficiario__icontains=proveedor)
        if medio_pago:
            queryset = queryset.filter(medio_pago=medio_pago)
        return queryset

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        ingresos = CajaMovimiento.objects.filter(tipo=CajaMovimiento.Tipo.INGRESO).aggregate(total=Sum("importe"))["total"] or Decimal("0.00")
        egresos = CajaMovimiento.objects.filter(tipo=CajaMovimiento.Tipo.EGRESO).aggregate(total=Sum("importe"))["total"] or Decimal("0.00")
        hoy = date.today()
        resumen_dia = CajaMovimiento.resumen_fecha(hoy)
        resumen_dia["saldo_final"] = resumen_dia["ingresos"] - resumen_dia["egresos"]
        resumen_dia["saldo_inicial"] = Decimal("0.00")
        inicio_mes = hoy.replace(day=1)
        movimientos_mes = CajaMovimiento.objects.filter(fecha__gte=inicio_mes, fecha__lte=hoy)
        ingresos_mes = movimientos_mes.filter(tipo=CajaMovimiento.Tipo.INGRESO).aggregate(total=Sum("importe"))["total"] or Decimal("0.00")
        egresos_mes = movimientos_mes.filter(tipo=CajaMovimiento.Tipo.EGRESO).aggregate(total=Sum("importe"))["total"] or Decimal("0.00")
        categorias = list(movimientos_mes.filter(tipo=CajaMovimiento.Tipo.EGRESO).values("categoria__nombre").annotate(total=Sum("importe")).order_by("-total"))
        maximo = max((item["total"] for item in categorias), default=Decimal("0.00"))
        for item in categorias:
            item["porcentaje"] = item["total"] / maximo * 100 if maximo else 0
        meses = []
        for desplazamiento in range(5, -1, -1):
            referencia = hoy.replace(day=1)
            for _ in range(desplazamiento):
                referencia = (referencia - timedelta(days=1)).replace(day=1)
            siguiente = (referencia + timedelta(days=32)).replace(day=1)
            movimientos = CajaMovimiento.objects.filter(fecha__gte=referencia, fecha__lt=siguiente)
            meses.append({"etiqueta": referencia.strftime("%m/%Y"), "ingresos": movimientos.filter(tipo=CajaMovimiento.Tipo.INGRESO).aggregate(total=Sum("importe"))["total"] or Decimal("0.00"), "egresos": movimientos.filter(tipo=CajaMovimiento.Tipo.EGRESO).aggregate(total=Sum("importe"))["total"] or Decimal("0.00")})
        maximo_mensual = max((max(item["ingresos"], item["egresos"]) for item in meses), default=Decimal("0.00"))
        for item in meses:
            item["ingresos_pct"] = item["ingresos"] / maximo_mensual * 100 if maximo_mensual else 0
            item["egresos_pct"] = item["egresos"] / maximo_mensual * 100 if maximo_mensual else 0
        context.update({"total_ingresos": ingresos, "total_egresos": egresos, "saldo_actual": ingresos - egresos, "resumen_dia": resumen_dia, "ingresos_mes": ingresos_mes, "egresos_mes": egresos_mes, "resultado_mes": ingresos_mes - egresos_mes, "egresos_categoria": categorias, "movimientos_mensuales": meses, "geriatrico_opciones": Geriatrico.objects.all(), "categoria_opciones": CategoriaCaja.objects.filter(activa=True), "medio_pago_opciones": Pago.MedioPago.choices, "filtros": self.request.GET})
        return context


class ExportarCajaView(CajaListView):
    def get(self, request, formato):
        movimientos = self.get_queryset()
        filas = [
            (
                movimiento.fecha,
                movimiento.tipo,
                movimiento.geriatrico.nombre,
                movimiento.categoria.nombre if movimiento.categoria else "",
                movimiento.proveedor_beneficiario or str(movimiento.residente or "") or movimiento.descripcion,
                movimiento.medio_pago,
                movimiento.usuario,
                movimiento.importe,
            )
            for movimiento in movimientos
        ]
        columnas = ["Fecha", "Tipo", "Geriátrico", "Categoría", "Proveedor / detalle", "Medio", "Usuario", "Importe"]
        institucion, _ = ConfiguracionInstitucional.objects.get_or_create(pk=1)
        if formato == "excel":
            return excel_response("caja", columnas, filas)
        return pdf_response("Reporte de caja", columnas, filas, institucion, request.user)


class EgresoCajaCreateView(LoginRequiredMixin, CreateView):
    model = CajaMovimiento
    form_class = EgresoCajaForm
    template_name = "institucional/egreso_form.html"
    success_url = reverse_lazy("caja_list")

    def form_valid(self, form):
        form.instance.tipo = CajaMovimiento.Tipo.EGRESO
        form.instance.usuario = self.request.user
        try:
            form.instance.full_clean()
        except ValidationError as error:
            form.add_error("importe", error.message_dict.get("importe", ["No se pudo registrar el egreso."])[0])
            return self.form_invalid(form)
        return super().form_valid(form)


class CategoriaCajaListView(LoginRequiredMixin, ListView):
    model = CategoriaCaja
    template_name = "institucional/categoria_caja_list.html"

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context["form"] = kwargs.get("form", CategoriaCajaForm())
        return context

    def post(self, request, *args, **kwargs):
        form = CategoriaCajaForm(request.POST)
        if form.is_valid():
            form.save()
            messages.success(request, "Categoría guardada.")
            return redirect("categoria_caja_list")
        return self.render_to_response(self.get_context_data(form=form))


class CajaCierreView(LoginRequiredMixin, View):
    def post(self, request):
        resumen = CajaMovimiento.resumen_fecha(date.today())
        CajaCierre.objects.update_or_create(fecha=date.today(), defaults={**resumen, "cerrado_por": request.user})
        messages.success(request, "Cierre de caja generado correctamente.")
        return redirect("caja_list")


class ConfiguracionView(LoginRequiredMixin, TemplateView):
    template_name = "institucional/configuracion.html"

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        configuracion, _ = ConfiguracionInstitucional.objects.get_or_create(pk=1)
        context.update({"institucion_form": kwargs.get("institucion_form", ConfiguracionInstitucionalForm(instance=configuracion)), "obras": ObraSocial.objects.all(), "medios": MedioPagoConfiguracion.objects.all(), "porcentajes": PorcentajeActualizacion.objects.all(), "categorias": CategoriaCaja.objects.all(), "historial_envios": HistorialEnvioEmail.objects.select_related("usuario").order_by("-fecha")[:20], "obra_form": ObraSocialForm(), "medio_form": MedioPagoConfiguracionForm(), "porcentaje_form": PorcentajeActualizacionForm(), "categoria_form": CategoriaCajaForm()})
        return context

    def post(self, request):
        configuracion, _ = ConfiguracionInstitucional.objects.get_or_create(pk=1)
        tipo = request.POST.get("tipo")
        if tipo == "institucion":
            form = ConfiguracionInstitucionalForm(request.POST, request.FILES, instance=configuracion)
        elif tipo == "obra": form = ObraSocialForm(request.POST)
        elif tipo == "medio": form = MedioPagoConfiguracionForm(request.POST)
        elif tipo == "porcentaje": form = PorcentajeActualizacionForm(request.POST)
        else: form = CategoriaCajaForm(request.POST)
        if form.is_valid():
            form.save(); messages.success(request, "Configuración guardada."); return redirect("configuracion")
        return self.render_to_response(self.get_context_data(institucion_form=form if tipo == "institucion" else None))


class PersonalListView(LoginRequiredMixin, ListView):
    model = Personal
    template_name = "institucional/personal_list.html"
    def get_queryset(self):
        qs = Personal.objects.all(); estado = self.request.GET.get("estado", "")
        return qs.filter(estado=estado) if estado else qs


class ExportarPersonalView(PersonalListView):
    def get(self, request, formato):
        filas = [
            (
                persona.nombre_completo,
                persona.dni,
                persona.cargo,
                persona.turno_habitual,
                persona.telefono,
                persona.cuil,
                persona.inicio_contrato,
                persona.estado,
                persona.observaciones,
            )
            for persona in self.get_queryset()
        ]
        columnas = ["Apellido y nombre", "DNI", "Cargo", "Turno habitual", "Teléfono", "CUIL", "Inicio de contrato", "Estado", "Observaciones"]
        institucion, _ = ConfiguracionInstitucional.objects.get_or_create(pk=1)
        if formato == "excel":
            return excel_response("personal", columnas, filas)
        return pdf_response("Reporte de Personal", columnas, filas, institucion, request.user)


class PersonalCreateView(LoginRequiredMixin, CreateView):
    model = Personal; form_class = PersonalForm; template_name = "institucional/personal_form.html"; success_url = reverse_lazy("personal_list")


class TurnosView(LoginRequiredMixin, TemplateView):
    template_name = "institucional/turnos.html"
    def dispatch(self, request, *args, **kwargs):
        self.mes = int(request.GET.get("mes", date.today().month)); self.anio = int(request.GET.get("anio", date.today().year)); return super().dispatch(request,*args,**kwargs)
    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs); grilla = GrillaTurnos.objects.filter(mes=self.mes, anio=self.anio).first()
        context.update({"mes": self.mes, "anio": self.anio, "dias": range(1, calendar.monthrange(self.anio,self.mes)[1]+1), "grilla": grilla, "personal": Personal.objects.filter(estado=Personal.Estado.ACTIVO), "codigos": AsignacionTurno.Codigo.choices})
        return context
    def post(self, request, *args, **kwargs):
        grilla, _ = GrillaTurnos.objects.get_or_create(mes=self.mes, anio=self.anio)
        for empleado in Personal.objects.filter(estado=Personal.Estado.ACTIVO):
            for dia in range(1, calendar.monthrange(self.anio,self.mes)[1]+1):
                codigo = request.POST.get(f"turno_{empleado.pk}_{dia}", "")
                AsignacionTurno.objects.update_or_create(grilla=grilla, personal=empleado, dia=dia, defaults={"codigo": codigo})
        messages.success(request, "Turnos actualizados."); return redirect(f"{reverse('turnos')}?mes={self.mes}&anio={self.anio}")


class ExportarTurnosView(TurnosView):
    nombres_meses = ("", "Enero", "Febrero", "Marzo", "Abril", "Mayo", "Junio", "Julio", "Agosto", "Septiembre", "Octubre", "Noviembre", "Diciembre")

    def get(self, request, formato):
        dias = list(range(1, calendar.monthrange(self.anio, self.mes)[1] + 1))
        personal = Personal.objects.filter(estado=Personal.Estado.ACTIVO)
        grilla = GrillaTurnos.objects.filter(mes=self.mes, anio=self.anio).first()
        asignaciones = {}
        if grilla:
            asignaciones = {(asignacion.personal_id, asignacion.dia): asignacion.codigo for asignacion in grilla.asignaciones.all()}
        columnas = ["Empleado", *[str(dia) for dia in dias]]
        filas = [(empleado.nombre_completo, *[asignaciones.get((empleado.pk, dia), "") for dia in dias]) for empleado in personal]
        institucion, _ = ConfiguracionInstitucional.objects.get_or_create(pk=1)
        if formato == "excel":
            return excel_response(f"turnos_{self.anio}_{self.mes:02d}", columnas, filas)
        periodo = f"{self.nombres_meses[self.mes]} {self.anio}"
        leyenda = "Leyenda: M = Mañana · T = Tarde · N = Noche · F = Franco · L = Licencia · V = Vacaciones"
        return pdf_response("Grilla mensual de turnos", columnas, filas, institucion, request.user, textos_adicionales=(f"Período: {periodo}", leyenda), anchos_columnas=[95] + [21] * len(dias), tamano_fuente=5)
