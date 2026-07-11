<template>
  <q-card style="min-width: 35vw">
    <q-card-section class="row">
      <q-card-actions align="left">
        <div class="text-h6">{{ $t("installAgent.title") }}</div>
      </q-card-actions>
      <q-space />
      <q-card-actions align="right">
        <q-btn v-close-popup flat round dense icon="close" />
      </q-card-actions>
    </q-card-section>
    <q-card-section>
      <q-form @submit.prevent="addAgent">
        <q-card-section class="q-gutter-sm">
          <q-select
            outlined
            dense
            options-dense
            :label="$t('installAgent.client')"
            v-model="client"
            :options="client_options"
            @update:model-value="site = sites[0]"
          />
        </q-card-section>
        <q-card-section class="q-gutter-sm">
          <q-select
            dense
            options-dense
            outlined
            :label="$t('installAgent.site')"
            v-model="site"
            :options="sites"
          />
        </q-card-section>
        <q-card-section>
          <div class="q-gutter-sm">
            <q-radio
              v-model="agentOS"
              val="windows"
              :label="$t('installAgent.osWindows')"
              @update:model-value="
                installMethod = 'powershell';
                goarch = GOARCH_AMD64;
              "
            />
            <q-radio
              v-model="agentOS"
              val="linux"
              :label="$t('installAgent.osLinux')"
              @update:model-value="
                installMethod = 'bash';
                goarch = GOARCH_AMD64;
              "
            />
            <q-radio
              v-model="agentOS"
              val="darwin"
              :label="$t('installAgent.osMacos')"
              @update:model-value="
                installMethod = 'mac';
                goarch = GOARCH_AMD64;
              "
            />
          </div>
        </q-card-section>
        <q-card-section>
          <div class="q-gutter-sm">
            <q-radio
              v-model="agenttype"
              val="server"
              :label="$t('installAgent.typeServer')"
              @update:model-value="power = false"
            />
            <q-radio
              v-model="agenttype"
              val="workstation"
              :label="$t('installAgent.typeWorkstation')"
            />
          </div>
        </q-card-section>
        <q-card-section>
          <div class="q-gutter-sm">
            <q-input
              v-model.number="expires"
              dense
              type="number"
              filled
              :label="$t('installAgent.tokenExpiration')"
              style="max-width: 200px"
              stack-label
            />
          </div>
        </q-card-section>
        <q-card-section v-show="agentOS === 'windows'">
          <div class="q-gutter-sm">
            <q-checkbox
              v-model="rdp"
              dense
              :label="$t('installAgent.enableRdp')"
            />
            <q-checkbox
              v-model="ping"
              dense
              :label="$t('installAgent.enablePing')"
            >
              <q-tooltip>
                {{ $t("installAgent.enablePingTooltip") }}
              </q-tooltip>
            </q-checkbox>
            <q-checkbox
              v-model="power"
              dense
              v-show="agenttype === 'workstation'"
              :label="$t('installAgent.disableSleep')"
            />
          </div>
        </q-card-section>
        <q-card-section>
          {{ $t("installAgent.arch") }}
          <div class="q-gutter-sm">
            <q-radio
              v-model="goarch"
              :val="GOARCH_AMD64"
              :label="$t('installAgent.arch64')"
              v-show="agentOS === 'windows' || agentOS === 'linux'"
            />
            <q-radio
              v-model="goarch"
              :val="GOARCH_AMD64"
              :label="$t('installAgent.archIntel64')"
              v-show="agentOS === 'darwin'"
            />
            <q-radio
              v-model="goarch"
              :val="GOARCH_i386"
              :label="$t('installAgent.arch32')"
              v-show="agentOS !== 'darwin'"
            />
            <q-radio
              v-model="goarch"
              :val="GOARCH_ARM64"
              :label="$t('installAgent.archArm64')"
              v-show="agentOS === 'linux'"
            />
            <q-radio
              v-model="goarch"
              :val="GOARCH_ARM64"
              :label="$t('installAgent.archAppleSilicon')"
              v-show="agentOS === 'darwin'"
            />
            <q-radio
              v-model="goarch"
              :val="GOARCH_ARM32"
              :label="$t('installAgent.archArm32')"
              v-show="agentOS === 'linux'"
            />
          </div>
        </q-card-section>
        <q-card-section>
          {{ $t("installAgent.installMethod") }}
          <div class="q-gutter-sm">
            <q-radio
              v-model="installMethod"
              val="powershell"
              v-show="agentOS === 'windows'"
              :label="$t('installAgent.methodPowershell')"
            />
            <q-radio
              v-model="installMethod"
              val="manual"
              v-show="agentOS === 'windows'"
              :label="$t('installAgent.methodStandardExe')"
            />
            <q-radio
              v-model="installMethod"
              val="exe"
              v-show="false"
              :label="$t('installAgent.methodGeneratedExe')"
            />
          </div>
        </q-card-section>
        <q-card-actions align="left">
          <q-btn :label="installButtonText" color="primary" type="submit" />
        </q-card-actions>
      </q-form>
    </q-card-section>
    <q-dialog v-model="showAgentDownload">
      <AgentDownload :info="info" @close="showAgentDownload = false" />
    </q-dialog>
  </q-card>
</template>

<script>
import mixins from "@/mixins/mixins";
import AgentDownload from "@/components/modals/agents/AgentDownload.vue";
import { getBaseUrl } from "@/boot/axios";
import {
  GOARCH_AMD64,
  GOARCH_i386,
  GOARCH_ARM64,
  GOARCH_ARM32,
} from "@/constants/constants";

export default {
  name: "InstallAgent",
  mixins: [mixins],
  components: { AgentDownload },
  props: {
    sitepk: Number,
  },
  data() {
    return {
      GOARCH_AMD64: GOARCH_AMD64,
      GOARCH_i386: GOARCH_i386,
      GOARCH_ARM64: GOARCH_ARM64,
      GOARCH_ARM32: GOARCH_ARM32,
      client_options: [],
      client: null,
      site: null,
      agenttype: "server",
      expires: 24,
      power: false,
      rdp: false,
      ping: false,
      showAgentDownload: false,
      info: {},
      installMethod: "powershell",
      goarch: GOARCH_AMD64,
      agentOS: "windows",
    };
  },
  methods: {
    getClients() {
      this.$q.loading.show();
      this.$axios
        .get("/clients/")
        .then((r) => {
          this.client_options = this.formatClientOptions(r.data);
          if (this.sitepk !== undefined && this.sitepk !== null) {
            this.client_options.forEach((client) => {
              let site = client.sites.find((site) => site.id === this.sitepk);

              if (site !== undefined) {
                this.client = client;
                this.site = { value: site.id, label: site.name };
              }
            });
          } else {
            this.client = this.client_options[0];
            this.site = this.sites[0];
          }
          this.$q.loading.hide();
        })
        .catch(() => {
          this.$q.loading.hide();
        });
    },
    addAgent() {
      const api = getBaseUrl();
      const clientStripped = this.client.label
        .replace(/\s/g, "")
        .toLowerCase()
        .replace(/([^a-zA-Z0-9]+)/g, "");
      const siteStripped = this.site.label
        .replace(/\s/g, "")
        .toLowerCase()
        .replace(/([^a-zA-Z0-9]+)/g, "");

      const fileName = `observer-${clientStripped}-${siteStripped}-${this.agenttype}-${this.goarch}.exe`;

      const data = {
        installMethod: this.installMethod,
        client: this.client.value,
        site: this.site.value,
        expires: this.expires,
        agenttype: this.agenttype,
        power: this.power ? 1 : 0,
        rdp: this.rdp ? 1 : 0,
        ping: this.ping ? 1 : 0,
        goarch: this.goarch,
        api,
        fileName,
        plat: this.agentOS,
      };

      if (this.installMethod === "manual") {
        this.$axios.post("/agents/installer/", data).then((r) => {
          this.info = {
            expires: this.expires,
            installMethod: this.installMethod,
            data: r.data,
            goarch: this.goarch,
            plat: this.agentOS,
          };
          this.showAgentDownload = true;
        });
      } else if (this.installMethod === "exe") {
        this.$q
          .dialog({
            title: this.$t("installAgent.warningTitle"),
            style: {
              width: "40vw",
              maxWidth: "50vw",
            },
            // El enlace de esta advertencia vive en installAgent.exeWarningMessage
            // (catálogos i18n) y apunta a docs.observer.cl/faq/#agentes-inesperados.
            message: this.$t("installAgent.exeWarningMessage"),
            color: "negative",
            ok: {
              label: this.$t("installAgent.continueLabel"),
              color: "negative",
              unelevated: true,
            },
            cancel: {
              label: this.$t("installAgent.cancel"),
              color: "grey",
            },
            persistent: true,
            html: true,
          })
          .onOk(() => {
            this.$q.loading.show({
              message: this.$t("installAgent.generatingExe"),
            });
            this.$axios
              .post("/agents/installer/", data, { responseType: "blob" })
              .then((r) => {
                this.$q.loading.hide();
                const blob = new Blob([r.data], {
                  type: "application/vnd.microsoft.portable-executable",
                });
                let link = document.createElement("a");
                link.href = window.URL.createObjectURL(blob);
                link.download = fileName;
                link.click();
                this.showDLMessage();
              })
              .catch(() => {
                this.$q.loading.hide();
              });
          });
      } else if (
        this.installMethod === "powershell" ||
        this.installMethod === "bash" ||
        this.installMethod === "mac"
      ) {
        this.$q.loading.show();
        let ext = this.installMethod === "powershell" ? "ps1" : "sh";
        const scriptName = `observer-${clientStripped}-${siteStripped}-${this.agenttype}.${ext}`;
        this.$axios
          .post("/agents/installer/", data, { responseType: "blob" })
          .then(({ data }) => {
            this.$q.loading.hide();
            const blob = new Blob([data], { type: "text/plain" });
            let link = document.createElement("a");
            link.href = window.URL.createObjectURL(blob);
            link.download = scriptName;
            link.click();
            // Tras bajar el script, mostrar cómo usarlo. Windows (PowerShell):
            // requiere consola elevada, comando de ejemplo y desinstalación vía
            // RMM/"Agregar o quitar programas". Linux/macOS: requiere root,
            // comando de ejemplo y (Linux) desinstalación con el mismo .sh.
            this.info = {
              plat: this.agentOS,
              installMethod: this.installMethod,
              expires: this.expires,
              scriptName,
              data: {},
            };
            this.showAgentDownload = true;
          })
          .catch(() => {
            this.$q.loading.hide();
          });
      }
    },
    showDLMessage() {
      this.$q.dialog({
        message: this.$t("installAgent.dlMessage", {
          client: this.client.label,
          site: this.site.label,
          type: this.agenttype,
          hours: this.expires,
        }),
      });
    },
  },
  computed: {
    sites() {
      return !!this.client ? this.formatSiteOptions(this.client.sites) : [];
    },
    installButtonText() {
      let text;
      switch (this.installMethod) {
        case "exe":
          text = this.$t("installAgent.btnGenerateExe");
          break;
        case "powershell":
          text = this.$t("installAgent.btnDownloadPowershell");
          break;
        case "manual":
          text = this.$t("installAgent.btnShowInstructions");
          break;
        case "bash":
          text = this.$t("installAgent.btnDownloadBash");
          break;
        case "mac":
          text = this.$t("installAgent.btnDownloadMac");
          break;
      }

      return text;
    },
  },
  mounted() {
    this.getClients();
  },
};
</script>
