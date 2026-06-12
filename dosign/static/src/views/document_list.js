/** @odoo-module **/

import { registry } from "@web/core/registry";
import { listView } from "@web/views/list/list_view";
import { ListController } from "@web/views/list/list_controller";
import { useService } from "@web/core/utils/hooks";
import { DosignUploadModal } from "@dosign/upload/upload_modal";

export class DosignListController extends ListController {
    setup() {
        super.setup();
        this.actionService = useService("action");
        this.dialogService = useService("dialog");
    }

    openEditor(documentId) {
        this.actionService.doAction({
            type: "ir.actions.client",
            tag: "dosign.editor",
            params: { document_id: documentId },
        });
    }

    /**
     * Clicking a row opens the document in the editor/viewer instead of the
     * form: a draft shows its placeholder fields, an edited document shows the
     * captured values and signatures.
     */
    openRecord(record) {
        this.openEditor(record.resId);
    }

    onUploadPdf() {
        this.dialogService.add(DosignUploadModal, {
            onCreated: (documentId) => this.openEditor(documentId),
        });
    }
}

registry.category("views").add("dosign_document_list", {
    ...listView,
    Controller: DosignListController,
    buttonTemplate: "dosign.ListButtons",
});
