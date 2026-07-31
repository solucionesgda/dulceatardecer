from django.contrib.auth.models import Group, Permission, User
from django.core.exceptions import ValidationError
from django.core import mail
from django.test import TestCase
from django.test.utils import override_settings
from django.urls import reverse
from django.utils import timezone
from datetime import date, timedelta
from decimal import Decimal
from io import BytesIO
import zipfile
from openpyxl import load_workbook
from .forms import ConfiguracionInstitucionalForm, EgresoCajaForm, PagoParcialForm, ResidenteForm
from .moneda import formatear_moneda
from .reportes import comprobante_pago_pdf, excel_response, pdf_response
from .models import AsignacionTurno, CajaCierre, CajaMovimiento, CategoriaCaja, ConfiguracionInstitucional, Geriatrico, GrillaTurnos, HistorialEnvioEmail, InvitacionPersonal, LecturaNormaPolitica, NormaPolitica, Pago, PagoParcial, PerfilUsuario, Personal, Residente, Tarea


class AccesoTest(TestCase):
    def setUp(self):
        self.usuario = User.objects.create_user("consulta", password="clave-segura")
        grupo, _ = Group.objects.get_or_create(name="Secretaría")
        permiso = Permission.objects.get(codename="view_geriatrico")
        grupo.permissions.add(permiso)
        self.usuario.groups.add(grupo)

    def test_inicio_requiere_login(self):
        response = self.client.get(reverse("inicio"))
        self.assertRedirects(response, f"{reverse('login')}?next={reverse('inicio')}")

    def test_consulta_puede_ver_lista_y_no_crear(self):
        self.client.login(username="consulta", password="clave-segura")
        self.assertEqual(self.client.get(reverse("geriatrico_list")).status_code, 200)
        self.assertEqual(self.client.get(reverse("geriatrico_create")).status_code, 403)

    def test_panel_muestra_metricas_reales(self):
        geriatrico = Geriatrico.objects.create(nombre="Geri 1", codigo="G1", direccion="Calle 1", capacidad_total=3)
        Residente.objects.create(geriatrico=geriatrico, nombre="Ana", apellido="Pérez", dni="12345678", fecha_ingreso="2026-01-01", contacto_familiar="3411234567")
        Residente.objects.create(geriatrico=geriatrico, nombre="Luis", apellido="Gómez", dni="87654321", fecha_ingreso="2026-01-01", contacto_familiar="3411234568", estado=Residente.Estado.TRASLADO)
        self.client.login(username="consulta", password="clave-segura")
        response = self.client.get(reverse("inicio"))
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.context["residentes_activos"], 1)
        self.assertEqual(response.context["camas_disponibles"], 2)

    def test_panel_filtra_por_geriatrico_y_periodo(self):
        uno = Geriatrico.objects.create(nombre="Geri 1", codigo="GD1", direccion="Calle 1", capacidad_total=3)
        dos = Geriatrico.objects.create(nombre="Geri 2", codigo="GD2", direccion="Calle 2", capacidad_total=4)
        Residente.objects.create(geriatrico=uno, nombre="Ana", apellido="Pérez", dni="11112222", fecha_ingreso="2026-01-01", contacto_familiar="3411234567")
        Residente.objects.create(geriatrico=dos, nombre="Luis", apellido="Gómez", dni="22223333", fecha_ingreso="2026-01-01", contacto_familiar="3411234568")
        self.client.login(username="consulta", password="clave-segura")
        response = self.client.get(reverse("inicio"), {"geriatrico": uno.pk, "mes": 7, "anio": 2026})
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.context["residentes_activos"], 1)
        self.assertEqual(response.context["capacidad_total"], 3)
        self.assertEqual(len(response.context["geriatrico_estadisticas"]), 1)

    def test_listado_residentes_permite_busqueda_y_filtros(self):
        geriatrico = Geriatrico.objects.create(nombre="Geri 1", codigo="G1", direccion="Calle 1", capacidad_total=3)
        Residente.objects.create(geriatrico=geriatrico, nombre="Ana", apellido="Pérez", dni="12345678", fecha_ingreso="2026-01-01", contacto_familiar="3411234567")
        self.client.login(username="consulta", password="clave-segura")
        response = self.client.get(reverse("residente_list"), {"q": "Pérez", "geriatrico": geriatrico.pk, "estado": Residente.Estado.ACTIVO})
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, "Ana")

    def test_listado_pagos_filtra_y_actualiza_vencidos(self):
        geriatrico = Geriatrico.objects.create(nombre="Geri 1", codigo="G1", direccion="Calle 1", capacidad_total=3)
        residente = Residente.objects.create(geriatrico=geriatrico, nombre="Ana", apellido="Pérez", dni="12345678", fecha_ingreso="2026-01-01", contacto_familiar="3411234567")
        pago = Pago.objects.create(residente=residente, periodo="2026-07", concepto="Cuota", monto=Decimal("1000.00"), fecha_vencimiento=date.today() - timedelta(days=1))
        self.client.login(username="consulta", password="clave-segura")
        response = self.client.get(reverse("pago_list"), {"q": "12345678", "estado": Pago.Estado.VENCIDO, "periodo": "2026-07", "geriatrico": geriatrico.pk})
        pago.refresh_from_db()
        self.assertEqual(response.status_code, 200)
        self.assertEqual(pago.estado, Pago.Estado.VENCIDO)
        self.assertContains(response, "Cuota")

    def test_pago_con_fecha_de_pago_se_guarda_pagado(self):
        geriatrico = Geriatrico.objects.create(nombre="Geri 1", codigo="G1", direccion="Calle 1", capacidad_total=3)
        residente = Residente.objects.create(geriatrico=geriatrico, nombre="Ana", apellido="Pérez", dni="12345678", fecha_ingreso="2026-01-01", contacto_familiar="3411234567")
        pago = Pago.objects.create(residente=residente, periodo="2026-07", concepto="Cuota", monto=Decimal("1000.00"), fecha_vencimiento=date.today(), fecha_pago=date.today())
        self.assertEqual(pago.estado, Pago.Estado.PAGADO)

    def crear_residente_con_monto(self, dni, monto):
        geriatrico, _ = Geriatrico.objects.get_or_create(nombre="Geri pagos", codigo="GP", defaults={"direccion": "Calle 1", "capacidad_total": 10})
        return Residente.objects.create(geriatrico=geriatrico, nombre="Ana", apellido=dni, dni=dni, fecha_ingreso="2026-01-01", contacto_familiar="3411234567", monto_mensual=Decimal(monto))

    def test_pago_completo(self):
        residente = self.crear_residente_con_monto("12345678", "1000.00")
        pago = Pago.objects.create(residente=residente, periodo="2026-08", concepto="Cuota", monto=Decimal("1000.00"), fecha_vencimiento=date.today())
        PagoParcial.objects.create(pago=pago, monto=Decimal("1000.00"), fecha_pago=date.today())
        pago.refresh_from_db()
        self.assertEqual(pago.estado, Pago.Estado.PAGADO)
        self.assertEqual(pago.saldo_pendiente, Decimal("0.00"))

    def test_pago_parcial_y_varios_abonos(self):
        residente = self.crear_residente_con_monto("22345678", "1000.00")
        pago = Pago.objects.create(residente=residente, periodo="2026-08", concepto="Cuota", monto=Decimal("1000.00"), fecha_vencimiento=date.today())
        PagoParcial.objects.create(pago=pago, monto=Decimal("300.00"), fecha_pago=date.today())
        pago.refresh_from_db()
        self.assertEqual(pago.estado, Pago.Estado.PARCIAL)
        PagoParcial.objects.create(pago=pago, monto=Decimal("700.00"), fecha_pago=date.today())
        self.assertEqual(pago.total_abonado, Decimal("1000.00"))
        self.assertEqual(pago.saldo_pendiente, Decimal("0.00"))

    def test_rechaza_abono_superior_al_saldo(self):
        residente = self.crear_residente_con_monto("32345678", "1000.00")
        pago = Pago.objects.create(residente=residente, periodo="2026-08", concepto="Cuota", monto=Decimal("1000.00"), fecha_vencimiento=date.today())
        PagoParcial.objects.create(pago=pago, monto=Decimal("700.00"), fecha_pago=date.today())
        with self.assertRaises(ValidationError):
            PagoParcial.objects.create(pago=pago, monto=Decimal("400.00"), fecha_pago=date.today())

    def test_montos_diferentes_por_residente(self):
        uno = self.crear_residente_con_monto("42345678", "1000.00")
        dos = self.crear_residente_con_monto("52345678", "2000.00")
        self.assertNotEqual(uno.monto_mensual, dos.monto_mensual)

    def test_ajuste_porcentual_no_modifica_pagos_existentes(self):
        residente = self.crear_residente_con_monto("62345678", "1000.00")
        pago = Pago.objects.create(residente=residente, periodo="2026-08", concepto="Cuota", monto=Decimal("1000.00"), fecha_vencimiento=date.today())
        self.client.login(username="consulta", password="clave-segura")
        response = self.client.post(reverse("ajuste_montos"), {"porcentaje": "10", "accion": "confirmar"})
        residente.refresh_from_db()
        pago.refresh_from_db()
        self.assertRedirects(response, reverse("pago_list"))
        self.assertEqual(residente.monto_mensual, Decimal("1100.00"))
        self.assertEqual(pago.monto, Decimal("1000.00"))

    def test_generacion_mensual_sin_duplicados(self):
        residente = self.crear_residente_con_monto("72345678", "1500.00")
        self.client.login(username="consulta", password="clave-segura")
        datos = {"periodo": "2026-09", "fecha_vencimiento": "2026-09-10", "geriatrico": ""}
        self.client.post(reverse("generar_cuotas"), datos)
        self.client.post(reverse("generar_cuotas"), datos)
        self.assertEqual(Pago.objects.filter(residente=residente, periodo="2026-09").count(), 1)

    def test_estados_pendiente_parcial_pagado_y_vencido(self):
        residente = self.crear_residente_con_monto("82345678", "1000.00")
        pendiente = Pago.objects.create(residente=residente, periodo="2026-10", concepto="Cuota", monto=Decimal("1000.00"), fecha_vencimiento=date.today())
        parcial = Pago.objects.create(residente=residente, periodo="2026-11", concepto="Cuota", monto=Decimal("1000.00"), fecha_vencimiento=date.today())
        PagoParcial.objects.create(pago=parcial, monto=Decimal("100.00"), fecha_pago=date.today())
        pagado = Pago.objects.create(residente=residente, periodo="2026-12", concepto="Cuota", monto=Decimal("1000.00"), fecha_vencimiento=date.today())
        PagoParcial.objects.create(pago=pagado, monto=Decimal("1000.00"), fecha_pago=date.today())
        vencido = Pago.objects.create(residente=residente, periodo="2027-01", concepto="Cuota", monto=Decimal("1000.00"), fecha_vencimiento=date.today() - timedelta(days=1))
        self.assertEqual(pendiente.estado, Pago.Estado.PENDIENTE)
        parcial.refresh_from_db(); pagado.refresh_from_db(); vencido.refresh_from_db()
        self.assertEqual(parcial.estado, Pago.Estado.PARCIAL)
        self.assertEqual(pagado.estado, Pago.Estado.PAGADO)
        self.assertEqual(vencido.estado, Pago.Estado.VENCIDO)

    def test_abono_genera_ingreso_automatico_en_caja(self):
        residente = self.crear_residente_con_monto("92345678", "1000.00")
        pago = Pago.objects.create(residente=residente, periodo="2027-02", concepto="Cuota", monto=Decimal("1000.00"), fecha_vencimiento=date.today())
        abono = PagoParcial.objects.create(pago=pago, monto=Decimal("300.00"), fecha_pago=date.today())
        movimiento = CajaMovimiento.objects.get(abono=abono)
        self.assertEqual(movimiento.tipo, CajaMovimiento.Tipo.INGRESO)
        self.assertEqual(movimiento.importe, Decimal("300.00"))

    def test_no_permite_egreso_superior_al_saldo(self):
        residente = self.crear_residente_con_monto("10345678", "1000.00")
        pago = Pago.objects.create(residente=residente, periodo="2027-03", concepto="Cuota", monto=Decimal("1000.00"), fecha_vencimiento=date.today())
        PagoParcial.objects.create(pago=pago, monto=Decimal("100.00"), fecha_pago=date.today())
        categoria, _ = CategoriaCaja.objects.get_or_create(nombre="Servicios")
        egreso = CajaMovimiento(tipo=CajaMovimiento.Tipo.EGRESO, fecha=date.today(), geriatrico=residente.geriatrico, categoria=categoria, importe=Decimal("101.00"))
        with self.assertRaises(ValidationError):
            egreso.full_clean()

    def test_cierre_caja_resume_movimientos_del_dia(self):
        residente = self.crear_residente_con_monto("11345678", "1000.00")
        pago = Pago.objects.create(residente=residente, periodo="2027-04", concepto="Cuota", monto=Decimal("1000.00"), fecha_vencimiento=date.today())
        PagoParcial.objects.create(pago=pago, monto=Decimal("100.00"), fecha_pago=date.today())
        categoria, _ = CategoriaCaja.objects.get_or_create(nombre="Farmacia")
        CajaMovimiento.objects.create(tipo=CajaMovimiento.Tipo.EGRESO, fecha=date.today(), geriatrico=residente.geriatrico, categoria=categoria, importe=Decimal("20.00"))
        self.client.login(username="consulta", password="clave-segura")
        self.client.post(reverse("caja_cierre"), {"geriatrico": residente.geriatrico_id})
        cierre = CajaCierre.objects.get(fecha=date.today().replace(day=1), geriatrico=residente.geriatrico)
        self.assertEqual(cierre.saldo_final, Decimal("80.00"))

    def test_exportaciones_caja_respetan_filtro_de_proveedor(self):
        residente = self.crear_residente_con_monto("12341234", "1000.00")
        categoria, _ = CategoriaCaja.objects.get_or_create(nombre="Servicios")
        CajaMovimiento.objects.create(tipo=CajaMovimiento.Tipo.EGRESO, fecha=date.today(), geriatrico=residente.geriatrico, categoria=categoria, proveedor_beneficiario="EPE", importe=Decimal("10.00"))
        self.client.login(username="consulta", password="clave-segura")
        for formato, contenido in (("excel", "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet"), ("pdf", "application/pdf")):
            response = self.client.get(reverse("caja_exportar", args=[formato]), {"proveedor": "EPE"})
            self.assertEqual(response.status_code, 200)
            self.assertEqual(response["Content-Type"], contenido)

    def test_exportaciones_personal_respetan_estado(self):
        empleado = Personal.objects.create(nombre_completo="Ana Pérez", dni="12345678", cargo=Personal.Cargo.CUIDADOR, turno_habitual="Mañana", inicio_contrato=date.today(), estado=Personal.Estado.ACTIVO)
        self.client.login(username="consulta", password="clave-segura")
        for formato, contenido in (("excel", "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet"), ("pdf", "application/pdf")):
            response = self.client.get(reverse("personal_exportar", args=[formato]), {"estado": Personal.Estado.ACTIVO})
            self.assertEqual(response.status_code, 200)
            self.assertEqual(response["Content-Type"], contenido)

    def test_exportaciones_turnos_respetan_mes_y_anio(self):
        empleado = Personal.objects.create(nombre_completo="Ana Pérez", dni="87654321", cargo=Personal.Cargo.CUIDADOR, turno_habitual="Mañana", inicio_contrato=date.today())
        grilla = GrillaTurnos.objects.create(mes=2, anio=2026)
        AsignacionTurno.objects.create(grilla=grilla, personal=empleado, dia=1, codigo=AsignacionTurno.Codigo.M)
        self.client.login(username="consulta", password="clave-segura")
        for formato, contenido in (("excel", "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet"), ("pdf", "application/pdf")):
            response = self.client.get(reverse("turnos_exportar", args=[formato]), {"mes": 2, "anio": 2026})
            self.assertEqual(response.status_code, 200)
            self.assertEqual(response["Content-Type"], contenido)

    def configurar_smtp(self):
        return ConfiguracionInstitucional.objects.create(nombre_institucion="Dulce Atardecer")

    def crear_pago_con_email(self):
        geriatrico = Geriatrico.objects.create(nombre="Geri email", codigo="GE", direccion="Calle 1", capacidad_total=3)
        residente = Residente.objects.create(geriatrico=geriatrico, nombre="Ana", apellido="Email", dni="55555555", fecha_ingreso="2026-01-01", contacto_familiar="3411234567", email_contacto="contacto@example.test")
        return residente, Pago.objects.create(residente=residente, periodo="2026-07", concepto="Cuota", monto=Decimal("1000.00"), fecha_vencimiento=date.today())

    def test_botones_email_y_destinatario_precargado(self):
        residente, pago = self.crear_pago_con_email()
        self.client.login(username="consulta", password="clave-segura")
        self.assertContains(self.client.get(reverse("pago_detail", args=[pago.pk])), "Enviar comprobante por email")
        self.assertContains(self.client.get(reverse("residente_detail", args=[residente.pk])), "Enviar estado de cuenta por email")
        self.assertContains(self.client.get(reverse("enviar_comprobante", args=[pago.pk])), "contacto@example.test")
        self.assertContains(self.client.get(reverse("enviar_estado_cuenta", args=[residente.pk])), "contacto@example.test")

    @override_settings(EMAIL_BACKEND="django.core.mail.backends.locmem.EmailBackend", SMTP_HOST="smtp.example.test", SMTP_PORT=587, SMTP_USERNAME="usuario", SMTP_PASSWORD="secreto", SMTP_USE_TLS=True, SMTP_USE_SSL=False, SMTP_FROM_EMAIL="noreply@example.test", SMTP_FROM_NAME="Dulce Atardecer")
    def test_envio_comprobante_adjunta_pdf_y_registra_historial(self):
        self.configurar_smtp(); _, pago = self.crear_pago_con_email(); self.client.login(username="consulta", password="clave-segura")
        response = self.client.post(reverse("enviar_comprobante", args=[pago.pk]), {"destinatario": "destino@example.test", "asunto": "Comprobante", "mensaje": "Adjunto"})
        self.assertRedirects(response, reverse("pago_detail", args=[pago.pk]))
        self.assertEqual(len(mail.outbox), 1)
        self.assertEqual(mail.outbox[0].to, ["destino@example.test"])
        self.assertEqual(mail.outbox[0].attachments[0][0], "comprobante.pdf")
        self.assertTrue(HistorialEnvioEmail.objects.filter(documento="Comprobante", resultado="Enviado").exists())

    @override_settings(EMAIL_BACKEND="django.core.mail.backends.locmem.EmailBackend", SMTP_HOST="smtp.example.test", SMTP_PORT=587, SMTP_USERNAME="usuario", SMTP_PASSWORD="secreto", SMTP_USE_TLS=True, SMTP_USE_SSL=False, SMTP_FROM_EMAIL="noreply@example.test", SMTP_FROM_NAME="Dulce Atardecer")
    def test_envio_estado_cuenta_registra_historial(self):
        self.configurar_smtp(); residente, _ = self.crear_pago_con_email(); self.client.login(username="consulta", password="clave-segura")
        response = self.client.post(reverse("enviar_estado_cuenta", args=[residente.pk]), {"destinatario": "destino@example.test", "asunto": "Estado", "mensaje": "Adjunto"})
        self.assertRedirects(response, reverse("residente_detail", args=[residente.pk]))
        self.assertEqual(mail.outbox[0].attachments[0][0], "estado_cuenta.pdf")
        self.assertTrue(HistorialEnvioEmail.objects.filter(documento="Estado de cuenta", resultado="Enviado").exists())

    def test_configuracion_smtp_incompleta_registra_error(self):
        _, pago = self.crear_pago_con_email(); self.client.login(username="consulta", password="clave-segura")
        self.client.post(reverse("enviar_comprobante", args=[pago.pk]), {"destinatario": "destino@example.test", "asunto": "Comprobante", "mensaje": "Adjunto"})
        historial = HistorialEnvioEmail.objects.get(documento="Comprobante")
        self.assertEqual(historial.resultado, "Error")
        self.assertIn("incompleta", historial.error)


class SeguridadRolesYSMTPTest(TestCase):
    def setUp(self):
        self.consulta = User.objects.create_user("solo-consulta", password="ClaveSegura1")
        self.consulta.groups.add(Group.objects.get_or_create(name="Consulta")[0])
        self.secretaria = User.objects.create_user("secretaria", password="ClaveSegura1")
        self.secretaria.groups.add(Group.objects.get_or_create(name="Secretaría")[0])

    def test_consulta_no_accede_a_gestion_por_url_ni_post(self):
        self.client.login(username="solo-consulta", password="ClaveSegura1")
        self.assertIn(self.client.get("/pagos/registrar/").status_code, (403, 404))
        self.assertEqual(self.client.post(reverse("generar_cuotas"), {}).status_code, 403)
        self.assertEqual(self.client.get(reverse("configuracion")).status_code, 403)

    def test_secretaria_no_accede_a_configuracion(self):
        self.client.login(username="secretaria", password="ClaveSegura1")
        self.assertEqual(self.client.get(reverse("configuracion")).status_code, 403)

    def test_smtp_no_persiste_campos_ni_aparece_en_formulario(self):
        campos = {campo.name for campo in ConfiguracionInstitucional._meta.get_fields()}
        self.assertFalse({"smtp_servidor", "smtp_puerto", "smtp_usuario", "smtp_contrasena", "smtp_tls", "smtp_ssl", "smtp_remitente", "smtp_nombre_remitente"} & campos)
        self.assertNotIn("smtp_contrasena", ConfiguracionInstitucionalForm().fields)


class TareasTest(TestCase):
    def setUp(self):
        self.usuario = User.objects.create_user("empleada", password="clave-segura")
        otro_usuario = User.objects.create_user("otra", password="clave-segura")
        self.personal = Personal.objects.create(usuario=self.usuario, nombre_completo="Ana Empleada", dni="33444555", cargo=Personal.Cargo.CUIDADOR, turno_habitual="Mañana", inicio_contrato=date.today())
        self.otra_personal = Personal.objects.create(usuario=otro_usuario, nombre_completo="Berta Empleada", dni="44555666", cargo=Personal.Cargo.CUIDADOR, turno_habitual="Tarde", inicio_contrato=date.today())

    def test_empleada_solo_ve_sus_tareas(self):
        propia = Tarea.objects.create(titulo="Tarea propia", asignada_a=self.personal, fecha=date.today(), turno=Tarea.Turno.MANANA)
        Tarea.objects.create(titulo="Tarea ajena", asignada_a=self.otra_personal, fecha=date.today(), turno=Tarea.Turno.TARDE)
        self.client.login(username="empleada", password="clave-segura")
        response = self.client.get(reverse("tarea_list"))
        self.assertContains(response, propia.titulo)
        self.assertNotContains(response, "Tarea ajena")

    def test_completar_tarea_registra_usuario_fecha_y_observacion(self):
        tarea = Tarea.objects.create(titulo="Control", asignada_a=self.personal, fecha=date.today(), turno=Tarea.Turno.MANANA)
        self.client.login(username="empleada", password="clave-segura")
        response = self.client.post(reverse("tarea_completar", args=[tarea.pk]), {"observacion": "Realizada sin novedades."})
        self.assertRedirects(response, reverse("tarea_list"))
        tarea.refresh_from_db()
        self.assertEqual(tarea.estado, Tarea.Estado.COMPLETADA)
        self.assertEqual(tarea.completada_por, self.usuario)
        self.assertIsNotNone(tarea.completada_en)
        self.assertEqual(tarea.observacion_completado, "Realizada sin novedades.")

    def test_norma_se_puede_marcar_como_leida(self):
        norma = NormaPolitica.objects.create(titulo="Higiene", contenido="Instrucciones de higiene.")
        self.client.login(username="empleada", password="clave-segura")
        response = self.client.post(reverse("norma_leer", args=[norma.pk]))
        self.assertRedirects(response, reverse("norma_list"))
        self.assertTrue(LecturaNormaPolitica.objects.filter(norma=norma, personal=self.personal).exists())

    def test_panel_de_tareas_es_solo_para_administracion(self):
        self.client.login(username="empleada", password="clave-segura")
        self.assertEqual(self.client.get(reverse("tarea_panel")).status_code, 403)
        administrador = User.objects.create_user("admin-tareas", password="clave-segura", is_staff=True)
        self.client.login(username="admin-tareas", password="clave-segura")
        self.assertEqual(self.client.get(reverse("tarea_panel")).status_code, 200)


class InvitacionesPersonalTest(TestCase):
    def crear_personal(self, dni="55666777"):
        return Personal.objects.create(nombre_completo="Clara Empleada", dni=dni, cargo=Personal.Cargo.CUIDADOR, turno_habitual="Mañana", inicio_contrato=date.today())

    def test_creacion_de_invitacion(self):
        personal = self.crear_personal()
        invitacion = InvitacionPersonal.objects.create(personal=personal)
        self.assertTrue(invitacion.vigente)
        self.assertEqual(invitacion.personal, personal)

    def test_activacion_correcta_vincula_cuenta(self):
        personal = self.crear_personal()
        invitacion = InvitacionPersonal.objects.create(personal=personal)
        response = self.client.post(reverse("activar_cuenta", args=[invitacion.token]), {"username": "clara", "email": "clara@example.test", "password1": "ClaveSegura1", "password2": "ClaveSegura1"})
        self.assertRedirects(response, reverse("tarea_list"))
        personal.refresh_from_db(); invitacion.refresh_from_db()
        self.assertEqual(personal.usuario.username, "clara")
        self.assertFalse(personal.usuario.is_staff)
        self.assertIsNotNone(invitacion.utilizada_en)

    def test_token_vencido_es_rechazado(self):
        personal = self.crear_personal()
        invitacion = InvitacionPersonal.objects.create(personal=personal, vence_en=timezone.now() - timedelta(minutes=1))
        self.assertEqual(self.client.get(reverse("activar_cuenta", args=[invitacion.token])).status_code, 400)

    def test_token_no_se_puede_reutilizar(self):
        personal = self.crear_personal()
        invitacion = InvitacionPersonal.objects.create(personal=personal, utilizada_en=timezone.now())
        self.assertEqual(self.client.get(reverse("activar_cuenta", args=[invitacion.token])).status_code, 400)

    def test_no_permite_invitacion_para_personal_con_usuario(self):
        usuario = User.objects.create_user("cuenta-activa", password="clave-segura")
        personal = self.crear_personal(); personal.usuario = usuario; personal.save()
        invitacion = InvitacionPersonal(personal=personal)
        with self.assertRaises(ValidationError):
            invitacion.full_clean()

    def test_empleada_activada_tiene_permisos_limitados(self):
        personal = self.crear_personal()
        invitacion = InvitacionPersonal.objects.create(personal=personal)
        self.client.post(reverse("activar_cuenta", args=[invitacion.token]), {"username": "clara", "email": "clara@example.test", "password1": "ClaveSegura1", "password2": "ClaveSegura1"})
        self.assertEqual(self.client.get(reverse("tarea_list")).status_code, 200)
        self.assertEqual(self.client.get(reverse("norma_list")).status_code, 200)
        self.assertEqual(self.client.get(reverse("residente_list")).status_code, 403)
        self.assertEqual(self.client.get("/admin/").status_code, 403)


class GeriatricoTest(TestCase):
    def test_codigo_es_unico(self):
        Geriatrico.objects.create(nombre="Geri 1", codigo="G1", direccion="Calle 1", capacidad_total=10)
        with self.assertRaises(Exception):
            Geriatrico.objects.create(nombre="Geri 2", codigo="G1", direccion="Calle 2", capacidad_total=12)

    def test_calcula_camas_disponibles(self):
        geriatrico = Geriatrico.objects.create(nombre="Geri 1", codigo="G1", direccion="Calle 1", capacidad_total=10)
        Residente.objects.create(geriatrico=geriatrico, nombre="Ana", apellido="Pérez", dni="1", fecha_ingreso="2026-01-01")
        Residente.objects.create(geriatrico=geriatrico, nombre="Luis", apellido="Gómez", dni="2", fecha_ingreso="2026-01-01")
        self.assertEqual(geriatrico.camas_disponibles, 8)

    def test_no_permite_superar_capacidad_con_residente_activo(self):
        geriatrico = Geriatrico.objects.create(nombre="Geri 1", codigo="G1", direccion="Calle 1", capacidad_total=1)
        Residente.objects.create(geriatrico=geriatrico, nombre="Ana", apellido="Pérez", dni="1", fecha_ingreso="2026-01-01")
        residente = Residente(geriatrico=geriatrico, nombre="Luis", apellido="Gómez", dni="2", fecha_ingreso="2026-01-01")
        with self.assertRaises(ValidationError):
            residente.full_clean()

    def test_telefono_debe_ser_numerico(self):
        geriatrico = Geriatrico.objects.create(nombre="Geri 1", codigo="G1", direccion="Calle 1", capacidad_total=2)
        residente = Residente(geriatrico=geriatrico, nombre="Ana", apellido="Pérez", dni="1", fecha_ingreso="2026-01-01", telefono="11-1234")
        with self.assertRaises(ValidationError):
            residente.full_clean()

    def test_contacto_familiar_es_obligatorio(self):
        geriatrico = Geriatrico.objects.create(nombre="Geri 1", codigo="G1", direccion="Calle 1", capacidad_total=2)
        residente = Residente(geriatrico=geriatrico, nombre="Ana", apellido="Pérez", dni="1", fecha_ingreso="2026-01-01")
        with self.assertRaises(ValidationError):
            residente.full_clean()

    def test_otra_obra_social_requiere_nombre(self):
        geriatrico = Geriatrico.objects.create(nombre="Geri 1", codigo="G1", direccion="Calle 1", capacidad_total=2)
        residente = Residente(geriatrico=geriatrico, nombre="Ana", apellido="Pérez", dni="1", fecha_ingreso="2026-01-01", contacto_familiar="Familiar", obra_social=Residente.ObraSocial.OTRA)
        with self.assertRaises(ValidationError):
            residente.full_clean()

    def test_numero_afiliado_solo_admite_letras_numeros_y_guiones(self):
        geriatrico = Geriatrico.objects.create(nombre="Geri 1", codigo="G1", direccion="Calle 1", capacidad_total=2)
        residente = Residente(geriatrico=geriatrico, nombre="Ana", apellido="Pérez", dni="1", fecha_ingreso="2026-01-01", contacto_familiar="3411234567", numero_afiliado="ABC 123")
        with self.assertRaises(ValidationError):
            residente.full_clean()

    def test_contacto_familiar_admite_nombre_y_apellido(self):
        geriatrico = Geriatrico.objects.create(nombre="Geri 1", codigo="G1", direccion="Calle 1", capacidad_total=2)
        residente = Residente(geriatrico=geriatrico, nombre="Ana", apellido="Pérez", dni="12345678", fecha_ingreso="2026-01-01", contacto_familiar="María Pérez")
        residente.full_clean()

    def test_contacto_familiar_rechaza_numeros(self):
        geriatrico = Geriatrico.objects.create(nombre="Geri contacto", codigo="GC", direccion="Calle 1", capacidad_total=2)
        residente = Residente(geriatrico=geriatrico, nombre="Ana", apellido="Pérez", dni="12345678", fecha_ingreso="2026-01-01", contacto_familiar="3411234567")
        with self.assertRaises(ValidationError):
            residente.full_clean()

    def test_no_permite_habitacion_ocupada_por_otro_residente_activo(self):
        geriatrico = Geriatrico.objects.create(nombre="Geri 1", codigo="G1", direccion="Calle 1", capacidad_total=2)
        Residente.objects.create(geriatrico=geriatrico, nombre="Ana", apellido="Pérez", dni="1", fecha_ingreso="2026-01-01", contacto_familiar="3411234567", habitacion="1")
        residente = Residente(geriatrico=geriatrico, nombre="Luis", apellido="Gómez", dni="2", fecha_ingreso="2026-01-01", contacto_familiar="3411234568", habitacion="1")
        with self.assertRaises(ValidationError):
            residente.full_clean()

    def test_dni_debe_tener_exactamente_ocho_numeros(self):
        geriatrico = Geriatrico.objects.create(nombre="Geri 1", codigo="G1", direccion="Calle 1", capacidad_total=2)
        residente = Residente(geriatrico=geriatrico, nombre="Ana", apellido="Pérez", dni="1234A678", fecha_ingreso="2026-01-01", contacto_familiar="3411234567")
        with self.assertRaises(ValidationError):
            residente.full_clean()

    def test_numero_afiliado_solo_admite_numeros(self):
        geriatrico = Geriatrico.objects.create(nombre="Geri 1", codigo="G1", direccion="Calle 1", capacidad_total=2)
        residente = Residente(geriatrico=geriatrico, nombre="Ana", apellido="Pérez", dni="12345678", fecha_ingreso="2026-01-01", contacto_familiar="3411234567", numero_afiliado="ABC-123")
        with self.assertRaises(ValidationError):
            residente.full_clean()

    def test_limpia_obra_social_otra_si_selecciona_otra_cobertura(self):
        geriatrico = Geriatrico.objects.create(nombre="Geri 1", codigo="G1", direccion="Calle 1", capacidad_total=2)
        residente = Residente(geriatrico=geriatrico, nombre="Ana", apellido="Pérez", dni="12345678", fecha_ingreso="2026-01-01", contacto_familiar="María Pérez", obra_social=Residente.ObraSocial.PAMI, obra_social_otra="Cobertura anterior")
        residente.full_clean()
        self.assertEqual(residente.obra_social_otra, "")


class CierreVersionUnoTest(TestCase):
    def setUp(self):
        self.admin = User.objects.create_user("admin-v1", password="ClaveSegura1", is_staff=True)
        self.empleada = User.objects.create_user("empleada-v1", password="ClaveSegura1")
        self.personal = Personal.objects.create(nombre_completo="Empleada V1", usuario=self.empleada, dni="33444555", cargo=Personal.Cargo.CUIDADOR, turno_habitual="Mañana", inicio_contrato=date.today())

    def test_edicion_de_perfil_y_foto_opcional(self):
        self.client.login(username="empleada-v1", password="ClaveSegura1")
        respuesta = self.client.post(reverse("mi_perfil"), {"accion": "datos", "first_name": "Ana", "last_name": "López", "email": "ana@example.test"})
        self.assertRedirects(respuesta, reverse("mi_perfil"))
        self.empleada.refresh_from_db()
        self.assertEqual(self.empleada.first_name, "Ana")
        self.assertTrue(PerfilUsuario.objects.filter(usuario=self.empleada).exists())

    def test_cambio_contrasena_conserva_sesion(self):
        self.client.login(username="empleada-v1", password="ClaveSegura1")
        respuesta = self.client.post(reverse("mi_perfil"), {"accion": "contrasena", "old_password": "ClaveSegura1", "new_password1": "NuevaClave2", "new_password2": "NuevaClave2"})
        self.assertRedirects(respuesta, reverse("mi_perfil"))
        self.assertTrue(self.client.login(username="empleada-v1", password="NuevaClave2"))

    def test_perfil_y_notificaciones_son_propios_de_empleada(self):
        Tarea.objects.create(titulo="Control", asignada_a=self.personal, fecha=date.today() - timedelta(days=1), turno=Tarea.Turno.MANANA)
        self.client.login(username="empleada-v1", password="ClaveSegura1")
        self.assertEqual(self.client.get(reverse("mi_perfil")).status_code, 200)
        respuesta = self.client.get(reverse("notificaciones"))
        self.assertContains(respuesta, "tarea(s) pendientes")
        self.assertEqual(self.client.get(reverse("backup_generar")).status_code, 403)

    def test_backup_es_descargable_y_restringido(self):
        self.client.login(username="admin-v1", password="ClaveSegura1")
        respuesta = self.client.post(reverse("backup_generar"))
        self.assertEqual(respuesta.status_code, 200)
        self.assertEqual(respuesta["Content-Type"], "application/zip")
        with zipfile.ZipFile(BytesIO(b"".join(respuesta.streaming_content) if hasattr(respuesta, "streaming_content") else respuesta.content)) as archivo:
            self.assertIn("RESTAURAR.txt", archivo.namelist())

    def test_acerca_del_sistema_requiere_login_y_es_visible(self):
        self.assertRedirects(self.client.get(reverse("acerca_sistema")), f"{reverse('login')}?next={reverse('acerca_sistema')}")
        self.client.login(username="admin-v1", password="ClaveSegura1")
        self.assertContains(self.client.get(reverse("acerca_sistema")), "Sistema de Gestión Integral")


class PwaTest(TestCase):
    def test_service_worker_es_publico_y_tiene_alcance_raiz(self):
        respuesta = self.client.get(reverse("service_worker"))
        self.assertEqual(respuesta.status_code, 200)
        self.assertEqual(respuesta["Service-Worker-Allowed"], "/")
        self.assertIn("/static/offline.html", respuesta.content.decode())
        self.assertNotIn("/pagos/", respuesta.content.decode())

    def test_login_incluye_manifest_y_metadatos_ios(self):
        respuesta = self.client.get(reverse("login"))
        self.assertContains(respuesta, "manifest.webmanifest")
        self.assertContains(respuesta, "apple-mobile-web-app-capable")
        self.assertContains(respuesta, "Añadir a pantalla de inicio")
        self.assertContains(respuesta, "Sistema creado por")
        self.assertContains(respuesta, "<strong>Datanova IT Solutions</strong>", html=False)
        self.assertContains(respuesta, "https://www.datanovait.com")


class MisTurnosTest(TestCase):
    def setUp(self):
        self.usuario = User.objects.create_user("turnos-propios", password="ClaveSegura1")
        self.personal = Personal.objects.create(nombre_completo="Ana Turnos", usuario=self.usuario, dni="77888999", cargo=Personal.Cargo.CUIDADOR, turno_habitual="Mañana", inicio_contrato=date.today())
        self.otro = Personal.objects.create(nombre_completo="Otra Empleada", dni="66777888", cargo=Personal.Cargo.CUIDADOR, turno_habitual="Tarde", inicio_contrato=date.today())
        hoy = date.today()
        grilla = GrillaTurnos.objects.create(mes=hoy.month, anio=hoy.year)
        AsignacionTurno.objects.create(grilla=grilla, personal=self.personal, dia=hoy.day, codigo=AsignacionTurno.Codigo.M)
        AsignacionTurno.objects.create(grilla=grilla, personal=self.otro, dia=hoy.day, codigo=AsignacionTurno.Codigo.N)

    def test_empleada_ve_solo_sus_turnos_y_no_edita_grilla(self):
        self.client.login(username="turnos-propios", password="ClaveSegura1")
        respuesta = self.client.get(reverse("mis_turnos"))
        self.assertEqual(respuesta.status_code, 200)
        self.assertContains(respuesta, "Mañana (7-15h)")
        self.assertNotContains(respuesta, "Otra Empleada")
        self.assertEqual(self.client.get(reverse("turnos")).status_code, 403)

    def test_panel_de_tareas_muestra_turno_de_hoy(self):
        self.client.login(username="turnos-propios", password="ClaveSegura1")
        respuesta = self.client.get(reverse("tarea_list"))
        self.assertContains(respuesta, "Hoy trabajás")
        self.assertContains(respuesta, "07:00 a 15:00")


class CorreccionesOperativasTest(TestCase):
    def setUp(self):
        self.usuario = User.objects.create_user("operador", password="ClaveSegura1")
        self.usuario.groups.add(Group.objects.get_or_create(name="Secretaría")[0])
        self.geriatrico = Geriatrico.objects.create(nombre="Geri web", codigo="GW", direccion="Calle 1", capacidad_total=5)
        self.residente = Residente.objects.create(geriatrico=self.geriatrico, nombre="Ana", apellido="Web", dni="11223344", fecha_ingreso=date.today(), contacto_familiar="María Pérez", monto_mensual=Decimal("1000.00"))
        self.client.login(username="operador", password="ClaveSegura1")

    def test_listado_residentes_muestra_acciones_y_afiliado(self):
        self.residente.numero_afiliado = "12345"; self.residente.save()
        respuesta = self.client.get(reverse("residente_list"))
        self.assertContains(respuesta, "Nuevo residente")
        self.assertContains(respuesta, "Exportar Excel")
        self.assertContains(respuesta, "Exportar PDF")
        self.assertContains(respuesta, "12345")

    def test_alta_residente_desde_web(self):
        datos = {"geriatrico": self.geriatrico.pk, "nombre": "Luis", "apellido": "Nuevo", "dni": "55667788", "fecha_ingreso": date.today(), "contacto_familiar": "Juan Gómez", "estado": Residente.Estado.ACTIVO, "movilidad": Residente.Movilidad.INDEPENDIENTE}
        respuesta = self.client.post(reverse("residente_create"), datos)
        self.assertRedirects(respuesta, reverse("residente_list"))
        self.assertTrue(Residente.objects.filter(dni="55667788").exists())

    def test_cuotas_rechazan_vencimiento_pasado(self):
        respuesta = self.client.post(reverse("generar_cuotas"), {"periodo": "2026-08", "fecha_vencimiento": date.today() - timedelta(days=1), "geriatrico": self.geriatrico.pk})
        self.assertContains(respuesta, "no puede ser anterior a la fecha actual")
        self.assertFalse(Pago.objects.filter(residente=self.residente, periodo="2026-08").exists())

class FormatoMonetarioTest(TestCase):
    def test_formato_argentino_con_miles_centavos_y_cero(self):
        self.assertEqual(formatear_moneda(1200000), "$ 1.200.000,00")
        self.assertEqual(formatear_moneda("85000.5"), "$ 85.000,50")
        self.assertEqual(formatear_moneda(0), "$ 0,00")

    def test_formularios_aceptan_punto_y_coma(self):
        geriatrico = Geriatrico.objects.create(nombre="Geri moneda", codigo="GM", direccion="Calle", capacidad_total=2)
        residente = Residente.objects.create(geriatrico=geriatrico, nombre="Ana", apellido="Moneda", dni="99887766", fecha_ingreso=date.today(), contacto_familiar="María Pérez")
        parcial_form = PagoParcialForm({"monto": "85000.5", "fecha_pago": date.today(), "medio_pago": "", "observaciones": ""})
        self.assertTrue(parcial_form.is_valid(), parcial_form.errors)
        categoria = CategoriaCaja.objects.create(nombre="Moneda")
        egreso_form = EgresoCajaForm({"fecha": date.today(), "geriatrico": geriatrico.pk, "categoria": categoria.pk, "proveedor_beneficiario": "", "descripcion": "", "importe": "1.200,50", "medio_pago": "", "observaciones": ""})
        self.assertTrue(egreso_form.is_valid(), egreso_form.errors)
        self.assertEqual(egreso_form.cleaned_data["importe"], Decimal("1200.50"))

    def test_exportaciones_pdf_y_excel_formatean_importes(self):
        institucion = ConfiguracionInstitucional.objects.create(nombre_institucion="Dulce Atardecer")
        excel = excel_response("prueba", ["Monto", "Concepto"], [(Decimal("1200000.50"), "Cuota")])
        libro = load_workbook(BytesIO(excel.content))
        self.assertEqual(libro.active["A2"].value, Decimal("1200000.50"))
        self.assertIn("$", libro.active["A2"].number_format)
        pdf = pdf_response("Prueba", ["Monto"], [(Decimal("1200000.50"),)], institucion, "usuario")
        self.assertEqual(pdf["Content-Type"], "application/pdf")
        self.assertIn("1.200.000,50".encode(), pdf.content)


class ComprobantePagoTest(TestCase):
    def setUp(self):
        self.usuario = User.objects.create_user("comprobantes", password="ClaveSegura1")
        self.usuario.groups.add(Group.objects.get_or_create(name="Secretaría")[0])
        geriatrico = Geriatrico.objects.create(nombre="Geri comprobantes", codigo="GCMP", direccion="Calle", capacidad_total=2)
        residente = Residente.objects.create(geriatrico=geriatrico, nombre="Ana", apellido="Comprobante", dni="88776655", fecha_ingreso=date.today(), contacto_familiar="María Pérez")
        self.pago = Pago.objects.create(residente=residente, periodo="2026-08", concepto="Cuota mensual", monto=Decimal("1200000.50"), fecha_vencimiento=date.today(), fecha_pago=date.today(), medio_pago=Pago.MedioPago.TRANSFERENCIA)
        self.institucion = ConfiguracionInstitucional.objects.create(nombre_institucion="Dulce Atardecer")
        self.client.login(username="comprobantes", password="ClaveSegura1")

    def test_descarga_y_email_reutilizan_comprobante(self):
        respuesta = self.client.get(reverse("descargar_comprobante", args=[self.pago.pk]))
        self.assertEqual(respuesta["Content-Type"], "application/pdf")
        self.assertIn("comprobante-pago", respuesta["Content-Disposition"])
        self.assertIn(b"COMPROBANTE DE PAGO", respuesta.content)
        self.assertIn(b"1.200.000,50", respuesta.content)
        self.assertIn(b"Datanova IT Solutions", comprobante_pago_pdf(self.pago, self.institucion, self.usuario))

    def test_ficha_muestra_boton_de_descarga(self):
        respuesta = self.client.get(reverse("pago_detail", args=[self.pago.pk]))
        self.assertContains(respuesta, "Descargar comprobante PDF")


class ReporteResidentesPdfTest(TestCase):
    def test_reporte_residentes_incluye_columnas_total_y_pie(self):
        usuario = User.objects.create_user("reporte-residentes", password="ClaveSegura1")
        usuario.groups.add(Group.objects.get_or_create(name="Consulta")[0])
        geriatrico = Geriatrico.objects.create(nombre="Geri reporte", codigo="GRP", direccion="Calle", capacidad_total=2)
        Residente.objects.create(geriatrico=geriatrico, nombre="Ana", apellido="Reporte", dni="44556677", fecha_ingreso=date.today(), contacto_familiar="María Pérez", obra_social=Residente.ObraSocial.PAMI, numero_afiliado="12345")
        ConfiguracionInstitucional.objects.create(nombre_institucion="Dulce Atardecer")
        self.client.login(username="reporte-residentes", password="ClaveSegura1")
        respuesta = self.client.get(reverse("residente_exportar", args=["pdf"]))
        self.assertEqual(respuesta["Content-Type"], "application/pdf")
        for texto in (b"REPORTE DE RESIDENTES", b"Total de residentes", b"afiliado", b"Datanova IT Solutions", b"Reporte, Ana"):
            self.assertIn(texto, respuesta.content)


class OperacionFinancieraFechasTest(TestCase):
    def setUp(self):
        self.usuario = User.objects.create_user("operacion-fechas", password="ClaveSegura1")
        self.usuario.groups.add(Group.objects.get_or_create(name="Secretaría")[0])
        self.geriatrico = Geriatrico.objects.create(nombre="Geri operativo", codigo="GOP", direccion="Calle", capacidad_total=5)
        self.otro_geriatrico = Geriatrico.objects.create(nombre="Geri alternativo", codigo="GAL", direccion="Calle", capacidad_total=5)
        self.residente = Residente.objects.create(geriatrico=self.geriatrico, nombre="Ana", apellido="Operativa", dni="66778899", fecha_ingreso=date.today(), contacto_familiar="María Pérez", monto_mensual=Decimal("1000.00"))
        self.otro_residente = Residente.objects.create(geriatrico=self.otro_geriatrico, nombre="Berta", apellido="Alternativa", dni="77889900", fecha_ingreso=date.today(), contacto_familiar="Lucía Pérez", monto_mensual=Decimal("1000.00"))
        self.client.login(username="operacion-fechas", password="ClaveSegura1")

    def test_rechaza_fechas_futuras_en_residente_pago_abono_y_egreso(self):
        futura = date.today() + timedelta(days=1)
        residente_form = ResidenteForm({"geriatrico": self.geriatrico.pk, "nombre": "Luis", "apellido": "Futuro", "dni": "88990011", "fecha_ingreso": futura, "contacto_familiar": "Juan Pérez", "movilidad": Residente.Movilidad.INDEPENDIENTE, "estado": Residente.Estado.ACTIVO})
        self.assertFalse(residente_form.is_valid()); self.assertIn("fecha_ingreso", residente_form.errors)
        pago = Pago(residente=self.residente, periodo="2026-08", concepto="Cuota", monto=Decimal("1000.00"), fecha_vencimiento=futura, fecha_pago=futura)
        with self.assertRaises(ValidationError):
            pago.full_clean()
        parcial_form = PagoParcialForm({"monto": "100", "fecha_pago": futura, "medio_pago": "", "observaciones": ""})
        self.assertFalse(parcial_form.is_valid()); self.assertIn("fecha_pago", parcial_form.errors)
        categoria = CategoriaCaja.objects.create(nombre="Operativo")
        egreso_form = EgresoCajaForm({"fecha": futura, "geriatrico": self.geriatrico.pk, "categoria": categoria.pk, "proveedor_beneficiario": "Proveedor", "descripcion": "", "importe": "10", "medio_pago": "", "observaciones": ""})
        self.assertFalse(egreso_form.is_valid()); self.assertIn("fecha", egreso_form.errors)

    def test_cuota_registra_abono_y_movimiento_de_caja(self):
        pago = Pago.objects.create(residente=self.residente, periodo="2026-08", concepto="Cuota", monto=Decimal("1000.00"), fecha_vencimiento=date.today())
        respuesta = self.client.post(reverse("pago_detail", args=[pago.pk]), {"monto": "1000", "fecha_pago": date.today(), "medio_pago": Pago.MedioPago.EFECTIVO, "observaciones": ""})
        self.assertEqual(respuesta.status_code, 302); pago.refresh_from_db()
        self.assertEqual(pago.estado, Pago.Estado.PAGADO); self.assertEqual(pago.saldo_pendiente, Decimal("0.00"))
        self.assertTrue(CajaMovimiento.objects.filter(pago=pago, importe=Decimal("1000.00"), tipo=CajaMovimiento.Tipo.INGRESO).exists())

    def test_pago_parcial_actualiza_estado_y_caja(self):
        pago = Pago.objects.create(residente=self.residente, periodo="2026-09", concepto="Cuota", monto=Decimal("1000.00"), fecha_vencimiento=date.today())
        respuesta = self.client.post(reverse("pago_detail", args=[pago.pk]), {"monto": "400", "fecha_pago": date.today(), "medio_pago": Pago.MedioPago.EFECTIVO, "observaciones": ""})
        self.assertEqual(respuesta.status_code, 302); pago.refresh_from_db()
        self.assertEqual(pago.estado, Pago.Estado.PARCIAL); self.assertEqual(pago.saldo_pendiente, Decimal("600.00"))
        self.assertTrue(CajaMovimiento.objects.filter(pago=pago, importe=Decimal("400.00")).exists())

    def test_indicadores_y_cierre_mensual(self):
        pago = Pago.objects.create(residente=self.residente, periodo=date.today().strftime("%Y-%m"), concepto="Cuota", monto=Decimal("1000.00"), fecha_vencimiento=date.today(), fecha_pago=date.today())
        categoria = CategoriaCaja.objects.create(nombre="Insumos operativos")
        CajaMovimiento.objects.create(fecha=date.today(), tipo=CajaMovimiento.Tipo.EGRESO, geriatrico=self.geriatrico, categoria=categoria, importe=Decimal("250.00"), descripcion="Compra")
        respuesta = self.client.get(reverse("caja_list"))
        self.assertEqual(respuesta.context["ingresos_mes"], Decimal("1000.00")); self.assertEqual(respuesta.context["egresos_mes"], Decimal("250.00")); self.assertEqual(respuesta.context["resultado_mes"], Decimal("750.00")); self.assertEqual(response_context := respuesta.context["saldo_actual"], Decimal("750.00"))
        self.client.post(reverse("caja_cierre"), {"geriatrico": self.geriatrico.pk}); cierre = CajaCierre.objects.get(fecha=date.today().replace(day=1), geriatrico=self.geriatrico)
        self.assertEqual(cierre.resultado, Decimal("750.00")); self.assertEqual(cierre.saldo_final, Decimal("750.00")); self.assertEqual(cierre.cantidad_cobros, 1); self.assertEqual(cierre.cantidad_egresos, 1)


class CierreCajaExperienciaTest(TestCase):
    def setUp(self):
        self.usuario = User.objects.create_user("cierre-caja", password="ClaveSegura1")
        self.usuario.groups.add(Group.objects.get_or_create(name="Secretaría")[0])
        self.geriatrico = Geriatrico.objects.create(nombre="Geri cierre", codigo="GCI", direccion="Calle", capacidad_total=3)
        self.categoria = CategoriaCaja.objects.create(nombre="Cierre categoría")
        CajaMovimiento.objects.create(tipo=CajaMovimiento.Tipo.INGRESO, fecha=date.today(), geriatrico=self.geriatrico, importe=Decimal("500.00"), descripcion="Cobro")
        CajaMovimiento.objects.create(tipo=CajaMovimiento.Tipo.EGRESO, fecha=date.today(), geriatrico=self.geriatrico, categoria=self.categoria, importe=Decimal("100.00"), descripcion="Compra")
        self.client.login(username="cierre-caja", password="ClaveSegura1")

    def test_crea_muestra_consulta_y_descarga_cierre(self):
        respuesta = self.client.post(reverse("caja_cierre"), {"geriatrico": self.geriatrico.pk})
        cierre = CajaCierre.objects.get(fecha=date.today().replace(day=1), geriatrico=self.geriatrico)
        self.assertRedirects(respuesta, f"{reverse('caja_list')}?cierre={cierre.pk}")
        self.assertEqual(cierre.ingresos, Decimal("500.00")); self.assertEqual(cierre.egresos, Decimal("100.00")); self.assertEqual(cierre.resultado, Decimal("400.00"))
        respuesta = self.client.get(reverse("caja_list"))
        self.assertEqual(respuesta.context["ultimo_cierre"], cierre)
        self.assertContains(respuesta, "Último cierre mensual")
        self.assertContains(self.client.get(reverse("caja_cierres")), "Geri cierre")
        pdf = self.client.get(reverse("caja_cierre_pdf", args=[cierre.pk]))
        self.assertEqual(pdf.status_code, 200); self.assertEqual(pdf["Content-Type"], "application/pdf")

    def test_cierres_historicos_sin_geriatrico_se_muestran_y_descargan(self):
        cierre = CajaCierre.objects.create(
            fecha=(date.today() - timedelta(days=32)).replace(day=1),
            saldo_inicial=Decimal("0.00"), ingresos=Decimal("100.00"), egresos=Decimal("20.00"),
            resultado=Decimal("80.00"), saldo_final=Decimal("80.00"), cantidad_cobros=1,
            cantidad_egresos=1, cerrado_por=self.usuario,
        )
        historial = self.client.get(reverse("caja_cierres"))
        self.assertContains(historial, "Todos los geriátricos")
        pdf = self.client.get(reverse("caja_cierre_pdf", args=[cierre.pk]))
        self.assertEqual(pdf.status_code, 200); self.assertEqual(pdf["Content-Type"], "application/pdf")

    def test_no_existe_el_flujo_publico_registrar_pago(self):
        respuesta = self.client.get(reverse("pago_list"))
        self.assertNotContains(respuesta, "Registrar pago")
        self.assertIn(self.client.get("/pagos/registrar/").status_code, (403, 404))

    def test_no_recalcula_un_cierre_existente_sin_confirmacion(self):
        self.client.post(reverse("caja_cierre"), {"geriatrico": self.geriatrico.pk})
        cierre = CajaCierre.objects.get(geriatrico=self.geriatrico)
        CajaMovimiento.objects.create(tipo=CajaMovimiento.Tipo.INGRESO, fecha=date.today(), geriatrico=self.geriatrico, importe=Decimal("50.00"), descripcion="Cobro posterior")
        respuesta = self.client.post(reverse("caja_cierre"), {"geriatrico": self.geriatrico.pk})
        self.assertRedirects(respuesta, f"{reverse('caja_list')}?confirmar_cierre={cierre.pk}")
        cierre.refresh_from_db(); self.assertEqual(cierre.ingresos, Decimal("500.00"))
        self.client.post(reverse("caja_cierre"), {"geriatrico": self.geriatrico.pk, "confirmar_reemplazo": "1"})
        cierre.refresh_from_db(); self.assertEqual(cierre.ingresos, Decimal("550.00"))
