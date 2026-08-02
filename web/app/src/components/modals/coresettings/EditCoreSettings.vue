<template>
  <q-card style="min-width: 60vw">
    <q-splitter v-model="splitterModel">
      <template v-slot:before>
        <q-tabs dense v-model="tab" vertical class="text-primary">
          <q-tab name="general" :label="$t('editCoreSettings.tabGeneral')" />
          <q-tab
            name="emailalerts"
            :label="$t('editCoreSettings.tabEmailAlerts')"
          />
          <q-tab
            name="smsalerts"
            :label="$t('editCoreSettings.tabSmsAlerts')"
          />
          <q-tab
            name="meshcentral"
            :label="$t('editCoreSettings.tabMeshCentral')"
          />
          <q-tab
            name="customfields"
            :label="$t('editCoreSettings.tabCustomFields')"
          />
          <q-tab name="keystore" :label="$t('editCoreSettings.tabKeyStore')" />
          <q-tab
            name="urlactions"
            :label="$t('editCoreSettings.tabUrlActions')"
          />
          <q-tab name="webhooks" :label="$t('editCoreSettings.tabWebHooks')" />
          <q-tab
            name="retention"
            :label="$t('editCoreSettings.tabRetention')"
          />
          <q-tab name="apikeys" :label="$t('editCoreSettings.tabApiKeys')" />
          <!-- SSO descartado (ADR-010, 2026-06-17): tab Single Sign-On eliminado (módulo ee/sso vaciado). -->
          <q-tab
            name="schedules"
            :label="$t('editCoreSettings.tabSchedules')"
          />
          <q-tab name="ai" :label="$t('editCoreSettings.tabAiAssistant')" />
        </q-tabs>
      </template>
      <template v-slot:after>
        <q-form @submit.prevent="editSettings">
          <q-card-section class="row items-center">
            <div class="text-h6">
              {{ $t("editCoreSettings.globalSettings") }}
            </div>
            <q-space />
            <q-btn icon="close" flat round dense v-close-popup />
          </q-card-section>
          <q-scroll-area :thumb-style="thumbStyle" style="height: 60vh">
            <q-tab-panels
              v-model="tab"
              animated
              transition-prev="jump-up"
              transition-next="jump-up"
            >
              <!-- general -->
              <q-tab-panel name="general">
                <div class="text-subtitle2">
                  {{ $t("editCoreSettings.tabGeneral") }}
                </div>
                <q-separator />
                <q-card-section class="row">
                  <q-checkbox
                    v-model="settings.agent_auto_update"
                    :label="$t('editCoreSettings.agentAutoUpdate')"
                  >
                    <q-tooltip>
                      {{ $t("editCoreSettings.agentAutoUpdateTooltip") }}
                    </q-tooltip>
                  </q-checkbox>
                </q-card-section>
                <q-card-section class="row">
                  <q-checkbox
                    v-model="settings.geo_tracking_enabled"
                    :label="$t('editCoreSettings.geoTracking')"
                  >
                    <q-tooltip>
                      {{ $t("editCoreSettings.geoTrackingTooltip") }}
                    </q-tooltip>
                  </q-checkbox>
                </q-card-section>
                <q-card-section class="row q-pl-lg">
                  <q-checkbox
                    v-model="settings.geo_force_location_on"
                    :disable="!settings.geo_tracking_enabled"
                    :label="$t('editCoreSettings.geoForceLocation')"
                  >
                    <q-tooltip>
                      {{ $t("editCoreSettings.geoForceLocationTooltip") }}
                    </q-tooltip>
                  </q-checkbox>
                </q-card-section>
                <!-- Geocerca por sitio (feature 026) -->
                <q-card-section class="row items-center q-pl-lg q-gutter-md">
                  <q-checkbox
                    v-model="settings.geo_geofence_enabled"
                    :disable="!settings.geo_tracking_enabled"
                    :label="$t('editCoreSettings.geoGeofence')"
                  >
                    <q-tooltip>
                      {{ $t("editCoreSettings.geoGeofenceTooltip") }}
                    </q-tooltip>
                  </q-checkbox>
                  <q-input
                    dense
                    outlined
                    type="number"
                    style="width: 12rem"
                    v-model.number="settings.geo_geofence_radius_m"
                    :disable="
                      !settings.geo_tracking_enabled ||
                      !settings.geo_geofence_enabled
                    "
                    :label="$t('editCoreSettings.geoGeofenceRadius')"
                    :rules="[
                      (val) =>
                        (val >= 50 && val <= 1000000) ||
                        $t('editCoreSettings.geoGeofenceRadiusRule'),
                    ]"
                  />
                </q-card-section>
                <q-card-section v-if="!hosted" class="row">
                  <q-checkbox
                    v-model="settings.enable_server_scripts"
                    :label="$t('editCoreSettings.enableServerScripts')"
                  >
                    <q-tooltip>{{
                      $t("editCoreSettings.enableServerScriptsTooltip")
                    }}</q-tooltip>
                  </q-checkbox>
                  <q-btn
                    size="sm"
                    round
                    dense
                    flat
                    icon="warning"
                    @click="
                      openURL(
                        'https://docs.observer.cl/functions/permissions/#permisos-con-implicancias-de-seguridad',
                      )
                    "
                  >
                  </q-btn>
                </q-card-section>
                <q-card-section v-if="!hosted" class="row">
                  <q-checkbox
                    v-model="settings.enable_server_webterminal"
                    :label="$t('editCoreSettings.enableWebTerminal')"
                  >
                    <q-tooltip>{{
                      $t("editCoreSettings.enableWebTerminalTooltip")
                    }}</q-tooltip>
                  </q-checkbox>
                  <q-btn
                    size="sm"
                    round
                    dense
                    flat
                    icon="warning"
                    @click="
                      openURL(
                        'https://docs.observer.cl/functions/permissions/#permisos-con-implicancias-de-seguridad',
                      )
                    "
                  >
                  </q-btn>
                </q-card-section>
                <q-card-section class="row">
                  <div class="col-4">
                    {{ $t("editCoreSettings.defaultAgentTimezone") }}
                  </div>
                  <div class="col-2"></div>
                  <observer-dropdown
                    filterable
                    outlined
                    dense
                    options-dense
                    v-model="settings.default_time_zone"
                    :options="allTimezones"
                    class="col-6"
                  />
                </q-card-section>
                <q-card-section class="row">
                  <div class="col-4">
                    {{ $t("editCoreSettings.defaultDateFormat") }}
                  </div>
                  <div class="col-2"></div>
                  <q-input
                    outlined
                    dense
                    v-model="settings.date_format"
                    class="col-6"
                  >
                    <template v-slot:after>
                      <q-btn
                        round
                        dense
                        flat
                        size="sm"
                        icon="info"
                        @click="
                          openURL(
                            'https://quasar.dev/quasar-utils/date-utils#format-for-display',
                          )
                        "
                      >
                        <q-tooltip>{{
                          $t("editCoreSettings.dateFormatTooltip")
                        }}</q-tooltip>
                      </q-btn>
                    </template>
                  </q-input>
                </q-card-section>
                <q-card-section class="row">
                  <div class="col-4">
                    {{ $t("editCoreSettings.defaultServerPolicy") }}
                  </div>
                  <div class="col-2"></div>
                  <q-select
                    clearable
                    map-options
                    emit-value
                    outlined
                    dense
                    options-dense
                    v-model="settings.server_policy"
                    :options="policies"
                    class="col-6"
                  />
                </q-card-section>
                <q-card-section class="row">
                  <div class="col-4">
                    {{ $t("editCoreSettings.defaultWorkstationPolicy") }}
                  </div>
                  <div class="col-2"></div>
                  <q-select
                    clearable
                    map-options
                    emit-value
                    outlined
                    dense
                    options-dense
                    v-model="settings.workstation_policy"
                    :options="policies"
                    class="col-6"
                  />
                </q-card-section>
                <q-card-section class="row">
                  <div class="col-4">
                    {{ $t("editCoreSettings.defaultAlertTemplate") }}
                  </div>
                  <div class="col-2"></div>
                  <q-select
                    clearable
                    map-options
                    emit-value
                    outlined
                    dense
                    options-dense
                    v-model="settings.alert_template"
                    :options="alertTemplateOptions"
                    class="col-6"
                  />
                </q-card-section>
                <q-card-section class="row">
                  <div class="col-4 flex items-center">
                    {{ $t("editCoreSettings.receiveNotificationsOn") }}
                  </div>
                  <div class="col-2"></div>
                  <q-checkbox
                    dense
                    v-model="settings.notify_on_info_alerts"
                    class="col-3"
                    :label="$t('editCoreSettings.informationalAlerts')"
                  />
                  <q-checkbox
                    dense
                    v-model="settings.notify_on_warning_alerts"
                    class="col-3"
                    :label="$t('editCoreSettings.warningAlerts')"
                  />
                </q-card-section>
                <q-card-section class="row">
                  <div class="col-4">
                    {{ $t("editCoreSettings.agentDebugLevel") }}
                  </div>
                  <div class="col-2"></div>
                  <q-select
                    emit-value
                    map-options
                    outlined
                    dense
                    options-dense
                    v-model="settings.agent_debug_level"
                    :options="logLevelOptions"
                    class="col-6"
                  />
                </q-card-section>
                <q-card-section class="row">
                  <div class="col-4">
                    {{ $t("editCoreSettings.clearFaultsDays") }}
                  </div>
                  <div class="col-2"></div>
                  <q-input
                    :hint="$t('editCoreSettings.disableFeatureHint')"
                    outlined
                    dense
                    v-model.number="settings.clear_faults_days"
                    class="col-6"
                    :rules="[
                      (val) => val >= 0 || $t('editCoreSettings.minZero'),
                    ]"
                  />
                </q-card-section>
                <q-card-section class="row">
                  <div class="col-4">
                    {{ $t("editCoreSettings.resetPatchPolicyLabel") }}
                  </div>
                  <div class="col-2"></div>
                  <q-btn
                    color="negative"
                    :label="$t('editCoreSettings.reset')"
                    @click="showResetPatchPolicy"
                  />
                </q-card-section>
              </q-tab-panel>
              <!-- email alerts -->
              <q-tab-panel name="emailalerts">
                <div class="text-subtitle2 row">
                  <div>{{ $t("editCoreSettings.emailAlertRouting") }}</div>
                  <q-space />
                  <div>
                    <q-btn
                      size="sm"
                      color="grey-5"
                      icon="fas fa-plus"
                      text-color="black"
                      :label="$t('editCoreSettings.addEmails')"
                      @click="toggleAddEmail"
                    />
                  </div>
                </div>
                <q-separator />
                <q-card-section class="row">
                  <div class="col-3">
                    {{ $t("editCoreSettings.recipients") }}
                  </div>
                  <div class="col-4"></div>
                  <div class="col-5">
                    <q-list
                      dense
                      v-if="
                        ready && settings.email_alert_recipients.length !== 0
                      "
                    >
                      <q-item
                        v-for="email in settings.email_alert_recipients"
                        :key="email"
                        clickable
                        v-ripple
                        @click="removeEmail(email)"
                      >
                        <q-item-section>
                          <q-item-label>{{ email }}</q-item-label>
                        </q-item-section>
                        <q-item-section side>
                          <q-icon name="delete" color="red" />
                        </q-item-section>
                      </q-item>
                    </q-list>
                    <q-list v-else>
                      <q-item-section>
                        <q-item-label>{{
                          $t("editCoreSettings.noRecipients")
                        }}</q-item-label>
                      </q-item-section>
                    </q-list>
                  </div>
                </q-card-section>
                <!-- smtp -->
                <div class="text-subtitle2">
                  {{ $t("editCoreSettings.smtpSettings") }}
                </div>
                <q-separator />
                <q-card-section class="row">
                  <div class="col-2">
                    {{ $t("editCoreSettings.fromEmail") }}
                  </div>
                  <div class="col-4"></div>
                  <q-input
                    outlined
                    dense
                    v-model="settings.smtp_from_email"
                    class="col-6 q-pa-none"
                    :rules="[
                      (val) =>
                        isValidEmail(val) ||
                        $t('editCoreSettings.invalidEmail'),
                    ]"
                  />
                </q-card-section>
                <q-card-section class="row">
                  <div class="col-2">{{ $t("editCoreSettings.fromName") }}</div>
                  <div class="col-4"></div>
                  <q-input
                    outlined
                    dense
                    v-model="settings.smtp_from_name"
                    class="col-6 q-pa-none"
                  />
                </q-card-section>
                <q-card-section class="row">
                  <div class="col-2">{{ $t("editCoreSettings.host") }}</div>
                  <div class="col-4"></div>
                  <q-input
                    outlined
                    dense
                    v-model="settings.smtp_host"
                    class="col-6 q-pa-none"
                  />
                </q-card-section>
                <q-card-section class="row">
                  <div class="col-2">{{ $t("editCoreSettings.port") }}</div>
                  <div class="col-4"></div>
                  <q-input
                    dense
                    v-model.number="settings.smtp_port"
                    type="number"
                    filled
                    class="q-pa-none"
                    :rules="[
                      (val) =>
                        (val > 0 && val <= 65535) ||
                        $t('editCoreSettings.invalidPort'),
                    ]"
                  />
                </q-card-section>
                <q-card-section class="row">
                  <q-checkbox
                    v-model="settings.smtp_requires_auth"
                    :label="$t('editCoreSettings.requiresAuth')"
                    class="q-pa-none"
                  />
                </q-card-section>
                <q-card-section
                  class="row"
                  v-show="settings.smtp_requires_auth"
                >
                  <div class="col-2">
                    {{ $t("editCoreSettings.username") }}
                  </div>
                  <div class="col-4"></div>
                  <q-input
                    outlined
                    dense
                    v-model="settings.smtp_host_user"
                    class="col-6 q-pa-none"
                  />
                </q-card-section>
                <q-card-section
                  class="row"
                  v-show="settings.smtp_requires_auth"
                >
                  <div class="col-2">
                    {{ $t("editCoreSettings.password") }}
                  </div>
                  <div class="col-4"></div>
                  <q-input
                    outlined
                    dense
                    class="col-6 q-pa-none"
                    v-model="settings.smtp_host_password"
                    :type="isPwd ? 'password' : 'text'"
                  >
                    <template v-slot:append>
                      <q-icon
                        :name="isPwd ? 'visibility_off' : 'visibility'"
                        class="cursor-pointer"
                        @click="isPwd = !isPwd"
                      />
                    </template>
                  </q-input>
                </q-card-section>
              </q-tab-panel>
              <!-- twilio sms alerts -->
              <q-tab-panel name="smsalerts">
                <div class="text-subtitle2 row">
                  <div>{{ $t("editCoreSettings.smsAlertRouting") }}</div>
                  <q-space />
                  <div>
                    <q-btn
                      size="sm"
                      color="grey-5"
                      icon="fas fa-plus"
                      text-color="black"
                      :label="$t('editCoreSettings.addNumbers')"
                      @click="toggleAddSMSNumber"
                    />
                  </div>
                </div>
                <q-separator />
                <q-card-section class="row">
                  <div class="col-3">
                    {{ $t("editCoreSettings.recipients") }}
                  </div>
                  <div class="col-4"></div>
                  <div class="col-5">
                    <q-list
                      dense
                      v-if="ready && settings.sms_alert_recipients.length !== 0"
                    >
                      <q-item
                        v-for="num in settings.sms_alert_recipients"
                        :key="num"
                        clickable
                        v-ripple
                        @click="removeSMSNumber(num)"
                      >
                        <q-item-section>
                          <q-item-label>{{ num }}</q-item-label>
                        </q-item-section>
                        <q-item-section side>
                          <q-icon name="delete" color="red" />
                        </q-item-section>
                      </q-item>
                    </q-list>
                    <q-list v-else>
                      <q-item-section>
                        <q-item-label>{{
                          $t("editCoreSettings.noRecipients")
                        }}</q-item-label>
                      </q-item-section>
                    </q-list>
                  </div>
                </q-card-section>
                <!-- smtp -->
                <div class="text-subtitle2">
                  {{ $t("editCoreSettings.twilioSettings") }}
                </div>
                <q-separator />
                <q-card-section class="row">
                  <div class="col-3">
                    {{ $t("editCoreSettings.twilioNumber") }}
                  </div>
                  <div class="col-3"></div>
                  <q-input
                    outlined
                    dense
                    v-model="settings.twilio_number"
                    class="col-6 q-pa-none"
                    placeholder="+12131231234"
                  />
                </q-card-section>
                <q-card-section class="row">
                  <div class="col-3">
                    {{ $t("editCoreSettings.twilioAccountSid") }}
                  </div>
                  <div class="col-3"></div>
                  <q-input
                    outlined
                    dense
                    v-model="settings.twilio_account_sid"
                    class="col-6 q-pa-none"
                  />
                </q-card-section>
                <q-card-section class="row">
                  <div class="col-3">
                    {{ $t("editCoreSettings.twilioAuthToken") }}
                  </div>
                  <div class="col-3"></div>
                  <q-input
                    outlined
                    dense
                    v-model="settings.twilio_auth_token"
                    class="col-6 q-pa-none"
                  />
                </q-card-section>
              </q-tab-panel>
              <!-- meshcentral -->
              <q-tab-panel name="meshcentral">
                <div class="text-subtitle2">
                  {{ $t("editCoreSettings.meshSettings") }}
                </div>
                <q-separator />
                <q-card-section class="row" v-if="!hosted">
                  <div class="col-4">
                    {{ $t("editCoreSettings.username") }}
                  </div>
                  <div class="col-2"></div>
                  <q-input
                    dense
                    outlined
                    v-model="settings.mesh_username"
                    class="col-6"
                    :rules="[
                      (val) =>
                        (val == val.toLowerCase() &&
                          val != val.toUpperCase()) ||
                        $t('editCoreSettings.usernameLowercase'),
                    ]"
                  />
                </q-card-section>
                <q-card-section class="row" v-if="!hosted">
                  <div class="col-4">
                    {{ $t("editCoreSettings.meshSite") }}
                  </div>
                  <div class="col-2"></div>
                  <q-input
                    dense
                    outlined
                    v-model="settings.mesh_site"
                    class="col-6"
                  />
                </q-card-section>
                <q-card-section class="row" v-if="!hosted">
                  <div class="col-4">
                    {{ $t("editCoreSettings.meshToken") }}
                  </div>
                  <div class="col-2"></div>
                  <q-input
                    dense
                    outlined
                    v-model="settings.mesh_token"
                    class="col-6"
                  />
                </q-card-section>
                <q-card-section class="row" v-if="!hosted">
                  <div class="col-4">
                    {{ $t("editCoreSettings.meshDeviceGroup") }}
                  </div>
                  <div class="col-2"></div>
                  <q-input
                    dense
                    outlined
                    v-model="settings.mesh_device_group"
                    class="col-6"
                  />
                </q-card-section>
                <q-card-section class="row" v-if="!hosted">
                  <div class="col-4 flex items-center">
                    {{ $t("editCoreSettings.syncMeshPerms") }}
                    <q-icon
                      right
                      name="ion-information-circle-outline"
                      size="sm"
                      class="cursor-pointer"
                    >
                      <q-tooltip class="text-caption">
                        {{ $t("editCoreSettings.syncMeshPermsTooltip") }}
                      </q-tooltip>
                    </q-icon>
                  </div>
                  <div class="col-2"></div>
                  <q-checkbox
                    dense
                    :model-value="settings.sync_mesh_with_trmm"
                    @update:model-value="confirmSyncChange"
                    class="col-6"
                  />
                </q-card-section>

                <q-card-section class="row items-center">
                  <div class="col-4 flex items-center">
                    {{ $t("editCoreSettings.companyName") }}
                    <q-icon
                      name="ion-information-circle-outline"
                      size="sm"
                      class="q-ml-sm cursor-pointer"
                    >
                      <q-tooltip class="text-caption">
                        {{ $t("editCoreSettings.companyNameTooltip") }}
                      </q-tooltip>
                    </q-icon>
                  </div>

                  <div class="col-2"></div>

                  <q-input
                    dense
                    outlined
                    v-model="settings.mesh_company_name"
                    class="col-6"
                  >
                  </q-input>
                </q-card-section>
              </q-tab-panel>

              <!-- custom fields -->
              <q-tab-panel name="customfields">
                <CustomFields />
              </q-tab-panel>

              <!-- key store -->
              <q-tab-panel name="keystore">
                <KeyStoreTable />
              </q-tab-panel>

              <!-- url actions -->
              <q-tab-panel name="urlactions">
                <URLActionsTable type="web" />
              </q-tab-panel>

              <!-- web hooks -->
              <q-tab-panel name="webhooks">
                <URLActionsTable type="rest" />
              </q-tab-panel>

              <!-- retention -->
              <q-tab-panel name="retention">
                <q-card-section class="row">
                  <div class="col-4">
                    {{ $t("editCoreSettings.checkHistoryDays") }}
                  </div>
                  <div class="col-2"></div>
                  <q-input
                    dense
                    outlined
                    v-model="settings.check_history_prune_days"
                    class="col-6"
                    :hint="$t('editCoreSettings.disableFeatureHint')"
                  />
                </q-card-section>
                <q-card-section class="row">
                  <div class="col-4">
                    {{ $t("editCoreSettings.resolvedAlertsDays") }}
                  </div>
                  <div class="col-2"></div>
                  <q-input
                    dense
                    outlined
                    v-model="settings.resolved_alerts_prune_days"
                    class="col-6"
                    :hint="$t('editCoreSettings.disableFeatureHint')"
                  />
                </q-card-section>
                <q-card-section class="row">
                  <div class="col-4">
                    {{ $t("editCoreSettings.agentHistoryDays") }}
                  </div>
                  <div class="col-2"></div>
                  <q-input
                    dense
                    outlined
                    v-model="settings.agent_history_prune_days"
                    class="col-6"
                    :hint="$t('editCoreSettings.disableFeatureHint')"
                  />
                </q-card-section>
                <q-card-section class="row">
                  <div class="col-4">
                    {{ $t("editCoreSettings.debugLogsDays") }}
                  </div>
                  <div class="col-2"></div>
                  <q-input
                    dense
                    outlined
                    v-model="settings.debug_log_prune_days"
                    class="col-6"
                    :hint="$t('editCoreSettings.disableFeatureHint')"
                  />
                </q-card-section>
                <q-card-section class="row">
                  <div class="col-4">
                    {{ $t("editCoreSettings.auditLogsDays") }}
                  </div>
                  <div class="col-2"></div>
                  <q-input
                    dense
                    outlined
                    v-model="settings.audit_log_prune_days"
                    class="col-6"
                    :hint="$t('editCoreSettings.disableFeatureHint')"
                  />
                </q-card-section>
                <q-card-section class="row">
                  <div class="col-4">
                    {{ $t("editCoreSettings.reportHistoryDays") }}
                  </div>
                  <div class="col-2"></div>
                  <q-input
                    dense
                    outlined
                    v-model="settings.report_history_prune_days"
                    class="col-6"
                    :hint="$t('editCoreSettings.disableFeatureHint')"
                  />
                </q-card-section>
              </q-tab-panel>

              <q-tab-panel name="apikeys">
                <APIKeysTable />
              </q-tab-panel>

              <!-- SSO descartado (ADR-010, 2026-06-17): panel y SSOProvidersTable eliminados (módulo ee/sso vaciado). -->

              <!-- schedules -->
              <q-tab-panel name="schedules">
                <ScheduleTable />
              </q-tab-panel>

              <!-- AI Assistant (LLM OpenAI-compatible) -->
              <q-tab-panel name="ai">
                <div class="text-subtitle2">
                  {{ $t("editCoreSettings.tabAiAssistant") }}
                </div>
                <q-separator />
                <q-card-section class="row">
                  <div class="col-4">{{ $t("editCoreSettings.aiApiKey") }}</div>
                  <div class="col-2"></div>
                  <q-input
                    dense
                    outlined
                    v-model="settings.open_ai_token"
                    class="col-6"
                  />
                </q-card-section>
                <q-card-section class="row">
                  <div class="col-4">
                    {{ $t("editCoreSettings.aiBaseUrl") }}
                  </div>
                  <div class="col-2"></div>
                  <q-input
                    dense
                    outlined
                    v-model="settings.open_ai_base_url"
                    class="col-6"
                    :hint="$t('editCoreSettings.aiBaseUrlHint')"
                  />
                </q-card-section>
                <q-card-section class="row">
                  <div class="col-4">{{ $t("editCoreSettings.aiModel") }}</div>
                  <div class="col-2"></div>
                  <q-input
                    dense
                    outlined
                    v-model="settings.open_ai_model"
                    class="col-6"
                    :hint="$t('editCoreSettings.aiModelHint')"
                  />
                </q-card-section>
                <q-card-section class="row">
                  <div class="col-4">
                    {{ $t("editCoreSettings.aiMaxTokens") }}
                  </div>
                  <div class="col-2"></div>
                  <q-input
                    dense
                    outlined
                    type="number"
                    v-model.number="settings.open_ai_max_tokens"
                    class="col-6"
                    :rules="[
                      (val) =>
                        (!!val && val > 0) ||
                        $t('editCoreSettings.aiMaxTokensRule'),
                    ]"
                    :hint="$t('editCoreSettings.aiMaxTokensHint')"
                  />
                </q-card-section>
                <q-card-section class="row">
                  <div class="col-4">
                    {{ $t("editCoreSettings.aiTemperature") }}
                  </div>
                  <div class="col-2"></div>
                  <q-input
                    dense
                    outlined
                    type="number"
                    step="0.1"
                    v-model.number="settings.open_ai_temperature"
                    class="col-6"
                    :hint="$t('editCoreSettings.aiTemperatureHint')"
                  />
                </q-card-section>
              </q-tab-panel>
            </q-tab-panels>
          </q-scroll-area>
          <q-card-section class="row items-center">
            <q-btn
              v-show="
                tab === 'general' ||
                tab === 'emailalerts' ||
                tab === 'smsalerts' ||
                tab === 'meshcentral' ||
                tab === 'retention' ||
                tab === 'ai'
              "
              :label="$t('editCoreSettings.save')"
              color="primary"
              type="submit"
            />
            <q-btn
              v-show="tab === 'emailalerts'"
              :label="$t('editCoreSettings.saveAndTestEmail')"
              color="primary"
              type="submit"
              class="q-ml-md"
              @click="emailTest = true"
            />
            <q-btn
              v-show="tab === 'smsalerts'"
              :label="$t('editCoreSettings.saveAndTestSms')"
              color="primary"
              type="submit"
              class="q-ml-md"
              @click="smsTest = true"
            />
          </q-card-section>
        </q-form>
      </template>
    </q-splitter>
  </q-card>
</template>

<script>
import { openURL } from "quasar";
import mixins from "@/mixins/mixins";
import ResetPatchPolicy from "@/components/modals/coresettings/ResetPatchPolicy.vue";
import CustomFields from "@/components/modals/coresettings/CustomFields.vue";
import KeyStoreTable from "@/components/modals/coresettings/KeyStoreTable.vue";
import URLActionsTable from "@/components/modals/coresettings/URLActionsTable.vue";
import APIKeysTable from "@/components/core/APIKeysTable.vue";
import ObserverDropdown from "@/components/ui/ObserverDropdown.vue";
import ScheduleTable from "@/core/settings/components/ScheduleTable.vue";

// SSO descartado (ADR-010, 2026-06-17): el dynamic import de SSOProvidersTable
// fue eliminado junto con el módulo ee/sso (vaciado, pendiente de reimplementación).

export default {
  name: "EditCoreSettings",
  emits: ["close"],
  components: {
    CustomFields,
    KeyStoreTable,
    URLActionsTable,
    APIKeysTable,
    ObserverDropdown,
    ScheduleTable,
  },
  mixins: [mixins],
  data() {
    return {
      // SSO descartado (ADR-010, 2026-06-17): flag ssoEnabled eliminado (módulo ee/sso vaciado).
      ready: false,
      policies: [],
      settings: {},
      email: null,
      tab: "general",
      splitterModel: 20,
      isPwd: true,
      allTimezones: [],
      emailTest: false,
      smsTest: false,
      thumbStyle: {
        right: "2px",
        borderRadius: "5px",
        backgroundColor: "#027be3",
        width: "5px",
        opacity: 0.75,
      },
      alertTemplateOptions: [],
    };
  },
  computed: {
    hosted() {
      return this.$store.state.hosted;
    },
    // Movido de data() a computed para reaccionar al cambio de idioma en caliente.
    logLevelOptions() {
      return [
        { label: this.$t("editCoreSettings.logInfo"), value: "info" },
        { label: this.$t("editCoreSettings.logWarning"), value: "warning" },
        { label: this.$t("editCoreSettings.logError"), value: "error" },
        { label: this.$t("editCoreSettings.logCritical"), value: "critical" },
      ];
    },
  },
  // SSO descartado (ADR-010, 2026-06-17): watch del tab "sso" eliminado (módulo ee/sso vaciado).
  methods: {
    openURL(url) {
      openURL(url);
    },
    getCoreSettings() {
      this.$axios.get("/core/settings/").then((r) => {
        this.settings = r.data;
        this.allTimezones = Object.freeze(r.data.all_timezones);
        this.ready = true;
      });
    },
    getPolicies() {
      this.$q.loading.show();
      this.$axios
        .get("/automation/policies/")
        .then((r) => {
          this.policies = r.data.map((policy) => ({
            label: policy.name,
            value: policy.id,
          }));
          this.$q.loading.hide();
        })
        .catch(() => {
          this.$q.loading.hide();
        });
    },
    getAlertTemplates() {
      this.$axios.get("alerts/templates/").then((r) => {
        this.alertTemplateOptions = r.data.map((template) => ({
          label: template.name,
          value: template.id,
        }));
      });
    },
    confirmSyncChange(newValue) {
      this.$q
        .dialog({
          title: this.$t("editCoreSettings.confirmSyncTitle"),
          message: this.$t("editCoreSettings.confirmSyncMessage"),
          ok: { label: this.$t("editCoreSettings.yes"), color: "primary" },
          cancel: { label: this.$t("editCoreSettings.no"), color: "negative" },
        })
        .onOk(() => {
          this.settings.sync_mesh_with_trmm = newValue;
        });
    },
    showResetPatchPolicy() {
      this.$q.dialog({
        component: ResetPatchPolicy,
      });
    },
    toggleAddEmail() {
      this.$q
        .dialog({
          title: this.$t("editCoreSettings.addEmailTitle"),
          prompt: {
            model: "",
            isValid: (val) => this.isValidEmail(val),
            type: "email",
          },
          cancel: true,
          ok: { label: this.$t("editCoreSettings.add"), color: "primary" },
          persistent: false,
        })
        .onOk((data) => {
          this.settings.email_alert_recipients.push(data);
        });
    },
    toggleAddSMSNumber() {
      this.$q
        .dialog({
          title: this.$t("editCoreSettings.addNumberTitle"),
          message: this.$t("editCoreSettings.addNumberMessage"),
          prompt: {
            model: "",
          },
          html: true,
          cancel: true,
          ok: { label: this.$t("editCoreSettings.add"), color: "primary" },
          persistent: false,
        })
        .onOk((data) => {
          this.settings.sms_alert_recipients.push(data);
        });
    },
    removeEmail(email) {
      const removed = this.settings.email_alert_recipients.filter(
        (k) => k !== email,
      );
      this.settings.email_alert_recipients = removed;
    },
    removeSMSNumber(num) {
      const removed = this.settings.sms_alert_recipients.filter(
        (k) => k !== num,
      );
      this.settings.sms_alert_recipients = removed;
    },
    editSettings() {
      this.$q.loading.show();
      delete this.settings.all_timezones;
      // El input numérico vacío entrega "" y el backend espera null (campo
      // opcional): sin esto, dejar la temperatura en blanco daría 400.
      if (this.settings.open_ai_temperature === "")
        this.settings.open_ai_temperature = null;
      this.$axios
        .put("/core/settings/", this.settings)
        .then(() => {
          this.$q.loading.hide();
          if (this.emailTest) {
            this.$q.loading.show({
              message: this.$t("editCoreSettings.sendingTestEmail"),
            });
            this.$axios
              .post("/core/emailtest/")
              .then((r) => {
                this.emailTest = false;
                this.$q.loading.hide();
                this.getCoreSettings();
                this.notifySuccess(r.data, 3000);
              })
              .catch(() => {
                this.emailTest = false;
                this.$q.loading.hide();
              });
          } else if (this.smsTest) {
            this.$q.loading.show({
              message: this.$t("editCoreSettings.sendingTestSms"),
            });
            this.$axios
              .post("/core/smstest/")
              .then((r) => {
                this.smsTest = false;
                this.$q.loading.hide();
                this.getCoreSettings();
                this.notifySuccess(r.data, 3000);
              })
              .catch(() => {
                this.smsTest = false;
                this.$q.loading.hide();
              });
          } else {
            this.$emit("close");
            this.$store.dispatch("getDashInfo", false);
            this.notifySuccess(this.$t("editCoreSettings.settingsEdited"));
          }
        })
        .catch(() => {
          this.$q.loading.hide();
        });
    },
  },
  mounted() {
    this.getCoreSettings();
    this.getPolicies();
    this.getAlertTemplates();
  },
};
</script>
