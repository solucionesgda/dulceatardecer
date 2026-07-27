from django.db import migrations, models


COBERTURAS = {"PAMI", "IAPOS", "OSDE", "Swiss Medical", "Galeno", "Sancor Salud", "Avalian", "Federada Salud", "Particular", "Otra", ""}


def conservar_coberturas_existentes(apps, schema_editor):
    Residente = apps.get_model("institucional", "Residente")
    for residente in Residente.objects.exclude(obra_social__in=COBERTURAS):
        residente.obra_social_otra = residente.obra_social
        residente.obra_social = "Otra"
        residente.save(update_fields=["obra_social", "obra_social_otra"])


class Migration(migrations.Migration):
    dependencies = [("institucional", "0004_residente_y_ocupacion_derivada")]

    operations = [
        migrations.AddField(
            model_name="residente",
            name="obra_social_otra",
            field=models.CharField(blank=True, max_length=100),
        ),
        migrations.RunPython(conservar_coberturas_existentes, migrations.RunPython.noop),
        migrations.AlterField(
            model_name="residente",
            name="obra_social",
            field=models.CharField(blank=True, choices=[("PAMI", "PAMI"), ("IAPOS", "IAPOS"), ("OSDE", "OSDE"), ("Swiss Medical", "Swiss Medical"), ("Galeno", "Galeno"), ("Sancor Salud", "Sancor Salud"), ("Avalian", "Avalian"), ("Federada Salud", "Federada Salud"), ("Particular", "Particular"), ("Otra", "Otra")], max_length=100),
        ),
    ]
