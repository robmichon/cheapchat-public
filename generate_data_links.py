import base64
import io

try:
    from reportlab.pdfgen import canvas
except ImportError:
    print("Brak biblioteki 'reportlab'. Zainstaluj ją poleceniem 'pip install reportlab'.")
    raise SystemExit(1)

try:
    from odf.opendocument import OpenDocumentText
    from odf.text import P
except ImportError:
    print("Brak biblioteki 'odfpy'. Zainstaluj ją poleceniem 'pip install odfpy'.")
    raise SystemExit(1)


def pdf_data_url(text: str = "Hello world") -> str:
    """Zwróć minimalny PDF jako URL typu data."""
    buf = io.BytesIO()
    c = canvas.Canvas(buf)
    c.drawString(72, 720, text)
    c.showPage()
    c.save()
    b64 = base64.b64encode(buf.getvalue()).decode()
    return f"data:application/pdf;base64,{b64}"


def odt_data_url(text: str) -> str:
    doc = OpenDocumentText()
    doc.text.addElement(P(text=text))
    buf = io.BytesIO()
    doc.save(buf)
    b64 = base64.b64encode(buf.getvalue()).decode()
    return f"data:application/vnd.oasis.opendocument.text;base64,{b64}"


if __name__ == "__main__":
    print("PDF link:", pdf_data_url("Hello PDF"))
    print("ODT link:", odt_data_url("Hello ODT"))
