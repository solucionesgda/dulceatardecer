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
