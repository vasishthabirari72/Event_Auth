import json
from importlib.resources import files
from io import BytesIO

from reportlab.graphics import renderPDF
from reportlab.graphics.barcode.qr import QrCodeWidget
from reportlab.graphics.shapes import Drawing
from reportlab.pdfgen.canvas import Canvas

from event_auth.core.documents import CouponDocument


class PdfOutput:
    def __init__(self) -> None:
        self.labels = json.loads((files("event_auth.adapters") / "pdf_labels.json").read_text())

    def render(self, document: CouponDocument) -> bytes:
        output = BytesIO()
        page = Canvas(output, pagesize=(360, 580), invariant=1)
        page.setTitle(self.labels["title"])
        y = 550
        for text, size in [
            (document.organization, 14),
            (document.event, 14),
            (document.slot, 12),
            (document.option, 24),
            (document.member_name, 12),
            (self.labels["member"] + document.member_code, 11),
            (self.labels["coupon"] + document.coupon_code, 11),
            (document.issued_at, 10),
        ]:
            font_size = float(size)
            while page.stringWidth(text, "Helvetica", font_size) > 324 and font_size > 5:
                font_size -= 0.5
            page.setFont("Helvetica", font_size)
            page.drawCentredString(180, y, text)
            y -= 28
        qr = QrCodeWidget(document.qr, barLevel="M")
        x0, y0, x1, y1 = qr.getBounds()
        drawing = Drawing(280, 280, transform=[280 / (x1 - x0), 0, 0, 280 / (y1 - y0), 0, 0])
        drawing.add(qr)
        renderPDF.draw(drawing, page, 40, 40)
        page.setFont("Helvetica", 11)
        page.drawCentredString(180, 20, self.labels["footer"])
        page.showPage()
        page.save()
        return output.getvalue()
