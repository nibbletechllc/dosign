from odoo import models, fields, api


class DosignTemplate(models.Model):
    _name = 'dosign.template'
    _description = 'Dosign Template'
    _order = 'name'

    name = fields.Char(string='Name', required=True)
    attachment_id = fields.Many2one(
        'ir.attachment', string='Base PDF', ondelete='restrict')
    item_ids = fields.One2many(
        'dosign.item', 'template_id', string='Fields')
    role_ids = fields.One2many(
        'dosign.role', 'template_id', string='Roles')

    item_count = fields.Integer(string='Fields', compute='_compute_counts')
    role_count = fields.Integer(string='Signers', compute='_compute_counts')

    company_id = fields.Many2one(
        'res.company', string='Company',
        default=lambda self: self.env.company)
    active = fields.Boolean(string='Active', default=True)

    @api.depends('item_ids', 'role_ids')
    def _compute_counts(self):
        for template in self:
            template.item_count = len(template.item_ids)
            template.role_count = len(template.role_ids)
