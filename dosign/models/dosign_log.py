from odoo import models, fields, api, _
from odoo.exceptions import AccessError


class DosignLog(models.Model):
    _name = 'dosign.log'
    _description = 'Dosign Audit Log'
    _order = 'timestamp desc, id desc'

    document_id = fields.Many2one(
        'dosign.document', string='Document', required=True, ondelete='cascade', index=True)
    signer_id = fields.Many2one('dosign.signer', string='Signer', ondelete='set null')
    action = fields.Selection([
        ('created', 'Created'),
        ('sent', 'Sent'),
        ('viewed', 'Viewed'),
        ('signed', 'Signed'),
        ('declined', 'Declined'),
        ('reminded', 'Reminded'),
        ('resent', 'Resent'),
        ('expired', 'Expired'),
        ('cancelled', 'Cancelled'),
        ('sealed', 'Sealed'),
        ('downloaded', 'Downloaded'),
    ], string='Action', required=True)
    actor = fields.Char(string='Actor')
    ip_address = fields.Char(string='IP Address')
    user_agent = fields.Char(string='User Agent')
    payload_hash = fields.Char(string='Payload SHA-256')
    timestamp = fields.Datetime(
        string='Timestamp', required=True, default=fields.Datetime.now)

    # --- Append-only enforcement ---------------------------------------

    def write(self, vals):
        raise AccessError(_('Audit log entries cannot be modified.'))

    def unlink(self):
        raise AccessError(_('Audit log entries cannot be deleted.'))
