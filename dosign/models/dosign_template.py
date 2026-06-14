from odoo import models, fields, api, _


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

    document_ids = fields.One2many('dosign.document', 'template_id', string='Documents')
    doc_in_progress_count = fields.Integer(
        string='In Progress', compute='_compute_doc_counts')
    doc_signed_count = fields.Integer(
        string='Signed', compute='_compute_doc_counts')

    favorite_user_ids = fields.Many2many(
        'res.users', 'dosign_template_favorite_rel', 'template_id', 'user_id',
        string='Favorited By', default=lambda self: self.env.user)
    is_favorite = fields.Boolean(
        string='Favorite', compute='_compute_is_favorite',
        inverse='_inverse_is_favorite', search='_search_is_favorite')

    company_id = fields.Many2one(
        'res.company', string='Company',
        default=lambda self: self.env.company)
    active = fields.Boolean(string='Active', default=True)

    @api.depends('item_ids', 'role_ids')
    def _compute_counts(self):
        for template in self:
            template.item_count = len(template.item_ids)
            template.role_count = len(template.role_ids)

    @api.depends('document_ids.state')
    def _compute_doc_counts(self):
        for template in self:
            docs = template.document_ids
            template.doc_in_progress_count = len(
                docs.filtered(lambda d: d.state in ('draft', 'sent', 'partial')))
            template.doc_signed_count = len(
                docs.filtered(lambda d: d.state == 'signed'))

    @api.depends_context('uid')
    @api.depends('favorite_user_ids')
    def _compute_is_favorite(self):
        uid = self.env.uid
        for template in self:
            template.is_favorite = uid in template.favorite_user_ids.ids

    def _inverse_is_favorite(self):
        user = self.env.user
        for template in self:
            if template.is_favorite:
                template.favorite_user_ids = [(4, user.id)]
            else:
                template.favorite_user_ids = [(3, user.id)]

    def _search_is_favorite(self, operator, value):
        if operator not in ('=', '!='):
            raise ValueError(_('Unsupported operator for is_favorite search.'))
        favorited = (operator == '=') == bool(value)
        key = 'in' if favorited else 'not in'
        return [('favorite_user_ids', key, [self.env.uid])]

    def action_open_editor(self):
        """Open the OWL editor in template mode (roles instead of signers)."""
        self.ensure_one()
        return {
            'type': 'ir.actions.client',
            'tag': 'dosign.editor',
            'name': self.name or _('Template'),
            'params': {'template_id': self.id},
        }

    def action_use(self):
        """Create a document from this template and open it in the editor."""
        self.ensure_one()
        document_id = self.env['dosign.document'].create_from_template(self.id)
        return self.env['dosign.document'].browse(document_id).action_open_editor()

    def action_duplicate(self):
        """Duplicate the template (PDF, roles and field layout) and open it."""
        self.ensure_one()
        new = self.create({
            'name': _('%s (copy)') % (self.name or ''),
            'company_id': self.company_id.id,
        })
        if self.attachment_id:
            new.attachment_id = self.attachment_id.copy({
                'res_model': 'dosign.template',
                'res_id': new.id,
            }).id
        role_map = {}
        for role in self.role_ids:
            role_map[role.id] = role.copy({'template_id': new.id}).id
        for item in self.item_ids:
            item.copy({
                'template_id': new.id,
                'role_id': role_map.get(item.role_id.id),
            })
        return new.action_open_editor()
