// Feature 051 · `node --test src/utils/coords.test.mjs` (la consola no tiene
// runner de JS; node:test viene con Node y no agrega dependencias).
import { test } from "node:test";
import assert from "node:assert/strict";
import { parseCoord, coordError } from "./coords.js";

test("coma o punto decimal dan el mismo número", () => {
  assert.equal(parseCoord("19,429449"), 19.429449);
  assert.equal(parseCoord("-99.205851"), -99.205851);
  assert.equal(parseCoord(" -99,205851 "), -99.205851);
  assert.equal(parseCoord("+19"), 19);
  assert.equal(parseCoord(19.4), 19.4);
});

test("vacío es «sin coordenada»", () => {
  for (const v of ["", "   ", null, undefined])
    assert.equal(parseCoord(v), null);
});

test("un texto que no es número es NaN, nunca null", () => {
  for (const v of ["19,4x", "1e3", "19.429,449", "19,", ",5", "abc", "19 4"]) {
    assert.ok(Number.isNaN(parseCoord(v)), v);
  }
});

test("las dos con coma pasan la validación", () => {
  assert.equal(coordError("19,429449", "-99,205851", 90), null);
  assert.equal(coordError("-99,205851", "19,429449", 180), null);
});

test("un texto inválido es error aunque la pareja esté vacía", () => {
  assert.equal(coordError("19,4x", "", 90), "invalid");
  assert.equal(coordError("19,4x", "19,4x", 90), "invalid");
});

test("ambas o ninguna, rango y null island", () => {
  assert.equal(coordError("", "", 90), null);
  assert.equal(coordError("", "-99,2", 90), "invalid");
  assert.equal(coordError("91", "0,5", 90), "invalid");
  assert.equal(coordError("0", "0", 90), "nullIsland");
});
