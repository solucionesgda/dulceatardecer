from django.db import migrations, models


class Migration(migrations.Migration):
    initial = True
    dependencies = []
    operations = [
        migrations.CreateModel(name="ConfiguracionInstitucional", fields=[("id", models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name="ID")), ("nombre_institucion", models.CharField(default="Dulce Atardecer", max_length=150)), ("observaciones", models.TextField(blank=True)), ("actualizado_en", models.DateTimeField(auto_now=True))], options={"verbose_name": "configuración institucional", "verbose_name_plural": "configuración institucional"}),
        migrations.CreateModel(name="Geriatrico", fields=[("id", models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name="ID")), ("nombre", models.CharField(max_length=150)), ("codigo", models.CharField(max_length=30, unique=True)), ("direccion", models.CharField(max_length=255)), ("capacidad_camas", models.PositiveIntegerField()), ("activo", models.BooleanField(default=True)), ("observaciones", models.TextField(blank=True))], options={"ordering": ["nombre"], "verbose_name": "geriátrico", "verbose_name_plural": "geriátricos"}),
    ]
