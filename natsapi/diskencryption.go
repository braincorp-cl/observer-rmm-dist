package api

// Feature 037 · Fase 2 (T012) — el estado de cifrado se persiste en tablas
// propias, además del blob de inventario.
//
// Por qué en tablas y no sólo en `wmi_detail`: RF-03 pide poder listar «agentes
// cuyo volumen de sistema no está protegido» con una consulta, sin recorrer JSON
// en Python. El blob sigue guardándose igual —esto se suma, no reemplaza—.
//
// ⚠️ Agrava DT-002 (`architecture.md#DT-002`): quien escribe estas tablas es
// este microservicio Go y no Django, así que `save()`, señales y auditoría
// genérica NO corren. Costo conocido y aceptado en el requirements §10. La
// contrapartida es que el historial de RN-A09 se escribe en el mismo SQL, en la
// misma transacción, y no puede quedar desalineado del estado actual.
//
// 📌 Los códigos de WMI viajan y se guardan CRUDOS (RN-A05). Este archivo no
// interpreta ninguno: el único que compara es `protection_status` contra su
// valor anterior, y lo hace en SQL con `IS DISTINCT FROM`. La traducción a
// etiqueta vive en la consola, y los nombres de los códigos en
// `observerrmm/constants.py`.

import (
	"github.com/jmoiron/sqlx"
	"github.com/lib/pq"
	"github.com/sirupsen/logrus"

	"github.com/braincorp-cl/observer-rmm-dist/natsapi/shared"
)

// reconciliarVolumenes decide si la lista de volúmenes del reporte puede
// reemplazar a la que hay guardada.
//
// Es la regla más peligrosa de la Fase 2 y por eso vive en su propia función,
// afuera del SQL: un reporte que **falló** no trae volúmenes, y borrar los
// existentes con ese reporte convertiría «no pudimos leer» en «este equipo no
// tiene volúmenes cifrables», que el panel muestra como cumplimiento resuelto.
// Es el ok falso de RF-07 con daño real: se pierde el último estado conocido.
//
// Con la lectura buena sí hay que reconciliar —incluso si vuelve vacía—, porque
// un volumen que dejó de existir (una unidad extraíble que se sacó) no puede
// quedar en el panel afirmando que sigue cifrado.
func reconciliarVolumenes(de *shared.DiskEncryption) bool {
	return de != nil && de.Error == nil
}

// guardarDiskEncryption escribe el reporte de cifrado de un agente.
//
// No devuelve error: es el mismo criterio que el resto de los handlers de
// `svc.go` —lo que se puede hacer es registrar y seguir—, pero acá con una
// diferencia que importa: todo va en UNA transacción. Un historial escrito con
// un estado actual que no se guardó sería una auditoría que miente, y es peor
// que no tener el dato.
func guardarDiskEncryption(db *sqlx.DB, logger *logrus.Logger, agentid string, de *shared.DiskEncryption) {
	// Ausencia de bloque = agente anterior a la feature. "Sin dato" es ausencia
	// de fila (RN-A03): no se crea nada, ni con valores por omisión.
	if de == nil {
		return
	}

	var pk int
	if err := db.QueryRow(
		`SELECT id FROM agents_agent WHERE agent_id = $1;`, agentid,
	).Scan(&pk); err != nil {
		// Mismo criterio que agentLostMode: un agente que no está en la tabla
		// no es un error del que valga la pena hablar fuerte.
		logger.Debugln("Cifrado: no se pudo resolver el agente:", err)
		return
	}

	tx, err := db.Begin()
	if err != nil {
		logger.Errorln("Cifrado: no se pudo abrir la transaccion:", err)
		return
	}
	defer tx.Rollback() //nolint:errcheck // rollback tras un Commit exitoso es no-op

	// 1. El hecho por equipo: ¿lo soporta? ¿pudimos leer? ¿cuándo?
	//
	// measured_at se refresca SIEMPRE, aunque nada haya cambiado: es la edad del
	// dato que el panel muestra, y con la cadencia de `agent-wmi` (50-66 min en
	// el peor caso) un tablero de cumplimiento sin esa fecha induce a error.
	if _, err := tx.Exec(`
	INSERT INTO agents_diskencryptionstate (agent_id, supported, query_error, measured_at)
	VALUES ($1, $2, $3, NOW())
	ON CONFLICT (agent_id) DO UPDATE SET
		supported = EXCLUDED.supported,
		query_error = EXCLUDED.query_error,
		measured_at = EXCLUDED.measured_at;`,
		pk, de.Soportado, de.Error,
	); err != nil {
		logger.Errorln("Cifrado: no se pudo guardar el estado del equipo:", err)
		return
	}

	deviceIDs := make([]string, 0, len(de.Volumenes))

	for _, v := range de.Volumenes {
		deviceIDs = append(deviceIDs, v.DeviceID)

		// 2. El historial ANTES del upsert: una vez sobreescrita la fila, el
		// estado anterior ya no existe en ninguna parte.
		//
		// El LEFT JOIN sobre una fila sintética es lo que hace que un volumen
		// NUEVO también quede registrado: sin fila previa, v.protection_status
		// es NULL, y `NULL IS DISTINCT FROM <código>` es verdadero, así que
		// entra con previous_status nulo — la primera vez que vemos un volumen
		// es un cambio legítimo (RN-A09). Y si el estado es el mismo, no se
		// inserta nada: una línea por cambio, nunca por latido.
		if _, err := tx.Exec(`
		INSERT INTO agents_diskencryptionhistory (agent_id, device_id, previous_status, new_status, changed_at)
		SELECT $1, $2, v.protection_status, $3, NOW()
		FROM (SELECT 1) AS presente
		LEFT JOIN agents_diskencryptionvolume v
			ON v.agent_id = $1 AND v.device_id = $2
		WHERE v.protection_status IS DISTINCT FROM $3;`,
			pk, v.DeviceID, v.ProtectionStatus,
		); err != nil {
			logger.Errorln("Cifrado: no se pudo escribir el historial:", err)
			return
		}

		// 3. El estado actual del volumen.
		if _, err := tx.Exec(`
		INSERT INTO agents_diskencryptionvolume (
			agent_id, device_id, drive_letter, protection_status, conversion_status,
			encryption_method, encryption_percentage, volume_type, is_system_volume,
			key_protector_count, key_protector_types, measured_at)
		VALUES ($1, $2, $3, $4, $5, $6, $7, $8, $9, $10, $11, NOW())
		ON CONFLICT (agent_id, device_id) DO UPDATE SET
			drive_letter = EXCLUDED.drive_letter,
			protection_status = EXCLUDED.protection_status,
			conversion_status = EXCLUDED.conversion_status,
			encryption_method = EXCLUDED.encryption_method,
			encryption_percentage = EXCLUDED.encryption_percentage,
			volume_type = EXCLUDED.volume_type,
			is_system_volume = EXCLUDED.is_system_volume,
			key_protector_count = EXCLUDED.key_protector_count,
			key_protector_types = EXCLUDED.key_protector_types,
			measured_at = EXCLUDED.measured_at;`,
			pk, v.DeviceID, v.DriveLetter, v.ProtectionStatus, v.ConversionStatus,
			v.EncryptionMethod, v.EncryptionPercentage, v.VolumeType, v.IsSystemVolume,
			v.KeyProtectorCount, tiposDeProtector(v.KeyProtectorTypes),
		); err != nil {
			logger.Errorln("Cifrado: no se pudo guardar el volumen:", err)
			return
		}
	}

	// 4. Los volúmenes que ya no están.
	//
	// 🪤 `device_id <> ALL('{}')` es VERDADERO, así que con la lista vacía esto
	// borra todas las filas del agente — que es justo lo correcto cuando el
	// equipo no soporta cifrado o no tiene volúmenes cifrables, y justo lo
	// PROHIBIDO cuando la lectura falló. Por eso la guarda es una función con
	// nombre y no una condición en línea.
	if reconciliarVolumenes(de) {
		// El `::text[]` va explícito: sin el casteo, el tipo del parámetro queda
		// a la inferencia de PostgreSQL, y un `<> ALL($2)` contra una columna
		// varchar es justo el caso donde la inferencia puede fallar en tiempo de
		// ejecución. Es un error que no se ve compilando ni probando en Linux:
		// aparece la primera vez que un agente reporta, en staging.
		if _, err := tx.Exec(`
		DELETE FROM agents_diskencryptionvolume
		WHERE agent_id = $1 AND device_id <> ALL($2::text[]);`,
			pk, pq.Array(deviceIDs),
		); err != nil {
			logger.Errorln("Cifrado: no se pudieron limpiar los volumenes viejos:", err)
			return
		}
	}

	if err := tx.Commit(); err != nil {
		logger.Errorln("Cifrado: no se pudo confirmar la transaccion:", err)
	}
}

// tiposDeProtector pasa la lista de tipos a un arreglo de PostgreSQL.
//
// Preserva la diferencia entre `null` y `[]`, que es dato: nulo es «no pudimos
// contar los protectores» y la lista vacía es «contamos y no hay ninguno»
// (RN-A06 sólo permite viajar la cantidad y el tipo, nunca el material).
func tiposDeProtector(tipos []uint32) interface{} {
	if tipos == nil {
		return nil
	}

	// pq.Array no sabe de []uint32; int64 es lo que el driver mapea a int[].
	valores := make([]int64, 0, len(tipos))
	for _, t := range tipos {
		valores = append(valores, int64(t))
	}
	return pq.Array(valores)
}
