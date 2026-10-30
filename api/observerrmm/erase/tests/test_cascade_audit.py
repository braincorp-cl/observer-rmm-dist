"""Auditoría de TODAS las rutas de borrado que pueden alcanzar una tabla append-only.

`EraseCertificate`, `EraseAuditRecord` y `CustodyEvent` heredan de
`ImmutableChainRecord`: son prueba legal y no se modifican ni se borran. La guarda
vive en `Model.save()` y `Model.delete()`.

🔴 El defecto que motiva este archivo: **un `on_delete=CASCADE` en una FK que
apunta a esas tablas las borra SIN disparar `ImmutableRecordError`**. El collector
de Django borra en bloque y NO llama al `delete()` de cada hijo, así que no hay
excepción, no hay log y la prueba legal desaparece en silencio durante una
operación administrativa corriente. Ya pasó: `EraseCertificate.client` era
`CASCADE` y borrar un cliente dejaba 0 certificados (corregido en la migración
`erase/0007`); `CustodyEvent.intake` nació `SET_NULL` por lo mismo.

De ahí la forma de los tests de este archivo, que es lo que importa entender:

  🔑 **se cuentan filas.** `assertRaises(ImmutableRecordError)` NO sirve para esto,
  porque el defecto es justamente que la excepción no se lanza. Un test que sólo
  espera la excepción pasa en verde mientras la evidencia se destruye. Lo único
  que lo detecta es el delta de filas antes/después del borrado.

  🔑 **cada borrado se acredita.** Un "delta 0" es trivial si el borrado nunca
  ocurrió (la punta no existía, un `RESTRICT` lo frenó, el filtro no tocó nada).
  Por eso todo test de delta 0 afirma ADEMÁS que las filas MUTABLES vecinas sí se
  fueron y que las FK quedaron en NULL: eso prueba que la cascada corrió de
  verdad y pasó por al lado de la tabla append-only sin llevársela.

Dos capas, porque ninguna alcanza sola:

- **Capa 1, el grafo** (`GrafoDeCascadaTests`): recorre el metadata de Django y el
  `information_schema` de PostgreSQL. No depende de que alguien se acuerde de
  escribir un test por cada FK nueva: si mañana aparece un `CASCADE` en cualquier
  app —a uno, dos o tres saltos— falla sin que nadie lo haya previsto. Es la que
  cubre la cascada transitiva, que es la que nadie ve.

- **Capa 2, el borrado real** (`RutasDeBorradoPorPuntaTests`): borra la punta de
  cada ruta (un `Client`, un `Site`, un `Agent`, un `User`, una `WipeOrder`, un
  `AssetIntake`) y cuenta. El grafo prueba la intención declarada; esto prueba lo
  que la base hace.

Resultado de la auditoría (2026-10-30): las 7 aristas FK que entran a las tres
tablas son `SET_NULL` y **ninguna ruta de cascada las alcanza**. Cada `SET_NULL`
es el único salto que sostiene la garantía; dar vuelta uno solo destruye evidencia
permanente, y por eso los siete quedan fijados acá uno por uno.

Lo que la auditoría SÍ encontró abierto, documentado acá sin corregir porque toca
esquema o es decisión de otros, no defectos a tapar en un test:

1. 🟠 `EraseAuditRecord.canonical_content()` hashea `order_id`, que es una FK
   `SET_NULL`. El `SET_NULL` salva la fila del borrado y, en el mismo movimiento,
   le rompe la verificación: su `record_hash` guardado deja de recomputar. La
   evidencia queda en pie pero se lee como adulterada, que es justo la señal que
   debía delatar una adulteración real (`HashAtadoAUnaFkAnulableTests`).
2. 🔴 `QuerySet.delete()` directo sobre una append-only: `ImmutableChainRecord`
   sobrecarga `Model.delete()` pero no el del queryset, así que ese camino borra
   evidencia sin disparar nada (`RutasQueSiBorranTests`).
3. 🟡 `LostModeEvidence.agent` en `CASCADE` (`agents/models.py:1504`), contra el
   plazo de retención propio de ADR-025 (`LostModeEvidenceCascadaTests`).

Ninguno de los tres es una cascada de FK que alcance una tabla append-only: de
esas no quedó ninguna. Son los agujeros del costado.
"""

import pytest
from django.apps import apps
from django.db import connection, models
from django.db.models.deletion import CASCADE, RestrictedError
from django.utils import timezone
from model_bakery import baker

from accounts.models import User
from agents.models import LostModeEvidence
from clients.models import Client, Site
from erase.models import (
    AssetIntake,
    CertificateKind,
    CustodyEvent,
    CustodyEventKind,
    EraseAction,
    EraseAuditRecord,
    EraseCertificate,
    ImmutableChainRecord,
    WipeOrder,
    WipePathTemplate,
)
from observerrmm.constants import LostModeEvidenceKind
from observerrmm.test import ObserverTestCase

# Las tres tablas append-only. Se derivan de `ImmutableChainRecord` y NO se
# escriben a mano: si mañana nace una cuarta cadena, entra sola a la auditoría.
APPEND_ONLY = (EraseAuditRecord, EraseCertificate, CustodyEvent)

# Censo de las aristas FK que ENTRAN a una tabla append-only, con su `on_delete`.
# Es el inventario auditado el 2026-10-30 y está fijado a propósito: sin él, el
# recorrido del grafo pasaría en verde el día que el descubrimiento de modelos se
# rompa y no encuentre nada que revisar (un test que no mira nada no falla nunca).
# Agregar una FK a una tabla append-only DEBE romper este test: es el momento
# exacto en que alguien tiene que decidir, a conciencia, qué pasa al borrar el
# padre.
ARISTAS_AUDITADAS = frozenset(
    {
        ("erase.EraseAuditRecord", "order", "erase.WipeOrder", "SET_NULL"),
        ("erase.EraseCertificate", "order", "erase.WipeOrder", "SET_NULL"),
        ("erase.EraseCertificate", "intake", "erase.AssetIntake", "SET_NULL"),
        ("erase.EraseCertificate", "client", "clients.Client", "SET_NULL"),
        ("erase.EraseCertificate", "site", "clients.Site", "SET_NULL"),
        ("erase.EraseCertificate", "agent", "agents.Agent", "SET_NULL"),
        ("erase.CustodyEvent", "intake", "erase.AssetIntake", "SET_NULL"),
    }
)


def _nombre_on_delete(campo):
    accion = campo.remote_field.on_delete
    return getattr(accion, "__name__", type(accion).__name__)


def _fks_concretas(modelo):
    """FK y O2O declaradas EN `modelo` (no las inversas).

    La dirección importa y es el centro de toda la auditoría: `on_delete` se
    declara en el HIJO y gobierna qué le pasa al hijo cuando se borra el PADRE.
    Entonces lo único que puede borrar una fila append-only por cascada son las
    FK declaradas sobre la propia tabla append-only. Las FK que apuntan HACIA
    ella se llevarían al apuntador, nunca la fila.
    """
    for campo in modelo._meta.get_fields():
        if not isinstance(campo, (models.ForeignKey, models.OneToOneField)):
            continue
        if campo.auto_created or not getattr(campo, "remote_field", None):
            continue
        yield campo


def _censo_aristas():
    """Las aristas FK entrantes a cada tabla append-only, derivadas del metadata."""
    return {
        (
            modelo._meta.label,
            campo.name,
            campo.remote_field.model._meta.label,
            _nombre_on_delete(campo),
        )
        for modelo in apps.get_models()
        if issubclass(modelo, ImmutableChainRecord)
        for campo in _fks_concretas(modelo)
    }


def _aristas_cascade():
    """Las aristas `CASCADE` que entran a una tabla append-only. Vacío = sano."""
    return [
        f"{modelo._meta.label}.{campo.name} -> "
        f"{campo.remote_field.model._meta.label}"
        for modelo in apps.get_models()
        if issubclass(modelo, ImmutableChainRecord)
        for campo in _fks_concretas(modelo)
        if campo.remote_field.on_delete is CASCADE
    ]


def _rutas_de_cascada():
    """Toda ruta `raíz --CASCADE--> ... --CASCADE--> append-only`. Vacío = sano.

    Sube desde cada tabla append-only por sus FK `CASCADE` hacia los padres, y de
    ahí recursivamente a quien borra a esos padres: una ruta de dos o tres saltos
    cuenta igual que una directa, porque el collector de Django las recorre
    completas en una sola operación.
    """
    entrantes = {}
    for modelo in apps.get_models():
        for campo in _fks_concretas(modelo):
            entrantes.setdefault(modelo._meta.label, []).append(
                (campo.remote_field.model._meta.label, campo)
            )

    rutas = []

    def subir(actual, camino):
        for padre, campo in entrantes.get(actual, []):
            if campo.remote_field.on_delete is not CASCADE or padre in camino:
                continue
            rutas.append(" --CASCADE--> ".join([padre] + camino))
            subir(padre, [padre] + camino)

    for modelo in APPEND_ONLY:
        subir(modelo._meta.label, [modelo._meta.label])
    return rutas


class CensoMixin:
    """Contar filas append-only, que es la única medición que detecta el defecto."""

    def censo(self):
        # `_base_manager` y no `objects`: `EraseCertificate.objects` es un
        # `EraseQuerySet` y el manager por omisión de un modelo puede filtrar. Lo
        # que se audita es la TABLA, no lo que un rol alcanza a ver.
        return {m.__name__: m._base_manager.count() for m in APPEND_ONLY}

    def assertDeltaCero(self, antes, que_se_borro, pobladas=None):
        """Delta 0 en las tres tablas, más la prueba de que se midió algo.

        `pobladas` son las cadenas que el fixture del test llenó y que por lo
        tanto TIENEN que seguir con filas al final. Sin esa segunda mitad, un
        censo de ceros haría pasar cualquier delta 0 sin medir nada: es el modo
        exacto en que un test de este tipo se vuelve decorativo.
        """
        despues = self.censo()
        self.assertEqual(
            despues,
            antes,
            f"{que_se_borro} se llevó filas append-only por arrastre: "
            f"{antes} -> {despues}. Es el defecto que esta auditoría persigue: "
            "la cascada NO pasa por Model.delete(), así que no hubo excepción.",
        )
        esperadas = [m.__name__ for m in APPEND_ONLY] if pobladas is None else pobladas
        vacias = [n for n in esperadas if despues[n] == 0]
        self.assertEqual(
            vacias,
            [],
            f"El censo de {vacias} quedó vacío ({despues}): el test no está "
            "midiendo nada.",
        )


class GrafoDeCascadaTests(CensoMixin, ObserverTestCase):
    """Capa 1: la auditoría del grafo, que no depende de acordarse de nada.

    Un test por ruta cubre las rutas que alguien pensó. Esto cubre las que no:
    recorre el metadata completo del proyecto, así que una cascada de dos o tres
    saltos nacida en otra app aparece acá sin que nadie la haya previsto.
    """

    def test_el_censo_de_aristas_es_el_auditado(self):
        """Control negativo del recorrido: fija QUÉ se está mirando.

        Sin esto, los tests de abajo pasarían en verde recorriendo un conjunto
        vacío el día que el descubrimiento de subclases deje de funcionar.
        """
        self.assertEqual(
            _censo_aristas(),
            set(ARISTAS_AUDITADAS),
            "Cambió el conjunto de FK que entran a una tabla append-only. No es "
            "un test que se actualice y siga: hay que DECIDIR qué pasa al borrar "
            "el padre de la arista nueva, y sólo `SET_NULL` conserva la "
            "evidencia.",
        )

    def test_las_tres_cadenas_estan_en_la_auditoria(self):
        """Si naciera una cuarta cadena append-only, entra sola a la auditoría."""
        descubiertas = {
            m._meta.label
            for m in apps.get_models()
            if issubclass(m, ImmutableChainRecord)
        }
        self.assertEqual(
            descubiertas,
            {m._meta.label for m in APPEND_ONLY},
            "Apareció o desapareció una cadena append-only.",
        )

    def test_ninguna_fk_entrante_a_una_append_only_es_cascade(self):
        """El corazón de la auditoría: ni una sola arista `CASCADE`.

        Dar vuelta cualquiera de estos `SET_NULL` destruye evidencia permanente
        en silencio, y el modelo no tiene forma de defenderse: la guarda de
        `Model.delete()` no se ejecuta en una cascada.
        """
        culpables = _aristas_cascade()
        self.assertEqual(
            culpables,
            [],
            "FK con CASCADE sobre una tabla append-only: borrar el padre se "
            f"lleva la evidencia sin excepción ni rastro -> {culpables}. "
            "Corresponde SET_NULL + identidad denormalizada en columnas propias.",
        )

    def test_ninguna_ruta_de_cascada_multisalto_alcanza_una_append_only(self):
        """La cascada transitiva, que es la que nadie ve.

        Sube desde cada tabla append-only por sus FK `CASCADE` hacia los padres, y
        de ahí recursivamente a quien borra a esos padres. Una ruta de dos o tres
        saltos cuenta igual que una directa: el collector de Django la recorre
        completa en una sola operación.
        """
        rutas = _rutas_de_cascada()
        self.assertEqual(
            rutas,
            [],
            f"Hay rutas de cascada que terminan en una tabla append-only: {rutas}",
        )

    def test_el_recorrido_detecta_un_cascade_inyectado(self):
        """🔑 El test que prueba que los dos de arriba sirven de algo.

        Un test-guarda que no puede fallar es peor que no tener ninguno: da la
        tranquilidad sin la cobertura, y nadie lo revisa de nuevo porque está en
        verde. Los dos tests anteriores afirman "no hay ninguna arista CASCADE", y
        esa aserción pasa idéntica si el recorrido está roto y no mira nada.

        Así que acá se inyecta justamente el defecto histórico —`
        EraseCertificate.client` en `CASCADE`, lo que destruyó certificados de
        verdad— y se exige que AMBOS detectores lo vean: el de aristas directas y
        el de rutas multisalto, que además tiene que reconstruir la ruta larga
        `clients.Client --CASCADE--> erase.EraseCertificate`.

        Se restaura en `finally` sí o sí: el `on_delete` vive en el metadata del
        modelo, que es estado de proceso y compartido con el resto de la sesión de
        tests.
        """
        campo = EraseCertificate._meta.get_field("client")
        original = campo.remote_field.on_delete

        self.assertEqual(_aristas_cascade(), [], "El punto de partida no está sano.")
        try:
            campo.remote_field.on_delete = CASCADE

            self.assertEqual(
                _aristas_cascade(),
                ["erase.EraseCertificate.client -> clients.Client"],
                "El detector de aristas directas NO vio el CASCADE inyectado: "
                "los tests de arriba están pasando sin mirar nada.",
            )
            self.assertIn(
                "clients.Client --CASCADE--> erase.EraseCertificate",
                _rutas_de_cascada(),
                "El detector de rutas NO reconstruyó la ruta del CASCADE " "inyectado.",
            )
        finally:
            campo.remote_field.on_delete = original

        # Y el metadata quedó como estaba, para los demás tests de la sesión.
        self.assertIs(campo.remote_field.on_delete, original)
        self.assertEqual(_aristas_cascade(), [])

    def test_la_base_de_datos_no_cascadea_por_su_cuenta(self):
        """Django cascadea en Python; la base tiene que quedarse quieta.

        El metadata de Django no vería un `ON DELETE CASCADE` puesto a mano en una
        migración con `RunSQL`, y ese borrado no pasaría ni por el collector ni
        por `Model.delete()`: sería invisible para todo lo demás de este archivo.
        """
        tablas = [m._meta.db_table for m in APPEND_ONLY]
        with connection.cursor() as cursor:
            cursor.execute(
                """
                SELECT tc.table_name, kcu.column_name, rc.delete_rule
                FROM information_schema.table_constraints tc
                JOIN information_schema.key_column_usage kcu
                  ON tc.constraint_name = kcu.constraint_name
                JOIN information_schema.referential_constraints rc
                  ON tc.constraint_name = rc.constraint_name
                WHERE tc.constraint_type = 'FOREIGN KEY'
                  AND tc.table_name = ANY(%s)
                ORDER BY 1, 2
                """,
                [tablas],
            )
            reglas = cursor.fetchall()

        # Control: que la consulta haya encontrado las 7 restricciones. Si no
        # devuelve nada, el test no está mirando la base.
        self.assertEqual(
            len(reglas),
            len(ARISTAS_AUDITADAS),
            f"Se esperaban {len(ARISTAS_AUDITADAS)} FK en la base, se vieron "
            f"{len(reglas)}: {reglas}",
        )
        cascadeando = [r for r in reglas if r[2] != "NO ACTION"]
        self.assertEqual(
            cascadeando,
            [],
            f"La base cascadea sola sobre una tabla append-only: {cascadeando}",
        )


class RutasDeBorradoPorPuntaTests(CensoMixin, ObserverTestCase):
    """Capa 2: borrar la punta de cada ruta y contar filas.

    El grafo prueba la intención declarada en los modelos; esto prueba lo que la
    base hace de verdad cuando alguien borra un cliente.

    El fixture cablea las SIETE aristas auditadas a la vez (cliente, sitio,
    agente, acta y orden, todos poblados), así que cada borrado de punta recorre
    todas las rutas que lo alcanzan en una sola operación.
    """

    def setUp(self):
        self.authenticate()
        self.setup_coresettings()

        self.cliente = baker.make("clients.Client", name="Cliente Auditoría")
        self.sitio = baker.make("clients.Site", client=self.cliente, name="Sitio Aud")
        self.agente = baker.make(
            "agents.Agent", site=self.sitio, hostname="EQ-AUD-1", agent_id="aid-aud-1"
        )

        self.acta = AssetIntake.objects.create(
            process_id="OE-IN-AUD-1",
            client=self.cliente,
            site=self.sitio,
            agent=self.agente,
            equipment_serial="SN-AUD-1",
            received_by="bodega",
        )
        self.orden = WipeOrder.objects.create(
            client=self.cliente,
            site=self.sitio,
            agent=self.agente,
            intake=self.acta,
            action=EraseAction.WIPE,
            agent_hostname="EQ-AUD-1",
            ordered_by="john",
        )
        # Una fila por cadena, con TODAS sus FK pobladas.
        self.auditoria = EraseAuditRecord.objects.create(
            order=self.orden,
            agent_id="aid-aud-1",
            hostname="EQ-AUD-1",
            event="created",
            actor="john",
        )
        self.certificado = EraseCertificate.objects.create(
            certificate_id="CERT-AUD-1",
            kind=CertificateKind.PHYSICAL_DESTRUCTION,
            order=self.orden,
            intake=self.acta,
            client=self.cliente,
            site=self.sitio,
            agent=self.agente,
            tenant="Cliente Auditoría",
            asset_tag="AT-AUD-1",
            data={"proceso": "OE-IN-AUD-1"},
            document_hash="d" * 64,
        )
        self.eslabon = CustodyEvent.objects.create(
            intake=self.acta,
            intake_process_id="OE-IN-AUD-1",
            equipment_serial="SN-AUD-1",
            kind=CustodyEventKind.RECEIVED,
            at=timezone.now(),
            actor="bodega",
        )

    # --- punta: Client (2 saltos por AssetIntake, WipeOrder y Site) ---

    def test_el_restrict_del_agente_frena_el_borrado_del_cliente(self):
        """`Agent.site` es `RESTRICT`: un cliente con equipos no se borra.

        Es la primera defensa de la ruta `Client -> Site -> Agent` y conviene
        dejarla fijada, porque explica por qué los tests que siguen tienen que
        dar de baja el agente antes: no es una comodidad del fixture, es que la
        operación real está bloqueada.
        """
        antes = self.censo()
        with self.assertRaises(RestrictedError):
            self.cliente.delete()
        self.assertDeltaCero(antes, "El borrado frenado del cliente")
        # Y el cliente sigue ahí: el RESTRICT abortó la transacción completa.
        self.assertEqual(Client.objects.filter(pk=self.cliente.pk).count(), 1)

    def test_borrar_el_cliente_no_borra_ninguna_fila_append_only(self):
        """La ruta larga, de dos saltos, y la que destruyó evidencia de verdad.

        `Client` cascadea a `AssetIntake`, a `WipeOrder`, a `WipePathTemplate` y a
        `Site`; las tres tablas append-only cuelgan de esos cuatro. El corte está
        en el segundo salto, y es un `SET_NULL` por arista.
        """
        baker.make("erase.WipePathTemplate", client=self.cliente, name="Plantilla Aud")
        antes = self.censo()
        self.agente.delete()  # el RESTRICT de arriba

        self.cliente.delete()

        self.assertDeltaCero(antes, "Borrar el cliente")

        # 🔑 Acreditar que la cascada CORRIÓ: sin esto, el delta 0 sería trivial.
        self.assertEqual(Client.objects.filter(pk=self.cliente.pk).count(), 0)
        self.assertEqual(Site.objects.filter(pk=self.sitio.pk).count(), 0)
        self.assertEqual(AssetIntake.objects.filter(pk=self.acta.pk).count(), 0)
        self.assertEqual(WipeOrder.objects.filter(pk=self.orden.pk).count(), 0)
        self.assertEqual(WipePathTemplate.objects.count(), 0)

        # Las filas quedaron huérfanas, no borradas: eso es lo que hace el corte.
        self.auditoria.refresh_from_db()
        self.certificado.refresh_from_db()
        self.eslabon.refresh_from_db()
        self.assertIsNone(self.auditoria.order_id)
        self.assertIsNone(self.certificado.client_id)
        self.assertIsNone(self.certificado.site_id)
        self.assertIsNone(self.certificado.intake_id)
        self.assertIsNone(self.certificado.order_id)
        self.assertIsNone(self.eslabon.intake_id)

        # Y huérfanas siguen sirviendo: la identidad está denormalizada en
        # columnas propias, que es la mitad que hace viable el SET_NULL.
        self.assertEqual(self.certificado.tenant, "Cliente Auditoría")
        self.assertEqual(self.auditoria.hostname, "EQ-AUD-1")
        self.assertEqual(self.eslabon.intake_process_id, "OE-IN-AUD-1")

        # Y la cadena de hash sigue verificando: nada se borró en medio.
        # 🟠 Sólo dos de las tres: `EraseAuditRecord` NO vuelve a verificar
        # después de este borrado, y no por una fila faltante sino porque su
        # `canonical_content()` hashea `order_id`, que el `SET_NULL` acaba de
        # anular. Es un hallazgo de esta auditoría y tiene su propio test en
        # `HashAtadoAUnaFkAnulableTests`.
        for fila in (self.certificado, self.eslabon):
            self.assertEqual(
                fila.compute_record_hash(fila.prev_hash),
                fila.record_hash,
                f"{type(fila).__name__} dejó de verificar tras el borrado.",
            )

    def test_borrar_el_cliente_en_bloque_por_queryset_tampoco_las_borra(self):
        """El mismo borrado por `QuerySet.delete()`, que es otro camino de código.

        Es el que toma una acción masiva del admin o una migración de datos, y no
        pasa por `BaseAuditModel.delete()` de cada fila. El collector es el mismo,
        pero vale fijarlo: es la forma en que este borrado ocurre en producción.
        """
        antes = self.censo()
        self.agente.delete()

        Client.objects.filter(pk=self.cliente.pk).delete()

        self.assertDeltaCero(antes, "Borrar el cliente en bloque")
        self.assertEqual(Client.objects.filter(pk=self.cliente.pk).count(), 0)
        self.assertEqual(AssetIntake.objects.filter(pk=self.acta.pk).count(), 0)

    # --- punta: Site ---

    def test_borrar_el_sitio_no_borra_ninguna_fila_append_only(self):
        """`EraseCertificate.site` a un salto; `AssetIntake.site` y
        `WipeOrder.site` también son `SET_NULL`, así que el acta y la orden
        sobreviven al sitio."""
        antes = self.censo()
        self.agente.delete()

        self.sitio.delete()

        self.assertDeltaCero(antes, "Borrar el sitio")
        self.assertEqual(Site.objects.filter(pk=self.sitio.pk).count(), 0)
        self.certificado.refresh_from_db()
        self.assertIsNone(self.certificado.site_id)
        # El acta NO cuelga del sitio: sigue viva con el sitio en NULL.
        self.acta.refresh_from_db()
        self.assertIsNone(self.acta.site_id)

    # --- punta: Agent ---

    def test_borrar_el_agente_no_borra_ninguna_fila_append_only(self):
        """Un equipo se da de baja todo el tiempo; es el borrado más corriente.

        `Agent` cascadea a 31 modelos. Ninguno es append-only: el certificado se
        queda con `agent` en NULL y la identidad del equipo en sus columnas.
        """
        antes = self.censo()

        self.agente.delete()

        self.assertDeltaCero(antes, "Borrar el agente")
        self.certificado.refresh_from_db()
        self.assertIsNone(self.certificado.agent_id)
        # La identidad del equipo no se fue con la FK.
        self.assertEqual(self.auditoria.hostname, "EQ-AUD-1")
        self.assertEqual(self.auditoria.agent_id, "aid-aud-1")
        # Acta y orden tampoco: su FK al agente también es SET_NULL.
        self.acta.refresh_from_db()
        self.orden.refresh_from_db()
        self.assertIsNone(self.acta.agent_id)
        self.assertIsNone(self.orden.agent_id)

    # --- punta: User ---

    def test_borrar_el_usuario_no_borra_ninguna_fila_append_only(self):
        """Ninguna tabla append-only tiene FK a `User`, y es deliberado.

        El actor se guarda como TEXTO (`EraseAuditRecord.actor`,
        `CustodyEvent.actor`, `WipeOrder.ordered_by`) justamente para que la traza
        sobreviva a que la cuenta se elimine. Una FK ahí —de cualquier tipo—
        acoplaría la evidencia al ciclo de vida de las cuentas.
        """
        antes = self.censo()

        User.objects.filter(username="john").delete()

        self.assertDeltaCero(antes, "Borrar el usuario")
        self.assertEqual(User.objects.filter(username="john").count(), 0)
        # El actor sigue nombrado en la evidencia.
        self.auditoria.refresh_from_db()
        self.assertEqual(self.auditoria.actor, "john")

    # --- punta: WipeOrder ---

    def test_borrar_la_orden_de_wipe_no_borra_ninguna_fila_append_only(self):
        """`WipeOrder` es MUTABLE y se borra; la auditoría de sus transiciones no.

        Es el salto intermedio de la ruta del cliente, y se prueba también
        directo: borrar la orden a mano tiene que dejar la auditoría completa.
        """
        antes = self.censo()

        self.orden.delete()

        self.assertDeltaCero(antes, "Borrar la orden de wipe")
        self.assertEqual(WipeOrder.objects.filter(pk=self.orden.pk).count(), 0)
        self.auditoria.refresh_from_db()
        self.certificado.refresh_from_db()
        self.assertIsNone(self.auditoria.order_id)
        self.assertIsNone(self.certificado.order_id)
        self.assertEqual(self.auditoria.event, "created")

    # --- punta: AssetIntake ---

    def test_borrar_el_acta_no_borra_ninguna_fila_append_only(self):
        """El acta se lleva su evidencia purgable (`DestructionEvidence`), no la
        cadena de custodia ni el certificado.

        Es la distinción de L-04 y se ve acá: el adjunto de 4 MB es purgable, el
        documento que lo citó es permanente y guarda su hash.
        """
        baker.make("erase.DestructionEvidence", intake=self.acta, sha256="e" * 64)
        antes = self.censo()

        self.acta.delete()

        self.assertDeltaCero(antes, "Borrar el acta")
        self.assertEqual(AssetIntake.objects.filter(pk=self.acta.pk).count(), 0)
        self.eslabon.refresh_from_db()
        self.certificado.refresh_from_db()
        self.assertIsNone(self.eslabon.intake_id)
        self.assertIsNone(self.certificado.intake_id)
        self.assertEqual(self.eslabon.equipment_serial, "SN-AUD-1")

    # --- la guarda de instancia, que es la que SÍ funciona ---

    def test_la_guarda_de_instancia_sigue_en_pie_en_las_tres_cadenas(self):
        """Control: la protección que sí funciona no se perdió por el camino.

        Se afirma junto a los conteos a propósito: es el contraste que explica por
        qué los demás tests cuentan filas en vez de esperar la excepción.
        """
        from erase.models import ImmutableRecordError

        for fila in (self.auditoria, self.certificado, self.eslabon):
            with self.assertRaises(ImmutableRecordError):
                fila.delete()
            self.assertEqual(
                type(fila)._base_manager.filter(pk=fila.pk).count(),
                1,
                f"{type(fila).__name__} se borró pese a la guarda.",
            )


class RutasQueSiBorranTests(CensoMixin, ObserverTestCase):
    """Las rutas que SÍ borran una fila append-only, documentadas sin corregir.

    No son cascadas de FK: ninguna la alcanza. Son los dos agujeros que quedan, y
    los dos son decisión de diseño pendiente, no defectos para tapar en un test.
    Estos tests FIJAN el comportamiento actual: si alguien agrega la guarda, fallan
    —y eso es correcto, porque el comportamiento habrá cambiado y la decisión
    quedó tomada.
    """

    def setUp(self):
        self.authenticate()
        self.setup_coresettings()
        self.cliente = baker.make("clients.Client", name="Cliente Hueco")

    def test_el_delete_de_queryset_elude_la_guarda_append_only(self):
        """🔴 `QuerySet.delete()` borra la evidencia sin disparar nada.

        `ImmutableChainRecord` sobrecarga `Model.delete()`, pero NO
        `QuerySet.delete()`, que es otro camino de código: un
        `EraseCertificate.objects.filter(...).delete()` en un shell, una tarea o
        una migración de datos se lleva la fila en silencio. Es el MISMO mecanismo
        del defecto que motiva este archivo —el borrado en bloque no pasa por
        `Model.delete()`— sólo que invocado a mano en vez de por una FK.

        Propuesta (no aplicada, no toca el esquema): un manager propio con
        `QuerySet.delete()` sobrecargado que lance `ImmutableRecordError`, igual
        que la guarda de instancia, y que la purga de adjuntos (D5) siga usando su
        propio camino porque borra archivos, nunca filas. Queda fuera de esta
        tarea: cambia una API pública del modelo y merece su propia decisión.
        """
        cert = EraseCertificate.objects.create(
            certificate_id="CERT-HUECO-1",
            kind=CertificateKind.PHYSICAL_DESTRUCTION,
            client=self.cliente,
            tenant="Cliente Hueco",
            data={"x": 1},
            document_hash="f" * 64,
        )

        borradas, _ = EraseCertificate.objects.filter(pk=cert.pk).delete()

        self.assertEqual(borradas, 1)
        self.assertEqual(
            EraseCertificate._base_manager.filter(pk=cert.pk).count(),
            0,
            "Si esto falla, se agregó la guarda de QuerySet: actualizar el test "
            "y cerrar la propuesta del docstring.",
        )


class HashAtadoAUnaFkAnulableTests(CensoMixin, ObserverTestCase):
    """🟠 Hallazgo de esta auditoría: el `SET_NULL` salva la fila y le rompe la prueba.

    `EraseAuditRecord.canonical_content()` hashea `order_id`, que es una FK
    `SET_NULL`. Entonces borrar la `WipeOrder` —o el `Client` que la arrastra— deja
    la fila en pie, que es lo que la auditoría de cascada buscaba, pero su
    `record_hash` guardado YA NO RECOMPUTA: el contenido canónico cambió debajo.

    Y acá está lo que lo vuelve serio, porque no es un detalle cosmético: el
    criterio de verificación de todo el módulo es «si el hash no recomputa, la fila
    fue manipulada» (`verify_certificate`, `verify_custody_chain`, y el docstring de
    `ImmutableChainRecord`: "un borrado intermedio rompe la continuidad y queda en
    evidencia"). Un borrado administrativo corriente produce exactamente esa
    señal. Queda una fila de evidencia legal que se lee como adulterada sin que
    nadie la haya tocado, y —peor— deja de poder distinguirse de una adulteración
    real: la señal que debía delatar el fraude la dispara el trámite.

    Las otras dos cadenas NO tienen el problema, y la diferencia es precisamente
    la lección del hallazgo:

      - `EraseCertificate.canonical_content()` hashea `tenant` (texto), no
        `client_id`.
      - `CustodyEvent.canonical_content()` hashea `intake_process_id` (texto), no
        `intake_id`.

    O sea: la identidad denormalizada que hace sobrevivir a la fila huérfana es la
    MISMA que hay que hashear. `EraseAuditRecord` ya la tiene (`agent_id`,
    `hostname`) y la hashea; lo que sobra es el `order_id` crudo al lado.

    Propuesta (NO aplicada — no se toca el modelo ni se escribe migración):

      1. Sacar `order_id` del `canonical_content()` de `EraseAuditRecord` y
         reemplazarlo por una referencia DENORMALIZADA e inmutable de la orden
         —un `order_ref` de texto con el identificador de la orden, congelado al
         insertar, al molde de `CustodyEvent.intake_process_id`—. La FK sigue
         existiendo para navegar; lo que entra al hash es el texto.
      2. La FK se queda en `SET_NULL`: el hallazgo no la cuestiona, la completa.

    El costo y por qué es decisión de otros, no de esta tarea: cambiar
    `canonical_content()` cambia el hash de las filas YA EMITIDAS, así que la
    cadena histórica deja de recomputar con el código nuevo. Hace falta decidir
    cómo se versiona el contenido canónico (un `hash_version` en la fila, o
    recomputar y re-anclar la cadena dejando constancia). Eso es esquema y
    migración, que esta tarea no entrega.
    """

    def setUp(self):
        self.authenticate()
        self.setup_coresettings()
        self.cliente = baker.make("clients.Client", name="Cliente Hash")
        self.orden = WipeOrder.objects.create(
            client=self.cliente,
            action=EraseAction.WIPE,
            agent_hostname="EQ-HASH",
            ordered_by="john",
        )

    def _auditoria(self):
        return EraseAuditRecord.objects.create(
            order=self.orden,
            agent_id="aid-hash",
            hostname="EQ-HASH",
            event="created",
            actor="john",
        )

    def test_el_cascade_rompe_la_verificacion_del_audit_record(self):
        """La medición del hallazgo: la fila queda, la prueba no.

        Fija el comportamiento de HOY. Si falla, se aplicó la propuesta del
        docstring de la clase y hay que cerrarla acá.
        """
        rec = self._auditoria()
        self.assertEqual(rec.compute_record_hash(rec.prev_hash), rec.record_hash)
        antes = self.censo()
        order_id_original = self.orden.pk

        self.cliente.delete()  # arrastra la orden por CASCADE

        # La fila sobrevivió: la auditoría de cascada hace su trabajo.
        self.assertDeltaCero(
            antes,
            "Borrar el cliente (hallazgo del hash)",
            pobladas=("EraseAuditRecord",),
        )
        rec.refresh_from_db()
        self.assertIsNone(rec.order_id)

        # 🟠 Pero su hash ya no recomputa, sin que nadie haya tocado la fila.
        self.assertNotEqual(
            rec.compute_record_hash(rec.prev_hash),
            rec.record_hash,
            "El hash volvió a recomputar: se aplicó la propuesta de sacar "
            "`order_id` del contenido canónico. Cerrar el hallazgo.",
        )

        # Y la causa es exactamente `order_id`, no otra cosa: devolviéndolo en
        # memoria, la fila verifica de nuevo. Sin este control, el test sólo
        # diría "algo cambió".
        rec.order_id = order_id_original
        self.assertEqual(
            rec.compute_record_hash(rec.prev_hash),
            rec.record_hash,
            "La ruptura no viene de `order_id`: hay otra causa que investigar.",
        )

    def test_las_otras_dos_cadenas_no_hashean_una_fk(self):
        """El contraste que señala el arreglo: ellas hashean la identidad, no la FK."""
        cert = EraseCertificate.objects.create(
            certificate_id="CERT-HASH-1",
            kind=CertificateKind.PHYSICAL_DESTRUCTION,
            order=self.orden,
            client=self.cliente,
            tenant="Cliente Hash",
            data={"x": 1},
            document_hash="b" * 64,
        )
        acta = AssetIntake.objects.create(
            process_id="OE-IN-HASH",
            client=self.cliente,
            equipment_serial="SN-HASH",
            received_by="bodega",
        )
        eslabon = CustodyEvent.objects.create(
            intake=acta,
            intake_process_id="OE-IN-HASH",
            equipment_serial="SN-HASH",
            kind=CustodyEventKind.RECEIVED,
            at=timezone.now(),
            actor="bodega",
        )
        # Ninguna FK de las dos entra al contenido canónico.
        self.assertNotIn("order_id", cert.canonical_content())
        self.assertNotIn("client_id", cert.canonical_content())
        self.assertNotIn("intake_id", eslabon.canonical_content())
        # Y por eso sobreviven al borrado VERIFICANDO, no sólo existiendo.
        self.cliente.delete()
        cert.refresh_from_db()
        eslabon.refresh_from_db()
        self.assertIsNone(cert.client_id)
        self.assertIsNone(eslabon.intake_id)
        self.assertEqual(cert.compute_record_hash(cert.prev_hash), cert.record_hash)
        self.assertEqual(
            eslabon.compute_record_hash(eslabon.prev_hash), eslabon.record_hash
        )

    @pytest.mark.xfail(
        strict=True,
        reason=(
            "Hallazgo abierto: EraseAuditRecord.canonical_content() hashea "
            "`order_id`, una FK SET_NULL, así que un borrado administrativo "
            "corriente deja la fila sin poder verificarse. El arreglo cambia el "
            "hash de las filas ya emitidas y necesita versionar el contenido "
            "canónico: es esquema y migración, fuera del alcance de esta "
            "auditoría. Ver el docstring de HashAtadoAUnaFkAnulableTests."
        ),
    )
    def test_el_contenido_canonico_no_depende_de_ninguna_fk_anulable(self):
        """El invariante CORRECTO, afirmado como tal y marcado fallo esperado.

        Se afirma en genérico sobre las tres cadenas a propósito: así cubre la
        cuarta que nazca mañana. Un `record_hash` sólo puede cubrir columnas que
        una cascada no pueda mover; si cubre una FK anulable, el `SET_NULL` que
        protege la fila le arruina la prueba.

        Está como `xfail(strict=True)` y no como aserción invertida porque esto NO
        es comportamiento a bendecir: es un defecto que esta tarea tiene prohibido
        arreglar (toca esquema). En `strict`, el día que alguien lo arregle este
        test pasa a verde y el `xfail` falla, que es el aviso de que hay que
        cerrar el hallazgo.
        """
        atados = []
        for modelo in APPEND_ONLY:
            anulables = {
                campo.attname for campo in _fks_concretas(modelo) if campo.null
            }
            # `canonical_content()` se inspecciona sobre una instancia vacía: las
            # claves no dependen de los valores.
            claves = set(modelo().canonical_content().keys())
            for attname in sorted(anulables & claves):
                atados.append(f"{modelo._meta.label}.canonical_content()[{attname}]")

        self.assertEqual(
            atados,
            [],
            "El contenido canónico depende de una FK anulable: un SET_NULL deja "
            f"la fila sin poder verificarse -> {atados}. Corresponde hashear la "
            "identidad denormalizada (texto congelado al insertar), no el id.",
        )


class LostModeEvidenceCascadaTests(CensoMixin, ObserverTestCase):
    """🟡 `LostModeEvidence.agent` está en `CASCADE` (`agents/models.py:1504`).

    NO se toca: la decisión es de otros. Lo que aporta este archivo es el análisis
    y la medición.

    Lo que pasa: `LostModeEvidence` NO hereda de `ImmutableChainRecord` —es un
    modelo corriente— así que dar de baja un agente se lleva su evidencia del modo
    perdido de inmediato. No hay excepción ni rastro, por el mismo motivo de
    siempre: la cascada no pasa por `Model.delete()`.

    La tensión: ADR-025 le da a esa evidencia un PLAZO DE RETENCIÓN PROPIO, y el
    propio modelo explica por qué duplica los puntos de `CheckHistory` (para no
    depender de una perilla de monitoreo). Pero el `CASCADE` la hace depender de
    algo más frágil todavía: que nadie dé de baja el equipo. Y dar de baja el
    equipo es exactamente lo que se hace cuando un caso de robo se cierra, que es
    cuando la evidencia recién empieza a importar.

    Las dos lecturas, y ninguna es obvia:

    - `CASCADE` es correcto si la evidencia es un ANEXO OPERATIVO del equipo: sin
      equipo no hay caso, y conservarla sería guardar capturas de pantalla y
      ubicaciones —dato personal de quien usaba el equipo— sin sujeto al cual
      referirlas. Minimización de datos a favor.
    - `CASCADE` es incorrecto si la evidencia es PRUEBA, como la trata ADR-025 al
      darle plazo propio. Entonces el plazo manda sobre el ciclo de vida del
      inventario, y borrar el agente antes del vencimiento destruye prueba de un
      delito que probablemente siga abierto.

    Si se decide que es prueba, la forma del arreglo es la ya probada acá:
    `SET_NULL` + identidad denormalizada (`agent_hostname`, `agent_serial`, el
    `agent_id` como texto), al molde de `EraseAuditRecord.agent_id`/`hostname`,
    más una purga por vencimiento que sí borre —`prune_lost_mode_evidence` ya
    existe y es el lugar—. Una pieza huérfana sin hostname no sirve de prueba, así
    que el `SET_NULL` solo no alcanza: van juntos o no van.

    Lo que sí queda fijado abajo, porque es la garantía que esta auditoría cubre:
    este `CASCADE` no toca ninguna tabla append-only.
    """

    def setUp(self):
        self.authenticate()
        self.setup_coresettings()
        self.cliente = baker.make("clients.Client", name="Cliente Perdido")
        self.sitio = baker.make("clients.Site", client=self.cliente)
        self.agente = baker.make(
            "agents.Agent", site=self.sitio, hostname="EQ-PERDIDO", agent_id="aid-lost"
        )
        self.certificado = EraseCertificate.objects.create(
            certificate_id="CERT-PERDIDO-1",
            kind=CertificateKind.REMOTE_DESTRUCTION,
            client=self.cliente,
            agent=self.agente,
            tenant="Cliente Perdido",
            data={"x": 1},
            document_hash="a" * 64,
        )
        self.auditoria = EraseAuditRecord.objects.create(
            agent_id="aid-lost", hostname="EQ-PERDIDO", event="created", actor="john"
        )
        self.eslabon = CustodyEvent.objects.create(
            intake_process_id="OE-IN-PERDIDO",
            equipment_serial="SN-PERDIDO",
            kind=CustodyEventKind.RECEIVED,
            at=timezone.now(),
            actor="bodega",
        )
        self.pieza = LostModeEvidence.objects.create(
            agent=self.agente,
            cycle=1,
            kind=LostModeEvidenceKind.GEO,
            lat=-33.45,
            lng=-70.66,
            accuracy_m=12,
            source="native",
        )

    def test_borrar_el_agente_se_lleva_la_evidencia_del_modo_perdido(self):
        """Medición del caso 🟡, sin juicio: el `CASCADE` borra, hoy, en silencio.

        Si esto falla, se cambió el `on_delete` y la decisión pendiente se tomó:
        actualizar el test con el criterio nuevo.
        """
        self.assertEqual(LostModeEvidence.objects.filter(pk=self.pieza.pk).count(), 1)

        self.agente.delete()

        self.assertEqual(
            LostModeEvidence.objects.filter(pk=self.pieza.pk).count(),
            0,
            "El CASCADE de LostModeEvidence.agent ya no borra: se tomó la "
            "decisión de ADR-025 y hay que actualizar este test.",
        )

    def test_pero_no_alcanza_ninguna_tabla_append_only(self):
        """La garantía que esta auditoría sí cubre, decida lo que se decida.

        `LostModeEvidence` es una hoja del grafo: no tiene hijos, así que su
        `CASCADE` no puede propagarse a la evidencia permanente.
        """
        antes = self.censo()

        self.agente.delete()

        self.assertDeltaCero(antes, "Borrar el agente con evidencia de modo perdido")
        self.certificado.refresh_from_db()
        self.assertIsNone(self.certificado.agent_id)
        self.assertEqual(self.certificado.tenant, "Cliente Perdido")
