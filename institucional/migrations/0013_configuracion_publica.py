from decimal import Decimal
from django.db import migrations, models


PORCENTAJES = [Decimal("5"), Decimal("8"), Decimal("10"), Decimal("12"), Decimal("15"), Decimal("20")]


def crear_porcentajes(apps, schema_editor):
    Modelo = apps.get_model("institucional", "PorcentajeActualizacion")
    for porcentaje in PORCENTAJES:
        Modelo.objects.get_or_create(porcentaje=porcentaje)


class Migration(migrations.Migration):
    dependencies = [("institucional", "0012_proveedor_y_categorias_iniciales")]
    operations = [
        migrations.AddField(model_name="configuracioninstitucional", name="direccion", field=models.CharField(blank=True, max_length=255)),
        migrations.AddField(model_name="configuracioninstitucional", name="telefono", field=models.CharField(blank=True, max_length=30)),
        migrations.AddField(model_name="configuracioninstitucional", name="email", field=models.EmailField(blank=True, max_length=254)),
        migrations.AddField(model_name="configuracioninstitucional", name="cuit", field=models.CharField(blank=True, max_length=20)),
        migrations.AddField(model_name="configuracioninstitucional", name="logo", field=models.FileField(blank=True, null=True, upload_to="logos/")),
        migrations.AddField(model_name="configuracioninstitucional", name="dia_vencimiento_defecto", field=models.PositiveSmallIntegerField(default=10)),
        migrations.AddField(model_name="configuracioninstitucional", name="concepto_cuota_defecto", field=models.CharField(default="Cuota mensual", max_length=150)),
        migrations.AddField(model_name="configuracioninstitucional", name="moneda", field=models.CharField(default="ARS", max_length=10)),
        migrations.CreateModel(name="ObraSocial", fields=[("id", models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name="ID")), ("nombre", models.CharField(max_length=100, unique=True)), ("activa", models.BooleanField(default=True))], options={"ordering": ["nombre"]}),
        migrations.CreateModel(name="MedioPagoConfiguracion", fields=[("id", models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name="ID")), ("nombre", models.CharField(max_length=50, unique=True)), ("activo", models.BooleanField(default=True))], options={"ordering": ["nombre"]}),
        migrations.CreateModel(name="PorcentajeActualizacion", fields=[("id", models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name="ID")), ("porcentaje", models.DecimalField(decimal_places=2, max_digits=6, unique=True)), ("activo", models.BooleanField(default=True))], options={"ordering": ["porcentaje"]}),
        migrations.RunPython(crear_porcentajes, migrations.RunPython.noop),
    ]
