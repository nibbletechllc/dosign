/** @odoo-module **/

import { registry } from "@web/core/registry";
import { listView } from "@web/views/list/list_view";
import { ListController } from "@web/views/list/list_controller";
import { useService } from "@web/core/utils/hooks";

export class DosignTemplateListController extends ListController {
    setup() {
        super.setup();
        this.actionService = useService("action");
    }

    /** Clicking a template row opens it in the PDF editor (template mode). */
    openRecord(record) {
        this.actionService.doAction({
            type: "ir.actions.client",
            tag: "dosign.editor",
            params: { template_id: record.resId },
        });
    }
}

registry.category("views").add("dosign_template_list", {
    ...listView,
    Controller: DosignTemplateListController,
});
