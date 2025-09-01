import base64
import io
from odf.opendocument import OpenDocumentText
from odf.text import P

PDF_TEMPLATE = b"""%PDF-1.4\n1 0 obj\n<< /Type /Catalog /Pages 2 0 R >>\nendobj\n2 0 obj\n<< /Type /Pages /Kids [3 0 R] /Count 1 >>\nendobj\n3 0 obj\n<< /Type /Page /Parent 2 0 R /MediaBox [0 0 200 200] /Contents 4 0 R\n   /Resources << /Font << /F1 5 0 R >> >> >>\nendobj\n4 0 obj\n<< /Length 55 >>\nstream\nBT\n/F1 24 Tf\n72 120 Td\n(Hello world) Tj\nET\nendstream\nendobj\n5 0 obj\n<< /Type /Font /Subtype /Type1 /BaseFont /Helvetica >>\nendobj\nxref\n0 6\n0000000000 65535 f \n0000000010 00000 n \n0000000067 00000 n \n0000000110 00000 n \n0000000218 00000 n \n0000000296 00000 n \ntrailer\n<< /Size 6 /Root 1 0 R >>\nstartxref\n344\n%%EOF\n"""


def pdf_data_url() -> str:
    b64 = base64.b64encode(PDF_TEMPLATE).decode()
    return f"data:application/pdf;base64,{b64}"


def odt_data_url(text: str) -> str:
    doc = OpenDocumentText()
    doc.text.addElement(P(text=text))
    buf = io.BytesIO()
    doc.save(buf)
    b64 = base64.b64encode(buf.getvalue()).decode()
    return f"data:application/vnd.oasis.opendocument.text;base64,{b64}"


if __name__ == "__main__":
    print("PDF link:", pdf_data_url())
    print("ODT link:", odt_data_url("Hello ODT"))
