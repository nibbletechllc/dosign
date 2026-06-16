import base64

from odoo.exceptions import AccessError, UserError
from odoo.tests.common import TransactionCase, tagged

# Minimal one-page PDF (US Letter).
_PDF = base64.b64decode(
    b'JVBERi0xLjQKMSAwIG9iago8PC9UeXBlL0NhdGFsb2cvUGFnZXMgMiAwIFI+PgplbmRvYmoKMiAw'
    b'IG9iago8PC9UeXBlL1BhZ2VzL0tpZHNbMyAwIFJdL0NvdW50IDE+PgplbmRvYmoKMyAwIG9iago8'
    b'PC9UeXBlL1BhZ2UvUGFyZW50IDIgMCBSL01lZGlhQm94WzAgMCA2MTIgNzkyXT4+CmVuZG9iagp4'
    b'cmVmCjAgNAowMDAwMDAwMDAwIDY1NTM1IGYgCjAwMDAwMDAwMDkgMDAwMDAgbiAKMDAwMDAwMDA1'
    b'OCAwMDAwMCBuIAowMDAwMDAwMTE1IDAwMDAwIG4gCnRyYWlsZXIKPDwvU2l6ZSA0L1Jvb3QgMSAw'
    b'IFI+PgpzdGFydHhyZWYKMTkwCiUlRU9GCg==')

# Small valid PNG (fully decodable by PIL, as ir.attachment requires).
_PNG = ('data:image/png;base64,iVBORw0KGgoAAAANSUhEUgAAAAQAAAAECAYAAACp8Z5+AAAAFUlE'
        'QVR4nGMU0Qj4z4AEmBjQAGEBAGTwAZPtEhoWAAAAAElFTkSuQmCC')


@tagged('post_install', '-at_install')
class TestDosign(TransactionCase):

    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        cls.Document = cls.env['dosign.document']
        cls.signature_type = cls.env.ref('dosign.field_type_signature')

    def _make_document(self, name='Test Doc'):
        doc = self.Document.create({'name': name})
        attachment = self.env['ir.attachment'].create({
            'name': 's.pdf', 'raw': _PDF, 'mimetype': 'application/pdf',
            'res_model': 'dosign.document', 'res_id': doc.id,
        })
        doc.attachment_id = attachment.id
        return doc

    def test_reference_sequence(self):
        doc = self.Document.create({'name': 'Seq'})
        self.assertTrue(doc.reference.startswith('DSN/'))

    def test_send_requires_pdf_and_signature(self):
        doc = self.Document.create({'name': 'No PDF'})
        with self.assertRaises(UserError):
            doc.action_send()
        doc = self._make_document()
        with self.assertRaises(UserError):
            doc.action_send()  # no signer yet

    def test_send_and_default_expiry(self):
        doc = self._make_document()
        signer = self.env['dosign.signer'].create({
            'document_id': doc.id, 'name': 'A', 'email': 'a@x.com'})
        self.env['dosign.item'].create({
            'document_id': doc.id, 'field_type_id': self.signature_type.id,
            'signer_id': signer.id, 'page': 1,
            'pos_x': 0.1, 'pos_y': 0.1, 'width': 0.2, 'height': 0.06})
        doc.action_send()
        self.assertEqual(doc.state, 'sent')
        self.assertTrue(signer.access_token)
        self.assertTrue(doc.expiry_date)

    def test_full_signature_flow(self):
        doc = self._make_document()
        signer = self.env['dosign.signer'].create({
            'document_id': doc.id, 'name': 'A', 'email': 'a@x.com'})
        self.env['dosign.item'].create({
            'document_id': doc.id, 'field_type_id': self.signature_type.id,
            'signer_id': signer.id, 'page': 1,
            'pos_x': 0.1, 'pos_y': 0.1, 'width': 0.2, 'height': 0.06})
        doc.action_send()
        doc._process_signature(signer, {}, signature=_PNG.split(',', 1)[1])
        self.assertEqual(doc.state, 'signed')
        self.assertEqual(signer.state, 'signed')
        self.assertTrue(doc.completed_attachment_id)
        self.assertTrue(doc.sha256_final)

    def test_log_is_append_only(self):
        doc = self._make_document()
        log = doc.log_ids[:1]
        self.assertTrue(log)
        with self.assertRaises(AccessError):
            log.write({'actor': 'x'})
        with self.assertRaises(AccessError):
            log.unlink()

    def test_expire_cron(self):
        doc = self._make_document()
        signer = self.env['dosign.signer'].create({
            'document_id': doc.id, 'name': 'A', 'email': 'a@x.com'})
        self.env['dosign.item'].create({
            'document_id': doc.id, 'field_type_id': self.signature_type.id,
            'signer_id': signer.id, 'page': 1,
            'pos_x': 0.1, 'pos_y': 0.1, 'width': 0.2, 'height': 0.06})
        doc.action_send()
        doc.expiry_date = '2000-01-01'
        self.Document._cron_expire_documents()
        self.assertEqual(doc.state, 'expired')

    def test_decline_cancels_document(self):
        doc = self._make_document()
        signer = self.env['dosign.signer'].create({
            'document_id': doc.id, 'name': 'A', 'email': 'a@x.com'})
        self.env['dosign.item'].create({
            'document_id': doc.id, 'field_type_id': self.signature_type.id,
            'signer_id': signer.id, 'page': 1,
            'pos_x': 0.1, 'pos_y': 0.1, 'width': 0.2, 'height': 0.06})
        doc.action_send()
        doc.action_decline(signer, reason='No thanks')
        self.assertEqual(signer.state, 'declined')
        self.assertEqual(doc.state, 'cancelled')

    def test_template_flow_and_favorites(self):
        doc = self._make_document('Tpl Source')
        signer = self.env['dosign.signer'].create({
            'document_id': doc.id, 'name': 'Customer', 'email': 'c@x.com'})
        self.env['dosign.item'].create({
            'document_id': doc.id, 'field_type_id': self.signature_type.id,
            'signer_id': signer.id, 'page': 1,
            'pos_x': 0.1, 'pos_y': 0.1, 'width': 0.2, 'height': 0.06})
        action = doc.action_save_as_template('My Template')
        template = self.env['dosign.template'].browse(action['params']['template_id'])
        self.assertEqual(template.role_count, 1)
        self.assertEqual(template.item_count, 1)
        # favorites search accepts normalized operators
        self.assertIn(template, self.env['dosign.template'].search(
            [('is_favorite', '=', True)]))
        # create document back from the template
        new_id = self.Document.create_from_template(template.id)
        new_doc = self.Document.browse(new_id)
        self.assertEqual(len(new_doc.item_ids), 1)
        self.assertTrue(new_doc.item_ids.role_id)
