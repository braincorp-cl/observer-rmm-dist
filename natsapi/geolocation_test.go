package api

import (
	"reflect"
	"testing"

	"github.com/ugorji/go/codec"

	"github.com/braincorp-cl/observer-rmm-dist/natsapi/shared"
)

// newDecoderLikeSvc replica EXACTAMENTE el handle de decode usado en Svc()
// (svc.go): MapType=map[string]interface{} y RawToString=true. Los tests deben
// usar el mismo handle o no prueban el comportamiento real de producción.
func newDecoderLikeSvc(data []byte) *codec.Decoder {
	var mh codec.MsgpackHandle
	mh.MapType = reflect.TypeOf(map[string]interface{}(nil))
	mh.RawToString = true
	return codec.NewDecoderBytes(data, &mh)
}

// encodeLikeAgent replica el encode del agente (checkin.go NatsMessage):
// codec.NewEncoderBytes(&resp, new(codec.MsgpackHandle)). El MsgpackHandle por
// defecto de ugorji honra los tags `codec`/`json` e ignora `msgpack:` (GAP-051).
func encodeLikeAgent(t *testing.T, v interface{}) []byte {
	t.Helper()
	var out []byte
	enc := codec.NewEncoderBytes(&out, new(codec.MsgpackHandle))
	if err := enc.Encode(v); err != nil {
		t.Fatalf("encode: %v", err)
	}
	return out
}

// T007: el payload GeoNats codificado por el agente debe decodificar con las
// claves de wire = tags `json:`, poblando el struct. Si alguien cambiara a
// `msgpack:` o desalineara una clave, este test caería (Agentid vacío).
func TestGeoNatsMsgpackRoundTrip(t *testing.T) {
	sent := shared.GeoNats{
		Func:       "geo",
		Agentid:    "aBcDeFgHiJkLmNoPqRsTuVwXyZ0123456789abcd",
		Version:    "2.11.0",
		Lat:        -33.4489,
		Long:       -70.6693,
		AccuracyM:  35,
		Source:     "native",
		CapturedAt: 1753257600,
	}
	data := encodeLikeAgent(t, sent)

	var got shared.GeoNats
	if err := newDecoderLikeSvc(data).Decode(&got); err != nil {
		t.Fatalf("decode GeoNats: %v", err)
	}

	if got.Agentid != sent.Agentid {
		t.Errorf("agent_id no matchea: got %q want %q (¿tags json: desalineados? GAP-051)", got.Agentid, sent.Agentid)
	}
	if got.Lat != sent.Lat || got.Long != sent.Long {
		t.Errorf("coords: got (%v,%v) want (%v,%v)", got.Lat, got.Long, sent.Lat, sent.Long)
	}
	if got.AccuracyM != sent.AccuracyM {
		t.Errorf("accuracy_m: got %d want %d", got.AccuracyM, sent.AccuracyM)
	}
	if got.Source != sent.Source || got.CapturedAt != sent.CapturedAt || got.Func != sent.Func {
		t.Errorf("campos discretos no matchean: %+v vs %+v", got, sent)
	}
}

// T007 (borde GAP-051): un mapa con las claves de wire debe poblar el struct.
// Esto prueba que las claves `json:` son las correctas, independiente del nombre
// del campo Go. Si una clave de wire estuviera mal, el campo quedaría en cero.
func TestGeoNatsWireKeysAreJSON(t *testing.T) {
	wire := map[string]interface{}{
		"func":        "geo",
		"agent_id":    "wireKeyAgentId000000000000000000000000000",
		"version":     "2.11.0",
		"lat":         -33.45,
		"long":        -70.67,
		"accuracy_m":  40,
		"source":      "wifi",
		"captured_at": int64(1753257601),
	}
	data := encodeLikeAgent(t, wire)

	var got shared.GeoNats
	if err := newDecoderLikeSvc(data).Decode(&got); err != nil {
		t.Fatalf("decode from wire map: %v", err)
	}
	if got.Agentid == "" {
		t.Fatal("agent_id vacío: la clave de wire `agent_id` no mapeó al campo (tag json: incorrecto)")
	}
	if got.Source != "wifi" || got.AccuracyM != 40 {
		t.Errorf("mapeo parcial: %+v", got)
	}
}

// T008: regresión CONTRACT-01. Los 6 check-ins existentes deben seguir
// decodificando intactos aun con el topic/struct geo nuevo presente en el
// paquete. Prueba el campo Agentid (clave de match en todos los UPDATE ... WHERE
// agent_id) de cada payload.
func TestExistingCheckinsDecodeIntact(t *testing.T) {
	const aid = "regressionAgentId00000000000000000000000"

	t.Run("agent-hello", func(t *testing.T) {
		data := encodeLikeAgent(t, shared.CheckInNats{Agentid: aid, Version: "2.11.0"})
		var p shared.CheckInNats
		if err := newDecoderLikeSvc(data).Decode(&p); err != nil || p.Agentid != aid {
			t.Fatalf("hello roto: err=%v agentid=%q", err, p.Agentid)
		}
		if p.Version != "2.11.0" {
			t.Errorf("hello version: %q", p.Version)
		}
	})

	t.Run("agent-publicip", func(t *testing.T) {
		data := encodeLikeAgent(t, shared.PublicIPNats{Agentid: aid, PublicIP: "1.2.3.4"})
		var p shared.PublicIPNats
		if err := newDecoderLikeSvc(data).Decode(&p); err != nil || p.Agentid != aid {
			t.Fatalf("publicip roto: err=%v agentid=%q", err, p.Agentid)
		}
		if p.PublicIP != "1.2.3.4" {
			t.Errorf("publicip ip: %q", p.PublicIP)
		}
	})

	t.Run("agent-agentinfo", func(t *testing.T) {
		data := encodeLikeAgent(t, shared.AgentInfoNats{Agentid: aid, Hostname: "host1", OS: "Windows", Platform: "windows", TotalRAM: 16, BootTime: 1, RebootNeeded: false, Username: "u", GoArch: "amd64"})
		var p shared.AgentInfoNats
		if err := newDecoderLikeSvc(data).Decode(&p); err != nil || p.Agentid != aid {
			t.Fatalf("agentinfo roto: err=%v agentid=%q", err, p.Agentid)
		}
		if p.Hostname != "host1" || p.Platform != "windows" {
			t.Errorf("agentinfo campos: %+v", p)
		}
	})

	t.Run("agent-disks", func(t *testing.T) {
		data := encodeLikeAgent(t, shared.WinDisksNats{Agentid: aid, Disks: []interface{}{map[string]interface{}{"device": "C:"}}})
		var p shared.WinDisksNats
		if err := newDecoderLikeSvc(data).Decode(&p); err != nil || p.Agentid != aid {
			t.Fatalf("disks roto: err=%v agentid=%q", err, p.Agentid)
		}
	})

	t.Run("agent-winsvc", func(t *testing.T) {
		data := encodeLikeAgent(t, shared.WinSvcNats{Agentid: aid, WinSvcs: []interface{}{map[string]interface{}{"name": "svc"}}})
		var p shared.WinSvcNats
		if err := newDecoderLikeSvc(data).Decode(&p); err != nil || p.Agentid != aid {
			t.Fatalf("winsvc roto: err=%v agentid=%q", err, p.Agentid)
		}
	})

	t.Run("agent-wmi", func(t *testing.T) {
		data := encodeLikeAgent(t, shared.WinWMINats{Agentid: aid, WMI: map[string]interface{}{"bios": "x"}})
		var p shared.WinWMINats
		if err := newDecoderLikeSvc(data).Decode(&p); err != nil || p.Agentid != aid {
			t.Fatalf("wmi roto: err=%v agentid=%q", err, p.Agentid)
		}
	})
}

// Feature 030 · la regla que decide si un punto entra a checks_checkhistory.
//
// El caso que motiva el test es el tercero: hasta el 2026-08-11 el handler
// descartaba TODO punto con la geo global apagada, y como la instalación por
// omisión viene con la geo apagada (ADR-024), la geo intensiva del modo perdido
// era un no-op de punta a punta. Se midió en terreno contra staging: cuatro
// publicaciones del agente, cero filas insertadas.
func TestGeoIngestAllowed(t *testing.T) {
	casos := []struct {
		nombre     string
		geoEnabled bool
		lostMode   bool
		quiere     bool
	}{
		{"operación normal con la geo encendida", true, false, true},
		{"geo encendida y además equipo perdido", true, true, true},
		{"geo apagada y equipo perdido: el modo perdido pisa el interruptor", false, true, true},
		{"geo apagada y equipo no marcado: se descarta", false, false, false},
	}
	for _, c := range casos {
		if got := geoIngestAllowed(c.geoEnabled, c.lostMode); got != c.quiere {
			t.Errorf("%s: geoIngestAllowed(%v, %v) = %v, quiere %v",
				c.nombre, c.geoEnabled, c.lostMode, got, c.quiere)
		}
	}
}

// Feature 030 · el fallback de sitio de la 026 NO aplica a un equipo perdido.
//
// El caso que lo motiva se vio en terreno el 2026-08-11: los tres puntos del
// equipo marcado quedaron con source="site" y las coordenadas DECLARADAS del
// sitio. Para un equipo estacionario eso es mejor que un fix por IP; para uno
// robado es evidencia fabricada — el recorrido muestra el equipo sentado en la
// oficina mientras alguien se lo lleva.
func TestHeredaCoordenadasDelSitio(t *testing.T) {
	casos := []struct {
		nombre         string
		lostMode       bool
		offsiteAllowed bool
		source         string
		quiere         bool
	}{
		{"estacionario sin fix medido: hereda, que es el caso de la 026", false, false, geoSourceIP, true},
		{"estacionario sin ubicación disponible: hereda", false, false, geoSourceUnavailable, true},
		{"equipo PERDIDO con fix por IP: NO hereda, entra el punto honesto", true, false, geoSourceIP, false},
		{"equipo PERDIDO sin ubicación: NO hereda", true, false, geoSourceUnavailable, false},
		{"equipo móvil declarado: NO hereda, no está clavado en la oficina", false, true, geoSourceIP, false},
		{"permiso denegado: NO hereda, taparlo esconde el diagnóstico", false, false, geoSourceDenied, false},
		{"fix medido de verdad: no hay nada que heredar", false, false, "native", false},
	}
	for _, c := range casos {
		if got := heredaCoordenadasDelSitio(c.lostMode, c.offsiteAllowed, c.source); got != c.quiere {
			t.Errorf("%s: heredaCoordenadasDelSitio(%v, %v, %q) = %v, quiere %v",
				c.nombre, c.lostMode, c.offsiteAllowed, c.source, got, c.quiere)
		}
	}
}
