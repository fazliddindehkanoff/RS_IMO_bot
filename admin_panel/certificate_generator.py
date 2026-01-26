"""Certificate generation utility."""
import os
import uuid
from datetime import datetime
from pathlib import Path
from django.conf import settings
from PIL import Image, ImageDraw, ImageFont
from admin_panel.models import Student, TestAttempt, Certificate


def generate_certificate(student: Student, test_attempt: TestAttempt) -> str:
    """
    Generate a certificate image for a student based on their test attempt.
    
    Args:
        student: Student model instance
        test_attempt: TestAttempt model instance
        
    Returns:
        Path to the generated certificate image file (relative to MEDIA_ROOT)
    """
    # Create certificates directory if it doesn't exist
    cert_dir = Path(settings.MEDIA_ROOT) / 'certificates'
    cert_dir.mkdir(parents=True, exist_ok=True)
    
    # Generate unique certificate number
    certificate_number = f"CERT-{datetime.now().strftime('%Y%m%d')}-{uuid.uuid4().hex[:8].upper()}"
    
    # Certificate dimensions (A4 size in pixels at 300 DPI)
    width, height = 2480, 3508  # A4 at 300 DPI
    
    # Create image with white background
    img = Image.new('RGB', (width, height), color='white')
    draw = ImageDraw.Draw(img)
    
    # Try to load fonts (fallback to default if not available)
    try:
        # Try common font paths
        import platform
        system = platform.system()
        
        if system == "Windows":
            font_paths = [
                "C:/Windows/Fonts/arial.ttf",
                "C:/Windows/Fonts/calibri.ttf",
            ]
        elif system == "Darwin":  # macOS
            font_paths = [
                "/System/Library/Fonts/Helvetica.ttc",
                "/Library/Fonts/Arial.ttf",
            ]
        else:  # Linux
            font_paths = [
                "/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf",
                "/usr/share/fonts/truetype/liberation/LiberationSans-Regular.ttf",
            ]
        
        font_found = False
        for font_path in font_paths:
            try:
                title_font = ImageFont.truetype(font_path, 80)
                name_font = ImageFont.truetype(font_path, 100)
                text_font = ImageFont.truetype(font_path, 50)
                small_font = ImageFont.truetype(font_path, 40)
                font_found = True
                break
            except:
                continue
        
        if not font_found:
            raise Exception("No font found")
    except:
        # Fallback to default font
        default_font = ImageFont.load_default()
        title_font = default_font
        name_font = default_font
        text_font = default_font
        small_font = default_font
    
    # Draw border
    border_width = 20
    draw.rectangle(
        [(border_width, border_width), (width - border_width, height - border_width)],
        outline='#1a237e',
        width=border_width
    )
    
    # Draw decorative border
    inner_border = 60
    draw.rectangle(
        [(inner_border, inner_border), (width - inner_border, height - inner_border)],
        outline='#3f51b5',
        width=5
    )
    
    # Helper function to get text width
    def get_text_width(text, font):
        """Get text width, with fallback for older PIL versions."""
        try:
            bbox = draw.textbbox((0, 0), text, font=font)
            return bbox[2] - bbox[0]
        except AttributeError:
            # Fallback for older PIL versions
            try:
                return draw.textsize(text, font=font)[0]
            except:
                # Ultimate fallback - estimate
                return len(text) * 20
    
    # Title
    title = "SERTIFIKAT"
    title_width = get_text_width(title, title_font)
    title_x = (width - title_width) // 2
    title_y = 300
    draw.text((title_x, title_y), title, fill='#1a237e', font=title_font)
    
    # Subtitle
    subtitle = "Test topshirish bo'yicha"
    subtitle_width = get_text_width(subtitle, text_font)
    subtitle_x = (width - subtitle_width) // 2
    subtitle_y = title_y + 120
    draw.text((subtitle_x, subtitle_y), subtitle, fill='#424242', font=text_font)
    
    # Student name
    student_name = f"{student.first_name} {student.last_name or ''}".strip()
    name_width = get_text_width(student_name, name_font)
    name_x = (width - name_width) // 2
    name_y = height // 2 - 200
    draw.text((name_x, name_y), student_name, fill='#1a237e', font=name_font)
    
    # Test information
    test_title = test_attempt.test.title
    score_text = f"Ball: {test_attempt.score:.1f}%" if test_attempt.score else "Ball: N/A"
    
    info_y = name_y + 200
    info_text = f"Test: {test_title}\n{score_text}"
    
    # Draw info text line by line
    info_lines = info_text.split('\n')
    for i, line in enumerate(info_lines):
        line_width = get_text_width(line, text_font)
        line_x = (width - line_width) // 2
        line_y = info_y + (i * 80)
        draw.text((line_x, line_y), line, fill='#424242', font=text_font)
    
    # Date
    date_text = f"Sana: {test_attempt.submitted_at.strftime('%d.%m.%Y') if test_attempt.submitted_at else datetime.now().strftime('%d.%m.%Y')}"
    date_width = get_text_width(date_text, small_font)
    date_x = (width - date_width) // 2
    date_y = height - 400
    draw.text((date_x, date_y), date_text, fill='#757575', font=small_font)
    
    # Certificate number
    cert_num_text = f"Sertifikat raqami: {certificate_number}"
    cert_num_width = get_text_width(cert_num_text, small_font)
    cert_num_x = (width - cert_num_width) // 2
    cert_num_y = date_y + 60
    draw.text((cert_num_x, cert_num_y), cert_num_text, fill='#757575', font=small_font)
    
    # Save image
    filename = f"{student.telegram_id}_{test_attempt.id}_{certificate_number}.jpg"
    filepath = cert_dir / filename
    img.save(filepath, 'JPEG', quality=95)
    
    # Save relative path
    relative_path = f"certificates/{filename}"
    
    # Create Certificate record
    # Note: We need to use Exam model, but TestAttempt uses Test model
    # For now, we'll create a certificate without exam (or we can create a dummy exam)
    # Actually, looking at the Certificate model, it requires an Exam, not a Test
    # We need to handle this - either create a mapping or modify the approach
    
    # Since Certificate model expects Exam but we have Test, we'll skip creating the Certificate record here
    # and let the admin action handle it, or we can modify the model later
    # For now, just return the image path
    
    return relative_path, certificate_number
