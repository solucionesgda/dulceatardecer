from django.core.validators import RegexValidator
from django.db import migrations, models
import django.db.models.deletion


class Migration(migrations.Migration):
    dependencies = [("institucional", "0003_remove_geriatrico_capacidad_camas")]

    operations = [
        migrations.RemoveConstraint(model_name="geriatrico", name="ocupacion_no_supera_capacidad"),
        migrations.RemoveField(model_name="geriatrico", name="camas_ocupadas"),
        migrations.CreateModel(
            name="Residente",
            fields=[
                ("id", models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name="ID")),
                ("nombre", models.CharField(max_length=100)),
                ("apellido", models.CharField(max_length=100)),
                ("dni", models.CharField(max_length=20, unique=True)),
                ("fecha_nacimiento", models.DateField(blank=True, null=True)),
                ("fecha_ingreso", models.DateField()),
                ("habitacion", models.CharField(blank=True, max_length=100)),
                ("obra_social", models.CharField(blank=True, max_length=100)),
                ("numero_afiliado", models.CharField(blank=True, max_length=100)),
                ("contacto_familiar", models.CharField(max_length=150)),
                ("email_contacto", models.EmailField(blank=True, max_length=254)),
                ("telefono", models.CharField(blank=True, max_length=30, validators=[RegexValidator("^\\d+$", "El teléfono solo puede contener números.")])),
                ("medico_tratante", models.CharField(blank=True, max_length=150)),
                ("diagnostico_principal", models.TextField(blank=True)),
                ("movilidad", models.CharField(choices=[("Independiente", "Independiente"), ("Asistida", "Asistida"), ("Silla de ruedas", "Silla de ruedas"), ("Rehabilitación", "Rehabilitación")], default="Independiente", max_length=30)),
                ("observaciones", models.TextField(blank=True)),
                ("estado", models.CharField(choices=[("Activo", "Activo"), ("Alta", "Alta"), ("Traslado", "Traslado"), ("Fallecido", "Fallecido")], default="Activo", max_length=20)),
                ("geriatrico", models.ForeignKey(on_delete=django.db.models.deletion.PROTECT, related_name="residentes", to="institucional.geriatrico")),
            ],
            options={"ordering": ["apellido", "nombre"], "verbose_name": "residente", "verbose_name_plural": "residentes"},
        ),
    ]
