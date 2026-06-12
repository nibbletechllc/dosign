import hashlib

from odoo import models, fields, api, _
from odoo.exceptions import UserError


class DosignDocument(models.Model):
    _name = 'dosign.document'
    _description = 'Dosign Document'
    _inherit = ['mail.thread', 'mail.activity.mixin']
    _order = 'create_date desc'

    name = fields.Char(
        string='Name', required=True, tracking=True, default=_('New Document'))
    reference = fields.Char(
        string='Reference', readonly=True, copy=False, index=True)

    attachment_id = fields.Many2one(
        'ir.attachment', string='Original PDF', ondelete='restrict', copy=False)
    completed_attachment_id = fields.Many2one(
        'ir.attachment', string='Signed PDF', ondelete='restrict', copy=False)

    state = fields.Selection([
        ('draft', 'Draft'),
        ('sent', 'To Sign'),
        ('partial', 'Partially Signed'),
        ('signed', 'Signed'),
        ('expired', 'Expired'),
        ('cancelled', 'Cancelled'),
    ], string='Status', default='draft', required=True, tracking=True, copy=False,
        group_expand='_group_expand_state')

    template_id = fields.Many2one(
        'dosign.template', string='Template', ondelete='set null')
    signer_ids = fields.One2many(
        'dosign.signer', 'document_id', string='Signers', copy=True)
    item_ids = fields.One2many(
        'dosign.item', 'document_id', string='Fields', copy=True)
    tag_ids = fields.Many2many('dosign.tag', string='Tags')
    log_ids = fields.One2many('dosign.log', 'document_id', string='Audit Trail')

    user_id = fields.Many2one(
        'res.users', string='Sent by', default=lambda self: self.env.user,
        tracking=True)
    expiry_date = fields.Date(string='Expiry Date', tracking=True)

    signer_count = fields.Integer(
        string='Signers', compute='_compute_progress', store=True)
    signed_count = fields.Integer(
        string='Signed', compute='_compute_progress', store=True)
    progress_label = fields.Char(
        string='Progress', compute='_compute_progress')

    sha256_original = fields.Char(string='Original SHA-256', readonly=True, copy=False)
    sha256_final = fields.Char(string='Final SHA-256', readonly=True, copy=False)

    certificate_id = fields.Many2one(
        'dosign.certificate', string='Seal Certificate', readonly=True, copy=False)
    company_id = fields.Many2one(
        'res.company', string='Company',
        default=lambda self: self.env.company)

    @api.model
    def _group_expand_state(self, states, domain):
        # Show fixed kanban columns in order, including empty ones.
        return ['draft', 'sent', 'partial', 'signed', 'expired']

    @api.depends('signer_ids', 'signer_ids.state')
    def _compute_progress(self):
        for doc in self:
            signers = doc.signer_ids
            doc.signer_count = len(signers)
            doc.signed_count = len(signers.filtered(lambda s: s.state == 'signed'))
            doc.progress_label = '%s / %s' % (doc.signed_count, doc.signer_count)

    @api.model_create_multi
    def create(self, vals_list):
        for vals in vals_list:
            if not vals.get('reference'):
                vals['reference'] = self.env['ir.sequence'].next_by_code(
                    'dosign.document') or _('New')
        documents = super().create(vals_list)
        for doc in documents:
            doc._log_event('created')
        return documents

    # --- State machine --------------------------------------------------

    def action_send(self):
        """Validate, generate tokens and move the document To Sign.

        Email delivery is wired in Phase 3; here we cover validation, token
        generation, the state transition and the audit log.
        """
        for doc in self:
            doc._validate_for_send()
            for signer in doc.signer_ids:
                signer._ensure_token()
            doc.state = 'sent'
            doc._log_event('sent')
        return True

    def action_sign_now(self):
        """Placeholder for the backend Sign Now flow (Phase 3)."""
        self.ensure_one()
        raise UserError(_('Sign Now will be available once the editor ships (Phase 3).'))

    def action_resend(self):
        for doc in self:
            if doc.state not in ('sent', 'partial', 'expired'):
                raise UserError(_('Only sent, partially signed or expired documents can be resent.'))
            if doc.state == 'expired':
                doc.state = 'sent'
            for signer in doc.signer_ids.filtered(lambda s: s.state in ('pending', 'viewed')):
                signer._regenerate_token()
            doc._log_event('resent')
        return True

    def action_cancel(self):
        for doc in self:
            if doc.state in ('signed', 'cancelled'):
                raise UserError(_('Signed or cancelled documents cannot be cancelled.'))
            doc.state = 'cancelled'
            doc._log_event('cancelled')
        return True

    def action_draft(self):
        for doc in self:
            if doc.state != 'cancelled':
                raise UserError(_('Only cancelled documents can be reset to draft.'))
            doc.state = 'draft'
        return True

    def _validate_for_send(self):
        self.ensure_one()
        if not self.attachment_id:
            raise UserError(_('Attach a PDF before sending.'))
        if not self.signer_ids:
            raise UserError(_('Add at least one signer before sending.'))
        signature_types = ('signature',)
        for signer in self.signer_ids:
            signer_items = self.item_ids.filtered(lambda i: i.signer_id == signer)
            if not signer_items.filtered(
                    lambda i: i.field_type_id.item_type in signature_types):
                raise UserError(_(
                    'Signer %s has no signature field assigned.') % signer.name)
        if self.item_ids.filtered(lambda i: not i.signer_id):
            raise UserError(_('Every field must be assigned to a signer.'))

    def _process_signature(self, signer, values):
        """Store a signer's submitted values and advance state (Phase 3)."""
        self.ensure_one()
        raise NotImplementedError('Signature processing lands in Phase 3.')

    def _finalize(self):
        """Flatten + PAdES-seal the completed document (Phase 4)."""
        self.ensure_one()
        raise NotImplementedError('Finalization lands in Phase 4.')

    # --- Helpers --------------------------------------------------------

    def _compute_sha256(self, data):
        return hashlib.sha256(data).hexdigest() if data else False

    def _log_event(self, action, signer=None, payload_hash=None):
        self.ensure_one()
        self.env['dosign.log'].sudo().create({
            'document_id': self.id,
            'signer_id': signer.id if signer else False,
            'action': action,
            'actor': self.env.user.login,
            'payload_hash': payload_hash,
        })
