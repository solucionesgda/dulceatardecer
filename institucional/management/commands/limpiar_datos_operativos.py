from django.core.management.base import BaseCommand
from django.db import transaction

from institucional.models import (
    AsignacionTurno,
    CajaCierre,
    CajaMovimiento,
    GrillaTurnos,
    HistorialEnvioEmail,
    InvitacionPersonal,
    LecturaNormaPolitica,
    Pago,
    PagoParcial,
    Residente,
    Tarea,
)


class Command(BaseCommand):
    help = "Elimina datos operativos conservando usuarios, personal, geriátricos, configuración y catálogos."

    modelos_operativos = (
        ("Cierres de Caja", CajaCierre),
        ("Movimientos de Caja", CajaMovimiento),
        ("Abonos", PagoParcial),
        ("Pagos y cuotas", Pago),
        ("Asignaciones de turnos", AsignacionTurno),
        ("Grillas de turnos", GrillaTurnos),
        ("Tareas", Tarea),
        ("Lecturas de normas", LecturaNormaPolitica),
        ("Invitaciones de empleadas", InvitacionPersonal),
        ("Historial de envíos de email", HistorialEnvioEmail),
        ("Residentes", Residente),
    )

    def add_arguments(self, parser):
        parser.add_argument(
            "--confirmar",
            action="store_true",
            help="Confirma la limpieza sin solicitar la palabra LIMPIAR.",
        )

    def mostrar_resumen(self):
        self.stdout.write("Se eliminarán los siguientes datos operativos:")
        for etiqueta, modelo in self.modelos_operativos:
            self.stdout.write(f"- {etiqueta}: {modelo.objects.count()}")

    def _eliminar(self, modelo):
        modelo.objects.all().delete()

    def handle(self, *args, **options):
        self.mostrar_resumen()
        if not options["confirmar"]:
            confirmacion = input("Escribí LIMPIAR para confirmar la operación: ")
            if confirmacion != "LIMPIAR":
                self.stdout.write(self.style.WARNING("Operación cancelada. No se eliminó ningún dato."))
                return

        with transaction.atomic():
            for _, modelo in self.modelos_operativos:
                self._eliminar(modelo)

        self.stdout.write(self.style.SUCCESS("Datos operativos eliminados correctamente."))
