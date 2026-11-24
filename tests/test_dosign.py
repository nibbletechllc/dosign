import base64
import io
import json

from odoo.exceptions import AccessError, UserError
from odoo.tests.common import HttpCase, TransactionCase, new_test_user, tagged

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
        action = doc.action_download_signed()
        self.assertEqual(action['url'], '/dosign/document/%s/signed_pdf' % doc.id)

    def test_download_requires_completed_document(self):
        doc = self._make_document()
        with self.assertRaises(UserError):
            doc.action_download_signed()

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


@tagged('post_install', '-at_install')
class TestDosignAccess(TransactionCase):
    """Record rules and integrity guards, exercised as non-admin users."""

    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        cls.signature_type = cls.env.ref('dosign.field_type_signature')
        cls.alice = new_test_user(
            cls.env, login='alice@dosign.test', email='alice@dosign.test',
            groups='dosign.group_dosign_user')
        cls.bob = new_test_user(
            cls.env, login='bob@dosign.test', email='bob@dosign.test',
            groups='dosign.group_dosign_user')

    def _make_document(self, user, signer_email='ext@x.com'):
        """Create, as `user`, a draft with one signer and one signature field."""
        env = self.env(user=user)
        doc = env['dosign.document'].create({'name': 'Access Doc'})
        attachment = self.env['ir.attachment'].create({
            'name': 's.pdf', 'raw': _PDF, 'mimetype': 'application/pdf',
            'res_model': 'dosign.document', 'res_id': doc.id,
        })
        doc.attachment_id = attachment.id
        signer = env['dosign.signer'].create({
            'document_id': doc.id, 'name': 'Ext', 'email': signer_email})
        item = env['dosign.item'].create({
            'document_id': doc.id, 'field_type_id': self.signature_type.id,
            'signer_id': signer.id, 'page': 1,
            'pos_x': 0.1, 'pos_y': 0.1, 'width': 0.2, 'height': 0.06})
        return doc, signer, item

    def test_children_hidden_from_other_users(self):
        doc, signer, item = self._make_document(self.alice)
        bob_env = self.env(user=self.bob)
        self.assertFalse(bob_env['dosign.signer'].search([('id', '=', signer.id)]))
        self.assertFalse(bob_env['dosign.item'].search([('id', '=', item.id)]))
        self.assertFalse(bob_env['dosign.log'].search([('document_id', '=', doc.id)]))
        with self.assertRaises(AccessError):
            signer.with_user(self.bob).read(['name'])
        with self.assertRaises(AccessError):
            item.with_user(self.bob).write({'pos_x': 0.5})

    def test_cosigner_reads_but_cannot_edit(self):
        doc, signer, item = self._make_document(self.alice, signer_email=self.bob.login)
        self.assertEqual(signer.with_user(self.bob).read(['name'])[0]['name'], 'Ext')
        with self.assertRaises(AccessError):
            signer.with_user(self.bob).write({'email': 'evil@x.com'})
        with self.assertRaises(AccessError):
            item.with_user(self.bob).unlink()
        with self.assertRaises(UserError):
            doc.with_user(self.bob).action_share()

    def test_token_not_readable_by_users(self):
        doc, signer, _item = self._make_document(self.alice)
        doc.action_send()
        self.assertTrue(signer.sudo().access_token)
        with self.assertRaises(AccessError):
            signer.read(['access_token'])
        # The sender still gets a working link through the explicit action.
        action = doc.action_share()
        self.assertIn(signer.sudo().access_token, action['params']['url'])

    def test_signing_data_cannot_be_forged(self):
        doc, signer, _item = self._make_document(self.alice)
        doc.action_send()
        with self.assertRaises(AccessError):
            signer.write({'state': 'signed'})
        with self.assertRaises(AccessError):
            signer.write({'signature_image': _PNG.split(',', 1)[1]})
        with self.assertRaises(AccessError):
            signer.env['dosign.signer'].create({
                'document_id': doc.id, 'name': 'X', 'email': 'x@x.com',
                'state': 'signed'})
        with self.assertRaises(AccessError):
            signer.env['dosign.log'].create({'document_id': doc.id, 'action': 'signed'})
        self.assertEqual(signer.state, 'pending')

    def test_layout_frozen_after_send(self):
        doc, signer, item = self._make_document(self.alice)
        item.write({'pos_x': 0.3})  # draft: allowed
        doc.action_send()
        with self.assertRaises(UserError):
            item.write({'pos_x': 0.6})
        with self.assertRaises(UserError):
            item.unlink()
        with self.assertRaises(UserError):
            item.env['dosign.item'].create({
                'document_id': doc.id, 'field_type_id': self.signature_type.id,
                'signer_id': signer.id, 'page': 1})
        with self.assertRaises(UserError):
            signer.unlink()
        with self.assertRaises(UserError):
            doc.write({'attachment_id': False})
        # A signer who has not acted yet can still have a typo fixed.
        signer.write({'email': 'fixed@x.com'})
        doc._process_signature(signer, {}, signature=_PNG.split(',', 1)[1])
        with self.assertRaises(UserError):
            signer.write({'email': 'late@x.com'})

    def test_reset_to_draft_clears_signatures(self):
        doc, signer, item = self._make_document(self.alice)
        second = signer.env['dosign.signer'].create({
            'document_id': doc.id, 'name': 'Second', 'email': 'two@x.com'})
        item.env['dosign.item'].create({
            'document_id': doc.id, 'field_type_id': self.signature_type.id,
            'signer_id': second.id, 'page': 1})
        doc.action_send()
        old_token = signer.sudo().access_token
        doc._process_signature(signer, {}, signature=_PNG.split(',', 1)[1])
        self.assertEqual(doc.state, 'partial')
        doc.action_cancel()
        doc.action_draft()
        self.assertEqual(doc.state, 'draft')
        self.assertEqual(signer.state, 'pending')
        self.assertFalse(signer.signature_image)
        self.assertFalse(signer.signed_on)
        self.assertFalse(signer.sudo().access_token)
        self.assertIn('reset', doc.log_ids.mapped('action'))
        # The draft is editable again and a resend issues fresh links.
        item.write({'pos_x': 0.4})
        doc.action_send()
        self.assertNotEqual(signer.sudo().access_token, old_token)


@tagged('post_install', '-at_install')
class TestDosignPartner(TransactionCase):
    """Smart button on contacts: documents in which the contact signs."""

    def test_partner_document_count(self):
        Partner = self.env['res.partner']
        company = Partner.create({'name': 'ACME', 'is_company': True})
        contact = Partner.create({
            'name': 'Jane', 'email': 'jane@acme.test', 'parent_id': company.id})
        other = Partner.create({'name': 'Other', 'email': 'other@x.test'})
        Document = self.env['dosign.document']
        Signer = self.env['dosign.signer']

        linked = Document.create({'name': 'Linked'})
        Signer.create({'document_id': linked.id, 'partner_id': contact.id,
                       'name': 'Jane', 'email': 'jane@acme.test'})
        # Signer typed by hand, not linked to the contact: matched by email.
        typed = Document.create({'name': 'Typed'})
        Signer.create({'document_id': typed.id, 'name': 'Jane',
                       'email': 'JANE@acme.test'})
        unrelated = Document.create({'name': 'Unrelated'})
        Signer.create({'document_id': unrelated.id, 'partner_id': other.id,
                       'name': 'Other', 'email': 'other@x.test'})

        self.assertEqual(contact.dosign_document_count, 2)
        # The company sees the documents of its contacts.
        self.assertEqual(company.dosign_document_count, 1)
        self.assertEqual(other.dosign_document_count, 1)

        action = contact.action_view_dosign_documents()
        self.assertEqual(action['res_model'], 'dosign.document')
        self.assertEqual(set(Document.search(action['domain']).ids),
                         {linked.id, typed.id})


@tagged('post_install', '-at_install')
class TestDosignMyPortal(HttpCase):
    """'Signature Documents' section of the customer portal (/my/dosign)."""

    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        cls.signature_type = cls.env.ref('dosign.field_type_signature')
        cls.portal_user = new_test_user(
            cls.env, login='portal_signer', email='portal@dosign.test',
            password='portal_signer', groups='base.group_portal')
        cls.partner = cls.portal_user.partner_id

    def _sent_document(self, name, **signer_vals):
        doc = self.env['dosign.document'].create({'name': name})
        doc.attachment_id = self.env['ir.attachment'].create({
            'name': 's.pdf', 'raw': _PDF, 'mimetype': 'application/pdf',
            'res_model': 'dosign.document', 'res_id': doc.id,
        })
        signer = self.env['dosign.signer'].create(dict(
            {'document_id': doc.id, 'name': 'Signer'}, **signer_vals))
        self.env['dosign.item'].create({
            'document_id': doc.id, 'field_type_id': self.signature_type.id,
            'signer_id': signer.id, 'page': 1,
            'pos_x': 0.1, 'pos_y': 0.1, 'width': 0.2, 'height': 0.06})
        doc.action_send()
        return doc, signer

    def test_portal_lists_only_linked_documents(self):
        mine, signer = self._sent_document(
            'Portal Linked Doc', partner_id=self.partner.id, email=self.partner.email)
        # Same email but not linked to the contact: must NOT be listed, since a
        # portal user can change their own email.
        self._sent_document('Portal Email Only Doc', email=self.partner.email)
        draft = self.env['dosign.document'].create({'name': 'Portal Draft Doc'})
        self.env['dosign.signer'].create({
            'document_id': draft.id, 'partner_id': self.partner.id,
            'name': 'Signer', 'email': self.partner.email})

        self.authenticate('portal_signer', 'portal_signer')
        response = self.url_open('/my/dosign')
        self.assertEqual(response.status_code, 200)
        self.assertIn('Portal Linked Doc', response.text)
        self.assertIn(signer._portal_sign_path(), response.text)
        self.assertNotIn('Portal Email Only Doc', response.text)
        self.assertNotIn('Portal Draft Doc', response.text)

        counters = self.make_jsonrpc_request(
            '/my/counters', {'counters': ['dosign_document_count']})
        self.assertEqual(counters['dosign_document_count'], 1)

        response = self.url_open('/my/dosign?filterby=signed')
        self.assertNotIn('Portal Linked Doc', response.text)


@tagged('post_install', '-at_install')
class TestDosignMultiSigner(HttpCase):
    """Several signers on one document, signing through the public routes."""

    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        cls.signature_type = cls.env.ref('dosign.field_type_signature')
        cls.text_type = cls.env.ref('dosign.field_type_text')

    def _document(self, signing_mode, ranks):
        """Sent document with one signer per rank, each with a signature field
        and a text field of its own."""
        doc = self.env['dosign.document'].create({
            'name': 'Multi %s' % signing_mode, 'signing_mode': signing_mode})
        doc.attachment_id = self.env['ir.attachment'].create({
            'name': 's.pdf', 'raw': _PDF, 'mimetype': 'application/pdf',
            'res_model': 'dosign.document', 'res_id': doc.id,
        })
        signers = self.env['dosign.signer']
        for index, rank in enumerate(ranks):
            signer = self.env['dosign.signer'].create({
                'document_id': doc.id, 'name': 'Signer %s' % index,
                'email': 'signer%s@x.test' % index, 'sequence': rank})
            for field_type, pos_x in ((self.signature_type, 0.1), (self.text_type, 0.5)):
                self.env['dosign.item'].create({
                    'document_id': doc.id, 'field_type_id': field_type.id,
                    'signer_id': signer.id, 'page': 1,
                    'pos_x': pos_x, 'pos_y': 0.1 + 0.2 * index,
                    'width': 0.2, 'height': 0.06})
            signers |= signer
        doc.action_send()
        return doc, signers

    def _notified(self, doc):
        return doc.log_ids.filtered(lambda log: log.action == 'sent').signer_id

    def _submit(self, signer):
        values = {str(item.id): 'Value of %s' % signer.name
                  for item in signer.item_ids if item.field_type_id == self.text_type}
        response = self.url_open(
            '/sign/%s/%s/submit' % (signer.document_id.id, signer.sudo().access_token),
            data=json.dumps({'values': values, 'signature': _PNG}),
            headers={'Content-Type': 'application/json'})
        self.env.invalidate_all()
        return response

    def _final_text(self, doc):
        from pypdf import PdfReader
        return PdfReader(io.BytesIO(doc.completed_attachment_id.raw)).pages[0].extract_text()

    def test_parallel_signers(self):
        doc, (first, second, third) = self._document('parallel', [10, 10, 10])
        self.assertEqual(self._notified(doc), first | second | third)

        self.assertEqual(self._submit(second).json(), {
            'success': True, 'completed': False, 'download_url': False})
        self.assertEqual(doc.state, 'partial')
        self.assertEqual(second.state, 'signed')
        # The same signer cannot sign twice.
        self.assertEqual(self._submit(second).status_code, 400)

        self.assertFalse(self._submit(first).json()['completed'])
        result = self._submit(third).json()
        self.assertTrue(result['completed'])
        self.assertEqual(doc.state, 'signed')
        self.assertEqual(doc.signed_count, 3)

        # Every signer's values and signature frame are stamped on the PDF.
        text = self._final_text(doc)
        for signer in first | second | third:
            self.assertIn('Value of %s' % signer.name, text)
            self.assertIn(signer.frame_hash, text)
        # Each signer's link now serves the completed document.
        for signer in first | second | third:
            page = self.url_open('/sign/%s/%s' % (doc.id, signer.sudo().access_token))
            self.assertIn('signed by all parties', page.text)

    def test_sequential_signers(self):
        # Rank 10 first, then the two rank-20 signers in parallel.
        doc, (first, second, third) = self._document('sequential', [10, 20, 20])
        self.assertEqual(self._notified(doc), first)

        # A later signer holding a link (e.g. shared) must wait for its turn.
        page = self.url_open('/sign/%s/%s' % (doc.id, second.sudo().access_token))
        self.assertIn('not your turn', page.text)
        self.assertEqual(second.state, 'pending')
        response = self._submit(second)
        self.assertEqual(response.status_code, 400)
        self.assertEqual(second.state, 'pending')

        self.assertFalse(self._submit(first).json()['completed'])
        self.assertEqual(doc.state, 'partial')
        self.assertEqual(self._notified(doc), first | second | third)

        self.assertFalse(self._submit(third).json()['completed'])
        self.assertTrue(self._submit(second).json()['completed'])
        self.assertEqual(doc.state, 'signed')
        text = self._final_text(doc)
        for signer in first | second | third:
            self.assertIn(signer.frame_hash, text)

    def test_decline_by_one_signer_cancels_for_all(self):
        doc, (first, second) = self._document('parallel', [10, 10])
        self.assertFalse(self._submit(first).json()['completed'])
        response = self.url_open(
            '/sign/%s/%s/decline' % (doc.id, second.sudo().access_token),
            data=json.dumps({'reason': 'Wrong amount'}),
            headers={'Content-Type': 'application/json'})
        self.assertEqual(response.status_code, 200)
        self.env.invalidate_all()
        self.assertEqual(second.state, 'declined')
        self.assertEqual(doc.state, 'cancelled')
        # The signer who already signed cannot sign or reach the form anymore.
        self.assertEqual(self._submit(first).status_code, 404)
