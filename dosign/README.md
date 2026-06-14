# Dosign — Odoo 19 Electronic Signature Module

Custom Odoo 19 (Community) module for electronic document signing with
visual signatures and PAdES cryptographic sealing. White-label by Nibble Tech LLC.

See the full specification in `../Dosign - Technical Design Document.docx`.

## Status

| Phase | Scope | State |
|-------|-------|-------|
| 1. Foundation | Models, security, sequence, field-type catalog, list/kanban/form views, menus | ✅ Done |
| 2. Editor | OWL client action: PDF.js canvas, palette, signer panel, drag/resize, autosave, upload modal | ✅ Done |
| 3. Send & Portal | Send dialog, mail templates, tokens, public signing portal, signature pad, decline | ✅ Done |
| 4. Finalize & Seal | `pdf_filler` (flatten + audit page), PKCS#12 parsing + Fernet password, pyHanko PAdES seal, completion mail with sealed PDF | ✅ Done |
| 5. Ops & Polish | Crons (expiry / reminders / cert watch), pivot/graph reports, settings, es i18n, tests | ✅ Done |

Sealing degrades gracefully: with no valid certificate the document is still
flattened and hashed (chatter note); with a TSA URL the seal is PAdES-B-T,
otherwise PAdES-B-B.

## Python dependencies

See `requirements.txt`:

```bash
pip install -r requirements.txt
```

`pyhanko` is the heavyweight new dependency. It needs `cryptography>=43`, which in
turn needs a recent `pyOpenSSL` — older pyOpenSSL breaks with cryptography>=42
(`module 'lib' has no attribute 'GEN_EMAIL'`), so upgrade pyOpenSSL too.

For a Docker deployment, bake these into the image so they survive container
re-creation (a plain `pip install` in a running container is lost on `pull`/recreate):

```dockerfile
FROM odoo:19
USER root
RUN pip install --no-cache-dir --break-system-packages \
    pypdf reportlab pyhanko 'cryptography>=43' 'pyOpenSSL>=24'
USER odoo
```

## Server configuration (Phase 4)

Add to `odoo.conf` a stable Fernet key (used to encrypt stored PKCS#12
passwords; keep it out of the database and back it up — losing it makes stored
certificate passwords unrecoverable):

```ini
dosign_fernet_key = <base64 Fernet key>   ; python -c "from cryptography.fernet import Fernet;print(Fernet.generate_key().decode())"
```

## Install

1. Copy/symlink the `dosign/` directory into your Odoo addons path.
2. Restart the Odoo server and update the apps list.
3. Install **Dosign** from the Apps menu (or `-i dosign -d <db>`).

Optional `ir.config_parameter`: `dosign.tsa_url` (RFC 3161 timestamp authority;
when set the seal is PAdES-B-T, otherwise PAdES-B-B).

## Public signing portal & multi-database

The signing portal is reached by external signers through an unauthenticated
tokenized link (`/sign/<id>/<token>`). Odoo must be able to resolve a **single
database** for these sessionless requests, otherwise it returns
`404 — No database is selected`.

- Serve Dosign on a host/instance where `dbfilter` resolves to exactly one
  database (e.g. `dbfilter = ^dosign$`). On a server hosting several databases
  on the same `host:port` (a shared dev box), run a **dedicated Odoo instance**
  for Dosign on its own port with that `dbfilter`.
- Set `web.base.url` (and `web.base.url.freeze = True`) for the Dosign database
  to that instance's public URL so request emails generate working links.
