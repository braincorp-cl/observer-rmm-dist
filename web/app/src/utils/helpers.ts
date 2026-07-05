import { copyToClipboard } from "quasar";
import { notifySuccess } from "@/utils/notify";
import { i18n } from "@/boot/i18n";

export function copyOutput(val: string) {
  copyToClipboard(val).then(() => {
    notifySuccess(i18n.global.t("common.copiedToClipboard"));
  });
}
