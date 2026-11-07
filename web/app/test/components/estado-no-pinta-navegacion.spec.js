/* eslint-env node */

// 050 / V2-G05: el color de estado NO va en la superficie propia de un control
// de navegación. El criterio dice «rojo, ámbar y verde solo significan estado;
// el teal solo marca acción o navegación», y su enmienda del 2026-10-14 es
// literal sobre dónde se mira: «un número o una insignia de estado DENTRO de un
// control es estado y no viola; viola si la superficie propia del control, es
// decir su fondo, borde o rótulo, lleva color de estado».
//
// 🔴 Por qué existe este spec. En la 14.ª corrida del grupo, dos críticos con
// lentes distintas midieron lo mismo: en «Agregar plantilla de alerta» el
// rótulo de la pestaña del paso 1 salía rgb(242,90,95) en oscuro y
// rgb(197,40,45) en claro, o sea `--q-negative`, y lo mismo el punto y la línea
// de unión. La causa no era CSS nuestro: era `:error` en el `<q-step>`.
// `.q-stepper__tab--error` de Quasar pone `color: var(--q-negative)` en el TAB
// ENTERO, y el rótulo, el punto y la línea lo heredan por `currentColor`.
//
// 🔑 Y la lección de la corrida anterior, aplicada acá antes de medir: un
// arreglo en la página donde encontraste la clase no dice nada de los otros
// sitios de la misma clase. El censo por código dio CUATRO, no uno:
//
//   src/components/modals/alerts/AlertTemplateForm.vue   paso 1
//   src/components/tasks/AutomatedTaskForm.vue           pasos 1, 2 y 3
//
// 🪤 De esos cuatro, uno no podía encenderse nunca: `isValidStep2` sólo se
// asignaba `true`. Era, además de ilegal por color, código que nadie leía.
//
// Lo que se vigila, en este orden:
//   1. el MECANISMO, montado: que `error` en un `q-step` sí pinta el tab. Sin
//      esto el censo de abajo sería una prohibición de una cadena de texto, no
//      la prueba de una regla;
//   2. el CENSO: ningún `q-step` del árbol trae `error`, `error-color` ni
//      `error-icon`;
//   3. el canal PERMITIDO, congelado: los `:error` que viven en un campo
//      (`q-field--error`, la excepción declarada) siguen ahí. Un barrido futuro
//      que borre «todos los :error» tiene que fallar acá;
//   4. el canal de REPOSICIÓN de AlertTemplateForm: el aviso que se perdió al
//      quitar el `:error` sale ahora del slot `message`, que es un mensaje y no
//      un control, y el campo del nombre conserva su `:rules`.
import { describe, it, expect, beforeAll } from "vitest";
import { mount } from "@vue/test-utils";
import { readFile } from "node:fs/promises";
import { dirname, resolve } from "node:path";
import { fileURLToPath } from "node:url";
import { leerVue, etiquetasDeApertura } from "../support/vue-sources.js";

// Quasar ya viene instalado en todo montaje por test/setup/quasar.js: pasar el
// plugin otra vez avisa «Plugin has already been applied».
//
// La ruta NO se arma con URL relativa: ver el comentario de
// test/support/vue-sources.js. Vite reescribe esa forma y deja de apuntar al
// archivo; se resuelve desde `import.meta.url` pelado.
const APP = resolve(dirname(fileURLToPath(import.meta.url)), "../..");

// Censo congelado de los `:error` que SÍ son legales porque viven en un campo:
// ahí el color de estado es `q-field--error`, que es la excepción (c) del
// criterio, aprobada por el usuario el 2026-10-16.
const ERROR_EN_CAMPO = {
  "src/components/agents/remotebg/RegistryValueModal.vue": "q-input",
  "src/views/EraseCertificatesView.vue": "q-input",
  "src/ee/reporting/components/ReportTemplateForm.vue": "q-input",
};

let vue;
beforeAll(async () => {
  vue = await leerVue();
});

describe("mecanismo: `error` en un q-step pinta el tab, no una insignia", () => {
  const montar = (error) =>
    mount(
      {
        props: { error: Boolean },
        template: `
          <q-stepper :model-value="1">
            <q-step :name="1" title="Uno" icon="settings" :error="error" />
          </q-stepper>`,
      },
      { props: { error } },
    );

  it("con error, el TAB lleva la clase de negativo", () => {
    const w = montar(true);
    expect(w.find(".q-stepper__tab--error").exists()).toBe(true);
    // El rótulo no tiene color propio: hereda el del tab. Por eso la violación
    // se ve en el rótulo aunque la clase esté en el ancestro.
    expect(w.find(".q-stepper__tab--error .q-stepper__title").exists()).toBe(
      true,
    );
  });

  // 🪤 Control negativo del mecanismo: sin `error` la clase no aparece. Sin
  // esta mitad, el test de arriba pasaría incluso si Quasar pusiera la clase
  // siempre, y entonces el censo no estaría arreglando nada.
  it("sin error, la clase no aparece", () => {
    const w = montar(false);
    expect(w.find(".q-stepper__tab--error").exists()).toBe(false);
    expect(w.find(".q-stepper__title").exists()).toBe(true);
  });
});

describe("censo: ningún paso de stepper pinta su propia superficie", () => {
  it("ningún q-step del árbol trae error, error-color ni error-icon", () => {
    const hallados = [];
    for (const { ruta, fuente } of vue) {
      for (const { etiqueta, linea } of etiquetasDeApertura(fuente, "q-step")) {
        if (/(^|\s)(:|v-bind:)?error(-color|-icon)?\s*=/.test(etiqueta)) {
          hallados.push(`${ruta}:${linea}`);
        }
      }
    }
    expect(hallados).toEqual([]);
  });

  it("el censo mira de verdad: hay steppers que censar", () => {
    const pasos = vue.reduce(
      (n, { fuente }) => n + etiquetasDeApertura(fuente, "q-step").length,
      0,
    );
    // 5 en AlertTemplateForm + 3 en AutomatedTaskForm. Si este número cae a 0
    // el censo de arriba pasaría por vacío, que es el modo de fallo silencioso
    // de toda prueba de ausencia.
    expect(pasos).toBeGreaterThanOrEqual(8);
  });
});

describe("el canal permitido sigue en pie", () => {
  it("los :error de campo (q-field--error, excepción declarada) no se tocaron", () => {
    const conError = {};
    for (const { ruta, fuente } of vue) {
      if (
        /(^|\s)(:|v-bind:)?error\s*=/.test(
          fuente.replace(/<!--[\s\S]*?-->/g, " "),
        )
      ) {
        // Se anota el componente que lo lleva, no sólo el archivo: lo que
        // distingue el caso legal del ilegal es la etiqueta, no la ruta.
        for (const comp of ["q-input", "q-select", "q-field"]) {
          if (
            etiquetasDeApertura(fuente, comp).some((t) =>
              /(^|\s)(:|v-bind:)?error\s*=/.test(t.etiqueta),
            )
          ) {
            conError[ruta] = comp;
          }
        }
      }
    }
    expect(conError).toEqual(ERROR_EN_CAMPO);
  });
});

describe("AlertTemplateForm: el aviso se repuso fuera del control", () => {
  let fuente;
  beforeAll(async () => {
    fuente = await readFile(
      resolve(APP, "src/components/modals/alerts/AlertTemplateForm.vue"),
      "utf8",
    );
  });

  it("el aviso sale del slot `message` y con la misma condición de antes", () => {
    expect(fuente).toMatch(
      /<template\s+v-if="!template\.name && step > 1"\s+#message>/,
    );
    expect(fuente).toContain("alertTemplate.generalIncomplete");
  });

  it("el campo del nombre conserva su regla, que es el canal del criterio", () => {
    expect(fuente).toMatch(/v-model="template\.name"/);
    expect(fuente).toMatch(/alertTemplate\.required/);
  });

  it("el mensaje existe en los dos idiomas", async () => {
    for (const idioma of ["es", "en"]) {
      const d = JSON.parse(
        await readFile(resolve(APP, `src/i18n/${idioma}.json`), "utf8"),
      );
      expect(d.alertTemplate.generalIncomplete).toBeTruthy();
    }
  });

  // 🪤 Mi propia suposición puesta a prueba: que el slot `message` de QStepper
  // existe y se renderiza FUERA del tab. Si Quasar lo cambiara de lugar, el
  // aviso podría volver a caer dentro del control sin que nadie lo note.
  it("el slot `message` se renderiza fuera del tab del paso", () => {
    const w = mount({
      template: `
        <q-stepper :model-value="2">
          <template #message><div class="aviso">falta el nombre</div></template>
          <q-step :name="1" title="Uno" icon="settings" />
          <q-step :name="2" title="Dos" icon="warning" />
        </q-stepper>`,
    });
    const aviso = w.find(".aviso");
    expect(aviso.exists()).toBe(true);
    expect(aviso.element.closest(".q-stepper__tab")).toBe(null);
  });
});
