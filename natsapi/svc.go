package api

import (
	"database/sql"
	"encoding/json"
	"reflect"
	"runtime"
	"time"

	"github.com/jmoiron/sqlx"
	_ "github.com/lib/pq"
	nats "github.com/nats-io/nats.go"
	"github.com/sirupsen/logrus"
	"github.com/ugorji/go/codec"
	"github.com/braincorp-cl/observer-rmm-dist/natsapi/shared"
)

// geoCheckHistoryID: centinela de check_id para las filas de geolocalización en
// checks_checkhistory (feature 023). DEBE coincidir con el literal de
// observerrmm/constants.py#GEO_CHECK_HISTORY_ID; el endpoint de lectura filtra
// por este mismo valor.
const geoCheckHistoryID = 2000000000

// Orígenes de un punto de ubicación. Espejo EXACTO de
// observerrmm/constants.py#GEO_SOURCE_* y de los literales que emite el agente
// (observer-agent/agent/geolocation.go). "site" NO lo emite el agente: lo produce
// este servicio como fallback declarado (feature 026).
const (
	geoSourceSite        = "site"
	geoSourceIP          = "ip"
	geoSourceDenied      = "denied"
	geoSourceUnavailable = "unavailable"
)

// geoIngestAllowed decide si un punto de ubicación entra a checks_checkhistory.
//
// Va en su propia función —y no en línea dentro del handler— porque es la regla
// que decide si la feature 030 sirve o no sirve, y sin esta costura no habría
// forma de probarla: el handler necesita NATS y PostgreSQL vivos.
func geoIngestAllowed(geoEnabled, lostMode bool) bool {
	return geoEnabled || lostMode
}

// agentLostMode responde si ESTE agente está marcado como perdido.
//
// Fail-safe APAGADO, igual que _lost_mode() en apiv3/utils.py: ante cualquier
// problema —tabla no migrada, BD con hipo, agente inexistente— responde "no está
// perdido". Del lado del servidor el peor desenlace es guardar ubicaciones de un
// equipo que nadie marcó, así que la duda se resuelve descartando.
func agentLostMode(db *sqlx.DB, logger *logrus.Logger, agentid string) bool {
	var active bool
	err := db.QueryRow(`
	SELECT s.active
	FROM agents_lostmodestate s
	JOIN agents_agent a ON a.id = s.agent_id
	WHERE a.agent_id = $1;`, agentid).Scan(&active)
	if err != nil {
		if err != sql.ErrNoRows {
			logger.Debugln("Geo: no se pudo leer el modo perdido del agente:", err)
		}
		return false
	}
	return active
}

func Svc(logger *logrus.Logger, cfg string) {
	logger.Debugln("Starting Svc()")
	db, r, err := GetConfig(cfg)
	if err != nil {
		logger.Fatalln(err)
	}

	opts := []nats.Option{
		nats.Name("observerrmm-nats-api"),
		nats.UserInfo("observerrmm", r.Key),
		nats.ReconnectWait(time.Second * 2),
		nats.RetryOnFailedConnect(true),
		nats.IgnoreAuthErrorAbort(),
		nats.MaxReconnects(-1),
		nats.ReconnectBufSize(-1),
		nats.DisconnectErrHandler(func(nc *nats.Conn, nerr error) {
			logger.Debugln("NATS disconnected:", nerr)
			logger.Debugf("%+v\n", nc.Statistics)
		}),
		nats.ReconnectHandler(func(nc *nats.Conn) {
			logger.Debugln("NATS reconnected")
			logger.Debugf("%+v\n", nc.Statistics)
		}),
		nats.ErrorHandler(func(nc *nats.Conn, sub *nats.Subscription, nerr error) {
			logger.Errorln("NATS error:", nerr)
			logger.Errorf("%+v\n", sub)
		}),
	}
	nc, err := nats.Connect(r.NatsURL, opts...)
	if err != nil {
		logger.Fatalln(err)
	}

	nc.Subscribe("*", func(msg *nats.Msg) {
		var mh codec.MsgpackHandle
		mh.MapType = reflect.TypeOf(map[string]interface{}(nil))
		mh.RawToString = true
		dec := codec.NewDecoderBytes(msg.Data, &mh)

		switch msg.Reply {
		case "agent-hello":
			go func() {
				var p shared.CheckInNats
				if err := dec.Decode(&p); err == nil {
					if !validAgent(logger, msg.Subject, p.Agentid) {
						return
					}
					now := time.Now().UTC()
					logger.Debugln("Hello", p, now)
					stmt := `
					UPDATE agents_agent
					SET last_seen=$1, version=$2
					WHERE agents_agent.agent_id=$3;
					`

					_, err = db.Exec(stmt, now, p.Version, p.Agentid)
					if err != nil {
						logger.Errorln(err)
					}
				}
			}()

		case "agent-publicip":
			go func() {
				var p shared.PublicIPNats
				if err := dec.Decode(&p); err == nil {
					if !validAgent(logger, msg.Subject, p.Agentid) {
						return
					}
					logger.Debugln("Public IP", p)
					stmt := `
					UPDATE agents_agent SET public_ip=$1 WHERE agents_agent.agent_id=$2;`
					_, err = db.Exec(stmt, p.PublicIP, p.Agentid)
					if err != nil {
						logger.Errorln(err)
					}
				}
			}()

		case "agent-agentinfo":
			go func() {
				var r shared.AgentInfoNats
				if err := dec.Decode(&r); err == nil {
					if !validAgent(logger, msg.Subject, r.Agentid) {
						return
					}
					stmt := `
						UPDATE agents_agent
						SET hostname=$1, operating_system=$2,
						plat=$3, total_ram=$4, boot_time=$5, needs_reboot=$6, logged_in_username=$7, goarch=$8
						WHERE agents_agent.agent_id=$9;`

					logger.Debugln("Info", r)
					_, err = db.Exec(stmt, r.Hostname, r.OS, r.Platform, r.TotalRAM, r.BootTime, r.RebootNeeded, r.Username, r.GoArch, r.Agentid)
					if err != nil {
						logger.Errorln(err)
					}

					if r.Username != "None" {
						stmt = `UPDATE agents_agent SET last_logged_in_user=$1 WHERE agents_agent.agent_id=$2;`
						logger.Debugln("Updating last logged in user:", r.Username)
						_, err = db.Exec(stmt, r.Username, r.Agentid)
						if err != nil {
							logger.Errorln(err)
						}
					}
				}
			}()

		case "agent-disks":
			go func() {
				var r shared.WinDisksNats
				if err := dec.Decode(&r); err == nil {
					if !validAgent(logger, msg.Subject, r.Agentid) {
						return
					}
					logger.Debugln("Disks", r)
					b, err := json.Marshal(r.Disks)
					if err != nil {
						logger.Errorln(err)
						return
					}
					stmt := `
					UPDATE agents_agent SET disks=$1 WHERE agents_agent.agent_id=$2;`

					_, err = db.Exec(stmt, b, r.Agentid)
					if err != nil {
						logger.Errorln(err)
					}
				}
			}()

		case "agent-winsvc":
			go func() {
				var r shared.WinSvcNats
				if err := dec.Decode(&r); err == nil {
					if !validAgent(logger, msg.Subject, r.Agentid) {
						return
					}
					logger.Debugln("WinSvc", r)
					b, err := json.Marshal(r.WinSvcs)
					if err != nil {
						logger.Errorln(err)
						return
					}

					stmt := `
					UPDATE agents_agent SET services=$1 WHERE agents_agent.agent_id=$2;`

					_, err = db.Exec(stmt, b, r.Agentid)
					if err != nil {
						logger.Errorln(err)
					}
				}
			}()

		case "agent-wmi":
			go func() {
				var r shared.WinWMINats
				if err := dec.Decode(&r); err == nil {
					if !validAgent(logger, msg.Subject, r.Agentid) {
						return
					}
					logger.Debugln("WMI", r)
					b, err := json.Marshal(r.WMI)
					if err != nil {
						logger.Errorln(err)
						return
					}
					stmt := `
					UPDATE agents_agent SET wmi_detail=$1 WHERE agents_agent.agent_id=$2;`

					_, err = db.Exec(stmt, b, r.Agentid)
					if err != nil {
						logger.Errorln(err)
					}
				}
			}()

		case "agent-geolocation":
			// Feature 023: la ubicación se guarda como una fila en
			// checks_checkhistory (mismo almacén y misma retención que los demás
			// checks). No hay UPDATE a agents_agent: la posición "actual" es la
			// última fila. Ver CONTRACT-01.
			go func() {
				var p shared.GeoNats
				if err := dec.Decode(&p); err != nil {
					return
				}
				if !validAgent(logger, msg.Subject, p.Agentid) {
					return
				}
				// Interruptor GLOBAL (defensa en profundidad): si está apagado,
				// ignorar aunque un agente publique.
				//
				// Feature 030 · el modo perdido pisa el interruptor TAMBIÉN acá.
				// Hasta el 2026-08-11 no lo hacía, y eso convertía la geo intensiva
				// en un no-op de punta a punta justo en la instalación por omisión
				// (geo apagada, ADR-024): medido en terreno contra staging, el
				// agente publicó un punto cada 60 s durante 4 minutos y el servidor
				// descartó los cuatro. El agente gastaba batería y se delataba
				// frente a quien tiene el equipo, y el recorrido quedaba vacío.
				// El régimen que lo autoriza es el de ADR-025 —motivo obligatorio,
				// permiso dedicado y auditoría que deja escrito que el marcaje pisa
				// esta perilla—, el mismo que ya aplican el agente (svc.go) y las
				// vistas de lectura (_geo_visible).
				var geoEnabled bool
				var geofenceRadius int
				if err := db.QueryRow(`SELECT geo_tracking_enabled, geo_geofence_radius_m FROM core_coresettings ORDER BY id LIMIT 1;`).Scan(&geoEnabled, &geofenceRadius); err != nil {
					// Sin poder leer la config no se ingiere: el fallo de lectura no
					// puede volverse un permiso.
					logger.Debugln("Geo: no se pudo leer la config global, descartando punto")
					return
				}
				// La consulta extra sólo ocurre con la geo global APAGADA, que es el
				// único caso donde el modo perdido cambia el desenlace.
				lostMode := false
				if !geoEnabled {
					lostMode = agentLostMode(db, logger, p.Agentid)
				}
				if !geoIngestAllowed(geoEnabled, lostMode) {
					logger.Debugln("Geo: interruptor global apagado y el equipo no está marcado como perdido, descartando punto")
					return
				}

				lat, long, accuracy, source := p.Lat, p.Long, p.AccuracyM, p.Source

				// Fallback de sitio (feature 026): un equipo ESTACIONARIO que no logró
				// medir su posición hereda las coordenadas declaradas de su Site. El caso
				// que lo motiva es la VM sin radio WiFi: su único origen posible es "ip",
				// y el bloque público está registrado en la casa matriz del ISP — 238 km
				// de error medidos (Entel/Santiago vs. el datacenter real en Talca). Las
				// coordenadas declaradas del sitio son estrictamente mejores.
				//
				// NO aplica a "denied": ahí el problema es de permisos y taparlo con la
				// posición del sitio esconde el diagnóstico en la consola. NO aplica a
				// equipos con geo_offsite_allowed: un notebook que se mueve no debe
				// aparecer clavado en la oficina.
				if source == geoSourceIP || source == geoSourceUnavailable {
					var siteLat, siteLong sql.NullFloat64
					var offsiteAllowed bool
					err := db.QueryRow(`
					SELECT s.latitude, s.longitude, a.geo_offsite_allowed
					FROM agents_agent a
					JOIN clients_site s ON a.site_id = s.id
					WHERE a.agent_id = $1;`, p.Agentid).Scan(&siteLat, &siteLong, &offsiteAllowed)
					if err != nil {
						logger.Debugln("Geo: no se pudo leer el sitio del agente:", err)
					} else if !offsiteAllowed && siteLat.Valid && siteLong.Valid {
						// La incertidumbre declarada es el propio perímetro del sitio:
						// lo que se afirma es "este equipo está dentro del sitio".
						lat, long, source = siteLat.Float64, siteLong.Float64, geoSourceSite
						accuracy = geofenceRadius
						logger.Debugln("Geo: sin fix medido, heredando coordenadas del sitio")
					}
				}

				// Estados sin fix: NO se guardan filas con coordenadas nulas
				// (CONTRACT-01 punto 3). No se loggean coordenadas a nivel normal.
				if source == geoSourceDenied || source == geoSourceUnavailable {
					logger.Debugln("Geo: sin fix, no se inserta punto")
					return
				}
				if lat < -90 || lat > 90 || long < -180 || long > 180 || (lat == 0 && long == 0) {
					logger.Debugln("Geo: coordenadas fuera de rango, descartando")
					return
				}
				results, err := json.Marshal(map[string]interface{}{
					"lat":         lat,
					"long":        long,
					"source":      source,
					"captured_at": p.CapturedAt,
				})
				if err != nil {
					logger.Errorln(err)
					return
				}
				stmt := `
				INSERT INTO checks_checkhistory (check_id, agent_id, x, y, results)
				VALUES ($1, $2, $3, $4, $5);`
				_, err = db.Exec(stmt, geoCheckHistoryID, p.Agentid, time.Now().UTC(), accuracy, results)
				if err != nil {
					logger.Errorln(err)
				}
			}()
		}
	})

	nc.Flush()

	if err := nc.LastError(); err != nil {
		logger.Fatalln(err)
	}
	runtime.Goexit()
}

func validAgent(logger *logrus.Logger, subject, agentid string) bool {
	if agentid != subject {
		logger.Errorf("agent_id mismatch: subject=%s agent_id=%s", subject, agentid)
		return false
	}
	return true
}
