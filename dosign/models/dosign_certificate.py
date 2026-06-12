from odoo import models, fields, api
from odoo.exceptions import ValidationError


class DosignCertificate(models.Model):
    _name = 'dosign.certificate'
    _description = 'Dosign Signing Certificate'
    _order = 'is_default desc, name'

    name = fields.Char(string='Name', required=True)
    p12_file = fields.Binary(string='PKCS#12 File', required=True, attachment=True)
    p12_filename = fields.Char(string='File Name')
    # Encrypted at rest with Fernet (see TDD 6.4). Write-only in views.
    p12_password = fields.Char(string='Password')

    subject = fields.Char(string='Subject', readonly=True)
    issuer = fields.Char(string='Issuer', readonly=True)
    serial = fields.Char(string='Serial Number', readonly=True)
    valid_from = fields.Datetime(string='Valid From', readonly=True)
    valid_to = fields.Datetime(string='Valid To', readonly=True)

    state = fields.Selection([
        ('valid', 'Valid'),
        ('expiring_soon', 'Expiring Soon'),
        ('expired', 'Expired'),
    ], string='Status', compute='_compute_state', store=True)

    is_default = fields.Boolean(string='Default for Company')
    company_id = fields.Many2one(
        'res.company', string='Company', required=True,
        default=lambda self: self.env.company)
    active = fields.Boolean(string='Active', default=True)

    _sql_constraints = [
        # One default certificate per company (partial unique index).
        ('default_per_company_uniq',
         'EXCLUDE (company_id WITH =) WHERE (is_default IS TRUE)',
         'Only one default certificate is allowed per company.'),
    ]

    @api.depends('valid_to')
    def _compute_state(self):
        now = fields.Datetime.now()
        threshold = fields.Datetime.add(now, days=30)
        for cert in self:
            if not cert.valid_to:
                cert.state = 'valid'
            elif cert.valid_to < now:
                cert.state = 'expired'
            elif cert.valid_to <= threshold:
                cert.state = 'expiring_soon'
            else:
                cert.state = 'valid'

    @api.constrains('p12_file', 'p12_password')
    def _check_certificate(self):
        # Full PKCS#12 parsing + Fernet password verification lands in Phase 4.
        for cert in self:
            if cert.p12_file and not cert.p12_password:
                raise ValidationError('A password is required for the PKCS#12 file.')
