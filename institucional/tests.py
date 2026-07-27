from django.contrib.auth.models import Group, Permission, User
from django.core.exceptions import ValidationError
from django.test import TestCase
from django.urls import reverse
from .models import Geriatrico, Residente


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
