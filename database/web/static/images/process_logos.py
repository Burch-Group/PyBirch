"""
Script to process the database logos image and create individual icon files.
Extracts each logo and creates theme-compatible SVG versions.
"""
from PIL import Image, ImageDraw
import numpy as np
import os

def extract_logos_from_image(input_path):
    """Extract individual logos from the combined image."""
    img = Image.open(input_path).convert('RGBA')
    width, height = img.size
    
    # The image shows 10 icons arranged in 2 rows of 5
    # Top row: beaker, microscope, machine, chip, warning
    # Bottom row: folder, laser, workflow, molecule, clipboard
    
    icons_per_row = 5
    rows = 2
    icon_width = width // icons_per_row
    icon_height = height // rows
    
    logos = []
    icon_names = [
        'precursors',  # beaker
        'samples',      # microscope
        'equipment',    # machine
        'instruments',  # chip
        'issues',       # warning
        'procedures',   # folder
        'scans',        # laser
        'queues',       # workflow
        'templates',    # molecule
        'projects'      # clipboard
    ]
    
    for row in range(rows):
        for col in range(icons_per_row):
            idx = row * icons_per_row + col
            if idx < len(icon_names):
                # Calculate bounding box with some padding
                left = col * icon_width + 30
                top = row * icon_height + 30
                right = (col + 1) * icon_width - 30
                bottom = (row + 1) * icon_height - 30
                
                # Extract the icon
                icon = img.crop((left, top, right, bottom))
                logos.append((icon_names[idx], icon))
    
    return logos

def create_svg_icon(icon_data, name, output_path, foreground_color='#ffffff'):
    """
    Create an SVG file from the icon data.
    Uses a simple approach: convert to binary (foreground/transparent).
    """
    # Convert to grayscale to detect non-background pixels
    gray = icon_data.convert('L')
    np_gray = np.array(gray)
    
    # Threshold to detect icon pixels (non-background)
    threshold = 50  # Adjust if needed
    mask = np_gray > threshold
    
    # Get dimensions
    height, width = mask.shape
    
    # Create SVG with transparent background
    svg_parts = [
        f'<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 {width} {height}" width="24" height="24">',
        f'<style>.icon-path {{ fill: {foreground_color}; }}</style>'
    ]
    
    # For simplicity, convert pixels to tiny rectangles (can be optimized with path tracing)
    # Group consecutive horizontal pixels into rectangles for efficiency
    for y in range(height):
        x = 0
        while x < width:
            if mask[y, x]:
                # Find the run length
                run_start = x
                while x < width and mask[y, x]:
                    x += 1
                run_width = x - run_start
                svg_parts.append(f'<rect class="icon-path" x="{run_start}" y="{y}" width="{run_width}" height="1"/>')
            else:
                x += 1
    
    svg_parts.append('</svg>')
    
    with open(output_path, 'w') as f:
        f.write('\n'.join(svg_parts))

def create_simple_svg_icons(logos, output_dir):
    """
    Create simplified SVG icons that can adapt to themes.
    Each SVG uses CSS classes that can be styled by the theme.
    """
    os.makedirs(output_dir, exist_ok=True)
    
    for name, icon_data in logos:
        output_path = os.path.join(output_dir, f'{name}.svg')
        create_svg_icon(icon_data, name, output_path, foreground_color='currentColor')
        print(f'Created: {output_path}')

def main():
    script_dir = os.path.dirname(os.path.abspath(__file__))
    
    # Input image path (you'll need to save the provided image here)
    input_image = os.path.join(script_dir, 'logos_source.png')
    
    if not os.path.exists(input_image):
        print(f"Please save the logos image as: {input_image}")
        return
    
    # Extract logos
    print("Extracting logos from image...")
    logos = extract_logos_from_image(input_image)
    
    # Create SVG icons
    print("Creating SVG icons...")
    create_simple_svg_icons(logos, script_dir)
    
    print("\nDone! Created theme-compatible SVG icons.")

if __name__ == '__main__':
    main()
