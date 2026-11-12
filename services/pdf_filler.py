"""Flatten signer values and signature images onto the original PDF and append
an audit page. Coordinates are normalized 0..1 from the top-left of each page
(zoom-independent), matching how the editor/portal store them."""

import io


FRAME_CAPTION = "Signed with Dosign"
FRAME_COLOR = (0.373, 0.659, 0.651)  # #5fa8a6, same as the on-screen frame


def _draw_signature_frame(c, x, y, w, h, frame_hash):
    """Stamp the signature frame around the image box (x, y, w, h): a rounded
    bracket on the left, a caption on the top edge and the signature id on the
    bottom edge. Mirrors static/src/common/signature_frame.scss."""
    pad = 2.5
    left, bottom, top = x - pad, y - pad, y + h + pad
    arm = w * 0.18
    radius = min(6.0, (top - bottom) / 2, arm)
    font_size = max(4.0, min(7.0, h * 0.16))
    text_x = left + arm + 2

    c.saveState()
    c.setStrokeColorRGB(*FRAME_COLOR)
    c.setFillColorRGB(*FRAME_COLOR)
    c.setLineWidth(0.8)
    path = c.beginPath()
    path.moveTo(left + arm, top)
    path.lineTo(left + radius, top)
    path.arcTo(left, top - 2 * radius, left + 2 * radius, top, 90, 90)
    path.lineTo(left, bottom + radius)
    path.arcTo(left, bottom, left + 2 * radius, bottom + 2 * radius, 180, 90)
    path.lineTo(left + arm, bottom)
    c.drawPath(path, stroke=1, fill=0)
    c.setFont("Helvetica", font_size)
    c.drawString(text_x, top - font_size * 0.35, FRAME_CAPTION)
    if frame_hash:
        c.setFont("Courier", font_size)
        c.drawString(text_x, bottom - font_size * 0.35, "%s..." % frame_hash)
    c.restoreState()


def _draw_overlay(width, height, items):
    from reportlab.pdfgen import canvas
    from reportlab.lib.utils import ImageReader
    from pypdf import PdfReader

    buf = io.BytesIO()
    c = canvas.Canvas(buf, pagesize=(width, height))
    for item in items:
        x = item["pos_x"] * width
        field_w = item["width"] * width
        field_h = item["height"] * height
        y_bottom = height - (item["pos_y"] + item["height"]) * height
        image_bytes = item.get("image_bytes")
        if image_bytes:
            reader = ImageReader(io.BytesIO(image_bytes))
            iw, ih = reader.getSize()
            draw_w = field_w
            draw_h = (draw_w * ih / iw) if iw else field_h
            # Let the signature fill the field width and grow upward on a thin
            # line, but cap the overflow so it stays reasonable.
            max_h = field_h * 4
            if draw_h > max_h:
                draw_h = max_h
                draw_w = (draw_h * iw / ih) if ih else field_w
            c.drawImage(reader, x, y_bottom, width=draw_w, height=draw_h,
                        mask="auto", preserveAspectRatio=True, anchor="sw")
            if item.get("frame_hash") is not None:
                _draw_signature_frame(c, x, y_bottom, draw_w, draw_h, item["frame_hash"])
        elif item.get("value_text"):
            font_size = max(6, field_h * 0.6)
            c.setFont("Helvetica", font_size)
            c.setFillColorRGB(0.1, 0.1, 0.1)
            baseline = y_bottom + (field_h - font_size) / 2 + font_size * 0.15
            c.drawString(x + 2, baseline, item["value_text"])
    c.showPage()
    c.save()
    buf.seek(0)
    return PdfReader(buf).pages[0]


def _audit_page(lines, page_size):
    from reportlab.pdfgen import canvas

    buf = io.BytesIO()
    c = canvas.Canvas(buf, pagesize=page_size)
    width, height = page_size
    y = height - 72
    c.setFont("Helvetica-Bold", 16)
    c.drawString(60, y, "Signature Audit Trail")
    y -= 28
    c.setFont("Helvetica", 9)
    for line in lines:
        if y < 60:
            c.showPage()
            y = height - 72
            c.setFont("Helvetica", 9)
        c.drawString(60, y, line[:120])
        y -= 14
    c.showPage()
    c.save()
    buf.seek(0)
    from pypdf import PdfReader
    return PdfReader(buf).pages[0]


def build_completed_pdf(original_bytes, items, audit_lines=None):
    """Return the flattened PDF (values + signatures stamped) with an appended
    audit page, as raw bytes."""
    from pypdf import PdfReader, PdfWriter
    from reportlab.lib.pagesizes import letter

    reader = PdfReader(io.BytesIO(original_bytes))
    writer = PdfWriter()
    by_page = {}
    for item in items:
        by_page.setdefault(item["page"], []).append(item)

    for index, page in enumerate(reader.pages, start=1):
        # Attach the page to the writer before merging: pypdf 7 no longer
        # allows modifying the contents of a page that belongs to a reader.
        page = writer.add_page(page)
        if index in by_page:
            pw = float(page.mediabox.width)
            ph = float(page.mediabox.height)
            page.merge_page(_draw_overlay(pw, ph, by_page[index]))

    if audit_lines:
        writer.add_page(_audit_page(audit_lines, letter))

    out = io.BytesIO()
    writer.write(out)
    return out.getvalue()
