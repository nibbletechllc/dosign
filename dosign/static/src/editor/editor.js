/** @odoo-module **/

import { Component, useState, onWillStart } from "@odoo/owl";
import { registry } from "@web/core/registry";
import { useService } from "@web/core/utils/hooks";
import { _t } from "@web/core/l10n/translation";
import { DosignPdfCanvas } from "@dosign/editor/pdf_canvas";
import { DosignSignerPanel } from "@dosign/editor/signer_panel";
import { DosignFieldPalette } from "@dosign/editor/field_palette";
import { DosignSendDialog } from "@dosign/editor/send_dialog";

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
        this.documentId = this.props.action.params.document_id;
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
        return `/dosign/document/${this.documentId}/pdf`;
    }

    get activeSigner() {
        return this.state.signers.find((s) => s.id === this.state.activeSignerId) || null;
    }

    get readonly() {
        return this.state.stateValue !== "draft";
    }

    async loadData() {
        const [doc] = await this.orm.read("dosign.document", [this.documentId], ["name", "state"]);
        this.state.name = doc.name;
        this.state.stateValue = doc.state;
        this.state.fieldTypes = await this.orm.searchRead(
            "dosign.field.type", [],
            ["name", "technical_name", "item_type", "icon", "default_width", "default_height"]
        );
        this.state.signers = await this.orm.searchRead(
            "dosign.signer", [["document_id", "=", this.documentId]],
            ["name", "email", "color", "sequence", "state", "signature_image", "initials_image"]
        );
        this.state.items = await this.orm.searchRead(
            "dosign.item", [["document_id", "=", this.documentId]],
            ["field_type_id", "signer_id", "page", "pos_x", "pos_y", "width", "height",
             "required", "value_text"]
        );
        if (this.state.signers.length) {
            this.state.activeSignerId = this.state.signers[0].id;
        }
        this.state.loaded = true;
    }

    _debounce(key, fn) {
        clearTimeout(this._timers[key]);
        this._timers[key] = setTimeout(fn, SAVE_DELAY);
    }

    // --- Document name --------------------------------------------------

    onNameChange(ev) {
        const name = ev.target.value;
        this.state.name = name;
        this._debounce("name", () =>
            this.orm.write("dosign.document", [this.documentId], { name })
        );
    }

    // --- Signers --------------------------------------------------------

    selectSigner(signerId) {
        this.state.activeSignerId = signerId;
    }

    async addSigner() {
        const index = this.state.signers.length;
        const vals = {
            document_id: this.documentId,
            name: _t("Signer %s", index + 1),
            email: "",
            color: index % SIGNER_COLOR_COUNT,
            sequence: (index + 1) * 10,
        };
        const [id] = await this.orm.create("dosign.signer", [vals]);
        this.state.signers.push({ id, ...vals, state: "pending" });
        this.state.activeSignerId = id;
    }

    updateSigner(signerId, vals) {
        const signer = this.state.signers.find((s) => s.id === signerId);
        if (signer) {
            Object.assign(signer, vals);
        }
        this._debounce(`signer-${signerId}`, () =>
            this.orm.write("dosign.signer", [signerId], vals)
        );
    }

    async removeSigner(signerId) {
        await this.orm.unlink("dosign.signer", [signerId]);
        this.state.items = this.state.items.filter(
            (it) => !(it.signer_id && it.signer_id[0] === signerId)
        );
        this.state.signers = this.state.signers.filter((s) => s.id !== signerId);
        if (this.state.activeSignerId === signerId) {
            this.state.activeSignerId = this.state.signers.length ? this.state.signers[0].id : null;
        }
    }

    // --- Items ----------------------------------------------------------

    async addItem(fieldTypeId, page, x, y) {
        if (!this.state.activeSignerId) {
            this.notification.add(_t("Add a signer before placing fields."), { type: "warning" });
            return;
        }
        const ft = this.state.fieldTypes.find((f) => f.id === fieldTypeId);
        const w = ft.default_width || 0.18;
        const h = ft.default_height || 0.05;
        const signer = this.activeSigner;
        const vals = {
            document_id: this.documentId,
            field_type_id: fieldTypeId,
            signer_id: this.state.activeSignerId,
            page,
            pos_x: clamp(x - w / 2, 0, 1 - w),
            pos_y: clamp(y - h / 2, 0, 1 - h),
            width: w,
            height: h,
            required: true,
        };
        const [id] = await this.orm.create("dosign.item", [vals]);
        this.state.items.push({
            id,
            field_type_id: [fieldTypeId, ft.name],
            signer_id: [signer.id, signer.name],
            page,
            pos_x: vals.pos_x,
            pos_y: vals.pos_y,
            width: w,
            height: h,
            required: true,
        });
    }

    updateItem(itemId, vals) {
        const item = this.state.items.find((it) => it.id === itemId);
        if (item) {
            Object.assign(item, vals);
        }
        this._debounce(`item-${itemId}`, () =>
            this.orm.write("dosign.item", [itemId], vals)
        );
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
                await this.orm.write("dosign.document", [this.documentId], vals);
                await this.orm.call("dosign.document", "action_send", [[this.documentId]]);
                this.notification.add(_t("Document sent to signers."), { type: "success" });
                this.backToList();
            },
        });
    }

    async signNow() {
        const action = await this.orm.call(
            "dosign.document", "action_sign_now", [[this.documentId]]);
        if (action) {
            this.actionService.doAction(action);
        }
    }

    backToList() {
        this.actionService.doAction("dosign.action_dosign_document");
    }
}

registry.category("actions").add("dosign.editor", DosignEditor);
