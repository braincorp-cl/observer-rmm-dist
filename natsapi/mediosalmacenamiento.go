package api

// Feature 055 · el inventario de medios se persiste en tablas propias, además
// del blob de inventario.
//
// Por qué en tablas y no sólo en `wmi_detail`: el panel pide poder listar
// «equipos sobre los que no hay categoría de sanitización alcanzable» con una
// consulta, sin recorrer JSON en Python a escala de flota. El blob sigue
// guardándose igual —esto se suma, no reemplaza—.
//
// ⚠️ Agrava DT-002 (`architecture.md#DT-002`): quien escribe estas tablas es
// este microservicio Go y no Django, así que `save()`, señales y auditoría
// genérica NO corren. Costo conocido y aceptado, con la misma contrapartida que
// en la feature 037: todo va en una transacción.
//
// 📌 Los códigos del sistema viajan y se guardan CRUDOS (RN-04). Este archivo
// no interpreta ninguno. La traducción a etiqueta vive en la consola, y los
// nombres de los códigos en `observerrmm/constants.py`.

import (
	"encoding/json"

	"github.com/jmoiron/sqlx"
	"github.com/lib/pq"
	"github.com/sirupsen/logrus"

	"github.com/braincorp-cl/observer-rmm-dist/natsapi/shared"
)

// reconciliarDiscos decide si la lista de discos del reporte puede reemplazar a
// la que hay guardada.
//
// Es la regla más peligrosa del handler y por eso vive en su propia función,
// afuera del SQL: un reporte que **falló** no trae discos, y borrar los
// existentes con ese reporte convertiría «no pudimos leer» en «este equipo no
// tiene discos», que el panel muestra como «sin dato» después de haber tenido
// un veredicto bueno. Se pierde el último estado conocido.
//
// Con la lectura buena sí hay que reconciliar —incluso si vuelve vacía—, porque
// un disco que dejó de existir (uno que se cambió físicamente) no puede quedar
// en el panel afirmando que sigue ahí.
func reconciliarDiscos(ma *shared.MediosAlmacenamiento) bool {
	return ma != nil && ma.Error == nil
}

// discosPersistibles deja fuera los medios extraíbles.
//
// 🔑 Defensa en profundidad: el agente ya los excluye, pero esta es la última
// puerta antes de la base. Un disco externo conectado en el momento de la
// medición no es un medio del equipo, y dejarlo entrar sería ofrecerse a borrar
// el respaldo de alguien.
//
// 🪤 La exclusión NO puede apoyarse en el bus. Medido el 2026-11-01 sobre los
// cinco tenants PROD: 29 de 1.305 discos se declaran extraíbles y llegan igual
// con bus `SCSI`, idéntico a los internos. El filtro por bus de
// `Agent.physical_disks` no atrapa ninguno, y copiarlo acá heredaría el defecto.
func discosPersistibles(discos []shared.MedioAlmacenamiento) []shared.MedioAlmacenamiento {
	fijos := make([]shared.MedioAlmacenamiento, 0, len(discos))
	for _, d := range discos {
		if d.Removable {
			continue
		}
		fijos = append(fijos, d)
	}
	return fijos
}

// capacidadesJSON pasa el mapa de capacidades a un valor que el driver entienda.
//
// Preserva la diferencia entre `null` y `{}`, que es dato: nulo es «no se
// intentó leer las capacidades» y el mapa vacío es «se preguntó al firmware y
// no declara ninguna». Fundirlos haría que un disco que nadie miró se vea igual
// que uno sin vía de sanitización — el ok falso que RN-02 prohíbe.
func capacidadesJSON(caps map[string]interface{}, logger *logrus.Logger) interface{} {
	if caps == nil {
		return nil
	}
	b, err := json.Marshal(caps)
	if err != nil {
		// Un mapa que no serializa no puede volverse `null` en silencio: eso
		// diría «no se intentó» sobre un disco que sí se sondeó. Se registra y
		// se guarda el mapa vacío, que es la verdad más cercana.
		logger.Errorln("Medios: no se pudieron serializar las capacidades:", err)
		return []byte("{}")
	}
	return b
}

// guardarMediosAlmacenamiento escribe el inventario de medios de un agente.
//
// No devuelve error: es el mismo criterio que el resto de los handlers de
// `svc.go` —lo que se puede hacer es registrar y seguir—, pero acá con una
// diferencia que importa: todo va en UNA transacción. Un estado por equipo que
// dice «se sondearon las capacidades» junto a discos que no se guardaron sería
// un panel que afirma haber medido lo que no midió.
func guardarMediosAlmacenamiento(
	db *sqlx.DB, logger *logrus.Logger, agentid string, ma *shared.MediosAlmacenamiento,
) {
	// Ausencia de bloque = agente anterior a la feature. «Sin dato» es ausencia
	// de fila (RN-02): no se crea nada, ni con valores por omisión.
	if ma == nil {
		return
	}

	var pk int
	if err := db.QueryRow(
		`SELECT id FROM agents_agent WHERE agent_id = $1;`, agentid,
	).Scan(&pk); err != nil {
		logger.Debugln("Medios: no se pudo resolver el agente:", err)
		return
	}

	tx, err := db.Begin()
	if err != nil {
		logger.Errorln("Medios: no se pudo abrir la transaccion:", err)
		return
	}
	defer tx.Rollback() //nolint:errcheck // rollback tras un Commit exitoso es no-op

	// 1. El hecho por equipo. `measured_at` se refresca SIEMPRE, aunque nada
	// haya cambiado: es la edad del dato que el panel muestra.
	if _, err := tx.Exec(`
	INSERT INTO agents_storagemediastate (agent_id, supported, query_error, capabilities_probed, measured_at)
	VALUES ($1, $2, $3, $4, NOW())
	ON CONFLICT (agent_id) DO UPDATE SET
		supported = EXCLUDED.supported,
		query_error = EXCLUDED.query_error,
		capabilities_probed = EXCLUDED.capabilities_probed,
		measured_at = EXCLUDED.measured_at;`,
		pk, ma.Soportado, ma.Error, ma.CapacidadesSondeadas,
	); err != nil {
		logger.Errorln("Medios: no se pudo guardar el estado del equipo:", err)
		return
	}

	fijos := discosPersistibles(ma.Discos)
	pnpIDs := make([]string, 0, len(fijos))

	for _, d := range fijos {
		pnpIDs = append(pnpIDs, d.PnpDeviceID)

		if _, err := tx.Exec(`
		INSERT INTO agents_storagemedium (
			agent_id, pnp_device_id, device_index, model, manufacturer, serial_number,
			firmware_revision, size_bytes, bus_type, media_type_code, spindle_speed,
			is_system_disk, is_virtual, removable, self_encrypting, sanitize_capabilities,
			measured_at)
		VALUES ($1, $2, $3, $4, $5, $6, $7, $8, $9, $10, $11, $12, $13, $14, $15, $16, NOW())
		ON CONFLICT (agent_id, pnp_device_id) DO UPDATE SET
			device_index = EXCLUDED.device_index,
			model = EXCLUDED.model,
			manufacturer = EXCLUDED.manufacturer,
			serial_number = EXCLUDED.serial_number,
			firmware_revision = EXCLUDED.firmware_revision,
			size_bytes = EXCLUDED.size_bytes,
			bus_type = EXCLUDED.bus_type,
			media_type_code = EXCLUDED.media_type_code,
			spindle_speed = EXCLUDED.spindle_speed,
			is_system_disk = EXCLUDED.is_system_disk,
			is_virtual = EXCLUDED.is_virtual,
			removable = EXCLUDED.removable,
			self_encrypting = EXCLUDED.self_encrypting,
			sanitize_capabilities = EXCLUDED.sanitize_capabilities,
			measured_at = EXCLUDED.measured_at;`,
			pk, d.PnpDeviceID, d.DeviceIndex, d.Model, d.Manufacturer, d.SerialNumber,
			d.FirmwareRevision, d.SizeBytes, d.BusType, d.MediaTypeCode, d.SpindleSpeed,
			d.IsSystemDisk, d.IsVirtual, d.Removable, d.SelfEncrypting,
			capacidadesJSON(d.SanitizeCapabilities, logger),
		); err != nil {
			logger.Errorln("Medios: no se pudo guardar el disco:", err)
			return
		}
	}

	// Los discos que ya no están.
	//
	// 🪤 `pnp_device_id <> ALL('{}')` es VERDADERO, así que con la lista vacía
	// esto borra todas las filas del agente — que es justo lo correcto cuando el
	// equipo no tiene discos fijos, y justo lo PROHIBIDO cuando la lectura
	// falló. Por eso la guarda es una función con nombre y no una condición en
	// línea.
	if reconciliarDiscos(ma) {
		// El `::text[]` va explícito: sin el casteo, el tipo del parámetro
		// queda a la inferencia de PostgreSQL, y un `<> ALL($2)` contra una
		// columna varchar es justo el caso donde la inferencia puede fallar en
		// tiempo de ejecución — un error que no se ve compilando.
		if _, err := tx.Exec(`
		DELETE FROM agents_storagemedium
		WHERE agent_id = $1 AND pnp_device_id <> ALL($2::text[]);`,
			pk, pq.Array(pnpIDs),
		); err != nil {
			logger.Errorln("Medios: no se pudieron limpiar los discos viejos:", err)
			return
		}
	}

	if err := tx.Commit(); err != nil {
		logger.Errorln("Medios: no se pudo confirmar la transaccion:", err)
	}
}
