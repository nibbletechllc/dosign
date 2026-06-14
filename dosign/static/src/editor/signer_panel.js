/** @odoo-module **/

import { Component } from "@odoo/owl";
import { signerColor } from "@dosign/editor/colors";

export class DosignSignerPanel extends Component {
    static template = "dosign.SignerPanel";
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
}
