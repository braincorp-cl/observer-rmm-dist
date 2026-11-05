import django.db.models.deletion
from django.db import migrations, models

import agents.lostmode_storage
import erase.models


class Migration(migrations.Migration):
    """Feature 053 · ola 1. Apéndice C de NIST SP 800-88 Rev. 2 y ancla doble.

    Alcance, en tres bloques:

    1. `AssetIntake` gana fabricante, modelo y destino final del medio: el mínimo
       del Apéndice C que el certificado no podía declarar porque el dato no se
       capturaba en ninguna parte.
    2. `WipeOrder` y `FileRetrievalOrder` ganan `intake`, el segundo expediente
       del que puede colgar una orden (RF-12), más el snapshot de fabricante y
       modelo en la orden de wipe (RF-04), que sobrevive al des-enrolamiento.
    3. `DestructionEvidence`, tabla propia para el adjunto que acredita una
       destrucción física (L-03), separada del certificado a propósito para que
       la retención pueda purgarla sin tocar un documento inmutable (L-04).

    NO toca `erase_erasecertificate` ni `erase_eraseauditrecord`: ni una columna,
    ni un `RunPython`, ni un `UPDATE` sobre `data`. Es justamente lo que mantiene
    verificables los certificados v1 ya emitidos, cuya firma se recomputa sobre
    el `data` almacenado tal cual.
    """

    dependencies = [
        ("erase", "0004_alter_retrievedfile_id"),
    ]

    operations = [
        # --- 1. Apéndice C en el acta de ingreso -------------------------------
        migrations.AddField(
            model_name="assetintake",
            name="equipment_make",
            field=models.CharField(blank=True, default="", max_length=255),
        ),
        migrations.AddField(
            model_name="assetintake",
            name="equipment_model",
            field=models.CharField(blank=True, default="", max_length=255),
        ),
        migrations.AddField(
            model_name="assetintake",
            name="media_disposition",
            field=models.CharField(
                blank=True,
                choices=[
                    ("internal_reuse", "Reutilización interna"),
                    ("external_reuse", "Reutilización externa o donación"),
                    ("returned", "Devuelto al propietario o arrendador"),
                    ("recycled", "Reciclaje por gestor autorizado"),
                    ("destroyed", "Destruido físicamente"),
                    ("retained", "Retenido en custodia"),
                    ("other", "Otro (ver detalle)"),
                ],
                default="",
                max_length=32,
            ),
        ),
        migrations.AddField(
            model_name="assetintake",
            name="media_disposition_detail",
            field=models.CharField(blank=True, default="", max_length=255),
        ),
        # --- 2. Ancla doble y snapshot del modelo ------------------------------
        migrations.AddField(
            model_name="wipeorder",
            name="agent_make_model",
            field=models.CharField(blank=True, default="", max_length=255),
        ),
        migrations.AddField(
            model_name="wipeorder",
            name="intake",
            field=models.ForeignKey(
                blank=True,
                null=True,
                on_delete=django.db.models.deletion.SET_NULL,
                related_name="wipe_orders",
                to="erase.assetintake",
            ),
        ),
        migrations.AddField(
            model_name="fileretrievalorder",
            name="intake",
            field=models.ForeignKey(
                blank=True,
                null=True,
                on_delete=django.db.models.deletion.SET_NULL,
                related_name="fileretrieval_orders",
                to="erase.assetintake",
            ),
        ),
        # --- 3. Evidencia de destrucción física, purgable ----------------------
        migrations.CreateModel(
            name="DestructionEvidence",
            fields=[
                # `AutoField`, no `BigAutoField`: el proyecto no fija
                # DEFAULT_AUTO_FIELD, asi que Django usa el default historico.
                # Escribirlo ancho es exactamente el desliz que la 043 tuvo que
                # corregir con `0004_alter_retrievedfile_id`.
                (
                    "id",
                    models.AutoField(
                        auto_created=True,
                        primary_key=True,
                        serialize=False,
                        verbose_name="ID",
                    ),
                ),
                (
                    "asset",
                    models.FileField(
                        blank=True,
                        null=True,
                        storage=agents.lostmode_storage.get_lost_mode_evidence_fs,
                        upload_to=erase.models.destruction_evidence_path,
                    ),
                ),
                (
                    "original_name",
                    models.CharField(blank=True, default="", max_length=255),
                ),
                ("size", models.PositiveBigIntegerField(default=0)),
                ("sha256", models.CharField(blank=True, default="", max_length=64)),
                (
                    "uploaded_by",
                    models.CharField(blank=True, default="", max_length=255),
                ),
                ("uploaded_at", models.DateTimeField(auto_now_add=True)),
                (
                    "intake",
                    models.ForeignKey(
                        on_delete=django.db.models.deletion.CASCADE,
                        related_name="destruction_evidence",
                        to="erase.assetintake",
                    ),
                ),
            ],
            options={
                "ordering": ["id"],
            },
        ),
    ]
