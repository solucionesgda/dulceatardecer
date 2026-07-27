from django.conf import settings
from django.db import migrations, models
import django.db.models.deletion


def migrar_categorias(apps, schema_editor):
    CategoriaCaja = apps.get_model("institucional", "CategoriaCaja")
    Movimiento = apps.get_model("institucional", "CajaMovimiento")
    for movimiento in Movimiento.objects.exclude(categoria=""):
        categoria, _ = CategoriaCaja.objects.get_or_create(nombre=movimiento.categoria)
        movimiento.categoria_nueva = categoria
        movimiento.save(update_fields=["categoria_nueva"])


class Migration(migrations.Migration):
    dependencies = [("institucional", "0010_caja_movimientos"), migrations.swappable_dependency(settings.AUTH_USER_MODEL)]

    operations = [
        migrations.CreateModel(
            name="CategoriaCaja",
            fields=[
                ("id", models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name="ID")),
                ("nombre", models.CharField(max_length=100, unique=True)),
                ("activa", models.BooleanField(default=True)),
            ],
            options={"ordering": ["nombre"], "verbose_name": "categoría de caja", "verbose_name_plural": "categorías de caja"},
        ),
        migrations.AddField(model_name="cajamovimiento", name="categoria_nueva", field=models.ForeignKey(blank=True, null=True, on_delete=django.db.models.deletion.PROTECT, related_name="movimientos", to="institucional.categoriacaja")),
        migrations.RunPython(migrar_categorias, migrations.RunPython.noop),
        migrations.RemoveField(model_name="cajamovimiento", name="categoria"),
        migrations.RenameField(model_name="cajamovimiento", old_name="categoria_nueva", new_name="categoria"),
        migrations.CreateModel(
            name="CajaCierre",
            fields=[
                ("id", models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name="ID")),
                ("fecha", models.DateField(unique=True)),
                ("saldo_inicial", models.DecimalField(decimal_places=2, max_digits=12)),
                ("ingresos", models.DecimalField(decimal_places=2, max_digits=12)),
                ("egresos", models.DecimalField(decimal_places=2, max_digits=12)),
                ("saldo_final", models.DecimalField(decimal_places=2, max_digits=12)),
                ("cantidad_cobros", models.PositiveIntegerField()),
                ("cantidad_egresos", models.PositiveIntegerField()),
                ("cerrado_en", models.DateTimeField(auto_now=True)),
                ("cerrado_por", models.ForeignKey(blank=True, null=True, on_delete=django.db.models.deletion.SET_NULL, to=settings.AUTH_USER_MODEL)),
            ],
            options={"ordering": ["-fecha"], "verbose_name": "cierre de caja", "verbose_name_plural": "cierres de caja"},
        ),
    ]
