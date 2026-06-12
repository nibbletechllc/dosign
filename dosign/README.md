# Dosign — Odoo 19 Electronic Signature Module

Custom Odoo 19 (Community) module for electronic document signing with
visual signatures and PAdES cryptographic sealing. White-label by Nibble Tech LLC.

See the full specification in `../Dosign - Technical Design Document.docx`.

## Status — Phase 1 (Foundation) ✅

| Layer | Delivered |
|-------|-----------|
| Models | `dosign.document` (state machine + chatter), `dosign.signer`, `dosign.item` (+ `dosign.item.option`), `dosign.field.type`, `dosign.template` (+ `dosign.role`), `dosign.certificate`, `dosign.log` (append-only), `dosign.tag` |
| Security | `Dosign / User` + `Dosign / Manager` groups, record rules (own-documents + multi-company), `ir.model.access.csv`, certificate access restricted to managers |
| Data | `DSN/%(year)s/` sequence, 12-entry field-type catalog, default tags |
| Views | Documents list (home) / kanban (status board) / form / search; templates, certificates, tags; menus |
| Assets | App icon |

### Deferred to later phases
- **Phase 2** — OWL editor client action (PDF.js canvas, palette, signer panel, drag/resize, autosave) and upload modal.
- **Phase 3** — Send dialog, mail templates, tokens delivery, public signing portal, signature dialog (`action_sign_now`, `_process_signature`).
- **Phase 4** — `pdf_filler`, audit page, full PKCS#12 parsing + Fernet password encryption, pyHanko PAdES sealing, completion mails (`_finalize`).
- **Phase 5** — Crons (expiry / reminders / cert watch), reports, settings, i18n, tests.

Stubs raising `NotImplementedError` / `UserError` mark the deferred entry points.

## Python dependencies

```bash
pip install pypdf reportlab pyhanko pyhanko-certvalidator cryptography
```

`cryptography` ships with Odoo; `pyhanko` is the only new heavyweight dependency.

## Install

1. Copy/symlink the `dosign/` directory into your Odoo addons path.
2. Restart the Odoo server and update the apps list.
3. Install **Dosign** from the Apps menu (or `-i dosign -d <db>`).

## Server configuration (needed from Phase 4)

Add to `odoo.conf`:

```ini
dosign_fernet_key = <base64 Fernet key>   ; encrypts stored PKCS#12 passwords
```

`ir.config_parameter` keys used later: `dosign.tsa_url` (default `https://freetsa.org/tsr`),
reminder cadence and default expiry.
