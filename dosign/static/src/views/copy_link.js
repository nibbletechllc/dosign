/** @odoo-module **/

import { registry } from "@web/core/registry";
import { _t } from "@web/core/l10n/translation";

// Function client action: copy a signing link to the clipboard. Falls back to a
// prompt when the Clipboard API is unavailable (e.g. plain-HTTP origins).
function copyLink(env, action) {
    const url = action.params.url;
    (async () => {
        try {
            await navigator.clipboard.writeText(url);
            env.services.notification.add(_t("Signing link copied to clipboard."), {
                type: "success",
            });
        } catch {
            window.prompt(_t("Copy this signing link:"), url);
        }
    })();
    // Return nothing so the current view stays in place.
}

registry.category("actions").add("dosign.copy_link", copyLink);
