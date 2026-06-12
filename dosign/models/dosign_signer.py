import secrets

from odoo import models, fields


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

    access_token = fields.Char(string='Access Token', copy=False, index=True, readonly=True)
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
    ip_address = fields.Char(string='IP Address', copy=False)
    user_agent = fields.Char(string='User Agent', copy=False)

    reminder_count = fields.Integer(string='Reminders Sent', default=0, copy=False)
    last_reminder = fields.Datetime(string='Last Reminder', copy=False)

    def _ensure_token(self):
        for signer in self:
            if not signer.access_token:
                signer.access_token = secrets.token_urlsafe(32)

    def _regenerate_token(self):
        for signer in self:
            signer.access_token = secrets.token_urlsafe(32)
