/** @odoo-module **/

import { Component, useState } from "@odoo/owl";
import { Dialog } from "@web/core/dialog/dialog";
import { AutoComplete } from "@web/core/autocomplete/autocomplete";
import { useService } from "@web/core/utils/hooks";
import { _t } from "@web/core/l10n/translation";
import { partnerSources } from "@dosign/editor/partner_search";

export class DosignRoleMapDialog extends Component {
    static template = "dosign.RoleMapDialog";
    static components = { Dialog, AutoComplete };
    static props = {
        close: Function,
        roles: Array,
        onConfirm: Function,
    };

    setup() {
        this.orm = useService("orm");
        this.title = _t("Assign signers to roles");
        this.searchPlaceholder = _t("Search a contact…");
        this.state = useState({
            entries: this.props.roles.map((role) => ({
                role_id: role.id,
                role_name: role.name,
                partner_id: false,
                partner_name: "",
                name: role.name,
                email: "",
            })),
        });
    }

    get valid() {
        return this.state.entries.every((e) => e.name.trim() && e.email.trim());
    }

    // --- Odoo contact picker -------------------------------------------

    /** Search contacts for one role; picking one fills its name and email. */
    partnerSources(entry) {
        return partnerSources(this.orm, (partner) => {
            entry.partner_id = partner.id;
            entry.partner_name = partner.name || "";
            entry.name = partner.name || entry.name;
            // Keep an email already typed when the contact has none.
            entry.email = partner.email || entry.email;
        });
    }

    unlinkPartner(entry) {
        entry.partner_id = false;
        entry.partner_name = "";
    }

    confirm() {
        if (!this.valid) {
            return;
        }
        this.props.onConfirm(
            this.state.entries.map((e) => ({
                role_id: e.role_id,
                partner_id: e.partner_id,
                name: e.name.trim(),
                email: e.email.trim(),
            })));
        this.props.close();
    }
}
