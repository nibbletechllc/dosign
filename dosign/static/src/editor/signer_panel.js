/** @odoo-module **/

import { Component } from "@odoo/owl";
import { useService } from "@web/core/utils/hooks";
import { _t } from "@web/core/l10n/translation";
import { AutoComplete } from "@web/core/autocomplete/autocomplete";
import { signerColor } from "@dosign/editor/colors";

export class DosignSignerPanel extends Component {
    static template = "dosign.SignerPanel";
    static components = { AutoComplete };
    static props = {
        signers: Array,
        items: Array,
        activeSignerId: { type: [Number, { value: null }], optional: true },
        readonly: { type: Boolean, optional: true },
        isTemplate: { type: Boolean, optional: true },
        participantField: { type: String, optional: true },
        onSelect: Function,
        onAdd: Function,
        onUpdate: Function,
        onRemove: Function,
    };

    setup() {
        this.orm = useService("orm");
    }

    color(signer) {
        return signerColor(signer.color);
    }

    fieldCount(signer) {
        const field = this.props.participantField || "signer_id";
        return this.props.items.filter(
            (it) => it[field] && it[field][0] === signer.id
        ).length;
    }

    onNameInput(ev, signer) {
        this.props.onUpdate(signer.id, { name: ev.target.value });
    }

    onEmailInput(ev, signer) {
        this.props.onUpdate(signer.id, { email: ev.target.value });
    }

    // --- Odoo contact picker -------------------------------------------

    partnerValue(signer) {
        return signer.partner_id ? signer.partner_id[1] : "";
    }

    partnerSources(signer) {
        return [{
            placeholder: _t("Searching contacts…"),
            options: (request) => this.loadPartners(request, signer),
        }];
    }

    async loadPartners(request, signer) {
        const term = (request || "").trim();
        const partners = await this.orm.searchRead(
            "res.partner",
            term ? ["|", ["name", "ilike", term], ["email", "ilike", term]] : [],
            ["name", "email", "is_company"],
            { limit: 8 });
        return partners.map((partner) => ({
            label: partner.email ? `${partner.name} (${partner.email})` : partner.name,
            onSelect: () => this.props.onUpdate(signer.id, {
                partner_id: partner.id,
                name: partner.name || "",
                email: partner.email || "",
            }),
        }));
    }
}
