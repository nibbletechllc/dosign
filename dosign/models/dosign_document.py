import base64
import hashlib

from odoo import models, fields, api, _
from odoo.exceptions import UserError


class DosignDocument(models.Model):
    _name = 'dosign.document'
    _description = 'Dosign Document'
    _inherit = ['mail.thread', 'mail.activity.mixin']
    _order = 'create_date desc'

    name = fields.Char(
        string='Name', required=True, tracking=True,
        default=lambda self: _('New Document'))
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
    signing_mode = fields.Selection([
        ('parallel', 'Parallel'),
        ('sequential', 'Sequential'),
    ], string='Signing Order', default='parallel', required=True,
        help='Parallel: all signers are notified at once. '
             'Sequential: each signer is notified after the previous one signs.')
    message = fields.Text(
        string='Message', help='Optional personal message included in the request email.')

    signer_count = fields.Integer(
        string='Signers', compute='_compute_progress', store=True)
    signed_count = fields.Integer(
        string='Signed', compute='_compute_progress', store=True)
    progress_label = fields.Char(
        string='Progress', compute='_compute_progress', store=True)

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

    # --- Editor (Phase 2) ----------------------------------------------

    def action_open_editor(self):
        """Open the OWL editor client action on this document."""
        self.ensure_one()
        return {
            'type': 'ir.actions.client',
            'tag': 'dosign.editor',
            'name': self.name or _('Editor'),
            'params': {'document_id': self.id},
        }

    @api.model
    def create_from_template(self, template_id):
        """Create a draft document from a template, copying its field layout.

        Roles stay on the copied items so the editor can map each one to a real
        signer. Returns the new document id for the client action to open.
        """
        template = self.env['dosign.template'].browse(template_id).exists()
        if not template:
            raise UserError(_('Template not found.'))
        document = self.create({
            'name': template.name,
            'template_id': template.id,
            'attachment_id': template.attachment_id.id,
        })
        for item in template.item_ids:
            item.copy({
                'template_id': False,
                'document_id': document.id,
                'signer_id': False,
            })
        return document.id

    def action_save_as_template(self, name=None):
        """Create a reusable template from this document: copy the PDF, turn each
        signer into a role, and copy the field layout bound to those roles."""
        self.ensure_one()
        template = self.env['dosign.template'].create({
            'name': name or _('%s Template') % (self.name or ''),
            'company_id': self.company_id.id,
        })
        if self.attachment_id:
            attachment = self.attachment_id.copy({
                'res_model': 'dosign.template',
                'res_id': template.id,
                'name': '%s.pdf' % (template.name or 'template'),
            })
            template.attachment_id = attachment.id
        role_by_signer = {}
        for signer in self.signer_ids:
            role = self.env['dosign.role'].create({
                'template_id': template.id,
                'name': signer.name,
                'sequence': signer.sequence,
                'color': signer.color,
            })
            role_by_signer[signer.id] = role.id
        for item in self.item_ids:
            item.copy({
                'document_id': False,
                'template_id': template.id,
                'signer_id': False,
                'role_id': role_by_signer.get(item.signer_id.id),
                'value_text': False,
            })
        return template.action_open_editor()

    # --- State machine --------------------------------------------------

    def action_send(self):
        """Validate, generate tokens, move To Sign and email the signers.

        In sequential mode only the first pending rank is emailed; later ranks
        are notified as earlier signers complete (see _process_signature).
        """
        for doc in self:
            doc._validate_for_send()
            for signer in doc.signer_ids:
                signer._ensure_token()
            if not doc.expiry_date:
                doc.expiry_date = fields.Date.add(fields.Date.today(), days=30)
            doc.state = 'sent'
            doc._send_request_emails(doc._current_recipients())
        return True

    def action_sign_now(self):
        """Send (if needed) and open the public signing portal for the current user."""
        self.ensure_one()
        if self.state == 'draft':
            self.action_send()
        email = (self.env.user.email or '').lower()
        signer = self.signer_ids.filtered(
            lambda s: s.email and s.email.lower() == email)[:1]
        if not signer:
            raise UserError(_('You are not listed as a signer on this document.'))
        signer._ensure_token()
        return {
            'type': 'ir.actions.act_url',
            'url': signer._portal_sign_path(),
            'target': 'new',
        }

    def action_resend(self):
        for doc in self:
            if doc.state not in ('sent', 'partial', 'expired'):
                raise UserError(_('Only sent, partially signed or expired documents can be resent.'))
            if doc.state == 'expired':
                doc.state = 'sent'
                if not doc.expiry_date or doc.expiry_date < fields.Date.today():
                    doc.expiry_date = fields.Date.add(fields.Date.today(), days=30)
            for signer in doc.signer_ids.filtered(lambda s: s.state in ('pending', 'viewed')):
                signer._regenerate_token()
            doc._log_event('resent')
            doc._send_request_emails(doc._current_recipients())
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

    # --- Signing (Phase 3) ---------------------------------------------

    def _current_recipients(self):
        """Signers who should receive a request email right now."""
        self.ensure_one()
        pending = self.signer_ids.filtered(lambda s: s.state in ('pending', 'viewed'))
        if self.signing_mode == 'sequential' and pending:
            current_rank = min(pending.mapped('sequence'))
            return pending.filtered(lambda s: s.sequence == current_rank)
        return pending

    def _send_request_emails(self, signers):
        template = self.env.ref(
            'dosign.mail_template_dosign_request', raise_if_not_found=False)
        for signer in signers:
            if template:
                template.send_mail(signer.id, force_send=False)
            self._log_event('sent', signer=signer)

    def _process_signature(self, signer, item_values, signature=None,
                           initials=None, metadata=None):
        """Store a signer's submitted values + signature and advance state."""
        self.ensure_one()
        metadata = metadata or {}
        for item in signer.item_ids:
            if item.id in item_values:
                item.value_text = item_values[item.id]
        signer.write({
            'state': 'signed',
            'signed_on': fields.Datetime.now(),
            'signature_image': signature or False,
            'initials_image': initials or False,
            'ip_address': metadata.get('ip'),
            'user_agent': metadata.get('user_agent'),
        })
        payload = repr(sorted(item_values.items()))
        self._log_event('signed', signer=signer,
                        payload_hash=self._compute_sha256(payload.encode()))
        if all(s.state == 'signed' for s in self.signer_ids):
            self._mark_signed()
        else:
            self.state = 'partial'
            if self.signing_mode == 'sequential':
                self._send_request_emails(self._current_recipients())
        return True

    def _mark_signed(self):
        self.ensure_one()
        self.state = 'signed'
        self._log_event('signed')
        self._finalize()
        template = self.env.ref(
            'dosign.mail_template_dosign_completed', raise_if_not_found=False)
        if template:
            email_values = {}
            if self.completed_attachment_id:
                email_values['attachment_ids'] = [self.completed_attachment_id.id]
            template.send_mail(self.id, force_send=False, email_values=email_values)

    def action_decline(self, signer, reason=None):
        self.ensure_one()
        signer.write({'state': 'declined', 'decline_reason': reason})
        self._log_event('declined', signer=signer)
        template = self.env.ref(
            'dosign.mail_template_dosign_declined', raise_if_not_found=False)
        if template:
            template.with_context(decline_reason=reason).send_mail(
                self.id, force_send=False)
        return True

    def _finalize(self):
        """Flatten values + signatures, append an audit page, PAdES-seal with
        the company certificate, and store the completed PDF. Never blocks: if
        no valid certificate is available the flattened+hashed PDF is still
        produced and a chatter note is posted (TDD 5.4 / 6.2)."""
        self.ensure_one()
        if not self.attachment_id or not self.attachment_id.raw:
            return False
        from odoo.addons.dosign.services import pdf_filler, pdf_sealer

        items = []
        for item in self.item_ids:
            signer = item.signer_id
            image = None
            kind = item.field_type_id.item_type
            if kind == 'signature' and signer.signature_image:
                image = base64.b64decode(signer.signature_image)
            elif kind == 'initials' and signer.initials_image:
                image = base64.b64decode(signer.initials_image)
            items.append({
                'page': item.page,
                'pos_x': item.pos_x, 'pos_y': item.pos_y,
                'width': item.width, 'height': item.height,
                'value_text': item.value_text or '',
                'image_bytes': image,
            })

        final_bytes = pdf_filler.build_completed_pdf(
            self.attachment_id.raw, items, self._build_audit_lines())
        self.sha256_final = self._compute_sha256(final_bytes)

        sealed = False
        certificate = self._seal_certificate()
        if certificate:
            try:
                final_bytes = pdf_sealer.seal(
                    final_bytes,
                    base64.b64decode(certificate.p12_file),
                    certificate._get_password(),
                    tsa_url=self._tsa_url())
                self.certificate_id = certificate.id
                self.sha256_final = self._compute_sha256(final_bytes)
                sealed = True
            except Exception as exc:  # noqa: BLE001 - never block finalization
                self.message_post(body=_('Cryptographic seal skipped: %s') % exc)
        else:
            self.message_post(body=_(
                'No valid certificate; document flattened and hashed but not sealed.'))

        attachment = self.env['ir.attachment'].create({
            'name': '%s (signed).pdf' % (self.name or 'document'),
            'raw': final_bytes,
            'mimetype': 'application/pdf',
            'res_model': 'dosign.document',
            'res_id': self.id,
        })
        self.completed_attachment_id = attachment.id
        if sealed:
            self._log_event('sealed')
        return True

    def _seal_certificate(self):
        self.ensure_one()
        return self.env['dosign.certificate'].sudo().search([
            ('company_id', '=', self.company_id.id),
            ('is_default', '=', True),
            ('state', '!=', 'expired'),
        ], limit=1)

    def _tsa_url(self):
        return self.env['ir.config_parameter'].sudo().get_param('dosign.tsa_url') or None

    def _build_audit_lines(self):
        self.ensure_one()
        lines = [
            'Document: %s' % (self.name or ''),
            'Reference: %s' % (self.reference or ''),
            'Original SHA-256: %s' % (self.sha256_original or 'n/a'),
            '',
            'Signers:',
        ]
        for signer in self.signer_ids:
            lines.append('  - %s <%s> | %s | %s | IP %s' % (
                signer.name, signer.email, signer.state,
                signer.signed_on or '', signer.ip_address or '-'))
        lines += ['', 'Event log:']
        for log in self.log_ids.sorted('timestamp'):
            lines.append('  %s  %s  %s' % (log.timestamp, log.action, log.actor or ''))
        return lines

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
