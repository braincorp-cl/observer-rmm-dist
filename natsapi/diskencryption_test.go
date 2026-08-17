package api

// Feature 037 · T012 — el guardián de la regla que puede borrar datos.
//
// El SQL de `guardarDiskEncryption` no se prueba acá: necesita PostgreSQL con las
// tablas migradas, y eso se verifica en el E2E de staging (T016). Lo que sí se
// prueba es la única decisión que se toma ANTES del SQL, porque es la que puede
// destruir el último estado conocido de un equipo.

import (
	"testing"

	"github.com/braincorp-cl/observer-rmm-dist/natsapi/shared"
)

func TestReconciliarVolumenes(t *testing.T) {
	fallo := "Espacio de nombres no valido"

	casos := []struct {
		nombre   string
		de       *shared.DiskEncryption
		esperado bool
	}{
		{
			"lectura buena con volumenes: hay que reconciliar",
			&shared.DiskEncryption{Soportado: true, Volumenes: []shared.DiskEncryptionVolume{{DeviceID: "vol-1"}}},
			true,
		},
		{
			"lectura buena SIN volumenes: tambien, un volumen que dejo de existir no puede quedar en el panel",
			&shared.DiskEncryption{Soportado: true, Volumenes: []shared.DiskEncryptionVolume{}},
			true,
		},
		{
			"equipo sin soporte: no tiene volumenes y es un hecho, no una duda",
			&shared.DiskEncryption{Soportado: false, Volumenes: []shared.DiskEncryptionVolume{}},
			true,
		},
		{
			"la consulta FALLO: jamas borrar, no sabemos nada de hoy",
			&shared.DiskEncryption{Soportado: true, Error: &fallo, Volumenes: []shared.DiskEncryptionVolume{}},
			false,
		},
		{
			"sin bloque: el agente es anterior a la feature",
			nil,
			false,
		},
	}

	for _, c := range casos {
		if got := reconciliarVolumenes(c.de); got != c.esperado {
			t.Errorf("%s: reconciliarVolumenes = %v, se esperaba %v", c.nombre, got, c.esperado)
		}
	}
}

// TestControlPositivoBorrarConLecturaFallida es el que le da valor al de arriba.
//
// La regla ingenua —"si el reporte llego, la lista de volumenes que trae es la
// verdad"— es la que se escribe sola, y con un reporte fallido borra las filas
// del equipo: el panel pasa de "cifrado" a "este equipo no tiene volumenes
// cifrables" sin que nadie haya cambiado nada en el equipo. Peor que un ok
// falso: pierde el ultimo estado conocido, que era la unica evidencia.
func TestControlPositivoBorrarConLecturaFallida(t *testing.T) {
	fallo := "WBEM_E_ACCESS_DENIED"
	reporteFallido := &shared.DiskEncryption{Soportado: true, Error: &fallo}

	reglaIngenua := func(de *shared.DiskEncryption) bool { return de != nil }

	if reconciliarVolumenes(reporteFallido) {
		t.Fatal("un reporte fallido NO autoriza a borrar los volumenes guardados")
	}
	if !reglaIngenua(reporteFallido) {
		t.Fatal("el control esta mal armado: la regla ingenua tiene que autorizar el borrado")
	}
}

// TestTiposDeProtectorPreservaElNulo: el nulo es "no pudimos contar" y la lista
// vacia es "contamos y no hay". Si el nulo se convirtiera en `{}`, la consola
// mostraria "0 protectores" en un volumen del que no sabemos nada (RN-A06).
func TestTiposDeProtectorPreservaElNulo(t *testing.T) {
	if got := tiposDeProtector(nil); got != nil {
		t.Errorf("nil tiene que seguir siendo NULL en la columna, llego %#v", got)
	}
	if got := tiposDeProtector([]uint32{}); got == nil {
		t.Error("la lista vacia NO es nula: es un arreglo vacio")
	}
	if got := tiposDeProtector([]uint32{3, 8}); got == nil {
		t.Error("los tipos tienen que llegar al driver")
	}
}
