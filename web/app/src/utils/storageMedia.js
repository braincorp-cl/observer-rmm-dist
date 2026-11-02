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

// El color del veredicto. Lo que importa acá es que "sin dato" y "sin categoría
// alcanzable" NO compartan color: son dos cosas distintas (RN-02), y pintarlas
// igual las fundiría en la pantalla aunque el backend las separe.
export function verdictColor(veredicto) {
  switch (veredicto) {
    case "purge_remote":
      return "green";
    case "purge_live_image":
      return "teal";
    case "clear_remote":
      return "blue";
    case "virtual_media":
      return "purple";
    case "no_category":
      return "orange";
    default:
      // "sin dato": gris, nunca rojo. Un equipo del que no sabemos nada no es
      // un incumplidor.
      return "grey";
  }
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
