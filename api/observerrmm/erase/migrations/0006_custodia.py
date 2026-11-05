import django.db.models.deletion
from django.db import migrations, models


class Migration(migrations.Migration):
    """Feature 053 · ola 2. Cadena de custodia por eventos y tipo de medio.

    Alcance, aditivo en todo:

    1. `CustodyEvent`, tabla nueva: un eslabón append-only y encadenado por cada
       cosa que le pasa al activo entre el acta y el certificado (RF-06). Cadena
       propia, porque `ImmutableChainRecord` es abstracta y cada subclase busca
       su eslabón anterior en su propia tabla.
    2. `AssetIntake` gana `media_type`, el campo del mínimo del Apéndice C que la
       ola 1 no emitió (RF-09). El *origen* del medio no es columna: se compone
       del acta al emitir el certificado.
    3. Dos índices, para que la reconciliación (RF-07) no haga seq scan sobre
       decenas de miles de actas y la línea de tiempo de un activo no recorra
       toda la cadena: `(client, created_at)` en el acta, `(intake, id)` en el
       evento.

    🔴 La FK del evento al acta es `SET_NULL`, no `CASCADE`. Un `CASCADE` no pasa
    por `Model.delete()` —el collector de Django borra en bloque— y eliminaría
    eslabones append-only sin disparar `ImmutableRecordError`, dejando la cadena
    con el `prev_hash` descolgado. Por eso el evento lleva la identidad del
    expediente denormalizada: un eslabón huérfano sigue valiendo.

    NO toca `erase_erasecertificate` ni `erase_eraseauditrecord`, igual que la
    0005: es lo que mantiene verificables los certificados v1 y v2 ya emitidos.
    """

    dependencies = [
        ("erase", "0005_appendix_c_y_ancla"),
    ]

    operations = [
        migrations.CreateModel(
            name="CustodyEvent",
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
                ("created_at", models.DateTimeField(editable=False)),
                (
                    "prev_hash",
                    models.CharField(
                        blank=True, default="", editable=False, max_length=64
                    ),
                ),
                (
                    "record_hash",
                    models.CharField(editable=False, max_length=64, unique=True),
                ),
                (
                    "intake_process_id",
                    models.CharField(blank=True, default="", max_length=64),
                ),
                (
                    "equipment_serial",
                    models.CharField(blank=True, default="", max_length=255),
                ),
                (
                    "kind",
                    models.CharField(
                        choices=[
                            ("received", "Recibido en custodia"),
                            ("relocated", "Trasladado"),
                            ("stored", "Almacenado a la espera de disposición"),
                            ("handed_to_processor", "Enviado a gestor externo"),
                            ("sanitized", "Medio saneado"),
                            ("destroyed", "Destruido físicamente"),
                            ("returned", "Devuelto a su propietario o arrendador"),
                        ],
                        max_length=32,
                    ),
                ),
                ("at", models.DateTimeField()),
                ("actor", models.CharField(blank=True, default="", max_length=255)),
                ("location", models.CharField(blank=True, default="", max_length=255)),
                ("detail", models.JSONField(blank=True, default=dict)),
            ],
            options={
                "ordering": ["id"],
            },
        ),
        migrations.AddField(
            model_name="assetintake",
            name="media_type",
            field=models.CharField(
                blank=True,
                choices=[
                    ("hdd", "Disco magnético (HDD)"),
                    ("ssd", "Estado sólido (SSD)"),
                    ("nvme", "Estado sólido NVMe"),
                    ("optical", "Óptico (CD/DVD/Blu-ray)"),
                    ("tape", "Cinta magnética"),
                    ("mobile", "Dispositivo móvil"),
                    ("other", "Otro"),
                ],
                default="",
                max_length=32,
            ),
        ),
        migrations.AddIndex(
            model_name="assetintake",
            index=models.Index(
                fields=["client", "created_at"], name="erase_intake_client_idx"
            ),
        ),
        migrations.AddField(
            model_name="custodyevent",
            name="intake",
            field=models.ForeignKey(
                blank=True,
                null=True,
                on_delete=django.db.models.deletion.SET_NULL,
                related_name="custody_events",
                to="erase.assetintake",
            ),
        ),
        migrations.AddIndex(
            model_name="custodyevent",
            index=models.Index(
                fields=["intake", "id"], name="erase_custody_intake_idx"
            ),
        ),
    ]
