"""Certificate generation utility."""
import os
import uuid
import io
from datetime import datetime
from pathlib import Path
from django.conf import settings
from reportlab.pdfgen import canvas
from reportlab.lib.pagesizes import A4, landscape
from reportlab.lib.colors import HexColor
from reportlab.pdfbase import pdfmetrics
from reportlab.pdfbase.ttfonts import TTFont
from pypdf import PdfReader, PdfWriter

from admin_panel.models import Student, TestAttempt, Certificate


def generate_certificate(student: Student, test_attempt: TestAttempt) -> tuple[str, str]:
    """
    Generate a certificate PDF for a student based on their test attempt.
    
    Args:
        student: Student model instance
        test_attempt: TestAttempt model instance
        
    Returns:
        tuple: (relative_path_to_certificate, certificate_number)
    """
    # Create certificates directory if it doesn't exist
    cert_dir = Path(settings.MEDIA_ROOT) / 'certificates'
    cert_dir.mkdir(parents=True, exist_ok=True)
    
    # Generate unique certificate number
    certificate_number = f"CERT-{datetime.now().strftime('%Y%m%d')}-{uuid.uuid4().hex[:8].upper()}"
    
    # Template path
    template_path = Path(settings.BASE_DIR) / 'certificate_template.pdf'
    
    if not template_path.exists():
        raise FileNotFoundError(f"Certificate template not found: {template_path}")
    
    # Create overlay PDF with text
    packet = io.BytesIO()
    # A4 landscape dimensions
    width, height = landscape(A4)
    c = canvas.Canvas(packet, pagesize=landscape(A4))
    
    # Font setup - using Helvetica as requested (standard)
    # If Uzbek characters are needed, a custom font registration would be better
    
    # 1. Student Full Name
    # X Range: 200 to 400 (Center -> 300)
    # Y: 490
    c.setFont("Helvetica-Bold", 24)  # Adjusted size to fit well
    student_name = f"{student.first_name} {student.last_name or ''}".strip().upper()
    c.drawCentredString(300, 490, student_name)
    
    # 2. Teacher Full Name
    # X Range: 200 to 400 (Center -> 300)
    # Y: 310
    c.setFont("Helvetica", 18)
    teacher_name = ""
    try:
        # Access reverse OneToOne relation
        if hasattr(student, 'teacher'):
            teacher_name = student.teacher.full_name
    except Exception:
        teacher_name = ""
        
    if teacher_name:
        c.drawCentredString(300, 310, teacher_name)

    # 3. Generated Date
    # X: 450
    # Y: 215
    # Format: Date only (e.g., "02.02.2026")
    c.setFont("Helvetica", 12)
    c.setFillColor(HexColor('#000000'))
    
    date_str = test_attempt.submitted_at.strftime('%d.%m.%Y') if test_attempt.submitted_at else datetime.now().strftime('%d.%m.%Y')
    c.drawString(450, 215, date_str)
    
    # Certificate Number (Optional - keeping it but maybe in a corner or removed if strictly following coordinates?)
    # The instructions didn't specify position for Certificate Number.
    # I'll comment it out to be safe and strictly follow the provided coordinates list, 
    # as extra text might overlap with the new template design.
    # c.drawRightString(width - 50, 50, f"№ {certificate_number}")
    
    c.save()
    packet.seek(0)
    
    # Merge overlay with template
    new_pdf = PdfReader(packet)
    existing_pdf = PdfReader(str(template_path))
    output = PdfWriter()
    
    page = existing_pdf.pages[0]
    page.merge_page(new_pdf.pages[0])
    output.add_page(page)
    
    # Save output
    filename = f"{student.telegram_id}_{test_attempt.id}_{certificate_number}.pdf"
    filepath = cert_dir / filename
    
    with open(filepath, "wb") as f:
        output.write(f)
    
    # Save relative path
    relative_path = f"certificates/{filename}"
    
    return relative_path, certificate_number
