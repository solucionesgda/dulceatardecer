from decimal import Decimal
from django.core.validators import MinValueValidator, RegexValidator
from django.db import migrations, models
import django.db.models.deletion


class Migration(migrations.Migration):
    dependencies = [("institucional", "0007_residente_validaciones_dni_afiliado")]

    operations = [
        migrations.CreateModel(
            name="Pago",
            fields=[
                ("id", models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name="ID")),
                ("periodo", models.CharField(max_length=7, validators=[RegexValidator("^\\d{4}-(0[1-9]|1[0-2])$", "El período debe tener el formato AAAA-MM.")])),
                ("concepto", models.CharField(max_length=150)),
                ("monto", models.DecimalField(decimal_places=2, max_digits=12, validators=[MinValueValidator(Decimal("0.01"))])),
                ("fecha_vencimiento", models.DateField()),
                ("fecha_pago", models.DateField(blank=True, null=True)),
                ("estado", models.CharField(choices=[("Pendiente", "Pendiente"), ("Pagado", "Pagado"), ("Vencido", "Vencido")], default="Pendiente", editable=False, max_length=10)),
                ("medio_pago", models.CharField(blank=True, choices=[("Efectivo", "Efectivo"), ("Transferencia", "Transferencia"), ("Débito automático", "Débito automático"), ("Cheque", "Cheque")], max_length=30)),
                ("observaciones", models.TextField(blank=True)),
                ("residente", models.ForeignKey(on_delete=django.db.models.deletion.PROTECT, related_name="pagos", to="institucional.residente")),
            ],
            options={"ordering": ["-periodo", "residente__apellido", "residente__nombre"], "verbose_name": "pago", "verbose_name_plural": "pagos"},
        ),
    ]
