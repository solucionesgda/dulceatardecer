from django.core.validators import RegexValidator
from django.db import migrations, models


class Migration(migrations.Migration):
    dependencies = [("institucional", "0005_residente_cobertura_otra")]

    operations = [
        migrations.AlterField(
            model_name="residente",
            name="contacto_familiar",
            field=models.CharField(max_length=150, validators=[RegexValidator("^\\d+$", "Ingrese únicamente números.")]),
        ),
        migrations.AlterField(
            model_name="residente",
            name="numero_afiliado",
            field=models.CharField(blank=True, max_length=100, validators=[RegexValidator("^[A-Za-z0-9-]+$", "El número de afiliado solo puede contener letras, números y guiones.")]),
        ),
    ]
