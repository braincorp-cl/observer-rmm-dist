<template>
  <q-card style="min-width: 70vw">
    <q-card-section class="row">
      <q-card-actions align="left">
        <div class="text-h6">{{ $t("agentDownload.title") }}</div>
      </q-card-actions>
      <q-space />
      <q-card-actions align="right">
        <q-btn v-close-popup flat round dense icon="close" />
      </q-card-actions>
    </q-card-section>
    <q-card-section>
      <p v-if="info.plat === 'windows'" class="text-subtitle1">
        {{ $t("agentDownload.windowsIntro") }}
      </p>
      <p v-else-if="info.plat === 'linux'" class="text-subtitle1">
        {{ $t("agentDownload.nixIntro") }}
      </p>
      <p v-else-if="info.plat === 'darwin'" class="text-subtitle1">
        {{ $t("agentDownload.macIntro") }}
      </p>

      <!-- Windows: comando de instalación manual (viene del backend) -->
      <p v-if="info.plat === 'windows'">
        <q-field outlined :color="$q.dark.isActive ? 'white' : 'black'">
          <code>{{ info.data.cmd }}</code>
        </q-field>
        <q-btn
          size="md"
          flat
          round
          icon="content_copy"
          :label="$t('agentDownload.copyToClipboard')"
          @click="copyValueToClip(info.data.cmd)"
        >
        </q-btn>
      </p>

      <!-- Linux / macOS: instalar y (Linux) desinstalar con el .sh descargado -->
      <template v-if="isNix">
        <div class="text-weight-medium q-mt-sm">
          {{ $t("agentDownload.nixInstallLabel") }}
        </div>
        <p>
          <q-field outlined :color="$q.dark.isActive ? 'white' : 'black'">
            <code>{{ installCmd }}</code>
          </q-field>
          <q-btn
            size="md"
            flat
            round
            icon="content_copy"
            :label="$t('agentDownload.copyToClipboard')"
            @click="copyValueToClip(installCmd)"
          >
          </q-btn>
        </p>
        <template v-if="info.plat === 'linux'">
          <div class="text-weight-medium q-mt-sm">
            {{ $t("agentDownload.nixUninstallLabel") }}
          </div>
          <p>
            <q-field outlined :color="$q.dark.isActive ? 'white' : 'black'">
              <code>{{ uninstallCmd }}</code>
            </q-field>
            <q-btn
              size="md"
              flat
              round
              icon="content_copy"
              :label="$t('agentDownload.copyToClipboard')"
              @click="copyValueToClip(uninstallCmd)"
            >
            </q-btn>
          </p>
          <q-banner dense class="bg-grey-3 text-black q-mb-sm">
            <template v-slot:avatar>
              <q-icon name="info" color="primary" />
            </template>
            {{ $t("agentDownload.nixHeadlessNote") }}
          </q-banner>
        </template>
        <q-banner
          v-if="info.plat === 'darwin'"
          dense
          class="bg-grey-3 text-black q-mb-sm"
        >
          <template v-slot:avatar>
            <q-icon name="info" color="primary" />
          </template>
          {{ $t("agentDownload.macUninstallNote") }}
        </q-banner>
      </template>

      <q-expansion-item
        switch-toggle-side
        header-class="text-primary"
        expand-separator
        :label="$t('agentDownload.viewOptionalArgs')"
      >
        <!-- args del script Windows -->
        <template v-if="info.plat === 'windows'">
          <div class="q-pa-xs q-gutter-xs">
            <q-badge
              class="text-caption q-mr-xs"
              color="grey"
              text-color="black"
            >
              <code>{{ $t("agentDownload.argLogDebug") }}</code>
            </q-badge>
            <span>{{ $t("agentDownload.descLogDebug") }}</span>
          </div>
          <div class="q-pa-xs q-gutter-xs">
            <q-badge
              class="text-caption q-mr-xs"
              color="grey"
              text-color="black"
            >
              <code>{{ $t("agentDownload.argSilent") }}</code>
            </q-badge>
            <span>{{ $t("agentDownload.descSilent") }}</span>
          </div>
          <div class="q-pa-xs q-gutter-xs">
            <q-badge
              class="text-caption q-mr-xs"
              color="grey"
              text-color="black"
            >
              <code>{{ $t("agentDownload.argLocalMesh") }}</code>
            </q-badge>
            <span>{{ $t("agentDownload.descLocalMesh") }}</span>
          </div>
          <div class="q-pa-xs q-gutter-xs">
            <q-badge
              class="text-caption q-mr-xs"
              color="grey"
              text-color="black"
            >
              <code>{{ $t("agentDownload.argMeshdir") }}</code>
            </q-badge>
            <span>{{ $t("agentDownload.descMeshdir") }}</span>
          </div>
          <div class="q-pa-xs q-gutter-xs">
            <q-badge
              class="text-caption q-mr-xs"
              color="grey"
              text-color="black"
            >
              <code>{{ $t("agentDownload.argCert") }}</code>
            </q-badge>
            <span>{{ $t("agentDownload.descCert") }}</span>
          </div>
          <div class="q-pa-xs q-gutter-xs">
            <q-badge
              class="text-caption q-mr-xs"
              color="grey"
              text-color="black"
            >
              <code>{{ $t("agentDownload.argDesc") }}</code>
            </q-badge>
            <span>{{ $t("agentDownload.descDesc") }}</span>
          </div>
          <div class="q-pa-xs q-gutter-xs">
            <q-badge
              class="text-caption q-mr-xs"
              color="grey"
              text-color="black"
            >
              <code>{{ $t("agentDownload.argProxy") }}</code>
            </q-badge>
            <span>{{ $t("agentDownload.descProxy") }}</span>
          </div>
        </template>

        <!-- args del script Linux / macOS -->
        <template v-if="isNix">
          <div class="q-pa-xs q-gutter-xs">
            <q-badge
              class="text-caption q-mr-xs"
              color="grey"
              text-color="black"
            >
              <code>{{ $t("agentDownload.argDebug") }}</code>
            </q-badge>
            <span>{{ $t("agentDownload.descLogDebug") }}</span>
          </div>
          <div class="q-pa-xs q-gutter-xs">
            <q-badge
              class="text-caption q-mr-xs"
              color="grey"
              text-color="black"
            >
              <code>{{ $t("agentDownload.argInsecure") }}</code>
            </q-badge>
            <span>{{ $t("agentDownload.descInsecure") }}</span>
          </div>
          <div class="q-pa-xs q-gutter-xs">
            <q-badge
              class="text-caption q-mr-xs"
              color="grey"
              text-color="black"
            >
              <code>{{ $t("agentDownload.argNomesh") }}</code>
            </q-badge>
            <span>{{ $t("agentDownload.descNomesh") }}</span>
          </div>
        </template>
      </q-expansion-item>
      <br />
      <p class="text-italic">
        {{ $t("agentDownload.authNote", { expires: info.expires }) }}
      </p>
      <q-btn
        v-if="info.plat === 'windows'"
        type="a"
        :href="info.data.url"
        color="primary"
        :label="$t('agentDownload.downloadAgent')"
      ></q-btn>
    </q-card-section>
  </q-card>
</template>

<script>
import mixins from "@/mixins/mixins";
import { notifySuccess } from "@/utils/notify";
import { copyToClipboard } from "quasar";
import { useI18n } from "vue-i18n";

export default {
  name: "AgentDownload",
  mixins: [mixins],
  props: ["info"],
  computed: {
    isNix() {
      return this.info.plat === "linux" || this.info.plat === "darwin";
    },
    installCmd() {
      return `sudo bash ./${this.info.scriptName}`;
    },
    uninstallCmd() {
      return `sudo bash ./${this.info.scriptName} uninstall`;
    },
  },
  setup() {
    const { t } = useI18n();

    function copyValueToClip(val) {
      copyToClipboard(val).then(() => {
        notifySuccess(t("agentDownload.copiedToClipboard"));
      });
    }

    return {
      copyValueToClip,
    };
  },
};
</script>
