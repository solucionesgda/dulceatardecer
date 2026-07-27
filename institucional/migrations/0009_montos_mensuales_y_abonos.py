from datetime import date
from decimal import Decimal

from django.core.validators import MinValueValidator
from django.db import migrations, models
import django.db.models.deletion


def crear_abonos_historicos(apps, schema_editor):
    Pago = apps.get_model("institucional", "Pago")
    PagoParcial = apps.get_model("institucional", "PagoParcial")
    for pago in Pago.objects.exclude(fecha_pago__isnull=True):
        if not PagoParcial.objects.filter(pago_id=pago.pk).exists():
            PagoParcial.objects.create(
                pago_id=pago.pk,
                monto=pago.monto,
                fecha_pago=pago.fecha_pago,
                medio_pago=pago.medio_pago,
                observaciones=pago.observaciones,
            )


class Migration(migrations.Migration):
    dependencies = [("institucional", "0008_pago")]

    operations = [
        migrations.AddField(
            model_name="residente",
            name="monto_mensual",
            field=models.DecimalField(blank=True, decimal_places=2, max_digits=12, null=True, validators=[MinValueValidator(Decimal("0.01"))]),
        ),
        migrations.CreateModel(
            name="PagoParcial",
            fields=[
                ("id", models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name="ID")),
                ("monto", models.DecimalField(decimal_places=2, max_digits=12, validators=[MinValueValidator(Decimal("0.01"))])),
                ("fecha_pago", models.DateField(default=date.today)),
                ("medio_pago", models.CharField(blank=True, choices=[("Efectivo", "Efectivo"), ("Transferencia", "Transferencia"), ("Débito automático", "Débito automático"), ("Cheque", "Cheque")], max_length=30)),
                ("observaciones", models.TextField(blank=True)),
                ("pago", models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, related_name="abonos", to="institucional.pago")),
            ],
            options={"ordering": ["fecha_pago", "pk"], "verbose_name": "abono", "verbose_name_plural": "abonos"},
        ),
        migrations.RunPython(crear_abonos_historicos, migrations.RunPython.noop),
        migrations.AlterField(
            model_name="pago",
            name="estado",
            field=models.CharField(choices=[("Pendiente", "Pendiente"), ("Parcial", "Parcial"), ("Pagado", "Pagado"), ("Vencido", "Vencido")], default="Pendiente", editable=False, max_length=10),
        ),
        migrations.AddConstraint(
            model_name="pago",
            constraint=models.UniqueConstraint(fields=("residente", "periodo"), name="pago_unico_por_residente_y_periodo"),
        ),
    ]
