/** @odoo-module **/

import { _t } from "@web/core/l10n/translation";

/**
 * AutoComplete sources searching Odoo contacts by name or email. Shared by the
 * signer panel and the template role assignment dialog.
 *
 * @param {Object} orm the ORM service of the calling component
 * @param {Function} onSelect called with the picked contact {id, name, email}
 */
export function partnerSources(orm, onSelect) {
    return [{
        placeholder: _t("Searching contacts…"),
        options: async (request) => {
            const term = (request || "").trim();
            const partners = await orm.searchRead(
                "res.partner",
                term ? ["|", ["name", "ilike", term], ["email", "ilike", term]] : [],
                ["name", "email"],
                { limit: 8 });
            return partners.map((partner) => ({
                label: partner.email ? `${partner.name} (${partner.email})` : partner.name,
                onSelect: () => onSelect(partner),
            }));
        },
    }];
}
