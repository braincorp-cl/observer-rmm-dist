import { createStore } from "vuex";
import { Screen, Dark, LoadingBar } from "quasar";
import axios from "axios";
import { formatDate } from "@/utils/format";
import { applyLocale } from "@/boot/i18n";

export default function () {
  const Store = new createStore({
    state() {
      return {
        tree: [],
        agents: [],
        treeReady: false,
        selectedTree: "",
        selectedRow: null,
        agentPlatform: "windows",
        agentTableLoading: false,
        needrefresh: false,
        tokenExpired: false,
        refreshSummaryTab: false,
        tableHeight: "300px",
        tabHeight: "300px",
        showScriptTemplates: false,
        agentDblClickAction: "",
        agentUrlAction: null,
        defaultAgentTblTab: null,
        clientTreeSort: "alphafail",
        clientTreeSplitter: 20,
        noCodeSign: false,
        hosted: false,
        clearSearchWhenSwitching: false,
        currentVersion: null,
        latestVersion: null,
        dateFormat: "MMM-DD-YYYY - HH:mm",
        openAIIntegrationEnabled: false,
        dash_info_color: "info",
        dash_positive_color: "positive",
        dash_negative_color: "negative",
        dash_warning_color: "warning",
        run_cmd_placeholder_text: {
          cmd: "rmdir /S /Q C:\\Windows\\System32",
          powershell: "Remove-Item -Recurse -Force C:\\Windows\\System32",
          shell: "rm -rf --no-preserve-root /",
        },
        server_scripts_enabled: true,
        web_terminal_enabled: true,
        sso_enabled: false,
        block_local_user_logon: false,
        // Modo mantenimiento (feature 036): alimentan el banner global de
        // MainLayout. Vienen de /core/dashinfo/ ya filtrados por rol en el backend
        // — acá no se vuelve a filtrar ni se cuenta sobre `agents`, porque la tabla
        // puede venir acotada por el nodo del árbol seleccionado y el banner tiene
        // que contar la flota entera que el usuario sí puede ver.
        maintenanceCount: 0,
        maintenanceOldestSince: null,
      };
    },
    getters: {
      clientTreeSplitterModel(state) {
        return state.clientTreeSplitter;
      },
      selectedAgentId(state) {
        return state.selectedRow;
      },
      showScriptTemplates(state) {
        return state.showScriptTemplates;
      },
      allClientsSelected(state) {
        return !state.selectedTree;
      },
      formatDate: (state) => (date) => {
        if (!state.dateFormat) return formatDate(date);
        else return formatDate(date, state.dateFormat);
      },
    },
    mutations: {
      AGENT_TABLE_LOADING(state, visible) {
        state.agentTableLoading = visible;
      },
      setActiveRow(state, agent_id) {
        state.selectedRow = agent_id;
      },
      setAgentPlatform(state, agentPlatform) {
        state.agentPlatform = agentPlatform;
      },
      loadTree(state, treebar) {
        state.tree = treebar;
        state.treeReady = true;
      },
      destroySubTable(state) {
        state.selectedRow = null;
      },
      SET_REFRESH_NEEDED(state, action) {
        state.needrefresh = action;
      },
      SET_TOKEN_EXPIRED(state, action) {
        state.tokenExpired = action;
      },
      SET_SPLITTER(state, val) {
        // top toolbar is 50px. Filebar is 40px and agent filter tabs are 44px
        // 046 F1: sin la barra de menús (FileBar, 40 px) la tabla recupera ese alto.
        // 🪤 050 (V2-G15): los 78 venían de la v1 y el tablero de la v2 metió el
        // bloque de KPIs sobre la tabla, así que la cuenta sobraba: MEDIDO, la
        // tabla terminaba 59,7 px POR DEBAJO del borde inferior de la ventana a
        // 900, 1200 y 1400 de alto (constante, el mismo número en los tres), y
        // el contenedor de página sólo podía desplazar 109. Efecto real: al
        // tabular, 6 de las 91 paradas del tablero enfocaban filas FUERA de
        // pantalla — el anillo se dibujaba donde nadie lo veía. Los 150 son esos
        // 78 + 60 del bloque nuevo + 12 px de aire para que el anillo de la
        // ÚLTIMA fila quepa dentro de la ventana (el anillo son 4 px por fuera).
        state.tableHeight = `${Screen.height - 50 - 150 - val}px`;

        // q-tabs are 37px
        state.tabHeight = `${val - 37}px`;
      },
      SET_CLIENT_SPLITTER(state, val) {
        state.clientTreeSplitter = val;
      },
      setShowScriptTemplates(state, show) {
        state.showScriptTemplates = show;
      },
      SET_AGENT_DBLCLICK_ACTION(state, action) {
        state.agentDblClickAction = action;
      },
      SET_URL_ACTION(state, action) {
        state.agentUrlAction = action;
      },
      SET_DEFAULT_AGENT_TBL_TAB(state, tab) {
        state.defaultAgentTblTab = tab;
      },
      SET_CLIENT_TREE_SORT(state, val) {
        state.clientTreeSort = val;
      },
      SET_HOSTED(state, val) {
        state.hosted = val;
      },
      setClearSearchWhenSwitching(state, val) {
        state.clearSearchWhenSwitching = val;
      },
      setLatestVersion(state, val) {
        state.latestVersion = val;
      },
      setCurrentVersion(state, val) {
        state.currentVersion = val;
      },
      setAgents(state, agents) {
        state.agents = agents;
      },
      setRefreshSummaryTab(state, val) {
        state.refreshSummaryTab = val;
      },
      setSelectedTree(state, val) {
        state.selectedTree = val;
      },
      setDateFormat(state, val) {
        state.dateFormat = val;
      },
      setOpenAIIntegrationStatus(state, val) {
        state.openAIIntegrationEnabled = val;
      },
      setMaintenanceInfo(state, { count, oldestSince }) {
        state.maintenanceCount = count || 0;
        state.maintenanceOldestSince = oldestSince || null;
      },
      setDashInfoColor(state, val) {
        state.dash_info_color = val;
      },
      setDashPositiveColor(state, val) {
        state.dash_positive_color = val;
      },
      setDashNegativeColor(state, val) {
        state.dash_negative_color = val;
      },
      setDashWarningColor(state, val) {
        state.dash_warning_color = val;
      },
      setRunCmdPlaceholders(state, obj) {
        state.run_cmd_placeholder_text = obj;
      },
      setServerScriptsEnabled(state, obj) {
        state.server_scripts_enabled = obj;
      },
      setWebTerminalEnabled(state, obj) {
        state.web_terminal_enabled = obj;
      },
      setSSOEnabled(state, obj) {
        state.sso_enabled = obj;
      },
      setBlockLocalUserLogon(state, obj) {
        state.block_local_user_logon = obj;
      },
    },
    actions: {
      setClientTreeSplitter(context, val) {
        axios
          .patch("/accounts/users/ui/", {
            client_tree_splitter: Math.trunc(val),
          })
          .then(() => {
            context.commit("SET_CLIENT_SPLITTER", val);
          });
      },
      setShowScriptTemplates(context, data) {
        axios
          // `show_community_scripts` es el nombre del campo en la API y en la BD
          // (accounts.User): acá se manda tal cual a propósito.
          .patch("/accounts/users/ui/", { show_community_scripts: data })
          .then(() => {
            context.commit("setShowScriptTemplates", data);
          });
      },
      refreshDashboard({ state, commit, dispatch }, clearTreeSelected = false) {
        if (clearTreeSelected || !state.selectedTree) {
          commit("setSelectedTree", "");
        }
        if (clearTreeSelected) commit("destroySubTable");

        dispatch("getDashInfo", false);
        dispatch("loadAgents");
        dispatch("loadTree");
      },
      async loadAgents({ state, commit }) {
        commit("AGENT_TABLE_LOADING", true);

        let localParams = null;
        if (state.defaultAgentTblTab !== "mixed") {
          if (localParams)
            localParams += `&monitoring_type=${state.defaultAgentTblTab}`;
          else localParams = `?monitoring_type=${state.defaultAgentTblTab}`;
        }

        if (state.selectedTree.includes("Client")) {
          if (localParams)
            localParams += `&client=${state.selectedTree.split("|")[1]}`;
          else localParams = `?client=${state.selectedTree.split("|")[1]}`;
        } else if (state.selectedTree.includes("Site")) {
          if (localParams)
            localParams += `&site=${state.selectedTree.split("|")[1]}`;
          else localParams = `?site=${state.selectedTree.split("|")[1]}`;
        }
        try {
          const { data } = await axios.get(
            `/agents/${localParams ? localParams : ""}`,
          );
          commit("setAgents", data);
        } catch (e) {
          console.error(e);
        }

        commit("AGENT_TABLE_LOADING", false);
      },
      async getDashInfo({ commit }, edited = true) {
        const { data } = await axios.get("/core/dashinfo/");
        commit("setDashInfoColor", data.dash_info_color);
        commit("setDashPositiveColor", data.dash_positive_color);
        commit("setDashNegativeColor", data.dash_negative_color);
        commit("setDashWarningColor", data.dash_warning_color);
        // 046: el rojo por defecto de la v1 es color de estado (UI-D05);
        // la barra de carga usa secondary (neutro: actividad, no estado ni acción).
        //
        // 🪤 V2-G02 (2026-11-12): esto estaba DENTRO de `if (edited)`, y por eso
        // el arreglo de la 046 no llegaba a tres superficies. `getDashInfo` se
        // despacha con `edited = false` desde TakeControl.vue:112,
        // MainLayout.vue:434 y la linea 218 de este archivo, asi que ahi la
        // barra se quedaba en el #f44336 de fabrica de Quasar — que no es ningun
        // token y ademas es un color de ESTADO usado como actividad. Medido: 12
        // lecturas en rem-takecontrol, rem-webterm y rem-webvnc, que son
        // justamente las que abren en ventana aparte. El color de la barra es un
        // default global, no un ajuste «editado»: va fuera de la condicional.
        LoadingBar.setDefaults({
          color:
            data.loading_bar_color === "red"
              ? "secondary"
              : data.loading_bar_color,
        });
        if (edited) {
          commit(
            "setClearSearchWhenSwitching",
            data.clear_search_when_switching,
          );
          commit("SET_DEFAULT_AGENT_TBL_TAB", data.default_agent_tbl_tab);
          commit("SET_CLIENT_TREE_SORT", data.client_tree_sort);
          commit("SET_CLIENT_SPLITTER", data.client_tree_splitter);
        }
        Dark.set(data.dark_mode);
        // i18n (feature 010): aplica el idioma del usuario al cargar dashinfo (RN-01).
        // Precedencia: preferencia del usuario -> default del servidor (env-config.js) -> en.
        applyLocale(
          data.language ||
            (typeof window !== "undefined" && window._env_
              ? window._env_.DEFAULT_LANG
              : "") ||
            "en",
        );
        commit("setCurrentVersion", data.ormm_version);
        commit("setLatestVersion", data.latest_ormm_ver);
        commit("SET_AGENT_DBLCLICK_ACTION", data.dbl_click_action);
        commit("SET_URL_ACTION", data.url_action);
        commit("setShowScriptTemplates", data.show_community_scripts);
        commit("SET_HOSTED", data.hosted);
        commit("SET_TOKEN_EXPIRED", data.token_is_expired);
        commit("setOpenAIIntegrationStatus", data.open_ai_integration_enabled);
        commit("setRunCmdPlaceholders", data.run_cmd_placeholder_text);
        commit("setServerScriptsEnabled", data.server_scripts_enabled);
        commit("setWebTerminalEnabled", data.web_terminal_enabled);
        commit("setBlockLocalUserLogon", data.block_local_user_logon);
        commit("setMaintenanceInfo", {
          count: data.maintenance_count,
          oldestSince: data.maintenance_oldest_since,
        });

        if (data?.date_format !== "") commit("setDateFormat", data.date_format);
        else commit("setDateFormat", data.default_date_format);
      },
      loadTree({ commit, state }) {
        setTimeout(() => {
          axios
            .get("/clients/")
            .then((r) => {
              if (r.data.length === 0) {
                this.$router.push({ name: "InitialSetup" });
              }

              let output = [];
              for (let client of r.data) {
                let childSites = [];
                for (let site of client.sites) {
                  let siteNode = {
                    label: site.name,
                    id: site.id,
                    raw: `Site|${site.id}`,
                    header: "generic",
                    icon: "apartment",
                    selectable: true,
                    site: site,
                  };

                  if (site.maintenance_mode) {
                    siteNode["color"] = "green";
                  } else if (site.failing_checks.error) {
                    siteNode["color"] = "negative";
                  } else if (site.failing_checks.warning) {
                    siteNode["color"] = "warning";
                  }

                  childSites.push(siteNode);
                }

                let clientNode = {
                  label: client.name,
                  id: client.id,
                  raw: `Client|${client.id}`,
                  header: "root",
                  icon: "business",
                  children: childSites,
                  client: client,
                };

                if (client.maintenance_mode) clientNode["color"] = "green";
                else if (client.failing_checks.error) {
                  clientNode["color"] = "negative";
                } else if (client.failing_checks.warning) {
                  clientNode["color"] = "warning";
                }

                output.push(clientNode);
              }

              const sorted = output.sort((a, b) =>
                a.label.localeCompare(b.label),
              );
              if (state.clientTreeSort === "alphafail") {
                // move failing clients to the top
                const failing = sorted.filter(
                  (i) => i.color === "negative" || i.color === "warning",
                );
                const ok = sorted.filter(
                  (i) => i.color !== "negative" && i.color !== "warning",
                );
                const sortedByFailing = [...failing, ...ok];
                commit("loadTree", sortedByFailing);
              } else {
                commit("loadTree", sorted);
              }
            })
            .catch(() => {
              state.treeReady = true;
            });
        }, 150);
      },
      checkVer(context) {
        axios.get("/core/version/").then((r) => {
          const version = r.data;

          if (localStorage.getItem("rmmver")) {
            if (localStorage.getItem("rmmver") === version) {
              return;
            } else {
              localStorage.setItem("rmmver", "0.0.1");
              context.commit("SET_REFRESH_NEEDED", true);
            }
          } else {
            localStorage.setItem("rmmver", version);
            return;
          }
        });
      },
      reload() {
        localStorage.removeItem("rmmver");
        location.reload();
      },
    },
  });

  return Store;
}
