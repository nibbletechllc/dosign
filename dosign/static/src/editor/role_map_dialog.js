/** @odoo-module **/

import { Component, useState } from "@odoo/owl";
import { Dialog } from "@web/core/dialog/dialog";

export class DosignRoleMapDialog extends Component {
    static template = "dosign.RoleMapDialog";
    static components = { Dialog };
    static props = {
        close: Function,
        roles: Array,
        onConfirm: Function,
    };

    setup() {
        this.state = useState({
            entries: this.props.roles.map((role) => ({
                role_id: role.id,
                role_name: role.name,
                name: role.name,
                email: "",
            })),
        });
    }

    get valid() {
        return this.state.entries.every((e) => e.name.trim() && e.email.trim());
    }

    confirm() {
        if (!this.valid) {
            return;
        }
        this.props.onConfirm(
            this.state.entries.map((e) => ({
                role_id: e.role_id,
                name: e.name.trim(),
                email: e.email.trim(),
            })));
        this.props.close();
    }
}
