<template>
  <q-dialog ref="dialog" @hide="onHide">
    <q-card class="q-dialog-plugin" style="width: 60vw">
      <q-bar>
        {{ title }}
        <q-space />
        <q-btn dense flat icon="close" v-close-popup>
          <q-tooltip>{{ $t("keyStoreForm.close") }}</q-tooltip>
        </q-btn>
      </q-bar>
      <q-form @submit="submit">
        <!-- name -->
        <q-card-section>
          <q-input
            :label="$t('keyStoreForm.name')"
            outlined
            dense
            v-model="localKey.name"
            :rules="[(val) => !!val || $t('keyStoreForm.required')]"
          />
        </q-card-section>

        <!-- value -->
        <q-card-section>
          <q-input
            :label="$t('keyStoreForm.value')"
            outlined
            dense
            v-model="localKey.value"
            class="obs-mono-values"
            :type="isPwd ? 'password' : 'text'"
            :hint="keepsStoredValue ? $t('keyStoreForm.keepHint') : ''"
            :rules="[
              (val) => !!val || keepsStoredValue || $t('keyStoreForm.required'),
            ]"
            ><template v-slot:append>
              <q-icon
                :name="isPwd ? 'visibility_off' : 'visibility'"
                class="cursor-pointer"
                @click="isPwd = !isPwd"
              />
            </template>
          </q-input>
        </q-card-section>

        <!-- RT-AUT-09: una clave secreta no vuelve nunca a la consola -->
        <q-card-section>
          <q-toggle
            v-model="localKey.is_secret"
            :label="$t('keyStoreForm.isSecret')"
          />
          <!-- V2-G02: `text-grey-7` es un gris de la paleta de Quasar y no
               un token del proyecto. Llego por el merge de RT-AUT-09. -->
          <div class="text-caption obs-text-muted">
            {{ $t("keyStoreForm.isSecretHint") }}
          </div>
        </q-card-section>

        <q-card-actions align="right">
          <q-btn flat :label="$t('keyStoreForm.cancel')" v-close-popup />
          <q-btn
            flat
            :label="$t('keyStoreForm.submit')"
            color="primary"
            type="submit"
          />
        </q-card-actions>
      </q-form>
    </q-card>
  </q-dialog>
</template>

<script>
import mixins from "@/mixins/mixins";

export default {
  name: "KeyStoreForm",
  emits: ["hide", "ok", "cancel"],
  mixins: [mixins],
  props: { globalKey: Object },
  data() {
    return {
      isPwd: true,
      localKey: {
        name: "",
        value: "",
        is_secret: true,
      },
    };
  },
  computed: {
    title() {
      return this.editing
        ? this.$t("keyStoreForm.titleEdit")
        : this.$t("keyStoreForm.titleAdd");
    },
    editing() {
      return !!this.globalKey;
    },
    // Al editar una clave secreta el valor llega vacío: dejarlo así conserva el
    // guardado. Quitar la marca de secreto, en cambio, exige escribir uno nuevo.
    keepsStoredValue() {
      return (
        this.editing && !!this.globalKey.is_secret && !!this.localKey.is_secret
      );
    },
  },
  methods: {
    submit() {
      this.$q.loading.show();

      let data = {
        ...this.localKey,
      };
      delete data.value_set;
      if (this.editing && !data.value) delete data.value;

      if (this.editing) {
        this.$axios
          .put(`/core/keystore/${data.id}/`, data)
          .then(() => {
            this.$q.loading.hide();
            this.onOk();
            this.notifySuccess(this.$t("keyStoreForm.editedSuccess"));
          })
          .catch(() => {
            this.$q.loading.hide();
          });
      } else {
        this.$axios
          .post("/core/keystore/", data)
          .then(() => {
            this.$q.loading.hide();
            this.onOk();
            this.notifySuccess(this.$t("keyStoreForm.addedSuccess"));
          })
          .catch(() => {
            this.$q.loading.hide();
          });
      }
    },
    show() {
      this.$refs.dialog.show();
    },
    hide() {
      this.$refs.dialog.hide();
    },
    onHide() {
      this.$emit("hide");
    },
    onOk() {
      this.$emit("ok");
      this.hide();
    },
  },
  mounted() {
    // If pk prop is set that means we are editing
    if (this.globalKey) Object.assign(this.localKey, this.globalKey);
  },
};
</script>
