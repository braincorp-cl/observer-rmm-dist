// 050 / V2-S06: las cinco pantallas de acceso siguen la maqueta.
//
// Este spec vigila los DOS modos de fallo que ya ocurrieron, no una idea
// abstracta de "está bonito":
//
// 1. 🪤 Una pantalla del flujo de acceso que NO usa la maqueta. Pasó de verdad:
//    T049 restiló la tarjeta de la v1 en login/setup/totp y no tocó las otras
//    dos. `SessionExpired.vue` tenía CERO commits en toda la rama y `NotFound`
//    uno solo, que era la prop `publicContext` del cableado de T047. El
//    gauntlet lo midió: 0,12–0,17 % de diferencia con la v1. Un `grep` del
//    import no basta —se puede importar y no usar—, así que se monta cada vista
//    y se exige la franja de marca EN EL DOM RENDERIZADO.
//
// 2. 🪤 El 404 imponiendo el chrome de acceso DENTRO del portal público.
//    `VerifyCertificateView` lo monta con `public-context` cuando el tenant
//    tiene el portal apagado: ahí la franja significaría dos marcas en pantalla
//    y una página completa embebida en otra. Es el fallo opuesto al 1, y una
//    regla que sólo mirara "todas llevan franja" lo provocaría.
import { describe, it, expect, vi, beforeEach } from "vitest";
import { mount } from "@vue/test-utils";
import { createI18n } from "vue-i18n";
import { Quasar } from "quasar";

import es from "@/i18n/es.json";
import en from "@/i18n/en.json";
import AccessLayout from "@/components/access/AccessLayout.vue";
import NotFound from "@/views/NotFound.vue";

// Las vistas del flujo traen store, router y websocket; acá sólo interesa el
// chrome, así que se monta el layout tal como cada una lo declara.
vi.mock("@/stores/auth", () => ({ useAuthStore: () => ({ logout: vi.fn() }) }));
vi.mock("@/websocket/websocket", () => ({
  useDashWSConnection: () => ({ close: vi.fn() }),
}));

function i18n() {
  return createI18n({
    legacy: false,
    locale: "es",
    fallbackLocale: "en",
    messages: { es, en },
  });
}

function montar(componente, props = {}) {
  return mount(componente, {
    props,
    global: {
      plugins: [Quasar, i18n()],
      stubs: {
        "router-link": true,
        QBtn: { template: "<button><slot /></button>" },
        QIcon: true,
        QTooltip: true,
      },
      mocks: { $router: { push: vi.fn() } },
    },
  });
}

describe("V2-S06 · la maqueta de acceso", () => {
  describe("AccessLayout rinde las piezas que el criterio nombra", () => {
    let w;
    beforeEach(() => {
      w = montar(AccessLayout, {
        heading: "Ingresar",
        footnote: "pie de prueba",
      });
    });

    it("tiene los DOS paneles, no una tarjeta centrada", () => {
      expect(w.find(".obs-access__brand").exists()).toBe(true);
      expect(w.find(".obs-access__panel").exists()).toBe(true);
    });

    it("la franja lleva marca gráfica, wordmark, titular y bajada", () => {
      expect(w.find(".obs-access__mark-img").exists()).toBe(true);
      expect(w.find(".obs-access__wordmark").text()).toBe("Observer RMM");
      expect(w.find(".obs-access__headline").text()).toBe(es.access.headline);
      expect(w.find(".obs-access__sub").text()).toBe(es.access.subhead);
    });

    it("el panel lleva encabezado propio y pie", () => {
      expect(w.find(".obs-access__heading").text()).toBe("Ingresar");
      expect(w.find(".obs-access__foot").text()).toBe("pie de prueba");
    });
  });

  describe("las cinco pantallas del criterio usan la maqueta", () => {
    // Importarlas de forma perezosa: algunas tiran de router/store al evaluar.
    const VISTAS = [
      ["LoginView", () => import("@/views/LoginView.vue")],
      ["InitialSetup", () => import("@/views/InitialSetup.vue")],
      ["TOTPSetup", () => import("@/views/TOTPSetup.vue")],
      ["SessionExpired", () => import("@/views/SessionExpired.vue")],
      ["NotFound", () => import("@/views/NotFound.vue")],
    ];

    for (const [nombre, cargar] of VISTAS) {
      it(`${nombre} declara AccessLayout en su plantilla`, async () => {
        const mod = await cargar();
        const def = mod.default;
        // El componente puede registrarlo por `components` (Options API) o
        // resolverlo del ámbito de `<script setup>`. En los dos casos el
        // render lo referencia, así que se busca en la fuente compilada.
        const fuente = (def.render || def.setup || "").toString();
        const registrado =
          (def.components && "AccessLayout" in def.components) ||
          fuente.includes("AccessLayout");
        expect(
          registrado,
          `${nombre} no usa AccessLayout: una pantalla de acceso fuera de la maqueta`,
        ).toBe(true);
      });
    }
  });

  describe("🪤 el 404 embebido en el portal público NO lleva el chrome", () => {
    it("con public-context no hay franja de marca", () => {
      const w = montar(NotFound, { publicContext: true });
      expect(
        w.find(".obs-access__brand").exists(),
        "el portal público mostraría dos marcas y una página dentro de otra",
      ).toBe(false);
      expect(w.find(".obs-nf--embebido").exists()).toBe(true);
    });

    it("con public-context tampoco va el botón «Volver»", () => {
      // Una página pública no tiene a dónde volver: "/" es un rebote al acceso.
      const w = montar(NotFound, { publicContext: true });
      expect(w.find("button").exists()).toBe(false);
    });

    it("sin la prop (404 de la consola) sí lleva la maqueta y la salida", () => {
      const w = montar(NotFound);
      expect(w.find(".obs-access__brand").exists()).toBe(true);
      expect(w.find("button").exists()).toBe(true);
    });
  });
});
