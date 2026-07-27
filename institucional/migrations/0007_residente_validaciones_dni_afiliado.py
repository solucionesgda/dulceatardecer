from django.core.validators import RegexValidator
from django.db import migrations, models


class Migration(migrations.Migration):
    dependencies = [("institucional", "0006_residente_validaciones_afiliado_contacto")]

    operations = [
        migrations.AlterField(
            model_name="residente",
            name="dni",
            field=models.CharField(max_length=8, unique=True, validators=[RegexValidator("^\\d{8}$", "El DNI debe contener exactamente 8 números.")]),
        ),
        migrations.AlterField(
            model_name="residente",
            name="numero_afiliado",
            field=models.CharField(blank=True, max_length=100, validators=[RegexValidator("^\\d+$", "El número de afiliado debe contener solo números.")]),
        ),
    ]
