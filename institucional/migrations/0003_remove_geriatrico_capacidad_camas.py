from django.db import migrations


class Migration(migrations.Migration):
    dependencies = [("institucional", "0002_geriatrico_capacidad_total_y_ocupacion")]

    operations = [
        migrations.RemoveField(
            model_name="geriatrico",
            name="capacidad_camas",
        ),
    ]
