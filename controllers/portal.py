import base64
import hmac
import json

from odoo import http, fields
from odoo.http import request


class DosignPortal(http.Controller):
    """Public, token-authenticated signing portal (TDD §7)."""

    # --- Token validation ----------------------------------------------

    def _get_signer(self, doc_id, token):
        """Return the signer for (doc, token) or None. All access via sudo
        only after the token is validated with a constant-time compare."""
        if not token:
            return None
        signer = request.env['dosign.signer'].sudo().search([
            ('document_id', '=', int(doc_id)),
            ('access_token', '!=', False),
        ])
        signer = signer.filtered(
            lambda s: hmac.compare_digest(s.access_token, token))[:1]
        if not signer:
            return None
        document = signer.document_id
        if document.state not in ('sent', 'partial'):
            return None
        if document.expiry_date and document.expiry_date < fields.Date.today():
            return None
        return signer

    def _signer_payload(self, signer):
        document = signer.document_id
        items = document.item_ids.filtered(lambda i: i.signer_id == signer)
        return {
            'document_id': document.id,
            'document_name': document.name,
            'signer_name': signer.name,
            'token': signer.access_token,
            'pdf_url': '/sign/%s/%s/pdf' % (document.id, signer.access_token),
            'submit_url': '/sign/%s/%s/submit' % (document.id, signer.access_token),
            'decline_url': '/sign/%s/%s/decline' % (document.id, signer.access_token),
            'items': [{
                'id': item.id,
                'type': item.field_type_id.item_type,
                'label': item.field_type_id.name,
                'page': item.page,
                'pos_x': item.pos_x,
                'pos_y': item.pos_y,
                'width': item.width,
                'height': item.height,
                'required': item.required,
                'placeholder': item.placeholder or '',
                'options': item.option_ids.mapped('name'),
                'value': item.value_text or '',
            } for item in items],
        }

    # --- Pages & assets -------------------------------------------------

    @http.route('/sign/<int:doc_id>/<token>', type='http', auth='public', website=False)
    def sign_page(self, doc_id, token, **kw):
        signer = self._get_signer(doc_id, token)
        if not signer:
            return request.not_found()
        if signer.state == 'pending':
            signer.sudo().state = 'viewed'
            signer.document_id._log_event('viewed', signer=signer)
        payload = self._signer_payload(signer)
        props = {'data': payload, 'csrf': request.csrf_token()}
        return request.render('dosign.portal_sign', {
            'props_json': json.dumps(props),
            'document_name': payload['document_name'],
            'signer': signer,
            'already_signed': signer.state == 'signed',
        })

    @http.route('/sign/<int:doc_id>/<token>/pdf', type='http', auth='public')
    def sign_pdf(self, doc_id, token, **kw):
        signer = self._get_signer(doc_id, token)
        if not signer:
            return request.not_found()
        attachment = signer.document_id.attachment_id.sudo()
        if not attachment or not attachment.raw:
            return request.not_found()
        return request.make_response(attachment.raw, [
            ('Content-Type', 'application/pdf'),
            ('Content-Disposition', 'inline'),
        ])

    # --- Submit / decline ----------------------------------------------

    @http.route('/sign/<int:doc_id>/<token>/submit', type='http',
                auth='public', methods=['POST'], csrf=False)
    def sign_submit(self, doc_id, token, **kw):
        signer = self._get_signer(doc_id, token)
        if not signer:
            return request.make_json_response({'error': 'Invalid link.'}, status=404)
        if signer.state == 'signed':
            return request.make_json_response({'error': 'Already signed.'}, status=400)

        try:
            data = request.get_json_data()
            raw_values = data.get('values') or {}
            item_values = {int(k): (v or '') for k, v in raw_values.items()}
        except (ValueError, TypeError, AttributeError):
            return request.make_json_response({'error': 'Malformed request.'}, status=400)
        signature = self._strip_data_url(data.get('signature'))
        initials = self._strip_data_url(data.get('initials'))

        if (signature and not self._is_valid_image(signature)) or \
           (initials and not self._is_valid_image(initials)):
            return request.make_json_response(
                {'error': 'Invalid signature image.'}, status=400)

        error = self._validate_submission(signer, item_values, signature, initials)
        if error:
            return request.make_json_response({'error': error}, status=400)

        metadata = {
            'ip': request.httprequest.remote_addr,
            'user_agent': request.httprequest.user_agent.string,
        }
        signer.document_id.sudo()._process_signature(
            signer, item_values, signature=signature,
            initials=initials, metadata=metadata)
        return request.make_json_response({'success': True})

    @http.route('/sign/<int:doc_id>/<token>/decline', type='http',
                auth='public', methods=['POST'], csrf=False)
    def sign_decline(self, doc_id, token, **kw):
        signer = self._get_signer(doc_id, token)
        if not signer:
            return request.make_json_response({'error': 'Invalid link.'}, status=404)
        data = request.get_json_data()
        signer.document_id.sudo().action_decline(signer, reason=data.get('reason'))
        return request.make_json_response({'success': True})

    @http.route('/sign/<int:doc_id>/<token>/download', type='http', auth='public')
    def sign_download(self, doc_id, token, **kw):
        signer = request.env['dosign.signer'].sudo().search([
            ('document_id', '=', int(doc_id)), ('access_token', '=', token)], limit=1)
        if not signer or signer.document_id.state != 'signed':
            return request.not_found()
        attachment = (signer.document_id.completed_attachment_id
                      or signer.document_id.attachment_id).sudo()
        if not attachment or not attachment.raw:
            return request.not_found()
        return request.make_response(attachment.raw, [
            ('Content-Type', 'application/pdf'),
            ('Content-Disposition',
             'attachment; filename="%s.pdf"' % (signer.document_id.name or 'document')),
        ])

    # --- Helpers --------------------------------------------------------

    def _strip_data_url(self, value):
        if value and ',' in value and value.startswith('data:'):
            return value.split(',', 1)[1]
        return value or False

    def _is_valid_image(self, b64_value):
        """Fully decode the image so a malformed/truncated one is rejected here
        (a clean 400) instead of blowing up later when ir.attachment computes
        the image dimensions (a 500)."""
        try:
            import io
            from PIL import Image
            raw = base64.b64decode(b64_value, validate=True)
            image = Image.open(io.BytesIO(raw))
            image.load()
        except Exception:
            return False
        return True

    def _validate_submission(self, signer, item_values, signature, initials):
        items = signer.document_id.item_ids.filtered(
            lambda i: i.signer_id == signer and i.required)
        for item in items:
            kind = item.field_type_id.item_type
            if kind == 'signature' and not signature:
                return 'A signature is required.'
            if kind == 'initials' and not initials:
                return 'Initials are required.'
            if kind not in ('signature', 'initials') and not item_values.get(item.id):
                return 'Please complete all required fields.'
        return None
