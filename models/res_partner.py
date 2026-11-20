from odoo import models, fields, _


class ResPartner(models.Model):
    _inherit = 'res.partner'

    dosign_document_count = fields.Integer(
        string='Signature Documents', compute='_compute_dosign_document_count',
        groups='dosign.group_dosign_user')

    def _dosign_document_domain(self):
        """Documents in which this contact (or one of its child contacts) is a
        signer. Signers typed by hand are not always linked to a contact, so the
        contact's email is matched as well."""
        self.ensure_one()
        domain = [('signer_ids.partner_id', 'child_of', self.ids)]
        if self.email:
            domain = ['|', ('signer_ids.email', '=ilike', self.email.strip())] + domain
        return domain

    def _compute_dosign_document_count(self):
        Document = self.env['dosign.document']
        for partner in self:
            partner.dosign_document_count = (
                Document.search_count(partner._dosign_document_domain())
                if partner.id else 0)

    def action_view_dosign_documents(self):
        self.ensure_one()
        action = self.env['ir.actions.act_window']._for_xml_id(
            'dosign.action_dosign_document')
        action.update({
            'name': _('Documents'),
            'domain': self._dosign_document_domain(),
            # Drop the default "My Documents" filter: here we want every
            # document of the contact the user is allowed to see.
            'context': {},
        })
        return action
