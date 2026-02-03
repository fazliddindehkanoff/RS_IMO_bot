import io
import os
from reportlab.pdfgen import canvas
from reportlab.lib.pagesizes import A4, landscape
from pypdf import PdfReader, PdfWriter, Transformation

def create_grid_pdf(width, height):
    """Create a PDF with a grid and coordinates."""
    packet = io.BytesIO()
    c = canvas.Canvas(packet, pagesize=(width, height))
    
    # Draw grid
    c.setStrokeColorRGB(1, 0, 0)  # Red
    c.setLineWidth(0.5)
    c.setFont("Helvetica", 8)
    
    step = 50
    for x in range(0, int(width), step):
        c.line(x, 0, x, height)
        c.drawString(x + 2, 10, str(x))
        c.drawString(x + 2, height - 10, str(x))
        
    for y in range(0, int(height), step):
        c.line(0, y, width, y)
        c.drawString(10, y + 2, str(y))
        c.drawString(width - 30, y + 2, str(y))

    # Draw finer grid
    c.setStrokeColorRGB(0.5, 0.5, 0.5) # Grey
    c.setLineWidth(0.2)
    step_fine = 10
    for x in range(0, int(width), step_fine):
        if x % 50 != 0:
            c.line(x, 0, x, height)
            
    for y in range(0, int(height), step_fine):
        if y % 50 != 0:
            c.line(0, y, width, y)

    c.save()
    packet.seek(0)
    return packet

def generate_debug_pdf(input_path, output_path):
    """Overlay grid on PDF."""
    if not os.path.exists(input_path):
        print(f"Error: {input_path} not found.")
        return

    # Read existing PDF
    reader = PdfReader(input_path)
    page = reader.pages[0]
    
    # Get page size
    width = float(page.mediabox.width)
    height = float(page.mediabox.height)
    print(f"Page size: {width}x{height}")

    # Create grid PDF
    grid_packet = create_grid_pdf(width, height)
    grid_reader = PdfReader(grid_packet)
    grid_page = grid_reader.pages[0]

    # Merge
    page.merge_page(grid_page)

    # Write output
    writer = PdfWriter()
    writer.add_page(page)
    
    with open(output_path, "wb") as f:
        writer.write(f)
    
    print(f"Debug PDF saved to {output_path}")

if __name__ == "__main__":
    # Assuming run from project root
    INPUT_FILE = "certificate_template.pdf"
    OUTPUT_FILE = "certificate_debug.pdf"
    
    generate_debug_pdf(INPUT_FILE, OUTPUT_FILE)
