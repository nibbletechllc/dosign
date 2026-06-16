/** @odoo-module **/

import { Component, useState } from "@odoo/owl";
import { NameAndSignature } from "@web/core/signature/name_and_signature";

// Wraps Odoo's NameAndSignature ("Adopt Your Signature": Auto from the name with
// font choices / Draw / Load an image) in the portal signing overlay.
export class SignaturePad extends Component {
    static template = "dosign.SignaturePad";
    static components = { NameAndSignature };
    static props = {
        title: { type: String, optional: true },
        defaultName: { type: String, optional: true },
        signatureType: { type: String, optional: true },
        onConfirm: Function,
        onCancel: Function,
    };

    setup() {
        this.signature = useState({
            name: this.props.defaultName || "",
            isSignatureEmpty: true,
        });
    }

    get nameAndSignatureProps() {
        return {
            signature: this.signature,
            signatureType: this.props.signatureType || "signature",
        };
    }

    confirm() {
        if (this.signature.isSignatureEmpty) {
            return;
        }
        this.props.onConfirm(this.signature.getSignatureImage());
    }
}
