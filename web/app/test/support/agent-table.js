/* eslint-env node */

// Montaje de src/components/AgentTable.vue en jsdom.
//
// AgentTable es un componente de Options API con cinco dependencias de entorno:
// vuex (mapState + commits), vue-i18n (los rótulos y el aria-label), el router
// ($router.push al espacio de trabajo), el `provide` de refreshDashboard y los
// plugins de Quasar ($q.loading / $q.notify / $q.dialog). Se le dan los cinco
// de verdad —catálogos i18n reales incluidos— y solo se finge lo que cruza la
// frontera del proceso: el router y axios.

import { mount } from "@vue/test-utils";
import { vi } from "vitest";
import { createStore } from "vuex";
import { createI18n } from "vue-i18n";
import messages from "@/i18n";
import AgentTable from "@/components/AgentTable.vue";

// Un equipo cualquiera de la flota, con lo justo para que la fila pinte.
export const UN_EQUIPO = {
  id: 1,
  agent_id: "3a7f1e2c-0000-4000-8000-000000000001",
  hostname: "EQUIPO-01",
  plat: "windows",
  client_name: "Cliente Uno",
  site_name: "Sitio Uno",
  description: "",
  status: "online",
  alert_template: null,
  checks: {
    total: 0,
    passing: 0,
    failing: 0,
    warning: 0,
    info: 0,
    has_failing_checks: false,
  },
  pending_actions_count: 0,
  last_seen: 1762300000,
  needs_reboot: false,
  italic: false,
  logged_username: "usuario",
  boot_time: 1762200000,
  patches_pending: false,
  monitoring_type: "server",
  maintenance_mode: false,
  overdue_text_alert: false,
  overdue_email_alert: false,
  overdue_dashboard_alert: false,
};

// Solo la columna del hostname: es la que se prueba, y menos columnas es menos
// DOM por montaje. `columns` y `visibleColumns` son props del componente, así
// que cada prueba puede pedir las que necesite.
export const COLUMNA_HOSTNAME = {
  name: "hostname",
  label: "Equipo",
  field: "hostname",
  align: "left",
  sortable: true,
};

export function mountAgentTable({
  agents = [UN_EQUIPO],
  columns = [COLUMNA_HOSTNAME],
  visibleColumns = ["hostname"],
  state = {},
  locale = "es",
} = {}) {
  const commit = vi.fn();
  const store = createStore({
    state: {
      tableHeight: "600px",
      dash_info_color: "info",
      dash_positive_color: "positive",
      dash_negative_color: "negative",
      dash_warning_color: "warning",
      // Sin acción de doble clic configurada: rowDoubleClicked hace su parte
      // (cancelar el temporizador y marcar la fila) sin abrir ningún diálogo.
      agentDblClickAction: "",
      agentUrlAction: null,
      selectedRow: null,
      agentTableLoading: false,
      ...state,
    },
    getters: { formatDate: () => (value) => String(value) },
    mutations: {
      setActiveRow: () => {},
      setAgentPlatform: () => {},
    },
    // Las mutaciones reales viven en el store de la app; acá solo interesa que
    // el componente las emita, así que se registran por suscripción.
    plugins: [(s) => s.subscribe((m) => commit(m.type, m.payload))],
  });

  const i18n = createI18n({
    legacy: false,
    globalInjection: true,
    locale,
    fallbackLocale: "en",
    messages,
  });

  const push = vi.fn();
  const axiosPut = vi.fn(() => Promise.resolve({ data: {} }));

  const wrapper = mount(AgentTable, {
    props: { agents, columns, search: "", visibleColumns },
    global: {
      plugins: [store, i18n],
      provide: { refreshDashboard: vi.fn() },
      // El menú de acciones del clic derecho no es lo que se prueba y su
      // setup() pide los scripts favoritos al backend en cuanto se monta
      // (composables/useAgentActions.js:113). Se corta acá.
      stubs: { AgentActionMenu: true },
      mocks: {
        $router: { push },
        $axios: {
          put: axiosPut,
          get: vi.fn(() => Promise.resolve({ data: {} })),
        },
      },
    },
    attachTo: document.body,
  });

  return { wrapper, push, commit, axiosPut };
}

// QTable con `virtual-scroll` no pinta ninguna fila hasta que corre su
// `onVirtualScrollEvt`, que va con debounce de 35 ms
// (quasar/src/components/virtual-scroll/use-virtual-scroll.js:693). Con
// temporizadores falsos hay que adelantarlos a mano o el <tbody> queda vacío.
export async function esperarFilas() {
  await vi.advanceTimersByTimeAsync(60);
}

// La ventana de 046 F4 / RN-03: un clic navega, pero recién a los 250 ms, para
// que un doble clic pueda cancelarlo (AgentTable.vue:593-599).
export const VENTANA_DOBLE_CLIC_MS = 250;
