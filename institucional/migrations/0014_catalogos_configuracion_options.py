from django.db import migrations


class Migration(migrations.Migration):
    dependencies = [("institucional", "0013_configuracion_publica")]
    operations = [
        migrations.AlterModelOptions(name="obrasocial", options={"ordering": ["nombre"], "verbose_name": "obra social / prepaga", "verbose_name_plural": "obras sociales / prepagas"}),
        migrations.AlterModelOptions(name="mediopagoconfiguracion", options={"ordering": ["nombre"], "verbose_name": "medio de pago", "verbose_name_plural": "medios de pago"}),
        migrations.AlterModelOptions(name="porcentajeactualizacion", options={"ordering": ["porcentaje"], "verbose_name": "porcentaje de actualización", "verbose_name_plural": "porcentajes de actualización"}),
    ]
