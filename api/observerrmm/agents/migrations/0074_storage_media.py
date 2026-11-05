"""Feature 055 · inventario de medios de almacenamiento.

Crea las dos tablas que guardan QUÉ MEDIO hay dentro de cada equipo y qué
categoría del estándar de sanitización es alcanzable sobre él.

Alcance de esta migración, y lo que deliberadamente NO hace:

* **No toca ninguna tabla existente.** Ni `agents_agent`, ni las tablas de
  cifrado de la 037, ni nada de `erase`. Los campos del certificado que esta
  feature llena ya existen en el documento y no son columnas.
* **No hay `RunPython` ni backfill.** La ausencia de fila es el estado «sin
  dato», y crear filas por adelantado convertiría «no sabemos» en un veredicto.
  Un agente que todavía no manda el bloque simplemente no tiene fila.
* **No hay tabla de historial.** A diferencia del estado de cifrado, que cambia
  solo, el hardware de un equipo no cambia salvo intervención física: una fila
  por latido sería ruido, no auditoría.

Los `choices` van literales y no importando el enum, igual que en `0066`: una
migración tiene que seguir aplicándose aunque el enum de hoy se reescriba.
"""

from django.db import migrations, models
import django.db.models.deletion


class Migration(migrations.Migration):
    dependencies = [
        ("agents", "0073_activity_049e"),
    ]

    operations = [
        migrations.CreateModel(
            name="StorageMediaState",
            fields=[
                (
                    "id",
                    models.AutoField(
                        auto_created=True,
                        primary_key=True,
                        serialize=False,
                        verbose_name="ID",
                    ),
                ),
                ("supported", models.BooleanField(default=True)),
                ("query_error", models.TextField(blank=True, null=True)),
                ("capabilities_probed", models.BooleanField(default=False)),
                ("measured_at", models.DateTimeField()),
                (
                    "agent",
                    models.OneToOneField(
                        on_delete=django.db.models.deletion.CASCADE,
                        related_name="storage_media",
                        to="agents.agent",
                    ),
                ),
            ],
        ),
        migrations.CreateModel(
            name="StorageMedium",
            fields=[
                (
                    "id",
                    models.AutoField(
                        auto_created=True,
                        primary_key=True,
                        serialize=False,
                        verbose_name="ID",
                    ),
                ),
                ("pnp_device_id", models.CharField(max_length=512)),
                (
                    "device_index",
                    models.PositiveSmallIntegerField(blank=True, null=True),
                ),
                ("model", models.CharField(blank=True, default="", max_length=255)),
                (
                    "manufacturer",
                    models.CharField(blank=True, default="", max_length=255),
                ),
                (
                    "serial_number",
                    models.CharField(blank=True, default="", max_length=255),
                ),
                (
                    "firmware_revision",
                    models.CharField(blank=True, default="", max_length=64),
                ),
                ("size_bytes", models.BigIntegerField(blank=True, null=True)),
                ("bus_type", models.PositiveSmallIntegerField(blank=True, null=True)),
                (
                    "media_type_code",
                    models.PositiveSmallIntegerField(blank=True, null=True),
                ),
                ("spindle_speed", models.BigIntegerField(blank=True, null=True)),
                ("is_system_disk", models.BooleanField(default=False)),
                ("is_virtual", models.BooleanField(default=False)),
                ("removable", models.BooleanField(default=False)),
                (
                    "self_encrypting",
                    models.PositiveSmallIntegerField(blank=True, null=True),
                ),
                ("sanitize_capabilities", models.JSONField(blank=True, null=True)),
                ("measured_at", models.DateTimeField()),
                (
                    "agent",
                    models.ForeignKey(
                        on_delete=django.db.models.deletion.CASCADE,
                        related_name="storage_media_devices",
                        to="agents.agent",
                    ),
                ),
            ],
            options={
                "unique_together": {("agent", "pnp_device_id")},
            },
        ),
        migrations.AddIndex(
            model_name="storagemedium",
            index=models.Index(
                fields=["is_system_disk", "media_type_code"],
                name="agents_stor_is_syst_e916f9_idx",
            ),
        ),
    ]
