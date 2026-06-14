/** @odoo-module **/

import { registry } from "@web/core/registry";
import { kanbanView } from "@web/views/kanban/kanban_view";
import { KanbanController } from "@web/views/kanban/kanban_controller";
import { useService } from "@web/core/utils/hooks";
import { DosignUploadModal } from "@dosign/upload/upload_modal";

export class DosignTemplateKanbanController extends KanbanController {
    setup() {
        super.setup();
        this.actionService = useService("action");
        this.dialogService = useService("dialog");
    }

    onUploadPdf() {
        this.dialogService.add(DosignUploadModal, {
            onCreated: (documentId) => this.actionService.doAction({
                type: "ir.actions.client",
                tag: "dosign.editor",
                params: { document_id: documentId },
            }),
        });
    }

    /** Clicking a template card opens the editor (template mode). */
    openRecord(record) {
        if (!record.data.attachment_id) {
            return super.openRecord(record);
        }
        this.actionService.doAction({
            type: "ir.actions.client",
            tag: "dosign.editor",
            params: { template_id: record.resId },
        });
    }
}

registry.category("views").add("dosign_template_kanban", {
    ...kanbanView,
    Controller: DosignTemplateKanbanController,
    buttonTemplate: "dosign.TemplateKanbanButtons",
});
