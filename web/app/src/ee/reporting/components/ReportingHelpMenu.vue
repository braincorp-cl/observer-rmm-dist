<template>
  <div class="q-px-sm">
    <div class="text-h5">{{ $t("reporting.helpMenu.reportTemplateTitle") }}</div>

    <div class="q-px-sm">
      <div class="text-body1">
        {{ $t("reporting.helpMenu.reportTemplatesLabel") }}
      </div>
    </div>

    <div class="text-h5">{{ $t("reporting.helpMenu.baseTemplateTitle") }}</div>

    <div class="q-px-sm">
      <div class="text-body1">
        {{ $t("reporting.helpMenu.baseTemplatePlaceholder") }}
      </div>
    </div>

    <div class="text-h5">{{ $t("reporting.helpMenu.dataQueryTitle") }}</div>

    <div class="q-px-sm">
      <div class="text-body1">
        {{ $t("reporting.helpMenu.dataQueryIntro") }}
      </div>
      <div class="text-h6">{{ $t("reporting.helpMenu.syntaxTitle") }}</div>
      <div class="q-px-sm">
        <div class="text-body1">
          {{ $t("reporting.helpMenu.syntaxBody") }}
        </div>
      </div>

      <div class="text-body1"></div>

      <div class="text-h6">{{ $t("reporting.helpMenu.structureTitle") }}</div>
      <div class="q-px-sm">
        <div class="text-body1">
          {{ $t("reporting.helpMenu.structureAutocomplete") }}
        </div>

        <dl>
          <dt>{{ $t("reporting.helpMenu.fieldModel") }}</dt>
          <dd>
            {{ $t("reporting.helpMenu.fieldModelDesc") }}
          </dd>
          <dt>{{ $t("reporting.helpMenu.fieldFilter") }}</dt>
          <dd></dd>
        </dl>
      </div>
    </div>
  </div>
</template>

<script setup lang="ts">
defineProps<{
  section: "template" | "baseTemplate" | "dataQuery";
}>();
</script>
