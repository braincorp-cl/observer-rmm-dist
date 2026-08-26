import uuid

import django.db.models.deletion
from django.db import migrations, models

import agents.lostmode_storage
import erase.models


class Migration(migrations.Migration):

    dependencies = [
        ("clients", "0025_site_latitude_site_longitude"),
        ("agents", "0068_agent_outside_geofence"),
        ("erase", "0001_initial"),
    ]

    operations = [
        migrations.CreateModel(
            name="FileRetrievalOrder",
            fields=[
                (
                    "id",
                    models.UUIDField(
                        default=uuid.uuid4,
                        editable=False,
                        primary_key=True,
                        serialize=False,
                    ),
                ),
                ("agent_id_snapshot", models.CharField(blank=True, default="", max_length=255)),
                ("agent_hostname", models.CharField(blank=True, default="", max_length=255)),
                ("agent_serial", models.CharField(blank=True, default="", max_length=255)),
                ("paths", models.JSONField(blank=True, default=list)),
                ("dry_run", models.BooleanField(default=False)),
                ("lost_mode_cycle", models.PositiveIntegerField(blank=True, null=True)),
                ("size_limit_bytes", models.PositiveBigIntegerField(default=0)),
                ("file_limit", models.PositiveIntegerField(default=0)),
                (
                    "status",
                    models.CharField(
                        choices=[
                            ("pending", "Pendiente de despacho / en cola"),
                            ("dispatched", "Despachada al equipo"),
                            ("uploading", "Subiendo archivos"),
                            ("done", "Completada"),
                            ("expired", "Expirada (equipo no reconectó a tiempo)"),
                            ("cancelled", "Cancelada"),
                            ("failed", "Fallida"),
                        ],
                        default="pending",
                        max_length=32,
                    ),
                ),
                ("requested_by", models.CharField(max_length=255)),
                ("requested_at", models.DateTimeField(auto_now_add=True)),
                ("dispatched_at", models.DateTimeField(blank=True, null=True)),
                ("completed_at", models.DateTimeField(blank=True, null=True)),
                ("cancelled_by", models.CharField(blank=True, default="", max_length=255)),
                ("cancelled_at", models.DateTimeField(blank=True, null=True)),
                ("expires_at", models.DateTimeField(blank=True, null=True)),
                ("result", models.JSONField(blank=True, null=True)),
                ("failure_reason", models.CharField(blank=True, default="", max_length=255)),
                (
                    "agent",
                    models.ForeignKey(
                        blank=True,
                        null=True,
                        on_delete=django.db.models.deletion.SET_NULL,
                        related_name="fileretrieval_orders",
                        to="agents.agent",
                    ),
                ),
                (
                    "client",
                    models.ForeignKey(
                        on_delete=django.db.models.deletion.CASCADE,
                        related_name="fileretrieval_orders",
                        to="clients.client",
                    ),
                ),
                (
                    "site",
                    models.ForeignKey(
                        blank=True,
                        null=True,
                        on_delete=django.db.models.deletion.SET_NULL,
                        related_name="fileretrieval_orders",
                        to="clients.site",
                    ),
                ),
            ],
            options={
                "ordering": ["-requested_at"],
            },
        ),
        migrations.CreateModel(
            name="RetrievedFile",
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
                ("source_path", models.TextField(blank=True, default="")),
                (
                    "asset",
                    models.FileField(
                        blank=True,
                        null=True,
                        storage=agents.lostmode_storage.get_lost_mode_evidence_fs,
                        upload_to=erase.models.retrieval_file_path,
                    ),
                ),
                ("size", models.PositiveBigIntegerField(default=0)),
                ("uploaded_at", models.DateTimeField(auto_now_add=True)),
                (
                    "order",
                    models.ForeignKey(
                        on_delete=django.db.models.deletion.CASCADE,
                        related_name="files",
                        to="erase.fileretrievalorder",
                    ),
                ),
            ],
            options={
                "ordering": ["id"],
            },
        ),
        migrations.AddIndex(
            model_name="fileretrievalorder",
            index=models.Index(
                fields=["status", "expires_at"],
                name="fr_order_status_expires_idx",
            ),
        ),
        migrations.AddIndex(
            model_name="fileretrievalorder",
            index=models.Index(
                fields=["lost_mode_cycle"],
                name="fr_order_lostcycle_idx",
            ),
        ),
        migrations.AddConstraint(
            model_name="retrievedfile",
            constraint=models.UniqueConstraint(
                fields=("order", "source_path"),
                name="uniq_retrieved_file_per_order_path",
            ),
        ),
    ]
