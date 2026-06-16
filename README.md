# Dosign

Electronic document signing for **Odoo 19** (Community) — upload a PDF, place
signature and data fields, send it to signers who sign through a public
tokenized portal (no account needed), and get back a flattened, **PAdES-sealed**
PDF with a full audit trail. White-label by **Nibble Tech LLC**.

> The Odoo addon lives in [`dosign/`](dosign/). See [`dosign/README.md`](dosign/README.md)
> for module details, and `Dosign - Technical Design Document.docx` for the full spec.

## Features

- **Editor (OWL + PDF.js):** drag signature/data fields onto the PDF, per-signer
  colors, autosave, upload modal.
- **Public signing portal:** tokenized `/sign/<id>/<token>` link, draw/type
  signature pad, decline; mobile-friendly.
- **Send flow:** parallel or sequential signing, request/reminder/completion
  emails, expiry.
- **Cryptographic seal:** company PKCS#12 certificate, Fernet-encrypted password,
  PAdES (B-B / B-T with a TSA) via pyHanko; appended audit page with hashes.
- **Templates:** save any document as a reusable template, role→signer mapping,
  Sign-style template list.
- **Ops:** daily crons (expiry, reminders, certificate watch), pivot/graph
  reports, settings, Spanish translation, test suite.

## Quick start

```bash
# 1. Python deps (see dosign/requirements.txt)
pip install -r dosign/requirements.txt

# 2. Put dosign/ on your Odoo addons path, then install
odoo -d <db> -i dosign

# 3. Configure a Fernet key in odoo.conf (encrypts stored certificate passwords)
#    python -c "from cryptography.fernet import Fernet;print(Fernet.generate_key().decode())"
#    dosign_fernet_key = <key>
```

The signing portal needs Odoo to resolve a **single database** for the
unauthenticated links — serve Dosign where `dbfilter` matches one DB (see
[`dosign/README.md`](dosign/README.md#public-signing-portal--multi-database)).

## Tests

```bash
odoo -d <db> -i dosign --test-enable --test-tags /dosign --stop-after-init
```

## License

LGPL-3 (module) — see [LICENSE](LICENSE).
