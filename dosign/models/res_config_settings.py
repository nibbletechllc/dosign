from odoo import models, fields


class ResConfigSettings(models.TransientModel):
    _inherit = 'res.config.settings'

    dosign_default_expiry_days = fields.Integer(
        string='Default Expiry (days)',
        config_parameter='dosign.default_expiry_days', default=30,
        help='Default number of days before a sent document expires.')
    dosign_reminder_interval_days = fields.Integer(
        string='Reminder Interval (days)',
        config_parameter='dosign.reminder_interval_days', default=3,
        help='Days between reminder emails to pending signers.')
    dosign_reminder_max = fields.Integer(
        string='Max Reminders',
        config_parameter='dosign.reminder_max', default=3,
        help='Maximum number of reminders sent per signer.')
    dosign_tsa_url = fields.Char(
        string='Timestamp Authority (TSA) URL',
        config_parameter='dosign.tsa_url',
        help='RFC 3161 TSA URL. When set, the PAdES seal is B-T; otherwise B-B.')
