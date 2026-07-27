from datetime import date
from decimal import Decimal

from django.conf import settings
from django.core.validators import MinValueValidator
from django.db import migrations, models
import django.db.models.deletion


class Migration(migrations.Migration):
    dependencies = [
        ("institucional", "0009_montos_mensuales_y_abonos"),
        migrations.swappable_dependency(settings.AUTH_USER_MODEL),
    ]

    operations = [
        migrations.AddField(
            model_name="pagoparcial",
            name="usuario",
            field=models.ForeignKey(blank=True, null=True, on_delete=django.db.models.deletion.SET_NULL, related_name="abonos_registrados", to=settings.AUTH_USER_MODEL),
        ),
        migrations.CreateModel(
            name="CajaMovimiento",
            fields=[
                ("id", models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name="ID")),
                ("fecha", models.DateField(default=date.today)),
                ("tipo", models.CharField(choices=[("Ingreso", "Ingreso"), ("Egreso", "Egreso")], max_length=10)),
                ("categoria", models.CharField(blank=True, max_length=100)),
                ("descripcion", models.CharField(blank=True, max_length=255)),
                ("importe", models.DecimalField(decimal_places=2, max_digits=12, validators=[MinValueValidator(Decimal("0.01"))])),
                ("medio_pago", models.CharField(blank=True, choices=[("Efectivo", "Efectivo"), ("Transferencia", "Transferencia"), ("Débito automático", "Débito automático"), ("Cheque", "Cheque")], max_length=30)),
                ("observaciones", models.TextField(blank=True)),
                ("abono", models.OneToOneField(blank=True, null=True, on_delete=django.db.models.deletion.PROTECT, related_name="movimiento_caja", to="institucional.pagoparcial")),
                ("geriatrico", models.ForeignKey(on_delete=django.db.models.deletion.PROTECT, related_name="movimientos_caja", to="institucional.geriatrico")),
                ("pago", models.ForeignKey(blank=True, null=True, on_delete=django.db.models.deletion.PROTECT, related_name="movimientos_caja", to="institucional.pago")),
                ("residente", models.ForeignKey(blank=True, null=True, on_delete=django.db.models.deletion.PROTECT, related_name="movimientos_caja", to="institucional.residente")),
                ("usuario", models.ForeignKey(blank=True, null=True, on_delete=django.db.models.deletion.SET_NULL, related_name="movimientos_caja", to=settings.AUTH_USER_MODEL)),
            ],
            options={"ordering": ["-fecha", "-pk"], "verbose_name": "movimiento de caja", "verbose_name_plural": "movimientos de caja"},
        ),
    ]
