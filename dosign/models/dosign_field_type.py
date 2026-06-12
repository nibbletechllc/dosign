from odoo import models, fields


class DosignFieldType(models.Model):
    _name = 'dosign.field.type'
    _description = 'Dosign Field Type'
    _order = 'sequence, id'

    name = fields.Char(string='Name', required=True, translate=True)
    technical_name = fields.Char(
        string='Technical Name', required=True,
        help='Stable identifier used by the editor palette and overlay engine.')
    item_type = fields.Selection([
        ('signature', 'Signature'),
        ('initials', 'Initials'),
        ('auto_text', 'Auto Text'),
        ('text', 'Text'),
        ('multiline', 'Multiline'),
        ('checkbox', 'Checkbox'),
        ('radio', 'Radio'),
        ('selection', 'Selection'),
        ('date', 'Date'),
    ], string='Behavior', required=True, default='text',
        help='Drives how the field renders and is captured in the signing portal.')
    auto_fill = fields.Selection([
        ('name', 'Signer Name'),
        ('email', 'Signer Email'),
        ('phone', 'Signer Phone'),
        ('company', 'Signer Company'),
    ], string='Auto-fill Source',
        help='For auto_text fields: signer/partner attribute used to pre-fill the value.')
    icon = fields.Char(string='Icon', help='Font Awesome class shown in the editor palette.')
    default_width = fields.Float(string='Default Width', default=0.18)
    default_height = fields.Float(string='Default Height', default=0.05)
    sequence = fields.Integer(string='Sequence', default=10)
    active = fields.Boolean(string='Active', default=True)

    _sql_constraints = [
        ('technical_name_uniq', 'unique(technical_name)',
         'A field type with this technical name already exists.'),
    ]
