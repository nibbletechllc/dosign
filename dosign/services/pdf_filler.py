"""Flatten signer values and signature images onto the original PDF and append
an audit page. Coordinates are normalized 0..1 from the top-left of each page
(zoom-independent), matching how the editor/portal store them."""

import io


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
        if index in by_page:
            pw = float(page.mediabox.width)
            ph = float(page.mediabox.height)
            page.merge_page(_draw_overlay(pw, ph, by_page[index]))
        writer.add_page(page)

    if audit_lines:
        writer.add_page(_audit_page(audit_lines, letter))

    out = io.BytesIO()
    writer.write(out)
    return out.getvalue()
