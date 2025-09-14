# lib/pdf_utils.py
import PyPDF2 as pdf

def extract_pdf_text_from_file(path: str) -> str:
    """Extract text from a PDF file given its path."""
    with open(path, 'rb') as f:
        reader = pdf.PdfReader(f)
        text = []
        for page in reader.pages:
            t = page.extract_text() or ''
            text.append(t)
        return "\n".join(text).strip()

def extract_pdf_text_from_upload(uploaded_file) -> str:
    """Extract text from a PDF file uploaded via Streamlit file uploader."""
    reader = pdf.PdfReader(uploaded_file)
    text = []
    for page in reader.pages:
        t = page.extract_text() or ''
        text.append(t)
    return "\n".join(text).strip()
