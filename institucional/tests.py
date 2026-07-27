from django.contrib.auth.models import Group, Permission, User
from django.test import TestCase
from django.urls import reverse
from .models import Geriatrico


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
        Geriatrico.objects.create(nombre="Geri 1", codigo="G1", direccion="Calle 1", capacidad_camas=10)
        with self.assertRaises(Exception):
            Geriatrico.objects.create(nombre="Geri 2", codigo="G1", direccion="Calle 2", capacidad_camas=12)
