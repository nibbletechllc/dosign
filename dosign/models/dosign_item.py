from odoo import models, fields, api
from odoo.exceptions import ValidationError


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
