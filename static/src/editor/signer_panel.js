/** @odoo-module **/

import { Component } from "@odoo/owl";
import { useService } from "@web/core/utils/hooks";
import { AutoComplete } from "@web/core/autocomplete/autocomplete";
import { signerColor } from "@dosign/editor/colors";
import { partnerSources } from "@dosign/editor/partner_search";

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
        const partner = signer.partner_id;
        if (Array.isArray(partner)) {
            return partner[1];
        }
        // Just picked in this session: the state holds the bare id, and the
        // signer name was set from the contact.
        return partner ? signer.name : "";
    }

    partnerSources(signer) {
        return partnerSources(this.orm, (partner) =>
            this.props.onUpdate(signer.id, {
                partner_id: partner.id,
                name: partner.name || "",
                email: partner.email || "",
            }));
    }
}
