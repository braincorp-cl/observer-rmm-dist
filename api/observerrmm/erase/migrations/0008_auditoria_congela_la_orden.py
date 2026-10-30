"""El hash de la auditoría deja de colgar de una FK anulable (053 · cierre).

🔴 `EraseAuditRecord.canonical_content()` hashea `order_id`, y esa FK es
`SET_NULL`. El `SET_NULL` salva la fila cuando se borra la orden —que es su
propósito— pero al anularse la referencia el `record_hash` guardado **deja de
recomputar**: la fila se lee como ADULTERADA. Un trámite administrativo
corriente producía exactamente la señal con la que el módulo denuncia
manipulación, y desde ahí dejaba de poder distinguirse de una adulteración real.
Verificado con dos hashes distintos antes y después de borrar la orden.

🔒 El backfill copia `order_id` en `order_pk`, así que **el valor que entra al
hash es el mismo entero de siempre** y los certificados y auditorías YA EMITIDOS
siguen verificando. Esa es la razón de que la columna sea un entero y no un texto
congelado al molde de `CustodyEvent.intake_process_id`: un texto habría
serializado `"5"` donde antes iba `5`, invalidando toda la cadena histórica.

⚠️ Lo que este backfill NO puede reparar: una fila cuya orden ya se borró tiene
`order_id` en NULL y no hay de dónde recuperar el entero. Su hash ya estaba roto
y seguirá roto. La migración las cuenta y lo dice en la salida en vez de dejarlo
pasar: si aparecen, hay que decidir si se re-anclan o se dejan con constancia.
"""

from django.db import migrations, models


def congelar_la_orden(apps, schema_editor):
    EraseAuditRecord = apps.get_model("erase", "EraseAuditRecord")

    migradas = EraseAuditRecord.objects.filter(order_id__isnull=False).update(
        order_pk=models.F("order_id")
    )
    huerfanas = EraseAuditRecord.objects.filter(order_id__isnull=True).count()

    print(f"\n    auditorías con orden viva, congeladas: {migradas}")
    if huerfanas:
        print(
            f"    🔴 {huerfanas} fila(s) con la orden YA borrada: su hash quedó "
            "roto antes de esta migración y no se puede recomputar."
        )
    else:
        print("    ✅ ninguna fila tenía la orden borrada: el histórico queda íntegro.")


def revertir(apps, schema_editor):
    """Nada que deshacer: quitar la columna la borra con el `RemoveField`."""


class Migration(migrations.Migration):

    dependencies = [
        ("erase", "0007_certificado_sobrevive_al_cliente"),
    ]

    operations = [
        migrations.AddField(
            model_name="eraseauditrecord",
            name="order_pk",
            field=models.PositiveIntegerField(blank=True, editable=False, null=True),
        ),
        migrations.RunPython(congelar_la_orden, revertir),
    ]
