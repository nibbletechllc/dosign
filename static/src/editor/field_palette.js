/** @odoo-module **/

import { Component } from "@odoo/owl";
import { signerColor } from "@dosign/editor/colors";

export class DosignFieldPalette extends Component {
    static template = "dosign.FieldPalette";
    static props = {
        fieldTypes: Array,
        activeSigner: { type: Object, optional: true },
    };

    get accentColor() {
        return this.props.activeSigner ? signerColor(this.props.activeSigner.color) : "#714B67";
    }

    onDragStart(ev, fieldType) {
        // Carry the field-type id; the canvas reads it on drop.
        ev.dataTransfer.setData("application/dosign-field", String(fieldType.id));
        ev.dataTransfer.effectAllowed = "copy";
    }
}
