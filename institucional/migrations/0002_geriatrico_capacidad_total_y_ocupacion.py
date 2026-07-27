from django.db import migrations, models


def copiar_capacidad_existente(apps, schema_editor):
    Geriatrico = apps.get_model("institucional", "Geriatrico")
    for geriatrico in Geriatrico.objects.all():
        geriatrico.capacidad_total = geriatrico.capacidad_camas
        geriatrico.save(update_fields=["capacidad_total"])


class Migration(migrations.Migration):
    dependencies = [("institucional", "0001_initial")]

    operations = [
        migrations.AddField(
            model_name="geriatrico",
            name="capacidad_total",
            field=models.PositiveIntegerField(null=True),
        ),
        migrations.RunPython(copiar_capacidad_existente, migrations.RunPython.noop),
        migrations.AlterField(
            model_name="geriatrico",
            name="capacidad_total",
            field=models.PositiveIntegerField(),
        ),
        migrations.AddField(
            model_name="geriatrico",
            name="camas_ocupadas",
            field=models.PositiveIntegerField(default=0),
        ),
        migrations.AddConstraint(
            model_name="geriatrico",
            constraint=models.CheckConstraint(condition=models.Q(("capacidad_total__gt", 0)), name="capacidad_total_mayor_a_cero"),
        ),
        migrations.AddConstraint(
            model_name="geriatrico",
            constraint=models.CheckConstraint(condition=models.Q(("camas_ocupadas__lte", models.F("capacidad_total"))), name="ocupacion_no_supera_capacidad"),
        ),
    ]
