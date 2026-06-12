from odoo import models, fields


class DosignRole(models.Model):
    _name = 'dosign.role'
    _description = 'Dosign Template Signer Role'
    _order = 'sequence, id'

    name = fields.Char(string='Role', required=True, translate=True)
    template_id = fields.Many2one(
        'dosign.template', string='Template', required=True, ondelete='cascade')
    sequence = fields.Integer(
        string='Signing Order', default=10,
        help='Roles with equal order sign in parallel; lower orders sign first.')
    color = fields.Integer(string='Color')
