import { useAuthStore } from "@/stores/auth";

const routes = [
  {
    path: "/",
    name: "MainLayout",
    component: () => import("@/layouts/MainLayout.vue"),
    children: [
      {
        // 050 (T026): los gestores principales son páginas, no diálogos.
        path: "scripts/:library?",
        name: "Scripts",
        component: () => import("@/views/ScriptsView.vue"),
        meta: {
          requireAuth: true,
        },
      },
      {
        // La política y la sección (chequeos/tareas) van en la URL.
        path: "automation/:policy?/:section?",
        name: "Automation",
        component: () => import("@/views/AutomationView.vue"),
        meta: {
          requireAuth: true,
        },
      },
      {
        path: "alerts",
        name: "Alerts",
        component: () => import("@/views/AlertsView.vue"),
        meta: {
          requireAuth: true,
        },
      },
      {
        // 046 (dirección 1c): la sección del espacio de trabajo va en la URL.
        path: "agents/:agent_id/:section?",
        name: "Agent",
        component: () => import("@/views/AgentWorkspace.vue"),
        meta: {
          requireAuth: true,
        },
      },
      {
        // Feature 030 · módulo de nivel superior, hermano del Dashboard. No es
        // un diálogo: un caso de equipo perdido se sigue en el tiempo y tiene
        // que poder compartirse por URL.
        path: "lost-equipment",
        name: "LostEquipment",
        component: () => import("@/views/LostEquipmentView.vue"),
        meta: {
          requireAuth: true,
        },
      },
      {
        // Feature 049-E · monitoreo en vivo sin video: última captura de cada
        // equipo monitoreado y botón para pedir una del momento.
        path: "activity-live",
        name: "ActivityLive",
        component: () => import("@/views/ActivityLiveView.vue"),
        meta: {
          requireAuth: true,
        },
      },
      {
        // Feature 037 · panel de cumplimiento de cifrado, hermano del Dashboard
        // y de Equipos perdidos. Es una vista de flota que se comparte por URL,
        // no un diálogo.
        path: "disk-encryption",
        name: "DiskEncryption",
        component: () => import("@/views/DiskEncryptionView.vue"),
        meta: {
          requireAuth: true,
        },
      },
      {
        // Feature 039 · Observer Erase · reportería de certificados de borrado y
        // custodia de activos (Bloques C+D). Vista de nivel superior, hermana del
        // Dashboard: la reportería se comparte por URL, no es un diálogo.
        path: "erase-certificates",
        name: "EraseCertificates",
        component: () => import("@/views/EraseCertificatesView.vue"),
        props: { mode: "certificates" },
        meta: {
          requireAuth: true,
        },
      },
      {
        // 050 (V2-S02): custodia de activos (Bloque D) con ruta propia; antes
        // era la segunda pestaña de /erase-certificates.
        path: "erase-intake",
        name: "EraseIntake",
        component: () => import("@/views/EraseCertificatesView.vue"),
        props: { mode: "intake" },
        meta: {
          requireAuth: true,
        },
      },
      {
        // Feature 039 · Observer Erase · gobernanza de las órdenes de borrado
        // (B0). No crea nada destructivo (Bloque A GATED): confirma a dos
        // personas y gobierna la ventana de arrepentimiento.
        path: "erase-orders",
        name: "EraseOrders",
        component: () => import("@/views/WipeOrdersView.vue"),
        meta: {
          requireAuth: true,
        },
      },
      {
        path: "",
        name: "Dashboard",
        component: () => import("@/views/DashboardView.vue"),
        meta: {
          requireAuth: true,
        },
      },
    ],
  },
  {
    path: "/setup",
    name: "InitialSetup",
    component: () => import("@/views/InitialSetup.vue"),
    meta: {
      requireAuth: true,
    },
  },
  {
    path: "/totp_setup",
    name: "TOTPSetup",
    component: () => import("@/views/TOTPSetup.vue"),
    meta: {
      requireAuth: true,
    },
  },
  {
    path: "/takecontrol/:agent_id",
    name: "TakeControl",
    component: () => import("@/views/TakeControl.vue"),
    meta: {
      requireAuth: true,
    },
  },
  {
    path: "/webvnc/:agent_id/:port",
    name: "VNC",
    component: () => import("@/views/WebVNC.vue"),
    meta: {
      requireAuth: true,
    },
  },
  {
    path: "/webterm",
    name: "WebTerm",
    component: () => import("@/views/WebTerminal.vue"),
    meta: {
      requireAuth: true,
    },
  },
  {
    // BrainCorp · fix — vista "Abrir reporte" del Historial de reportes.
    // openReportHistory() hace window.open("/reports/history/:id?..."); sin esta
    // ruta caía en el catchAll → NotFound (404). Va antes de "/reports/:id" para
    // que el segmento estático "history" tenga prioridad.
    path: "/reports/history/:id",
    name: "ReportHistoryView",
    component: () => import("@/ee/reporting/views/ReportHistoryView.vue"),
    props: (route) => ({
      id: Number(route.params.id),
      format: route.query.format,
    }),
    meta: {
      requireAuth: true,
    },
  },
  {
    // BrainCorp · fix — la vista de "Abrir reporte" (PDF/HTML) del Gestor de
    // Reportes. openReport() hace window.open("/reports/:id?..."); sin esta ruta
    // caía en el catchAll → NotFound (404). Es pantalla completa (iframe del
    // reporte), por eso va al nivel superior, no dentro de MainLayout.
    path: "/reports/:id",
    name: "ReportView",
    component: () => import("@/ee/reporting/views/ReportView.vue"),
    props: (route) => ({
      id: Number(route.params.id),
      format: route.query.format,
      dependsOn: route.query.dependsOn ? JSON.parse(route.query.dependsOn) : [],
      dependencies: route.query.dependencies
        ? JSON.parse(route.query.dependencies)
        : {},
    }),
    meta: {
      requireAuth: true,
    },
  },
  {
    path: "/remotebackground/:agent_id",
    name: "RemoteBackground",
    component: () => import("@/views/RemoteBackground.vue"),
    meta: {
      requireAuth: true,
    },
  },
  {
    path: "/login",
    name: "Login",
    component: () => import("@/views/LoginView.vue"),
    meta: {
      requiresVisitor: true,
    },
  },
  {
    path: "/expired",
    name: "SessionExpired",
    component: () => import("@/views/SessionExpired.vue"),
    beforeEnter: (_, from) => {
      const auth = useAuthStore();
      auth.next = from.fullPath;
    },
  },
  // SSO descartado (ADR-010, 2026-06-17): ruta de callback OAuth eliminada (módulo ee/sso vaciado).
  { path: "/:catchAll(.*)", component: () => import("@/views/NotFound.vue") },
];

export default routes;
