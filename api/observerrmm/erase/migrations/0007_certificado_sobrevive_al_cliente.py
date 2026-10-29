from django.db import migrations, models
import django.db.models.deletion


class Migration(migrations.Migration):
    """El certificado sobrevive al borrado de su cliente (deuda A003).

    `EraseCertificate.client` era `CASCADE` desde la feature 039: borrar un
    cliente eliminaba sus certificados **sin disparar `ImmutableRecordError`**,
    porque el collector de Django borra en bloque y no llama a `Model.delete()`.
    Evidencia permanente destruida en silencio por una operación administrativa
    corriente. Verificado antes de corregirlo: sobrevivían 0.

    🔒 Esta migración **no toca el contenido** de la tabla: solo afloja el `NOT
    NULL` de una columna FK. Ni `data`, ni `document_hash`, ni `canonical_bytes`,
    así que los certificados ya emitidos siguen verificando — el test del hash
    congelado y el del esquema lo vigilan.

    El certificado no queda sin identidad: `tenant` guarda el nombre del cliente,
    viaja dentro del documento firmado y entra en `canonical_content`.
    """

    dependencies = [
        ("clients", "0026_client_site_activity_monitoring"),
        ("erase", "0006_custodia"),
    ]

    operations = [
        migrations.AlterField(
            model_name="erasecertificate",
            name="client",
            field=models.ForeignKey(
                blank=True,
                null=True,
                on_delete=django.db.models.deletion.SET_NULL,
                related_name="erase_certificates",
                to="clients.client",
            ),
        ),
    ]
