<template>
  <q-input
    outlined
    dense
    :model-value="displayValue"
    :type="inputType"
    :readonly="!editing"
    :placeholder="placeholder"
    :input-class="masked ? 'ormm-secret-mask' : ''"
    bottom-slots
    @update:model-value="onInput"
    @click="beginEdit"
    @keydown="onKeydown"
    @focus="beginEdit"
    @blur="onBlur"
    v-bind="$attrs"
  >
    <template v-slot:hint>
      <span :class="cleared ? 'text-negative' : ''">{{ hint }}</span>
    </template>

    <template v-slot:append>
      <!-- editando: mostrar u ocultar lo que se escribe, o descartar el cambio -->
      <template v-if="editing">
        <q-btn
          flat
          dense
          round
          size="sm"
          :icon="revealed ? 'visibility' : 'visibility_off'"
          :aria-label="revealed ? t('secretInput.hide') : t('secretInput.show')"
          @mousedown.prevent
          @click="revealed = !revealed"
        >
          <q-tooltip>
            {{ revealed ? t("secretInput.hide") : t("secretInput.show") }}
          </q-tooltip>
        </q-btn>
        <q-btn
          flat
          dense
          round
          size="sm"
          icon="close"
          :aria-label="t('secretInput.cancel')"
          @mousedown.prevent
          @click="cancelEdit"
        >
          <q-tooltip>{{ t("secretInput.cancel") }}</q-tooltip>
        </q-btn>
      </template>

      <!-- marcado para quitar: se puede deshacer hasta que se guarde -->
      <q-btn
        v-else-if="cleared"
        flat
        dense
        round
        size="sm"
        icon="undo"
        :aria-label="t('secretInput.undo')"
        @mousedown.prevent
        @click="undoRemove"
      >
        <q-tooltip>{{ t("secretInput.undo") }}</q-tooltip>
      </q-btn>

      <!-- en reposo con valor guardado: sólo se puede quitar -->
      <q-btn
        v-else-if="isSet"
        flat
        dense
        round
        size="sm"
        icon="delete_outline"
        :aria-label="t('secretInput.remove')"
        @mousedown.prevent
        @click="confirmRemove"
      >
        <q-tooltip>{{ t("secretInput.remove") }}</q-tooltip>
      </q-btn>
    </template>
  </q-input>
</template>

<script setup>
import { computed, ref, watch } from "vue";
import { useQuasar } from "quasar";
import { useI18n } from "vue-i18n";

defineOptions({
  name: "secret-input",
  inheritAttrs: false,
});

// Largo fijo: el relleno no debe delatar cuántos caracteres tiene el valor real.
const MASK = "•".repeat(12);

// Tiene que ser idéntico al CLEAR_SECRET de core/serializers.py. Vacío significa
// "no lo toqué", así que el borrado necesita una señal propia.
const CLEAR_SECRET = "__ORMM_SECRET_CLEAR__";

const props = defineProps({
  modelValue: {
    type: String,
    default: "",
  },
  // El backend no manda el valor guardado, sólo si existe.
  isSet: {
    type: Boolean,
    default: false,
  },
});

const emit = defineEmits(["update:modelValue"]);

const $q = useQuasar();
const { t } = useI18n();

const editing = ref(false);
const revealed = ref(true);
const cleared = ref(false);

const masked = computed(() => !editing.value && props.isSet && !cleared.value);

const displayValue = computed(() => {
  if (editing.value) return props.modelValue;
  return masked.value ? MASK : "";
});

const inputType = computed(() =>
  editing.value && !revealed.value ? "password" : "text",
);

const placeholder = computed(() => {
  if (editing.value) return t("secretInput.typeNewValue");
  return masked.value || cleared.value ? "" : t("secretInput.notSet");
});

const hint = computed(() => {
  if (cleared.value) return t("secretInput.willBeRemoved");
  if (editing.value) return "";
  return props.isSet ? t("secretInput.stored") : "";
});

// Último valor que emitió este campo, para distinguir lo que escribe la persona
// de lo que reescribe el formulario al recargarse.
const ownValue = ref("");

function update(value) {
  ownValue.value = value;
  emit("update:modelValue", value);
}

function beginEdit() {
  if (editing.value) return;
  editing.value = true;
  revealed.value = true;
  cleared.value = false;
  update("");
}

function onInput(value) {
  update(value);
}

// El campo en reposo es de sólo lectura, y ahí QInput no emite `focus`: sin esto
// se podía enfocar con el tabulador y quedar atrapado, sin forma de escribir.
// Probado en staging: el clic dejaba el campo enfocado pero enmascarado.
function onKeydown(e) {
  if (editing.value) return;
  if (e.ctrlKey || e.metaKey || e.altKey) return;
  if (["Tab", "Shift", "Escape"].includes(e.key)) return;

  // Enter dentro del formulario lo enviaría en vez de abrir la edición
  if (e.key === "Enter") e.preventDefault();

  beginEdit();

  // el primer carácter no se pierde: el input de sólo lectura no lo recibe
  if (e.key.length === 1) update(e.key);
}

function onBlur() {
  // salir sin escribir nada deja el valor guardado intacto
  if (editing.value && !props.modelValue) editing.value = false;
}

function cancelEdit() {
  editing.value = false;
  update("");
}

function confirmRemove() {
  $q.dialog({
    title: t("secretInput.removeTitle"),
    message: t("secretInput.removeMessage"),
    ok: { label: t("secretInput.remove"), color: "negative" },
    cancel: { label: t("secretInput.cancel"), color: "primary" },
  }).onOk(() => {
    cleared.value = true;
    editing.value = false;
    update(CLEAR_SECRET);
  });
}

function undoRemove() {
  cleared.value = false;
  update("");
}

// El formulario recarga la configuración después de "Guardar y probar": ahí el
// campo vuelve a reposo en vez de quedarse mostrando lo que se acaba de escribir.
watch(
  () => props.modelValue,
  (value) => {
    if (value === ownValue.value) return;
    ownValue.value = value;
    editing.value = false;
    cleared.value = false;
  },
);
</script>

<style>
/* Los puntos del valor guardado se leen como relleno, no como texto editable. */
.ormm-secret-mask {
  letter-spacing: 0.18em;
  opacity: 0.6;
}
</style>
