/** @odoo-module **/

import { Component, useState } from "@odoo/owl";
import { Dialog } from "@web/core/dialog/dialog";

export class DosignSendDialog extends Component {
    static template = "dosign.SendDialog";
    static components = { Dialog };
    static props = {
        close: Function,
        signers: Array,
        onConfirm: Function,
    };

    setup() {
        this.state = useState({
            message: "",
            expiryDate: "",
            signingMode: "parallel",
        });
    }

    confirm() {
        this.props.onConfirm({
            message: this.state.message,
            expiry_date: this.state.expiryDate || false,
            signing_mode: this.state.signingMode,
        });
        this.props.close();
    }
}
