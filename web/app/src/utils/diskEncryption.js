// Feature 037 · traducción de los códigos crudos de WMI (RN-A05).
//
// El backend guarda y transporta los números de `Win32_EncryptableVolume` SIN
// interpretarlos: el único que compara un código es la persistencia, y sólo el
// de protección. La lectura en texto legible es cosa de la consola, y vive
// EN UN SOLO LUGAR —acá— para que el panel de flota y el detalle del agente no
// tengan dos tablas que un día divergen.
//
// Cada función recibe el `t` de vue-i18n en vez de importarlo: así sirve tanto
// en Composition API (useI18n) como en cualquier otro contexto, sin acoplarse a
// una instancia. Un código que no está en la tabla no se traga —se muestra el
// número con una marca de "desconocido"— porque un código nuevo de una versión
// futura de Windows es justo lo que no hay que esconder.

function traducir(t, prefijo, code) {
  if (code == null) return "";
  const clave = `diskEncryption.${prefijo}.${code}`;
  const texto = t(clave);
  // vue-i18n devuelve la clave misma cuando no existe: eso es el código
  // desconocido, y se muestra crudo con su marca en vez de un texto vacío.
  if (texto === clave) return t("diskEncryption.codeUnknown", { code });
  return texto;
}

// ProtectionStatus: 0 = apagada, 1 = encendida, 2 = desconocida (WMI).
export function protectionStatusLabel(t, code) {
  return traducir(t, "protection", code);
}

// ConversionStatus (GetConversionStatus): 0 descifrado, 1 cifrado,
// 2 cifrando, 3 descifrando, 4 cifrado en pausa, 5 descifrado en pausa.
export function conversionStatusLabel(t, code) {
  return traducir(t, "conversion", code);
}

// EncryptionMethod: 0 ninguno … 6 XTS-AES-128, 7 XTS-AES-256.
export function encryptionMethodLabel(t, code) {
  return traducir(t, "method", code);
}

// VolumeType: 0 sistema, 1 datos fijos, 2 datos extraíbles.
export function volumeTypeLabel(t, code) {
  return traducir(t, "volumeType", code);
}
