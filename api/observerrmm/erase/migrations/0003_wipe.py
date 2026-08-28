import django.db.models.deletion
from django.db import migrations, models


class Migration(migrations.Migration):
    """Feature 043 · wipe (A2). Extiende WipeOrder (verificación por relectura) y
    agrega la plantilla de rutas. No toca la cadena inmutable (C/D)."""

    dependencies = [
        ("clients", "0025_site_latitude_site_longitude"),
        ("erase", "0002_fileretrieval"),
    ]

    operations = [
        migrations.AddField(
            model_name="wipeorder",
            name="verified",
            field=models.BooleanField(blank=True, null=True),
        ),
        migrations.AddField(
            model_name="wipeorder",
            name="method_applied",
            field=models.CharField(blank=True, default="", max_length=64),
        ),
        migrations.AlterField(
            model_name="wipeorder",
            name="status",
            field=models.CharField(
                choices=[
                    ("draft", "Borrador"),
                    ("pending_confirmation", "Pendiente de segunda confirmación"),
                    ("confirmed", "Confirmada"),
                    ("recovery_window", "En ventana de arrepentimiento"),
                    ("dispatched", "Despachada al equipo"),
                    ("cancelled", "Cancelada"),
                    ("executed", "Ejecutada"),
                    ("incomplete", "Ejecutada sin verificación (incompleta)"),
                    ("failed", "Fallida"),
                ],
                default="draft",
                max_length=32,
            ),
        ),
        migrations.CreateModel(
            name="WipePathTemplate",
            fields=[
                (
                    "id",
                    models.BigAutoField(
                        auto_created=True,
                        primary_key=True,
                        serialize=False,
                        verbose_name="ID",
                    ),
                ),
                ("name", models.CharField(max_length=255)),
                (
                    "os_scope",
                    models.CharField(
                        choices=[
                            ("windows", "Windows"),
                            ("linux", "Linux"),
                            ("macos", "macOS"),
                            ("any", "Cualquiera"),
                        ],
                        default="any",
                        max_length=16,
                    ),
                ),
                ("paths", models.JSONField(blank=True, default=list)),
                ("created_by", models.CharField(blank=True, default="", max_length=255)),
                ("created_at", models.DateTimeField(auto_now_add=True)),
                (
                    "client",
                    models.ForeignKey(
                        on_delete=django.db.models.deletion.CASCADE,
                        related_name="wipe_path_templates",
                        to="clients.client",
                    ),
                ),
                (
                    "site",
                    models.ForeignKey(
                        blank=True,
                        null=True,
                        on_delete=django.db.models.deletion.SET_NULL,
                        related_name="wipe_path_templates",
                        to="clients.site",
                    ),
                ),
            ],
            options={
                "ordering": ["client_id", "name"],
            },
        ),
    ]
