/**
 * Tokens del servidor del módulo Erase, traducidos sin pintarlos crudos.
 *
 * El backend manda tokens (`internal_reuse`, `NOT_VERIFIED`) y la consola tiene
 * que mostrarlos en el idioma del usuario. El patrón inline del módulo
 * —`t(\`erase.kind.${valor}\`)`— alcanza mientras el token exista en el catálogo,
 * pero acá no siempre existe: un certificado **v1**, emitido antes de la feature
 * 053, trae `verification_result: "PASS"` y valores que ninguna clave cubre.
 * Sin respaldo, vue-i18n devuelve la ruta de la clave y el usuario vería
 * `erase.verificationResult.ALGO` en una celda.
 *
 * De ahí el respaldo al valor crudo: mostrar `PASS` es feo, mostrar
 * `erase.verificationResult.PASS` es un error visible.
 */
import { i18n } from "@/boot/i18n";

function traducir(seccion: string, valor: string | null | undefined): string {
  const token = (valor ?? "").trim();
  if (!token) return "";
  const clave = `erase.${seccion}.${token}`;
  // `te` pregunta si la clave existe; sin esto `t` devolvería la ruta misma.
  return i18n.global.te(clave) ? i18n.global.t(clave) : token;
}

/** Destino final del medio (`MediaDisposition`). */
export function labelDisposition(valor?: string | null): string {
  return traducir("disposition", valor);
}

/** Cómo se acreditó la destrucción (`DestructionVerification`). */
export function labelVerificationMethod(valor?: string | null): string {
  return traducir("verificationMethod", valor);
}

/** Veredicto de verificación (`PASS` / `NOT_VERIFIED`, y lo que traiga un v1). */
export function labelVerificationResult(valor?: string | null): string {
  return traducir("verificationResult", valor);
}
