from django.db import migrations, models


CATEGORIAS = ["Alimentos", "Farmacia", "Sueldos", "Servicios", "Mantenimiento", "Limpieza", "Impuestos", "Honorarios", "Insumos", "Combustible", "Otros"]


def crear_categorias(apps, schema_editor):
    CategoriaCaja = apps.get_model("institucional", "CategoriaCaja")
    for nombre in CATEGORIAS:
        CategoriaCaja.objects.get_or_create(nombre=nombre)


class Migration(migrations.Migration):
    dependencies = [("institucional", "0011_categorias_y_cierres_caja")]
    operations = [
        migrations.AddField(model_name="cajamovimiento", name="proveedor_beneficiario", field=models.CharField(blank=True, max_length=150)),
        migrations.RunPython(crear_categorias, migrations.RunPython.noop),
    ]
