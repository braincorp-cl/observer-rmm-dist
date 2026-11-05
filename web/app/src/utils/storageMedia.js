// Feature 055 · la traducción de los códigos crudos del medio.
//
// Vive en la consola y no en el servidor, por RN-04: el backend transporta el
// número que entrega el sistema sin interpretarlo, y congelar una etiqueta
// nuestra en la base obligaría a migrar datos cada vez que cambie el texto.

// Un código que no conocemos NO se pinta como un hueco: se muestra tal cual,
// entre paréntesis, para que quien lo vea pueda buscarlo. Inventar "Desconocido"
// a secas perdería el único dato que hay.
function etiqueta(t, prefijo, codigo) {
  if (codigo === null || codigo === undefined) {
    return t(`${prefijo}.unknown`);
  }
  const clave = `${prefijo}.${codigo}`;
  const texto = t(clave);
  return texto === clave ? `${t(`${prefijo}.unknown`)} (${codigo})` : texto;
}

export function mediaTypeLabel(t, codigo) {
  return etiqueta(t, "storageMedia.mediaType", codigo);
}

export function busTypeLabel(t, codigo) {
  return etiqueta(t, "storageMedia.busType", codigo);
}

export function selfEncryptingLabel(t, codigo) {
  return etiqueta(t, "storageMedia.selfEncrypting", codigo);
}

// El color del veredicto. Llegaba del merge con la paleta CRUDA de la v1 —seis
// colores de Quasar, teal incluido— y en la v2 el teal es el color de la acción
// (UI-N03/D05): un badge teal se lee como algo que se puede pinchar.
//
// 🔑 El color lleva la SEVERIDAD y el rótulo lleva el veredicto concreto, así
// que no hacen falta seis colores: dos veredictos pueden compartir uno cuando el
// texto los distingue. "Purga remota" y "Purga con imagen en vivo" comparten
// `positive` porque la severidad es la misma —la categoría más alta ES
// alcanzable— y lo que cambia es la vía, que es justo lo que dice el rótulo.
//
// Lo que NO puede pasar (RN-02): que "sin dato" y "sin categoría alcanzable"
// compartan color. Son dos cosas distintas y pintarlas igual las fundiría en
// pantalla aunque el backend las separe. Acá quedan en los dos extremos — gris
// neutro contra `negative`.
//
// Mismo patrón que `stateColorMap` en DiskEncryptionView: un mapa a los colores
// semánticos del tema, no un switch con nombres de la paleta de Quasar.
const verdictColorMap = {
  // La categoría más alta es alcanzable: sin problema de baja.
  purge_remote: "positive",
  purge_live_image: "positive",
  // Sólo Clear: alcanzable pero de menor garantía, y la decisión lo tiene que
  // tomar en cuenta.
  clear_remote: "warning",
  // Medio virtual: la pregunta no aplica a este disco, el medio real está en
  // otra parte (ver `overwriteIsDefensible`). Es una nota, no un incumplimiento.
  virtual_media: "info",
  // Ninguna categoría alcanzable: el caso que manda a destrucción física.
  no_category: "negative",
  // "sin dato": gris, nunca rojo. Un equipo del que no sabemos nada no es un
  // incumplidor.
  no_data: "grey",
};

export function verdictColor(veredicto) {
  return verdictColorMap[veredicto] ?? "grey";
}

// La capacidad legible. Los bytes son el dato; el redondeo es cortesía.
export function capacityLabel(bytes) {
  if (bytes === null || bytes === undefined || bytes <= 0) return "";
  const gb = bytes / 1_000_000_000;
  return gb >= 1000
    ? `${(gb / 1000).toFixed(2)} TB`
    : `${Math.round(gb)} GB`;
}

// 🔑 La señal que decide si la consola puede advertir sobre una sobrescritura.
// Tres respuestas, no dos: sí, no, y no se sabe. La tercera es la que impide
// que el silencio se lea como aprobación (RN-02).
//
// Recibe el DISCO de sistema, no la fila: la vista de flota lo trae como
// `fila.system_disk` y el detalle del equipo dentro de `media[]`, y haciéndola
// pedir la fila sólo servía para uno de los dos. Tenerla en un solo lugar es el
// punto — el diálogo de borrado traía su propia copia de esta regla, con el
// mismo defecto, y una copia que nadie mira no se arregla cuando la otra sí.
//
// 🪤 No alcanza con el código del medio: un disco de hipervisor se declara «de
// platos» ante el sistema operativo —VMware llega con medio 3 y bus de disco
// real, medido el 2026-11-02— y sobrescribirlo no toca el medio real, que está
// en otra parte. `is_virtual` viene DERIVADO del servidor (bus + identidad del
// dispositivo); acá sólo se traduce el código, que es lo que a la consola le
// toca (RN-04).
export function overwriteIsDefensible(disco) {
  if (!disco || disco.media_type_code === null || disco.media_type_code === undefined) {
    return null;
  }
  return disco.media_type_code === 3 && disco.is_virtual === false;
}
