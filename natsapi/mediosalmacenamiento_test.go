package api

// Feature 055 · los guardianes de las decisiones que se toman ANTES del SQL.
//
// El SQL de `guardarMediosAlmacenamiento` no se prueba acá: necesita PostgreSQL
// con las tablas migradas, y eso se verifica en el E2E de staging. Lo que sí se
// prueba es lo que puede destruir o falsear un dato sin que nadie lo note.

import (
	"encoding/json"
	"testing"

	"github.com/sirupsen/logrus"

	"github.com/braincorp-cl/observer-rmm-dist/natsapi/shared"
)

func TestReconciliarDiscos(t *testing.T) {
	fallo := "Espacio de nombres no valido"

	casos := []struct {
		nombre   string
		ma       *shared.MediosAlmacenamiento
		esperado bool
	}{
		{
			"lectura buena con discos: hay que reconciliar",
			&shared.MediosAlmacenamiento{Soportado: true, Discos: []shared.MedioAlmacenamiento{{PnpDeviceID: "disco-1"}}},
			true,
		},
		{
			"lectura buena SIN discos: tambien, un disco que se cambio no puede seguir en el panel",
			&shared.MediosAlmacenamiento{Soportado: true, Discos: []shared.MedioAlmacenamiento{}},
			true,
		},
		{
			"equipo sin soporte: no sabemos que medio hay, pero el reporte es valido",
			&shared.MediosAlmacenamiento{Soportado: false, Discos: []shared.MedioAlmacenamiento{}},
			true,
		},
		{
			"la consulta FALLO: jamas borrar, no sabemos nada de hoy",
			&shared.MediosAlmacenamiento{Soportado: true, Error: &fallo, Discos: []shared.MedioAlmacenamiento{}},
			false,
		},
		{
			"sin bloque: el agente es anterior a la feature",
			nil,
			false,
		},
	}

	for _, c := range casos {
		t.Run(c.nombre, func(t *testing.T) {
			if got := reconciliarDiscos(c.ma); got != c.esperado {
				t.Fatalf("reconciliarDiscos() = %v, se esperaba %v", got, c.esperado)
			}
		})
	}
}

func TestControlPositivoBorrarDiscosConLecturaFallida(t *testing.T) {
	// El control que explica por qué la guarda existe. Si alguien la borra y
	// deja el DELETE suelto, un reporte fallido —que no trae discos— limpiaria
	// el inventario del equipo entero, y el panel pasaria de un veredicto bueno
	// a "sin dato" sin que nadie haya tocado el hardware.
	fallo := "acceso denegado"
	ma := &shared.MediosAlmacenamiento{Soportado: true, Error: &fallo}

	if reconciliarDiscos(ma) {
		t.Fatal("un reporte fallido NO puede habilitar el borrado de los discos guardados")
	}
}

func TestDiscosPersistiblesExcluyeExtraibles(t *testing.T) {
	// 🪤 El caso medido: un disco externo llega con el MISMO bus que uno
	// interno. Si la exclusión se apoyara en el bus, los dos entrarian igual.
	discos := []shared.MedioAlmacenamiento{
		{PnpDeviceID: "interno", Removable: false},
		{PnpDeviceID: "externo-usb", Removable: true},
		{PnpDeviceID: "interno-2", Removable: false},
	}

	fijos := discosPersistibles(discos)

	if len(fijos) != 2 {
		t.Fatalf("quedaron %d discos, se esperaban 2", len(fijos))
	}
	for _, d := range fijos {
		if d.Removable {
			t.Fatalf("un extraible se colo al inventario: %s", d.PnpDeviceID)
		}
	}
}

func TestDiscosPersistiblesNoDevuelveNil(t *testing.T) {
	// Con todos los discos extraibles, la lista queda vacia PERO NO nula: el
	// DELETE de reconciliación usa esa lista, y la diferencia entre vacia y
	// nula no puede alterar el SQL que se ejecuta.
	fijos := discosPersistibles([]shared.MedioAlmacenamiento{{PnpDeviceID: "usb", Removable: true}})

	if fijos == nil {
		t.Fatal("la lista no puede ser nula: el DELETE de reconciliación la usa")
	}
	if len(fijos) != 0 {
		t.Fatalf("quedaron %d discos, se esperaban 0", len(fijos))
	}
}

func TestCapacidadesJSONPreservaElNulo(t *testing.T) {
	logger := logrus.New()
	logger.SetLevel(logrus.PanicLevel)

	// Nulo es "no se intento leer las capacidades". Si esto devolviera "{}",
	// un disco que nadie sondeo se veria igual que uno sondeado sin resultado,
	// y el veredicto diria "sin categoria alcanzable" sobre algo no medido.
	if got := capacidadesJSON(nil, logger); got != nil {
		t.Fatalf("un mapa nulo tiene que seguir siendo nulo, se obtuvo %v", got)
	}

	// El mapa vacio es "se pregunto y el firmware no declara ninguna".
	got := capacidadesJSON(map[string]interface{}{}, logger)
	if got == nil {
		t.Fatal("un mapa vacio NO es lo mismo que nulo: se pregunto y no hay")
	}
	b, ok := got.([]byte)
	if !ok {
		t.Fatalf("se esperaba JSON serializado, se obtuvo %T", got)
	}
	if string(b) != "{}" {
		t.Fatalf("se esperaba {}, se obtuvo %s", b)
	}
}

func TestCapacidadesJSONSerializaElDetalle(t *testing.T) {
	logger := logrus.New()
	logger.SetLevel(logrus.PanicLevel)

	caps := map[string]interface{}{
		"supported": true,
		"commands":  []string{"nvme_sanitize"},
	}

	b, ok := capacidadesJSON(caps, logger).([]byte)
	if !ok {
		t.Fatal("se esperaba JSON serializado")
	}

	var vuelta map[string]interface{}
	if err := json.Unmarshal(b, &vuelta); err != nil {
		t.Fatalf("el JSON guardado no se puede releer: %v", err)
	}
	// La clave que el filtro SQL del panel consulta directamente. Si cambia de
	// nombre acá, el veredicto "purge con imagen live" deja de encontrarse.
	if vuelta["supported"] != true {
		t.Fatalf("la clave que el filtro SQL consulta no sobrevivio: %v", vuelta)
	}
}
