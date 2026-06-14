"""Apply a PAdES cryptographic seal to the completed PDF using the company
PKCS#12 certificate (pyHanko). Falls back gracefully: with a TSA URL the seal is
PAdES-B-T, otherwise PAdES-B-B. Embedding full validation info (B-LT) needs a
trust/validation context and is left configurable for production."""

import io
import tempfile
import os


def seal(pdf_bytes, p12_bytes, passphrase, reason="Dosign completion seal",
         tsa_url=None):
    from pyhanko.sign import signers, fields
    from pyhanko.pdf_utils.incremental_writer import IncrementalPdfFileWriter

    # pyHanko loads PKCS#12 from a file path; use a short-lived temp file.
    tmp = tempfile.NamedTemporaryFile(suffix=".p12", delete=False)
    try:
        tmp.write(p12_bytes)
        tmp.close()
        signer = signers.SimpleSigner.load_pkcs12(
            pfx_file=tmp.name,
            passphrase=passphrase.encode() if passphrase else None,
        )
    finally:
        os.unlink(tmp.name)

    if signer is None:
        raise ValueError("Could not load the PKCS#12 certificate (bad password?).")

    timestamper = None
    if tsa_url:
        from pyhanko.sign.timestamps import HTTPTimeStamper
        timestamper = HTTPTimeStamper(tsa_url)

    meta = signers.PdfSignatureMetadata(
        field_name="DosignSeal",
        subfilter=fields.SigSeedSubFilter.PADES,
        reason=reason,
        md_algorithm="sha256",
    )
    writer = IncrementalPdfFileWriter(io.BytesIO(pdf_bytes))
    out = io.BytesIO()
    signers.sign_pdf(writer, meta, signer=signer, timestamper=timestamper, output=out)
    return out.getvalue()
