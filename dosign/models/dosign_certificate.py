import base64

from odoo import models, fields, api, _
from odoo.exceptions import ValidationError, UserError
from odoo.tools import config


class DosignCertificate(models.Model):
    _name = 'dosign.certificate'
    _description = 'Dosign Signing Certificate'
    _order = 'is_default desc, name'

    name = fields.Char(string='Name', required=True)
    p12_file = fields.Binary(string='PKCS#12 File', required=True, attachment=True)
    p12_filename = fields.Char(string='File Name')
    # Write-only password input; encrypted into p12_password_enc on save (6.4).
    p12_password = fields.Char(string='Password')
    p12_password_enc = fields.Char(string='Encrypted Password', copy=False)

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

    # --- Fernet password protection (TDD 6.4) --------------------------

    def _fernet(self):
        from cryptography.fernet import Fernet
        key = config.get('dosign_fernet_key')
        if not key:
            raise UserError(_(
                'dosign_fernet_key is not configured in the Odoo server config.'))
        return Fernet(key.encode() if isinstance(key, str) else key)

    def _get_password(self):
        """Decrypt and return the PKCS#12 password (in-memory only)."""
        self.ensure_one()
        if not self.p12_password_enc:
            return ''
        from cryptography.fernet import InvalidToken
        try:
            return self._fernet().decrypt(self.p12_password_enc.encode()).decode()
        except InvalidToken:
            raise UserError(_('Stored certificate password could not be decrypted.'))

    # --- PKCS#12 parsing ------------------------------------------------

    def _parse_p12(self, p12_b64, password):
        from cryptography.hazmat.primitives.serialization import pkcs12
        raw = base64.b64decode(p12_b64)
        try:
            _key, cert, _chain = pkcs12.load_key_and_certificates(
                raw, password.encode() if password else None)
        except (ValueError, TypeError):
            raise UserError(_('Invalid PKCS#12 file or password.'))
        if cert is None:
            raise UserError(_('No certificate found in the PKCS#12 file.'))
        return {
            'subject': cert.subject.rfc4514_string(),
            'issuer': cert.issuer.rfc4514_string(),
            'serial': format(cert.serial_number, 'X'),
            'valid_from': cert.not_valid_before_utc.replace(tzinfo=None),
            'valid_to': cert.not_valid_after_utc.replace(tzinfo=None),
        }

    def _apply_p12(self, vals):
        """Parse metadata + encrypt the password when a file/password is set."""
        p12_b64 = vals.get('p12_file')
        password = vals.get('p12_password')
        if p12_b64 is None and password is None:
            return vals
        cert_file = p12_b64 if p12_b64 is not None else self.p12_file
        pwd = password if password is not None else self._get_password()
        if cert_file:
            vals.update(self._parse_p12(cert_file, pwd))
        if password is not None:
            vals['p12_password_enc'] = self._fernet().encrypt(
                (password or '').encode()).decode()
            vals['p12_password'] = False  # never store plaintext
        return vals

    @api.model_create_multi
    def create(self, vals_list):
        certs = self.env['dosign.certificate']
        for vals in vals_list:
            certs |= super().create(self.browse()._apply_p12(dict(vals)))
        return certs

    def write(self, vals):
        if 'p12_file' in vals or 'p12_password' in vals:
            for cert in self:
                super(DosignCertificate, cert).write(cert._apply_p12(dict(vals)))
            return True
        return super().write(vals)

    @api.constrains('p12_file', 'p12_password_enc')
    def _check_certificate(self):
        for cert in self:
            if cert.p12_file and not cert.p12_password_enc:
                raise ValidationError(_('A password is required for the PKCS#12 file.'))

    @api.model
    def _cron_certificate_watch(self):
        """Recompute state (it depends on the current date) and alert managers
        about certificates that are expiring soon or already expired."""
        certs = self.search([])
        if not certs:
            return True
        certs._compute_state()
        certs.flush_recordset(['state'])
        alerts = certs.filtered(lambda c: c.state in ('expiring_soon', 'expired'))
        if not alerts:
            return True
        managers = self.env.ref('dosign.group_dosign_manager').users
        emails = ','.join(u.email for u in managers if u.email)
        if not emails:
            return True
        template = self.env.ref(
            'dosign.mail_template_dosign_cert_alert', raise_if_not_found=False)
        if template:
            for cert in alerts:
                template.send_mail(
                    cert.id, force_send=False, email_values={'email_to': emails})
        return True
