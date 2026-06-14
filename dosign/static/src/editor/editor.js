/** @odoo-module **/

import { Component, useState, onWillStart } from "@odoo/owl";
import { registry } from "@web/core/registry";
import { useService } from "@web/core/utils/hooks";
import { _t } from "@web/core/l10n/translation";
import { DosignPdfCanvas } from "@dosign/editor/pdf_canvas";
import { DosignSignerPanel } from "@dosign/editor/signer_panel";
import { DosignFieldPalette } from "@dosign/editor/field_palette";
import { DosignSendDialog } from "@dosign/editor/send_dialog";
import { DosignRoleMapDialog } from "@dosign/editor/role_map_dialog";

const SIGNER_COLOR_COUNT = 8;
const SAVE_DELAY = 600;

function clamp(value, min, max) {
    return Math.max(min, Math.min(max, value));
}

export class DosignEditor extends Component {
    static template = "dosign.Editor";
    static components = { DosignPdfCanvas, DosignSignerPanel, DosignFieldPalette };
    static props = ["*"];

    setup() {
        this.orm = useService("orm");
        this.actionService = useService("action");
        this.notification = useService("notification");
        this.dialog = useService("dialog");

        const params = this.props.action.params || {};
        this.isTemplate = !!params.template_id;
        this.recordId = params.template_id || params.document_id;
        this.recordModel = this.isTemplate ? "dosign.template" : "dosign.document";
        this.ownerField = this.isTemplate ? "template_id" : "document_id";
        this.participantModel = this.isTemplate ? "dosign.role" : "dosign.signer";
        this.participantField = this.isTemplate ? "role_id" : "signer_id";

        this._timers = {};
        this.state = useState({
            loaded: false,
            name: "",
            stateValue: "draft",
            signers: [],
            items: [],
            fieldTypes: [],
            activeSignerId: null,
        });
        onWillStart(() => this.loadData());
    }

    get pdfUrl() {
        return this.isTemplate
            ? `/dosign/template/${this.recordId}/pdf`
            : `/dosign/document/${this.recordId}/pdf`;
    }

    get activeSigner() {
        return this.state.signers.find((s) => s.id === this.state.activeSignerId) || null;
    }

    get readonly() {
        return !this.isTemplate && this.state.stateValue !== "draft";
    }

    participantOf(item) {
        const ref = item[this.participantField];
        return Array.isArray(ref) ? ref[0] : ref;
    }

    async loadData() {
        const [rec] = await this.orm.read(
            this.recordModel, [this.recordId],
            this.isTemplate ? ["name"] : ["name", "state"]);
        this.state.name = rec.name;
        this.state.stateValue = this.isTemplate ? "template" : rec.state;
        this.state.fieldTypes = await this.orm.searchRead(
            "dosign.field.type", [],
            ["name", "technical_name", "item_type", "icon", "default_width", "default_height"]);
        const participantFields = this.isTemplate
            ? ["name", "color", "sequence"]
            : ["name", "email", "color", "sequence", "state", "signature_image", "initials_image"];
        this.state.signers = await this.orm.searchRead(
            this.participantModel, [[this.ownerField, "=", this.recordId]], participantFields);
        this.state.items = await this.orm.searchRead(
            "dosign.item", [[this.ownerField, "=", this.recordId]],
            ["field_type_id", "signer_id", "role_id", "page", "pos_x", "pos_y",
             "width", "height", "required", "value_text"]);
        if (this.state.signers.length) {
            this.state.activeSignerId = this.state.signers[0].id;
        }
        this.state.loaded = true;
        if (!this.isTemplate) {
            this.maybeMapRoles();
        }
    }

    // --- Role mapping (document created from a template) ----------------

    maybeMapRoles() {
        const roles = new Map();
        for (const item of this.state.items) {
            const signerId = Array.isArray(item.signer_id) ? item.signer_id[0] : item.signer_id;
            if (!signerId && item.role_id) {
                roles.set(item.role_id[0], item.role_id[1]);
            }
        }
        if (!roles.size) {
            return;
        }
        this.dialog.add(DosignRoleMapDialog, {
            roles: [...roles.entries()].map(([id, name]) => ({ id, name })),
            onConfirm: (mapping) => this.applyRoleMapping(mapping),
        });
    }

    async applyRoleMapping(mapping) {
        for (let i = 0; i < mapping.length; i++) {
            const entry = mapping[i];
            const [signerId] = await this.orm.create("dosign.signer", [{
                document_id: this.recordId,
                name: entry.name,
                email: entry.email,
                color: i % SIGNER_COLOR_COUNT,
                sequence: (i + 1) * 10,
            }]);
            const itemIds = this.state.items
                .filter((it) => it.role_id && it.role_id[0] === entry.role_id)
                .map((it) => it.id);
            if (itemIds.length) {
                await this.orm.write("dosign.item", itemIds, { signer_id: signerId, role_id: false });
            }
        }
        await this.loadData();
    }

    // --- Persistence helpers -------------------------------------------

    _debounce(key, fn) {
        clearTimeout(this._timers[key]);
        this._timers[key] = setTimeout(fn, SAVE_DELAY);
    }

    onNameChange(ev) {
        const name = ev.target.value;
        this.state.name = name;
        this._debounce("name", () => this.orm.write(this.recordModel, [this.recordId], { name }));
    }

    // --- Participants (signers or roles) -------------------------------

    selectSigner(signerId) {
        this.state.activeSignerId = signerId;
    }

    async addSigner() {
        const index = this.state.signers.length;
        const vals = this.isTemplate
            ? {
                template_id: this.recordId,
                name: _t("Role %s", index + 1),
                color: index % SIGNER_COLOR_COUNT,
                sequence: (index + 1) * 10,
            }
            : {
                document_id: this.recordId,
                name: _t("Signer %s", index + 1),
                email: "",
                color: index % SIGNER_COLOR_COUNT,
                sequence: (index + 1) * 10,
            };
        const [id] = await this.orm.create(this.participantModel, [vals]);
        this.state.signers.push({ id, ...vals, state: "pending" });
        this.state.activeSignerId = id;
    }

    updateSigner(signerId, vals) {
        const signer = this.state.signers.find((s) => s.id === signerId);
        if (signer) {
            Object.assign(signer, vals);
        }
        this._debounce(`p-${signerId}`, () =>
            this.orm.write(this.participantModel, [signerId], vals));
    }

    async removeSigner(signerId) {
        await this.orm.unlink(this.participantModel, [signerId]);
        this.state.items = this.state.items.filter((it) => this.participantOf(it) !== signerId);
        this.state.signers = this.state.signers.filter((s) => s.id !== signerId);
        if (this.state.activeSignerId === signerId) {
            this.state.activeSignerId = this.state.signers.length ? this.state.signers[0].id : null;
        }
    }

    // --- Items ----------------------------------------------------------

    async addItem(fieldTypeId, page, x, y) {
        if (!this.state.activeSignerId) {
            this.notification.add(
                this.isTemplate
                    ? _t("Add a role before placing fields.")
                    : _t("Add a signer before placing fields."),
                { type: "warning" });
            return;
        }
        const ft = this.state.fieldTypes.find((f) => f.id === fieldTypeId);
        const w = ft.default_width || 0.18;
        const h = ft.default_height || 0.05;
        const participant = this.activeSigner;
        const vals = {
            field_type_id: fieldTypeId,
            page,
            pos_x: clamp(x - w / 2, 0, 1 - w),
            pos_y: clamp(y - h / 2, 0, 1 - h),
            width: w,
            height: h,
            required: true,
        };
        vals[this.ownerField] = this.recordId;
        vals[this.participantField] = this.state.activeSignerId;
        const [id] = await this.orm.create("dosign.item", [vals]);
        const itemRec = {
            id,
            field_type_id: [fieldTypeId, ft.name],
            signer_id: false,
            role_id: false,
            page,
            pos_x: vals.pos_x,
            pos_y: vals.pos_y,
            width: w,
            height: h,
            required: true,
        };
        itemRec[this.participantField] = [participant.id, participant.name];
        this.state.items.push(itemRec);
    }

    updateItem(itemId, vals) {
        const item = this.state.items.find((it) => it.id === itemId);
        if (item) {
            Object.assign(item, vals);
        }
        this._debounce(`item-${itemId}`, () => this.orm.write("dosign.item", [itemId], vals));
    }

    async removeItem(itemId) {
        await this.orm.unlink("dosign.item", [itemId]);
        this.state.items = this.state.items.filter((it) => it.id !== itemId);
    }

    // --- Actions --------------------------------------------------------

    send() {
        this.dialog.add(DosignSendDialog, {
            signers: this.state.signers,
            onConfirm: async (vals) => {
                await this.orm.write("dosign.document", [this.recordId], vals);
                await this.orm.call("dosign.document", "action_send", [[this.recordId]]);
                this.notification.add(_t("Document sent to signers."), { type: "success" });
                this.backToList();
            },
        });
    }

    async signNow() {
        const action = await this.orm.call(
            "dosign.document", "action_sign_now", [[this.recordId]]);
        if (action) {
            this.actionService.doAction(action);
        }
    }

    async saveAsTemplate() {
        const name = window.prompt(_t("Template name:"), `${this.state.name} ${_t("Template")}`);
        if (!name) {
            return;
        }
        const action = await this.orm.call(
            "dosign.document", "action_save_as_template", [[this.recordId], name]);
        this.notification.add(_t("Template saved."), { type: "success" });
        if (action) {
            this.actionService.doAction(action);
        }
    }

    backToList() {
        this.actionService.doAction(
            this.isTemplate ? "dosign.action_dosign_template" : "dosign.action_dosign_document");
    }
}

registry.category("actions").add("dosign.editor", DosignEditor);
