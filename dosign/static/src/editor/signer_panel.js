/** @odoo-module **/

import { Component } from "@odoo/owl";
import { signerColor } from "@dosign/editor/colors";

export class DosignSignerPanel extends Component {
    static template = "dosign.SignerPanel";
    static props = {
        signers: Array,
        items: Array,
        activeSignerId: { type: [Number, { value: null }], optional: true },
        onSelect: Function,
        onAdd: Function,
        onUpdate: Function,
        onRemove: Function,
    };

    color(signer) {
        return signerColor(signer.color);
    }

    fieldCount(signer) {
        return this.props.items.filter(
            (it) => it.signer_id && it.signer_id[0] === signer.id
        ).length;
    }

    onNameInput(ev, signer) {
        this.props.onUpdate(signer.id, { name: ev.target.value });
    }

    onEmailInput(ev, signer) {
        this.props.onUpdate(signer.id, { email: ev.target.value });
    }
}
