from django.contrib.auth.models import Group, Permission
from django.core.management.base import BaseCommand
from institucional.models import ConfiguracionInstitucional, Geriatrico


class Command(BaseCommand):
    help = "Crea la configuración, los grupos y los geriátricos iniciales."

    def handle(self, *args, **options):
        permisos = {
            "Administrador": ["add_geriatrico", "change_geriatrico", "delete_geriatrico", "view_geriatrico", "add_configuracioninstitucional", "change_configuracioninstitucional", "delete_configuracioninstitucional", "view_configuracioninstitucional"],
            "Secretaría": ["add_geriatrico", "change_geriatrico", "view_geriatrico", "view_configuracioninstitucional"],
            "Consulta": ["view_geriatrico", "view_configuracioninstitucional"],
        }
        for nombre, codenames in permisos.items():
            grupo, _ = Group.objects.get_or_create(name=nombre)
            grupo.permissions.set(Permission.objects.filter(content_type__app_label="institucional", codename__in=codenames))
        for numero in range(1, 4):
            Geriatrico.objects.get_or_create(codigo=f"GERI-{numero}", defaults={"nombre": f"Geri {numero}", "direccion": "A definir", "capacidad_camas": 10, "activo": True})
        ConfiguracionInstitucional.objects.get_or_create(pk=1)
        self.stdout.write(self.style.SUCCESS("Datos iniciales cargados correctamente."))
