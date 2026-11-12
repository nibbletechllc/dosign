import hashlib
import secrets

from odoo import models, fields, api, _
from odoo.exceptions import AccessError, UserError

# Fields that record what a signer did (or grant access to the portal). They are
# only ever written by the signing flow itself, which runs in sudo; a backend
# user must never be able to set them through the ORM/RPC.
PROTECTED_FIELDS = frozenset({
    'state', 'access_token', 'signature_image', 'initials_image', 'signed_on',
    'decline_reason', 'ip_address', 'user_agent', 'reminder_count', 'last_reminder',
})


class DosignSigner(models.Model):
    _name = 'dosign.signer'
    _description = 'Dosign Signer'
    _order = 'sequence, id'

    document_id = fields.Many2one(
        'dosign.document', string='Document', required=True, ondelete='cascade')
    partner_id = fields.Many2one(
        'res.partner', string='Contact', ondelete='set null',
        help='Optional link to an existing contact; auto-matched by email.')
    name = fields.Char(string='Name', required=True)
    email = fields.Char(string='Email', required=True)
    sequence = fields.Integer(
        string='Signing Order', default=10,
        help='Equal values sign in parallel; lower orders sign first.')
    color = fields.Integer(string='Color')

    # The token is a bearer credential for the public portal: never readable
    # through the ORM by regular users. Internal code reads it with sudo().
    access_token = fields.Char(
        string='Access Token', copy=False, index=True, readonly=True,
        groups='base.group_system')
    state = fields.Selection([
        ('pending', 'Pending'),
        ('viewed', 'Viewed'),
        ('signed', 'Signed'),
        ('declined', 'Declined'),
    ], string='Status', default='pending', required=True, copy=False)

    item_ids = fields.One2many('dosign.item', 'signer_id', string='Fields')

    signature_image = fields.Binary(string='Signature', copy=False)
    initials_image = fields.Binary(string='Initials', copy=False)
    signed_on = fields.Datetime(string='Signed On', copy=False)
    decline_reason = fields.Text(string='Decline Reason', copy=False)
    ip_address = fields.Char(string='IP Address', copy=False)
    user_agent = fields.Char(string='User Agent', copy=False)

    reminder_count = fields.Integer(string='Reminders Sent', default=0, copy=False)
    last_reminder = fields.Datetime(string='Last Reminder', copy=False)

    # Short public identifier printed in the signature frame. Derived from the
    # (secret) token with a one-way hash, so it is stable for a signing round
    # and reveals nothing usable.
    frame_hash = fields.Char(
        string='Signature ID', compute='_compute_frame_hash', compute_sudo=True)

    @api.depends('access_token')
    def _compute_frame_hash(self):
        for signer in self:
            token = signer.access_token
            signer.frame_hash = (
                hashlib.sha256(token.encode()).hexdigest()[:10] if token else False)

    @api.onchange('partner_id')
    def _onchange_partner_id(self):
        if self.partner_id:
            self.name = self.partner_id.name
            self.email = self.partner_id.email

    # --- Integrity guards ----------------------------------------------

    @api.model_create_multi
    def create(self, vals_list):
        if not self.env.su:
            for vals in vals_list:
                forged = [
                    name for name in PROTECTED_FIELDS
                    if vals.get(name) and not (name == 'state' and vals[name] == 'pending')
                ]
                if forged:
                    raise AccessError(_(
                        'Signing data cannot be set manually (%s).') % ', '.join(sorted(forged)))
            documents = self.env['dosign.document'].browse(
                [vals['document_id'] for vals in vals_list if vals.get('document_id')])
            if any(doc.state != 'draft' for doc in documents):
                raise UserError(_('Signers can only be added while the document is a draft.'))
        return super().create(vals_list)

    def write(self, vals):
        if not self.env.su:
            forged = PROTECTED_FIELDS & set(vals)
            if forged:
                raise AccessError(_(
                    'Signing data cannot be modified manually (%s).') % ', '.join(sorted(forged)))
            for signer in self:
                doc_state = signer.document_id.state
                if doc_state == 'draft':
                    continue
                # After sending, only a signer who has not acted yet can be
                # corrected (e.g. a typo in the email before resending).
                if (doc_state in ('sent', 'partial')
                        and signer.state in ('pending', 'viewed')
                        and 'document_id' not in vals):
                    continue
                raise UserError(_(
                    'Signer %s can no longer be modified.') % signer.name)
            if vals.get('document_id'):
                target = self.env['dosign.document'].browse(vals['document_id'])
                if target.state != 'draft':
                    raise UserError(_('Signers can only be added while the document is a draft.'))
        return super().write(vals)

    def unlink(self):
        if not self.env.su and any(s.document_id.state != 'draft' for s in self):
            raise UserError(_('Signers can only be removed while the document is a draft.'))
        return super().unlink()

    # --- Tokens ---------------------------------------------------------

    def _ensure_token(self):
        for signer in self.sudo():
            if not signer.access_token:
                signer.access_token = secrets.token_urlsafe(32)

    def _regenerate_token(self):
        for signer in self.sudo():
            signer.access_token = secrets.token_urlsafe(32)

    def _portal_sign_path(self):
        """Relative tokenized signing path for this signer."""
        self.ensure_one()
        return '/sign/%s/%s' % (self.document_id.id, self.sudo().access_token)

    def _portal_sign_url(self):
        """Absolute tokenized signing URL (used in request emails)."""
        self.ensure_one()
        return self.get_base_url() + self._portal_sign_path()
