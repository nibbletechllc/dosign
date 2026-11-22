from odoo import _, fields, http
from odoo.http import request
from odoo.addons.portal.controllers.portal import CustomerPortal, pager as portal_pager

# Drafts have not been sent yet, so they never show up in the portal.
PORTAL_STATES = ('sent', 'partial', 'signed', 'expired', 'cancelled')
OPEN_STATES = ('sent', 'partial')


class DosignCustomerPortal(CustomerPortal):
    """'Documents' section of the customer portal (/my): the signature
    documents in which the logged-in contact is a signer.

    Only signers explicitly linked to the user's contact are matched, never by
    email: portal users can change their own email from /my/account, so an email
    match would let anyone list (and sign) someone else's documents."""

    def _dosign_document_domain(self, extra_signer_domain=None):
        signer_domain = [('partner_id', '=', request.env.user.partner_id.id)]
        if extra_signer_domain:
            signer_domain += extra_signer_domain
        return [('signer_ids', 'any', signer_domain), ('state', 'in', PORTAL_STATES)]

    def _dosign_searchbar_filters(self):
        return {
            'all': {'label': _('All'), 'domain': []},
            'to_sign': {
                'label': _('To Sign'),
                'domain': [('state', 'in', OPEN_STATES)],
                'signer_domain': [('state', 'in', ('pending', 'viewed'))],
            },
            'signed': {'label': _('Completed'), 'domain': [('state', '=', 'signed')]},
        }

    def _dosign_searchbar_sortings(self):
        return {
            'date': {'label': _('Newest'), 'order': 'create_date desc, id desc'},
            'name': {'label': _('Name'), 'order': 'name asc, id desc'},
        }

    def _prepare_home_portal_values(self, counters):
        values = super()._prepare_home_portal_values(counters)
        if 'dosign_document_count' in counters:
            values['dosign_document_count'] = request.env['dosign.document'].sudo() \
                .search_count(self._dosign_document_domain())
        return values

    def _dosign_row(self, document, partner):
        """Status and actions of one document, seen by the given signer."""
        signer = document.signer_ids.filtered(lambda s: s.partner_id == partner)[:1]
        row = {
            'document': document,
            'signer': signer,
            'sign_url': False,
            'download_url': False,
        }
        expired = bool(document.expiry_date and document.expiry_date < fields.Date.today())
        if document.state == 'signed':
            row.update(status=_('Completed'), badge='success')
            if document.completed_attachment_id:
                row['download_url'] = '/sign/%s/%s/download' % (
                    document.id, signer.access_token)
        elif signer.state == 'declined':
            row.update(status=_('Declined'), badge='danger')
        elif document.state == 'cancelled':
            row.update(status=_('Cancelled'), badge='secondary')
        elif document.state == 'expired' or expired:
            row.update(status=_('Expired'), badge='secondary')
        elif signer.state == 'signed':
            row.update(status=_('Waiting for other signers'), badge='info')
        elif signer in document._current_recipients():
            row.update(status=_('Waiting for your signature'), badge='warning')
            row['sign_url'] = signer._portal_sign_path()
        else:
            # Sequential signing: an earlier signer has not signed yet.
            row.update(status=_('Waiting for your turn'), badge='info')
        return row

    @http.route(['/my/dosign', '/my/dosign/page/<int:page>'], type='http',
                auth='user', website=True)
    def portal_my_dosign_documents(self, page=1, sortby=None, filterby=None, **kw):
        values = self._prepare_portal_layout_values()
        Document = request.env['dosign.document'].sudo()

        searchbar_sortings = self._dosign_searchbar_sortings()
        sortby = sortby if sortby in searchbar_sortings else 'date'
        searchbar_filters = self._dosign_searchbar_filters()
        filterby = filterby if filterby in searchbar_filters else 'all'
        selected = searchbar_filters[filterby]
        domain = self._dosign_document_domain(selected.get('signer_domain')) + selected['domain']

        document_count = Document.search_count(domain)
        pager = portal_pager(
            url='/my/dosign',
            url_args={'sortby': sortby, 'filterby': filterby},
            total=document_count,
            page=page,
            step=self._items_per_page,
        )
        documents = Document.search(
            domain, order=searchbar_sortings[sortby]['order'],
            limit=self._items_per_page, offset=pager['offset'])
        partner = request.env.user.partner_id

        values.update({
            'rows': [self._dosign_row(document, partner) for document in documents],
            'page_name': 'dosign_documents',
            'default_url': '/my/dosign',
            'pager': pager,
            'searchbar_sortings': searchbar_sortings,
            'sortby': sortby,
            'searchbar_filters': searchbar_filters,
            'filterby': filterby,
        })
        return request.render('dosign.portal_my_dosign_documents', values)
