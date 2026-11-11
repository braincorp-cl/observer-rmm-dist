// Censo congelado de V2-G09: todo .vue del diff de release/v2 contra main tiene
// que figurar en LAS DOS listas del gate de i18n.
//
// Por que existe: el gate `lint:i18n` ENUMERA archivos, en dos sitios que no se
// hablan -el override de .eslintrc.js y el propio script de package.json-. Un
// .vue nuevo no aparece en ninguno y el gate no se queja: da verde sobre un
// archivo que nunca mira. La pasada global de T051 (2026-11-11) midio 6
// ausencias en el override y 3 en el script, despues de 19 corridas de gauntlet
// sin que nadie lo notara, porque ningun comando lo comprobaba.
//
// 🔑 La guarda que de verdad importa: si no se puede calcular el diff, este test
// FALLA. Un censo que devuelve lista vacia y pasa es el cero silencioso que
// perseguimos: seria indistinguible de «todo esta en las listas».
import { describe, it, expect } from "vitest";
import { execFileSync } from "node:child_process";
import { readFileSync } from "node:fs";
import { fileURLToPath } from "node:url";
import { dirname, resolve } from "node:path";

const APP = resolve(dirname(fileURLToPath(import.meta.url)), "../..");

function git(...args) {
  return execFileSync("git", ["-C", APP, ...args], {
    encoding: "utf8",
    stdio: ["ignore", "pipe", "ignore"],
  }).trim();
}

// El piso del control positivo. El rediseno de la v2 toca mas de cien .vue; si
// el censo devuelve menos que esto, lo que fallo es la MEDICION, no el producto.
const PISO = 50;

describe("V2-G09 · censo de las dos listas del gate de i18n", () => {
  let vue = null;
  let fallo = null;

  try {
    const base = git("merge-base", "HEAD", "origin/main");
    // `--relative` es obligatorio: sin el, git devuelve las rutas relativas a la
    // RAIZ del repo (web/app/src/...) y las dos listas guardan src/..., asi que
    // ningun archivo casaria y el test fallaria entero por un prefijo.
    vue = git("diff", "--name-only", "--relative", base, "HEAD", "--", "src")
      .split("\n")
      .map((l) => l.trim())
      .filter((l) => l.endsWith(".vue"));
  } catch (e) {
    fallo = e.message;
  }

  it("el censo se pudo medir (sin esto, cualquier verde es ciego)", () => {
    expect(fallo, `no se pudo calcular el diff contra origin/main: ${fallo}`).toBeNull();
    expect(vue).not.toBeNull();
    expect(
      vue.length,
      `el diff devolvio ${vue?.length} .vue, por debajo del piso de ${PISO}: ` +
        "la medicion esta rota (¿falta `git fetch origin main`? ¿clon shallow?)",
    ).toBeGreaterThanOrEqual(PISO);
  });

  it("cada .vue del diff figura en el override de .eslintrc.js", () => {
    const eslintrc = readFileSync(resolve(APP, ".eslintrc.js"), "utf8");
    const faltan = vue.filter((f) => !eslintrc.includes(f));
    expect(faltan, `faltan en el override de .eslintrc.js:\n  ${faltan.join("\n  ")}`).toEqual([]);
  });

  it("cada .vue del diff figura en el script lint:i18n de package.json", () => {
    const pkg = JSON.parse(readFileSync(resolve(APP, "package.json"), "utf8"));
    const script = pkg.scripts["lint:i18n"];
    expect(script, "no existe el script lint:i18n").toBeTruthy();
    const faltan = vue.filter((f) => !script.includes(f));
    expect(faltan, `faltan en el script lint:i18n:\n  ${faltan.join("\n  ")}`).toEqual([]);
  });

  it("control negativo: un .vue inventado NO figura en ninguna lista", () => {
    const inventado = "src/components/__no_existe_g09__.vue";
    const eslintrc = readFileSync(resolve(APP, ".eslintrc.js"), "utf8");
    const pkg = JSON.parse(readFileSync(resolve(APP, "package.json"), "utf8"));
    expect(eslintrc.includes(inventado)).toBe(false);
    expect(pkg.scripts["lint:i18n"].includes(inventado)).toBe(false);
  });
});
