from odoo import http
from odoo.http import request

MAX_PDF_SIZE = 25 * 1024 * 1024  # 25 MB (TDD 5.1)


class DosignEditorController(http.Controller):
    """Backend-facing endpoints for the OWL editor (Phase 2)."""

    @http.route('/dosign/document/<int:doc_id>/pdf', type='http', auth='user')
    def document_pdf(self, doc_id, **kw):
        document = request.env['dosign.document'].browse(doc_id).exists()
        if not document:
            return request.not_found()
        # Enforces the record rules for the current user.
        document.check_access('read')
        attachment = document.attachment_id.sudo()
        if not attachment or not attachment.raw:
            return request.not_found()
        content = attachment.raw
        headers = [
            ('Content-Type', 'application/pdf'),
            ('Content-Length', str(len(content))),
            ('Content-Disposition', 'inline; filename="%s.pdf"' % (document.name or 'document')),
        ]
        return request.make_response(content, headers)

    @http.route('/dosign/template/<int:template_id>/pdf', type='http', auth='user')
    def template_pdf(self, template_id, **kw):
        template = request.env['dosign.template'].browse(template_id).exists()
        if not template:
            return request.not_found()
        template.check_access('read')
        attachment = template.attachment_id.sudo()
        if not attachment or not attachment.raw:
            return request.not_found()
        return request.make_response(attachment.raw, [
            ('Content-Type', 'application/pdf'),
            ('Content-Length', str(len(attachment.raw))),
            ('Content-Disposition', 'inline; filename="%s.pdf"' % (template.name or 'template')),
        ])

    @http.route('/dosign/upload', type='http', auth='user', methods=['POST'], csrf=True)
    def upload(self, ufile=None, **kw):
        if not ufile:
            return request.make_json_response({'error': 'No file provided.'}, status=400)
        data = ufile.read()
        # Server-side validation: PDF magic bytes + size cap.
        if not data[:5].startswith(b'%PDF'):
            return request.make_json_response({'error': 'The file is not a PDF.'}, status=400)
        if len(data) > MAX_PDF_SIZE:
            return request.make_json_response({'error': 'The file exceeds 25 MB.'}, status=400)
        filename = (ufile.filename or 'Document')
        name = filename.rsplit('.', 1)[0] if '.' in filename else filename
        document = request.env['dosign.document'].create({'name': name})
        attachment = request.env['ir.attachment'].create({
            'name': '%s.pdf' % name,
            'raw': data,
            'mimetype': 'application/pdf',
            'res_model': 'dosign.document',
            'res_id': document.id,
        })
        document.write({
            'attachment_id': attachment.id,
            'sha256_original': document._compute_sha256(data),
        })
        return request.make_json_response({'id': document.id, 'name': document.name})
