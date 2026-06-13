{
    'name': 'Dosign',
    'version': '19.0.1.0.0',
    'category': 'Productivity/Sign',
    'summary': 'Electronic document signing with PAdES sealing',
    'description': """
Dosign — Electronic Document Signing for Odoo 19
================================================
Upload PDFs, place signature/data fields visually, and send them by email to
one or more signers who sign through a public tokenized portal (no account
required). On completion the document is flattened and cryptographically sealed
with a company X.509 certificate (PAdES-B-LT).

Phase 1 (Foundation): data model, security, sequences, list/kanban/form views,
field-type catalog and menus.
""",
    'author': 'Nibble Tech LLC',
    'website': 'https://nibbletec.com',
    'license': 'LGPL-3',
    'depends': ['base', 'mail', 'portal', 'web'],
    # Python deps (pypdf, reportlab, pyhanko, pyhanko_certvalidator, cryptography)
    # are declared per-phase when first imported (Phase 4 sealing). Declaring them
    # now would block installation of the Phase 1 foundation, which imports none.
    'data': [
        'security/dosign_security.xml',
        'security/ir.model.access.csv',
        'data/dosign_sequence.xml',
        'data/dosign_field_type_data.xml',
        'data/dosign_tag_data.xml',
        'data/dosign_mail_templates.xml',
        'views/dosign_document_views.xml',
        'views/dosign_template_views.xml',
        'views/dosign_certificate_views.xml',
        'views/dosign_tag_views.xml',
        'views/dosign_portal_templates.xml',
        'views/dosign_menus.xml',
    ],
    'assets': {
        'web.assets_backend': [
            'dosign/static/src/editor/**/*',
            'dosign/static/src/upload/**/*',
            'dosign/static/src/views/**/*',
        ],
        'web.assets_frontend': [
            'dosign/static/src/portal/**/*',
        ],
    },
    'installable': True,
    'application': True,
}
