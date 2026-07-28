from django.contrib.auth.models import Group, Permission, User
from django.core.exceptions import ValidationError
from django.test import TestCase
from django.urls import reverse
from datetime import date, timedelta
from decimal import Decimal
from .models import CajaCierre, CajaMovimiento, CategoriaCaja, Geriatrico, Pago, PagoParcial, Personal, Residente


class AccesoTest(TestCase):
    def setUp(self):
        self.usuario = User.objects.create_user("consulta", password="clave-segura")
        grupo = Group.objects.create(name="Consulta")
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
        self.client.post(reverse("caja_cierre"))
        cierre = CajaCierre.objects.get(fecha=date.today())
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

    def test_contacto_familiar_solo_admite_numeros(self):
        geriatrico = Geriatrico.objects.create(nombre="Geri 1", codigo="G1", direccion="Calle 1", capacidad_total=2)
        residente = Residente(geriatrico=geriatrico, nombre="Ana", apellido="Pérez", dni="1", fecha_ingreso="2026-01-01", contacto_familiar="Contacto")
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
        residente = Residente(geriatrico=geriatrico, nombre="Ana", apellido="Pérez", dni="12345678", fecha_ingreso="2026-01-01", contacto_familiar="3411234567", obra_social=Residente.ObraSocial.PAMI, obra_social_otra="Cobertura anterior")
        residente.full_clean()
        self.assertEqual(residente.obra_social_otra, "")
