from odoo import models, fields, api, _
from odoo.exceptions import UserError, ValidationError


class DosignItem(models.Model):
    _name = 'dosign.item'
    _description = 'Dosign Placed Field'
    _order = 'page, id'

    document_id = fields.Many2one(
        'dosign.document', string='Document', ondelete='cascade')
    template_id = fields.Many2one(
        'dosign.template', string='Template', ondelete='cascade')

    field_type_id = fields.Many2one(
        'dosign.field.type', string='Field Type', required=True, ondelete='restrict')
    item_type = fields.Selection(
        related='field_type_id.item_type', store=True, string='Behavior')

    signer_id = fields.Many2one(
        'dosign.signer', string='Signer', ondelete='cascade')
    role_id = fields.Many2one(
        'dosign.role', string='Role', ondelete='cascade')

    page = fields.Integer(string='Page', required=True, default=1)
    # Normalized 0..1 coordinates relative to the page, zoom-independent.
    pos_x = fields.Float(string='X', required=True, default=0.0)
    pos_y = fields.Float(string='Y', required=True, default=0.0)
    width = fields.Float(string='Width', required=True, default=0.18)
    height = fields.Float(string='Height', required=True, default=0.05)

    required = fields.Boolean(string='Required', default=True)
    placeholder = fields.Char(string='Placeholder')
    option_ids = fields.One2many('dosign.item.option', 'item_id', string='Options')
    value_text = fields.Text(string='Value', copy=False)

    # --- Integrity guards ----------------------------------------------
    # The layout of a document is frozen once it leaves draft: signers must
    # sign exactly what was sent. Only the signing flow (sudo) writes values.

    def _check_document_editable(self, documents):
        if not self.env.su and any(doc.state != 'draft' for doc in documents):
            raise UserError(_(
                'Fields can only be changed while the document is a draft.'))

    @api.model_create_multi
    def create(self, vals_list):
        self._check_document_editable(self.env['dosign.document'].browse(
            [vals['document_id'] for vals in vals_list if vals.get('document_id')]))
        return super().create(vals_list)

    def write(self, vals):
        documents = self.document_id
        if vals.get('document_id'):
            documents |= self.env['dosign.document'].browse(vals['document_id'])
        self._check_document_editable(documents)
        return super().write(vals)

    def unlink(self):
        self._check_document_editable(self.document_id)
        return super().unlink()

    @api.constrains('document_id', 'template_id')
    def _check_owner(self):
        for item in self:
            if bool(item.document_id) == bool(item.template_id):
                raise ValidationError(
                    'A field must belong to exactly one of a document or a template.')

    @api.constrains('page')
    def _check_page(self):
        for item in self:
            if item.page < 1:
                raise ValidationError('Page number must be 1 or greater.')


class DosignItemOption(models.Model):
    _name = 'dosign.item.option'
    _description = 'Dosign Field Option'
    _order = 'sequence, id'

    item_id = fields.Many2one(
        'dosign.item', string='Field', required=True, ondelete='cascade')
    name = fields.Char(string='Label', required=True)
    sequence = fields.Integer(string='Sequence', default=10)

    @api.model_create_multi
    def create(self, vals_list):
        items = self.env['dosign.item'].browse(
            [vals['item_id'] for vals in vals_list if vals.get('item_id')])
        items._check_document_editable(items.document_id)
        return super().create(vals_list)

    def write(self, vals):
        items = self.item_id
        if vals.get('item_id'):
            items |= self.env['dosign.item'].browse(vals['item_id'])
        items._check_document_editable(items.document_id)
        return super().write(vals)

    def unlink(self):
        self.item_id._check_document_editable(self.item_id.document_id)
        return super().unlink()
