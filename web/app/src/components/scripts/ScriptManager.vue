<template>
  <q-dialog ref="dialogRef" @hide="onDialogHide">
    <q-card
      class="q-dialog-plugin"
      id="script-manager-card"
      :style="{
        width: `${$q.screen.width - 100}px`,
        'max-width': `${$q.screen.width - 100}px`,
        height: `${$q.screen.height - 100}px`,
        'max-height': `${$q.screen.height - 100}px`,
      }"
    >
      <q-bar>
        <q-btn
          @click="getScripts"
          class="q-mr-sm"
          dense
          flat
          push
          icon="refresh"
        />{{ $t("scriptManager.title") }}
        <q-space />
        <q-btn dense flat icon="close" v-close-popup>
          <q-tooltip class="bg-white text-primary">{{
            $t("scriptsCommon.close")
          }}</q-tooltip>
        </q-btn>
      </q-bar>
      <div class="row q-pt-xs q-pl-xs">
        <q-btn-dropdown
          icon="add"
          :label="$t('scriptsCommon.newBtn')"
          no-caps
          dense
          flat
        >
          <q-list dense>
            <q-item clickable v-close-popup @click="newScriptModal">
              <q-item-section side>
                <q-icon size="xs" name="add" />
              </q-item-section>
              <q-item-section>
                <q-item-label>{{ $t("scriptManager.newScript") }}</q-item-label>
              </q-item-section>
            </q-item>
            <q-item clickable v-close-popup @click="uploadScriptModal">
              <q-item-section side>
                <q-icon size="xs" name="cloud_upload" />
              </q-item-section>
              <q-item-section>
                <q-item-label>{{
                  $t("scriptManager.uploadScript")
                }}</q-item-label>
              </q-item-section>
            </q-item>
          </q-list>
        </q-btn-dropdown>
        <q-btn
          no-caps
          dense
          flat
          class="q-ml-sm"
          :label="$t('scriptManager.scriptSnippets')"
          icon="mdi-script"
          @click="ScriptSnippetModal"
        />
        <q-btn
          dense
          flat
          no-caps
          class="q-ml-sm"
          :label="
            tableView
              ? $t('scriptManager.folderView')
              : $t('scriptManager.tableViewBtn')
          "
          :icon="tableView ? 'folder' : 'list'"
          @click="tableView = !tableView"
        />
        <q-btn
          dense
          flat
          no-caps
          class="q-ml-sm"
          :label="
            showCommunityScripts
              ? $t('scriptManager.hideCommunityScripts')
              : $t('scriptManager.showCommunityScripts')
          "
          :icon="showCommunityScripts ? 'visibility_off' : 'visibility'"
          @click="setShowCommunityScripts(!showCommunityScripts)"
        />

        <q-btn
          dense
          flat
          no-caps
          class="q-ml-sm"
          :label="
            showHiddenScripts
              ? $t('scriptManager.hideHiddenScripts')
              : $t('scriptManager.showHiddenScripts')
          "
          :icon="showHiddenScripts ? 'visibility_off' : 'visibility'"
          @click="showHiddenScripts = !showHiddenScripts"
        />

        <q-space />
        <q-input
          v-model="search"
          style="width: 300px"
          :label="$t('scriptManager.search')"
          dense
          outlined
          clearable
          class="q-pr-md q-pb-xs"
        >
          <template v-slot:prepend>
            <q-icon name="search" color="primary" />
          </template>
        </q-input>
      </div>
      <!-- List View -->
      <div
        v-if="!tableView"
        class="scroll q-pl-xs"
        :style="{
          'max-height': `${$q.screen.height - 182}px`,
          'min-height': `${$q.screen.height - 382}px`,
        }"
      >
        <q-tree
          ref="folderTree"
          :nodes="tree"
          :filter="search"
          no-connectors
          node-key="id"
          v-model:expanded="expanded"
          :no-results-label="$t('scriptManager.noScriptsFound')"
          :no-nodes-label="$t('scriptManager.noScriptsFound')"
        >
          <template v-slot:header-script="props">
            <div
              class="cursor-pointer"
              @dblclick="
                props.node.script_type === 'builtin'
                  ? viewCodeModal(props.node)
                  : editScriptModal(props.node)
              "
            >
              <q-icon
                v-if="props.node.favorite"
                color="yellow-8"
                name="star"
                size="sm"
                class="q-px-sm"
              />
              <q-icon
                v-else
                color="yellow-8"
                name="star_outline"
                size="sm"
                class="q-px-sm"
              />

              <q-icon
                v-if="props.node.shell === 'powershell'"
                name="mdi-powershell"
                color="primary"
              >
                <q-tooltip>{{ $t("scriptsCommon.shellPowershell") }}</q-tooltip>
              </q-icon>
              <q-icon
                v-else-if="props.node.shell === 'python'"
                name="mdi-language-python"
                color="primary"
              >
                <q-tooltip>{{ $t("scriptsCommon.shellPython") }}</q-tooltip>
              </q-icon>
              <q-icon
                v-else-if="props.node.shell === 'cmd'"
                name="mdi-microsoft-windows"
                color="primary"
              >
                <q-tooltip>{{ $t("scriptsCommon.shellBatch") }}</q-tooltip>
              </q-icon>
              <q-icon
                v-else-if="props.node.shell === 'shell'"
                name="mdi-bash"
                color="primary"
              >
                <q-tooltip>{{ $t("scriptsCommon.shellShell") }}</q-tooltip>
              </q-icon>
              <q-icon
                v-else-if="props.node.shell === 'nushell'"
                name="mdi-code-greater-than"
                color="primary"
              >
                <q-tooltip>{{ $t("scriptsCommon.shellNushell") }}</q-tooltip>
              </q-icon>
              <q-icon
                v-else-if="props.node.shell === 'deno'"
                name="mdi-language-typescript"
                color="primary"
              >
                <q-tooltip>{{ $t("scriptsCommon.shellDeno") }}</q-tooltip>
              </q-icon>

              <!-- is community script icon -->
              <img
                v-if="props.node.script_type === 'builtin'"
                class="vertical-middle"
                :src="trmmLogo"
                style="height: 20px; max-width: 20px"
              />

              <span
                class="q-pl-xs text-weight-bold"
                :style="{ color: props.node.hidden ? 'grey' : '' }"
                >{{ props.node.name }}</span
              >
              <span class="q-pl-xs">{{ props.node.description }}</span>
            </div>

            <!-- context menu -->
            <q-menu context-menu>
              <q-list dense style="min-width: 200px">
                <q-item
                  clickable
                  v-close-popup
                  @click="viewCodeModal(props.node)"
                >
                  <q-item-section side>
                    <q-icon name="remove_red_eye" />
                  </q-item-section>
                  <q-item-section>{{
                    $t("scriptManager.viewCode")
                  }}</q-item-section>
                </q-item>

                <q-item
                  clickable
                  v-close-popup
                  @click="cloneScriptModal(props.node)"
                >
                  <q-item-section side>
                    <q-icon name="content_copy" />
                  </q-item-section>
                  <q-item-section>{{
                    $t("scriptManager.clone")
                  }}</q-item-section>
                </q-item>

                <q-item
                  clickable
                  v-close-popup
                  @click="editScriptModal(props.node)"
                  :disable="props.node.script_type === 'builtin'"
                >
                  <q-item-section side>
                    <q-icon name="edit" />
                  </q-item-section>
                  <q-item-section>{{
                    $t("scriptsCommon.edit")
                  }}</q-item-section>
                </q-item>

                <q-item
                  clickable
                  v-close-popup
                  @click="deleteScript(props.node)"
                  :disable="props.node.script_type === 'builtin'"
                >
                  <q-item-section side>
                    <q-icon name="delete" />
                  </q-item-section>
                  <q-item-section>{{
                    $t("scriptsCommon.delete")
                  }}</q-item-section>
                </q-item>

                <q-separator></q-separator>

                <q-item
                  clickable
                  v-close-popup
                  @click="favoriteScript(props.node)"
                >
                  <q-item-section side>
                    <q-icon name="star" />
                  </q-item-section>
                  <q-item-section>{{
                    props.node.favorite
                      ? $t("scriptManager.removeFavorite")
                      : $t("scriptManager.addFavorite")
                  }}</q-item-section>
                </q-item>

                <q-item
                  clickable
                  v-close-popup
                  @click="exportScript(props.node)"
                >
                  <q-item-section side>
                    <q-icon name="cloud_download" />
                  </q-item-section>
                  <q-item-section>{{
                    $t("scriptManager.downloadScript")
                  }}</q-item-section>
                </q-item>

                <q-separator />

                <q-item clickable v-close-popup @click="hideScript(props.node)">
                  <q-item-section side>
                    <q-icon
                      :name="
                        props.node.hidden ? 'visibility' : 'visibility_off'
                      "
                    />
                  </q-item-section>
                  <q-item-section>{{
                    props.node.hidden
                      ? $t("scriptManager.showScript")
                      : $t("scriptManager.hideScript")
                  }}</q-item-section>
                </q-item>

                <q-separator></q-separator>

                <q-item clickable v-close-popup>
                  <q-item-section>{{
                    $t("scriptsCommon.close")
                  }}</q-item-section>
                </q-item>
              </q-list>
            </q-menu>
          </template>
        </q-tree>
      </div>
      <observer-table
        v-if="tableView"
        dense
        :style="{ 'max-height': `${$q.screen.height - 182}px` }"
        :rows="visibleScripts"
        :columns="columns"
        :loading="loading"
        :pagination="{ rowsPerPage: 0, sortBy: 'favorite', descending: true }"
        :filter="search"
        row-key="id"
        binary-state-sort
        virtual-scroll
        :rows-per-page-options="[0]"
        column-select
        :storage-key="storageKey"
      >
        <template v-slot:header-cell-favorite="props">
          <q-th :props="props" auto-width>
            <q-icon name="star" color="yellow-8" size="sm" />
          </q-th>
        </template>

        <template v-slot:header-cell-shell="props">
          <q-th :props="props" auto-width>{{ $t("scriptManager.shell") }}</q-th>
        </template>

        <template v-slot:no-data>{{
          $t("scriptManager.noScriptsFound")
        }}</template>
        <template v-slot:body="props">
          <!-- Table View -->
          <q-tr
            :props="props"
            @dblclick="
              props.row.script_type === 'builtin'
                ? viewCodeModal(props.row)
                : editScriptModal(props.row)
            "
            class="cursor-pointer"
          >
            <!-- Context Menu -->
            <q-menu context-menu>
              <q-list dense style="min-width: 200px">
                <q-item
                  clickable
                  v-close-popup
                  @click="viewCodeModal(props.row)"
                >
                  <q-item-section side>
                    <q-icon name="remove_red_eye" />
                  </q-item-section>
                  <q-item-section>{{
                    $t("scriptManager.viewCode")
                  }}</q-item-section>
                </q-item>

                <q-item
                  clickable
                  v-close-popup
                  @click="cloneScriptModal(props.row)"
                >
                  <q-item-section side>
                    <q-icon name="content_copy" />
                  </q-item-section>
                  <q-item-section>{{
                    $t("scriptManager.clone")
                  }}</q-item-section>
                </q-item>

                <q-item
                  clickable
                  v-close-popup
                  @click="editScriptModal(props.row)"
                  :disable="props.row.script_type === 'builtin'"
                >
                  <q-item-section side>
                    <q-icon name="edit" />
                  </q-item-section>
                  <q-item-section>{{
                    $t("scriptsCommon.edit")
                  }}</q-item-section>
                </q-item>

                <q-item
                  clickable
                  v-close-popup
                  @click="deleteScript(props.row)"
                  :disable="props.row.script_type === 'builtin'"
                >
                  <q-item-section side>
                    <q-icon name="delete" />
                  </q-item-section>
                  <q-item-section>{{
                    $t("scriptsCommon.delete")
                  }}</q-item-section>
                </q-item>

                <q-separator></q-separator>

                <q-item
                  clickable
                  v-close-popup
                  @click="favoriteScript(props.row)"
                >
                  <q-item-section side>
                    <q-icon name="star" />
                  </q-item-section>
                  <q-item-section>{{
                    props.row.favorite
                      ? $t("scriptManager.removeFavorite")
                      : $t("scriptManager.addFavorite")
                  }}</q-item-section>
                </q-item>

                <q-item
                  clickable
                  v-close-popup
                  @click="exportScript(props.row)"
                >
                  <q-item-section side>
                    <q-icon name="cloud_download" />
                  </q-item-section>
                  <q-item-section>{{
                    $t("scriptManager.downloadScript")
                  }}</q-item-section>
                </q-item>

                <q-separator />

                <q-item clickable v-close-popup @click="hideScript(props.row)">
                  <q-item-section side>
                    <q-icon
                      :name="props.row.hidden ? 'visibility' : 'visibility_off'"
                    />
                  </q-item-section>
                  <q-item-section>{{
                    props.row.hidden
                      ? $t("scriptManager.showScript")
                      : $t("scriptManager.hideScript")
                  }}</q-item-section>
                </q-item>

                <q-separator></q-separator>

                <q-item clickable v-close-popup>
                  <q-item-section>{{
                    $t("scriptsCommon.close")
                  }}</q-item-section>
                </q-item>
              </q-list>
            </q-menu>
            <!-- favorite -->
            <q-td key="favorite" :props="props">
              <q-icon
                v-if="props.row.favorite"
                color="yellow-8"
                name="star"
                size="sm"
              />
            </q-td>
            <!-- shell icon -->
            <q-td key="shell" :props="props">
              <q-icon
                v-if="props.row.shell === 'powershell'"
                name="mdi-powershell"
                color="primary"
                size="sm"
              >
                <q-tooltip>{{ $t("scriptsCommon.shellPowershell") }}</q-tooltip>
              </q-icon>
              <q-icon
                v-else-if="props.row.shell === 'python'"
                name="mdi-language-python"
                color="primary"
                size="sm"
              >
                <q-tooltip>{{ $t("scriptsCommon.shellPython") }}</q-tooltip>
              </q-icon>
              <q-icon
                v-else-if="props.row.shell === 'cmd'"
                name="mdi-microsoft-windows"
                color="primary"
                size="sm"
              >
                <q-tooltip>{{ $t("scriptsCommon.shellBatch") }}</q-tooltip>
              </q-icon>
              <q-icon
                v-else-if="props.row.shell === 'shell'"
                size="sm"
                name="mdi-bash"
                color="primary"
              >
                <q-tooltip>{{ $t("scriptsCommon.shellShell") }}</q-tooltip>
              </q-icon>
              <q-icon
                v-else-if="props.row.shell === 'nushell'"
                size="sm"
                name="mdi-code-greater-than"
                color="primary"
              >
                <q-tooltip>{{ $t("scriptsCommon.shellNushell") }}</q-tooltip>
              </q-icon>
              <q-icon
                v-else-if="props.row.shell === 'deno'"
                size="sm"
                name="mdi-language-typescript"
                color="primary"
              >
                <q-tooltip>{{ $t("scriptsCommon.shellDeno") }}</q-tooltip>
              </q-icon>
            </q-td>
            <!-- supported platforms -->
            <q-td key="supported_platforms" :props="props">
              <q-badge
                v-if="
                  !props.row.supported_platforms ||
                  props.row.supported_platforms.length === 0
                "
                >{{ $t("scriptManager.platformAll") }}</q-badge
              >
              <q-badge
                v-else
                v-for="plat in props.row.supported_platforms"
                :key="plat"
                color="primary"
                class="q-pr-xs"
                >{{ capitalize(plat) }}</q-badge
              >
            </q-td>
            <!-- name -->
            <q-td
              key="name"
              :props="props"
              :style="{ color: props.row.hidden ? 'grey' : '' }"
            >
              <!-- is community script icon -->
              <img
                v-if="props.row.script_type === 'builtin'"
                :src="trmmLogo"
                style="height: 20px; max-width: 20px"
              />
              {{ truncateText(props.row.name, 50) }}
              <q-tooltip
                v-if="props.row.name.length >= 50"
                style="font-size: 12px"
              >
                {{ props.row.name }}
              </q-tooltip>
              <q-tooltip :delay="600">{{
                $t("scriptManager.idLabel", { id: props.row.id })
              }}</q-tooltip>
            </q-td>
            <!-- args -->
            <q-td key="args" :props="props">
              <span v-if="props.row.args.length > 0">
                {{ truncateText(props.row.args.toString(), 30) }}
                <q-tooltip
                  v-if="props.row.args.toString().length >= 30"
                  style="font-size: 12px"
                >
                  {{ props.row.args }}
                </q-tooltip>
              </span>
            </q-td>

            <q-td key="category" :props="props">{{ props.row.category }}</q-td>
            <q-td key="desc" :props="props">
              {{ truncateText(props.row.description, 30) }}
              <q-tooltip
                v-if="props.row.description.length >= 30"
                style="font-size: 12px"
                >{{ props.row.description }}</q-tooltip
              >
            </q-td>
            <q-td key="default_timeout" :props="props">{{
              props.row.default_timeout
            }}</q-td>
            <q-td></q-td>
          </q-tr>
        </template>
      </observer-table>
    </q-card>
  </q-dialog>
</template>

<script>
// composition imports
import { ref, computed, onMounted } from "vue";
import { useI18n } from "vue-i18n";
import { useStore } from "vuex";
import { useQuasar, useDialogPluginComponent, exportFile } from "quasar";
import { useStorage } from "@vueuse/core";
import {
  fetchScripts,
  editScript,
  downloadScript,
  removeScript,
} from "@/api/scripts";
import { capitalize, truncateText } from "@/utils/format";
import { notifySuccess } from "@/utils/notify";

// ui imports
import ScriptUploadModal from "@/components/scripts/ScriptUploadModal.vue";
import ScriptFormModal from "@/components/scripts/ScriptFormModal.vue";
import ScriptSnippets from "@/components/scripts/ScriptSnippets.vue";
import ObserverTable from "@/core/dashboard/ui/ObserverTable.vue";

import trmmLogo from "@/assets/trmm_256.png";

export default {
  name: "ScriptManager",
  components: {
    ObserverTable,
  },
  emits: [...useDialogPluginComponent.emits],
  setup() {
    // setup vuex store
    const store = useStore();
    const showCommunityScripts = computed(
      () => store.state.showCommunityScripts,
    );

    // setup quasar plugins
    const { dialogRef, onDialogHide } = useDialogPluginComponent();
    const $q = useQuasar();

    // i18n
    const { t } = useI18n();

    // table columns (computed for language reactivity)
    const columns = computed(() => [
      {
        name: "favorite",
        label: t("scriptManager.columnFavorites"),
        field: "favorite",
        align: "left",
        sortable: true,
      },
      {
        name: "shell",
        label: t("scriptManager.shell"),
        field: "shell",
        align: "left",
        sortable: true,
      },
      {
        name: "supported_platforms",
        label: t("scriptManager.columnPlatforms"),
        field: "supported_platforms",
        align: "left",
        sortable: true,
      },
      {
        name: "name",
        label: t("scriptsCommon.name"),
        field: "name",
        align: "left",
        sortable: true,
      },
      {
        name: "args",
        label: t("scriptManager.columnDefaultArgs"),
        field: "args",
        align: "left",
        sortable: true,
      },
      {
        name: "category",
        label: t("scriptsCommon.category"),
        field: "category",
        align: "left",
        sortable: true,
      },
      {
        name: "desc",
        label: t("scriptsCommon.description"),
        field: "description",
        align: "left",
        sortable: false,
      },
      {
        name: "default_timeout",
        label: t("scriptManager.columnDefaultTimeout"),
        field: "default_timeout",
        align: "left",
        sortable: true,
      },
    ]);

    // script manager logic
    const scripts = ref([]);
    const showHiddenScripts = ref(false);

    async function getScripts() {
      loading.value = true;
      try {
        scripts.value = await fetchScripts({ showHiddenScripts: true });
      } catch (e) {
        console.error(e);
      }
      loading.value = false;
    }

    async function favoriteScript(script) {
      loading.value = true;
      const notifyText = !script.favorite
        ? t("scriptManager.scriptFavorited")
        : t("scriptManager.scriptUnfavorited");
      try {
        await editScript({
          id: script.id,
          favorite: !script.favorite,
        });
        await getScripts();
        notifySuccess(notifyText);
      } catch (e) {}

      loading.value = false;
    }

    async function hideScript(script) {
      loading.value = true;
      const notifyText = !script.hidden
        ? t("scriptManager.scriptHidden")
        : t("scriptManager.scriptUnhidden");
      try {
        await editScript({
          id: script.id,
          hidden: !script.hidden,
        });
        await getScripts();
        notifySuccess(notifyText);
      } catch (e) {}

      loading.value = false;
    }

    function deleteScript(script) {
      $q.dialog({
        title: t("scriptManager.deleteTitle", { name: script.name }),
        cancel: true,
        ok: { label: t("scriptsCommon.delete"), color: "negative" },
      }).onOk(async () => {
        loading.value = true;
        try {
          const data = await removeScript(script.id);
          notifySuccess(data);
          getScripts();
        } catch (e) {}

        loading.value = false;
      });
    }

    async function exportScript(script) {
      loading.value = true;

      try {
        const { code, filename } = await downloadScript(script.id);
        exportFile(filename, new Blob([code]), {
          mimeType: "text/plain;charset=utf-8",
        });
      } catch (e) {
        console.error(e);
      }
      loading.value = false;
    }

    // table and tree view setup
    const storageKey = "scriptmanager_";
    const search = ref("");
    const tableView = useStorage(`${storageKey}tableView`, true);
    const expanded = useStorage(`${storageKey}expanded`, []);
    const loading = ref(false);

    const visibleScripts = computed(() => {
      if (showHiddenScripts.value) {
        return showCommunityScripts.value
          ? scripts.value
          : scripts.value.filter((i) => i.script_type !== "builtin");
      } else {
        return showCommunityScripts.value
          ? scripts.value.filter((i) => !i.hidden)
          : scripts.value.filter(
              (i) => i.script_type !== "builtin" && !i.hidden,
            );
      }
    });

    const categories = computed(() => {
      let list = [];
      visibleScripts.value.forEach((script) => {
        if (!!script.category && !list.includes(script.category)) {
          list.push(script.category);
        }
      });
      return list;
    });

    const tree = computed(() => {
      if (tableView.value || visibleScripts.value.length === 0) {
        return [];
      } else {
        let nodes = [];

        // copy scripts and categories to new array
        let scriptsTemp = Object.assign([], visibleScripts.value);
        let categoriesTemp = Object.assign([], categories.value);

        // add Unassigned category
        categoriesTemp.push("Unassigned");

        const sortedCategories = categoriesTemp.sort();

        // sort by name property
        const sortedScripts = scriptsTemp.sort(function (a, b) {
          const nameA = a.name.toUpperCase();
          const nameB = b.name.toUpperCase();

          if (nameA < nameB) {
            return -1;
          }
          if (nameA > nameB) {
            return 1;
          }
          // names must be equal
          return 0;
        });

        sortedCategories.forEach((category) => {
          let temp = {
            icon: "folder",
            iconColor: "yellow-9",
            label: category,
            selectable: false,
            id: category,
            children: [],
          };

          for (let x = 0; x < sortedScripts.length; x++) {
            if (sortedScripts[x].category === category) {
              temp.children.push({
                label: sortedScripts[x].name,
                header: "script",
                ...sortedScripts[x],
              });
            } else if (
              category === "Unassigned" &&
              !sortedScripts[x].category
            ) {
              temp.children.push({
                label: sortedScripts[x].name,
                header: "script",
                ...sortedScripts[x],
              });
            }
          }

          nodes.push(temp);
        });

        return nodes;
      }
    });

    // dialog open functions
    function viewCodeModal(script) {
      $q.dialog({
        component: ScriptFormModal,
        componentProps: {
          script: script,
          readonly: true,
        },
      });
    }

    function newScriptModal() {
      $q.dialog({
        component: ScriptFormModal,
        componentProps: {
          categories: categories.value,
          readonly: false,
        },
      }).onOk(() => {
        getScripts();
      });
    }

    function editScriptModal(script) {
      $q.dialog({
        component: ScriptFormModal,
        componentProps: {
          script: script,
          categories: categories.value,
          readonly: false,
        },
      }).onOk(() => {
        getScripts();
      });
    }

    function cloneScriptModal(script) {
      $q.dialog({
        component: ScriptFormModal,
        componentProps: {
          script: script,
          categories: categories.value,
          readonly: false,
          clone: true,
        },
      }).onOk(() => {
        getScripts();
      });
    }

    function uploadScriptModal() {
      $q.dialog({
        component: ScriptUploadModal,
        componentProps: {
          categories: categories.value,
        },
      }).onOk(() => {
        getScripts();
      });
    }

    function ScriptSnippetModal() {
      $q.dialog({
        component: ScriptSnippets,
      });
    }

    // component life cycle hooks
    onMounted(getScripts);

    return {
      // reactive data
      search,
      tableView,
      expanded,
      loading,
      showCommunityScripts,
      showHiddenScripts,
      trmmLogo,

      // computed
      visibleScripts,

      // non-reactive data
      columns,
      storageKey,

      // api methods
      getScripts,
      deleteScript,
      favoriteScript,
      hideScript,
      exportScript,

      // dialog methods
      viewCodeModal,
      newScriptModal,
      editScriptModal,
      cloneScriptModal,
      uploadScriptModal,
      ScriptSnippetModal,

      // table and tree view methods
      tree,
      setShowCommunityScripts: (show) =>
        store.dispatch("setShowCommunityScripts", show),

      // helper methods
      truncateText,
      capitalize,

      // quasar dialog plugin
      dialogRef,
      onDialogHide,
    };
  },
};
</script>
