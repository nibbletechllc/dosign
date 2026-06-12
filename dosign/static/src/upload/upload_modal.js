/** @odoo-module **/

import { Component, useState, useRef, onWillStart } from "@odoo/owl";
import { Dialog } from "@web/core/dialog/dialog";
import { useService } from "@web/core/utils/hooks";
import { _t } from "@web/core/l10n/translation";

const MAX_SIZE = 25 * 1024 * 1024;

export class DosignUploadModal extends Component {
    static template = "dosign.UploadModal";
    static components = { Dialog };
    static props = {
        close: Function,
        onCreated: Function,
    };

    setup() {
        this.orm = useService("orm");
        this.notification = useService("notification");
        this.fileInput = useRef("fileInput");
        this.state = useState({
            templates: [],
            dragging: false,
            uploading: false,
        });
        onWillStart(async () => {
            this.state.templates = await this.orm.searchRead(
                "dosign.template", [], ["name", "item_count", "role_count"]
            );
        });
    }

    triggerPicker() {
        this.fileInput.el.click();
    }

    onFileChange(ev) {
        const file = ev.target.files[0];
        if (file) {
            this.uploadFile(file);
        }
    }

    onDragOver(ev) {
        ev.preventDefault();
        this.state.dragging = true;
    }

    onDragLeave() {
        this.state.dragging = false;
    }

    onDrop(ev) {
        ev.preventDefault();
        this.state.dragging = false;
        const file = ev.dataTransfer.files[0];
        if (file) {
            this.uploadFile(file);
        }
    }

    async uploadFile(file) {
        if (file.type !== "application/pdf") {
            this.notification.add(_t("Please select a PDF file."), { type: "danger" });
            return;
        }
        if (file.size > MAX_SIZE) {
            this.notification.add(_t("The file exceeds 25 MB."), { type: "danger" });
            return;
        }
        this.state.uploading = true;
        const formData = new FormData();
        formData.append("ufile", file);
        formData.append("csrf_token", odoo.csrf_token);
        try {
            const response = await fetch("/dosign/upload", { method: "POST", body: formData });
            const data = await response.json();
            if (!response.ok || data.error) {
                throw new Error(data.error || _t("Upload failed."));
            }
            this.props.onCreated(data.id);
            this.props.close();
        } catch (error) {
            this.notification.add(error.message || _t("Upload failed."), { type: "danger" });
        } finally {
            this.state.uploading = false;
        }
    }

    async useTemplate(templateId) {
        try {
            const docId = await this.orm.call(
                "dosign.document", "create_from_template", [templateId]
            );
            this.props.onCreated(docId);
            this.props.close();
        } catch (error) {
            this.notification.add(error.message || _t("Could not use template."), { type: "danger" });
        }
    }
}
