import cv2
import numpy as np
import matplotlib.pyplot as plt
import pytesseract
import tkinter as tk
from tkinter import ttk, filedialog, messagebox
from matplotlib.backends.backend_tkagg import FigureCanvasTkAgg
from matplotlib.figure import Figure
import threading
import os
import re
import platform
import subprocess
from skimage import measure
from scipy import ndimage


class LetsGoDigitalOCR:
    """OCR using pytesseract with letsgodigital language for 7-segment displays."""
    
    def __init__(self):
        """Initialize the OCR reader."""
        print("Initializing LetsGoDigital OCR for 7-segment displays...")
        self.check_letsgodigital_installed()
    
    def check_letsgodigital_installed(self):
        """Check if letsgodigital.traineddata is installed."""
        try:
            # Try a simple test to see if the language is available
            test_img = np.ones((50, 100), dtype=np.uint8) * 255
            pytesseract.image_to_string(test_img, lang='letsgodigital', config='--psm 7')
            print("✓ letsgodigital language data found!")
        except Exception as e:
            print("⚠ Warning: letsgodigital language not found!")
            print("\nTo install letsgodigital.traineddata:")
            print("1. Download from: https://github.com/Shreeshrii/tessdata_shreetest/raw/master/letsgodigital.traineddata")
            print("2. Copy to Tesseract tessdata folder:")
            print("   - Windows: C:\\Program Files\\Tesseract-OCR\\tessdata\\")
            print("   - Linux: /usr/share/tesseract-ocr/4.00/tessdata/")
            print("   - macOS: /usr/local/share/tessdata/")
            print("\nFalling back to standard OCR configuration...\n")
    
    def get_ocr_config(self):
        """Get OCR configuration optimized for 7-segment displays."""
        # PSM 7: Treat the image as a single text line
        # PSM 8: Treat the image as a single word
        # Use letsgodigital language specifically trained for 7-segment displays
        config = '--psm 7 -l letsgodigital -c tessedit_char_whitelist=0123456789.-'
        return config
    
    def preprocess_for_ocr(self, image):
        """Preprocess image for OCR."""
        # Convert to grayscale if needed
        if len(image.shape) == 3:
            gray = cv2.cvtColor(image, cv2.COLOR_RGB2GRAY)
        else:
            gray = image.copy()
        
        return gray
    
    def read_display(self, image):
        """Read the display using pytesseract with letsgodigital."""
        try:
            # Preprocess
            processed = self.preprocess_for_ocr(image)
            
            # Use pytesseract with letsgodigital language
            text = pytesseract.image_to_string(processed, config=self.get_ocr_config())
            
            # Extract number from text
            text = text.strip()
            
            # Clean up common OCR errors
            text = text.replace('O', '0').replace('o', '0')
            text = text.replace('I', '1').replace('l', '1').replace('|', '1')
            text = text.replace('S', '5').replace('s', '5')
            
            # Extract decimal number
            match = re.search(r'-?\d+\.?\d*', text)
            if match:
                try:
                    number = float(match.group())
                    return number
                except ValueError:
                    return None
            
            return None
            
        except Exception as e:
            print(f"Error in OCR recognition: {e}")
            return None


def setup_tesseract():
    """
    Automatically detect and configure Tesseract OCR path for Windows.
    """
    if platform.system() == "Windows":
        # Common Tesseract installation paths on Windows
        possible_paths = [
            r"C:\Program Files\Tesseract-OCR\tesseract.exe",
            r"C:\Program Files (x86)\Tesseract-OCR\tesseract.exe",
            r"C:\Users\{}\AppData\Local\Tesseract-OCR\tesseract.exe".format(os.getenv('USERNAME')),
            r"C:\Tools\tesseract\tesseract.exe"
        ]
        
        for path in possible_paths:
            if os.path.exists(path):
                pytesseract.pytesseract.tesseract_cmd = path
                print(f"Found Tesseract at: {path}")
                return True
                
        # If not found, show installation instructions
        error_msg = r"""
TESSERACT OCR NOT FOUND!

To use this tool, you need to install Tesseract OCR:

1. Download Tesseract for Windows from:
   https://github.com/UB-Mannheim/tesseract/wiki

2. Install it to the default location (C:\Program Files\Tesseract-OCR\)

3. Alternatively, you can:
   - Add Tesseract to your system PATH, OR
   - Set the path manually in the code:
     pytesseract.pytesseract.tesseract_cmd = r'C:\path\to\tesseract.exe'

4. Restart this script after installation.
"""
        print(error_msg)
        messagebox.showerror("Tesseract Not Found", error_msg)
        return False
    
    else:
        # For Linux/Mac, assume it's in PATH or user has configured it
        try:
            subprocess.run(['tesseract', '--version'], capture_output=True, check=True)
            print("Tesseract found in system PATH")
            return True
        except (subprocess.CalledProcessError, FileNotFoundError):
            error_msg = """
TESSERACT OCR NOT FOUND!

Please install Tesseract OCR:

Linux: sudo apt-get install tesseract-ocr
macOS: brew install tesseract

Then restart this script.
"""
            print(error_msg)
            messagebox.showerror("Tesseract Not Found", error_msg)
            return False


class VideoNumberExtractor:
    def __init__(self):
        self.video_path = None
        self.first_frame = None
        self.roi = None  # (x1, y1, x2, y2)
        self.denoise_value = 5
        self.threshold_value = 127
        self.frame_results = []
        self.roi_points = []  # Initialize roi_points list
        self.segment_reader = LetsGoDigitalOCR()  # Initialize OCR with letsgodigital language
        
        # GUI components
        self.root = None
        self.canvas = None
        self.fig = None
        self.ax = None
        self.denoise_scale = None
        self.threshold_scale = None
        
    def load_video(self, video_path):
        """Load video and extract first frame for ROI selection."""
        self.video_path = video_path
        cap = cv2.VideoCapture(video_path)
        
        if not cap.isOpened():
            raise ValueError(f"Could not open video file: {video_path}")
        
        ret, frame = cap.read()
        cap.release()
        
        if not ret:
            raise ValueError("Could not read first frame from video")
        
        self.first_frame = cv2.cvtColor(frame, cv2.COLOR_BGR2RGB)
        print(f"Video loaded successfully. First frame shape: {self.first_frame.shape}")
        
    def setup_roi_selection_gui(self):
        """Create GUI for ROI selection with real-time threshold preview."""
        self.root = tk.Tk()
        self.root.title("Video Number Extractor - ROI Selection")
        self.root.state('zoomed')  # Maximize window on Windows
        
        # Create main frame
        main_frame = ttk.Frame(self.root)
        main_frame.pack(fill=tk.BOTH, expand=True, padx=10, pady=10)
        
        # Instructions
        instructions = ttk.Label(main_frame, 
                                text="1. Click to select TOP-LEFT corner of text box\n2. Click to select BOTTOM-RIGHT corner of text box\n3. Adjust denoise and threshold values\n4. Click 'Done' when satisfied",
                                font=('Arial', 12))
        instructions.pack(pady=(0, 10))
        
        # Create matplotlib figure
        self.fig = Figure(figsize=(12, 8))
        self.ax = self.fig.add_subplot(111)
        
        # Create canvas and add to tkinter
        self.canvas = FigureCanvasTkAgg(self.fig, main_frame)
        self.canvas.get_tk_widget().pack(fill=tk.BOTH, expand=True)
        
        # Control panel
        control_frame = ttk.Frame(main_frame)
        control_frame.pack(fill=tk.X, pady=(10, 0))
        
        # Denoise slider
        denoise_frame = ttk.Frame(control_frame)
        denoise_frame.pack(side=tk.LEFT, fill=tk.X, expand=True, padx=(0, 10))
        ttk.Label(denoise_frame, text="Denoise (blur kernel size):").pack(anchor=tk.W)
        self.denoise_scale = ttk.Scale(denoise_frame, from_=1, to=21, orient=tk.HORIZONTAL, 
                                      command=self.update_preview)
        self.denoise_scale.set(self.denoise_value)
        self.denoise_scale.pack(fill=tk.X)
        
        # Threshold slider
        threshold_frame = ttk.Frame(control_frame)
        threshold_frame.pack(side=tk.LEFT, fill=tk.X, expand=True, padx=(10, 0))
        ttk.Label(threshold_frame, text="Threshold value:").pack(anchor=tk.W)
        self.threshold_scale = ttk.Scale(threshold_frame, from_=0, to=255, orient=tk.HORIZONTAL,
                                        command=self.update_preview)
        self.threshold_scale.set(self.threshold_value)
        self.threshold_scale.pack(fill=tk.X)
        
        # Buttons
        button_frame = ttk.Frame(main_frame)
        button_frame.pack(pady=(10, 0))
        
        ttk.Button(button_frame, text="Reset ROI", command=self.reset_roi).pack(side=tk.LEFT, padx=(0, 10))
        ttk.Button(button_frame, text="Done", command=self.finish_roi_selection).pack(side=tk.LEFT)
        
        # Display initial frame
        self.display_frame()
        
        # Connect mouse click event
        self.canvas.mpl_connect('button_press_event', self.on_mouse_click)
        
    def display_frame(self):
        """Display the first frame in the matplotlib canvas."""
        # Clear the current axis only (not the whole figure for initial display)
        self.ax.clear()
        self.ax.imshow(self.first_frame)
        self.ax.set_title("Select Text Box Region - Click top-left, then bottom-right")
        self.ax.axis('off')
        
        # If we have ROI points, draw them
        if len(self.roi_points) == 1:
            # Draw first point
            self.ax.plot(self.roi_points[0][0], self.roi_points[0][1], 'ro', markersize=8)
            self.ax.text(self.roi_points[0][0], self.roi_points[0][1] - 10, 'Top-Left', 
                        color='red', fontweight='bold')
        elif len(self.roi_points) == 2:
            # Draw rectangle
            x1, y1 = self.roi_points[0]
            x2, y2 = self.roi_points[1]
            
            # Ensure proper ordering
            x1, x2 = min(x1, x2), max(x1, x2)
            y1, y2 = min(y1, y2), max(y1, y2)
            
            rect_width = x2 - x1
            rect_height = y2 - y1
            
            rect = plt.Rectangle((x1, y1), rect_width, rect_height, 
                               linewidth=2, edgecolor='red', facecolor='none')
            self.ax.add_patch(rect)
            
            self.ax.plot(x1, y1, 'ro', markersize=8)
            self.ax.plot(x2, y2, 'bo', markersize=8)
            
            # Update ROI
            self.roi = (int(x1), int(y1), int(x2), int(y2))
            
            # Update preview if we have a complete ROI
            self.update_preview()
            return
        
        # Use draw_idle for better performance
        self.canvas.draw_idle()
    
    def on_mouse_click(self, event):
        """Handle mouse clicks for ROI selection."""
        if event.inaxes != self.ax:
            return
            
        if len(self.roi_points) < 2:
            self.roi_points.append((event.xdata, event.ydata))
            self.display_frame()
            
            if len(self.roi_points) == 2:
                print(f"ROI selected: {self.roi}")
    
    def update_preview(self, *args):
        """Update the threshold preview in real-time."""
        if self.roi is None or len(self.roi_points) < 2:
            return
            
        try:
            # Get current slider values
            denoise = int(self.denoise_scale.get())
            threshold = int(self.threshold_scale.get())
            
            # Make denoise odd if even
            if denoise % 2 == 0:
                denoise += 1
                
            self.denoise_value = denoise
            self.threshold_value = threshold
            
            # Extract ROI from first frame
            x1, y1, x2, y2 = self.roi
            roi_image = self.first_frame[y1:y2, x1:x2]
            
            # Apply preprocessing
            processed = self.preprocess_roi(roi_image, denoise, threshold)
            
            # COMPLETELY clear the figure to prevent stacking
            self.fig.clear()
            
            # Create subplot layout with proper clearing
            gs = self.fig.add_gridspec(2, 2, height_ratios=[3, 1], hspace=0.3, wspace=0.2)
            
            # Main image
            ax_main = self.fig.add_subplot(gs[0, :])
            ax_main.imshow(self.first_frame)
            ax_main.set_title("Full Frame with Selected ROI", fontsize=12)
            ax_main.axis('off')
            
            # Draw ROI rectangle
            rect_width = x2 - x1
            rect_height = y2 - y1
            rect = plt.Rectangle((x1, y1), rect_width, rect_height,
                               linewidth=2, edgecolor='red', facecolor='none')
            ax_main.add_patch(rect)
            
            # Original ROI
            ax_orig = self.fig.add_subplot(gs[1, 0])
            ax_orig.imshow(roi_image)
            ax_orig.set_title("Original ROI", fontsize=10)
            ax_orig.axis('off')
            
            # Processed ROI
            ax_proc = self.fig.add_subplot(gs[1, 1])
            ax_proc.imshow(processed, cmap='gray')
            ax_proc.set_title(f"Processed (D:{denoise}, T:{threshold})", fontsize=10)
            ax_proc.axis('off')
            
            # Try segment recognition on processed image
            try:
                # Use letsgodigital OCR for 7-segment display recognition
                detected_number = self.segment_reader.read_display(processed)
                
                if detected_number is not None:
                    ax_proc.text(0.5, -0.15, f"Detected: {detected_number:.3f}", 
                               transform=ax_proc.transAxes, ha='center', va='top',
                               fontsize=9, 
                               bbox=dict(boxstyle="round,pad=0.3", facecolor="yellow", alpha=0.8))
                else:
                    ax_proc.text(0.5, -0.15, "No number detected", 
                               transform=ax_proc.transAxes, ha='center', va='top',
                               fontsize=9,
                               bbox=dict(boxstyle="round,pad=0.3", facecolor="orange", alpha=0.8))
            except Exception as e:
                ax_proc.text(0.5, -0.15, f"Recognition Error: {str(e)[:20]}", 
                           transform=ax_proc.transAxes, ha='center', va='top',
                           fontsize=9,
                           bbox=dict(boxstyle="round,pad=0.3", facecolor="red", alpha=0.8))
                
            # Update the canvas efficiently
            self.canvas.draw_idle()  # Use draw_idle() instead of draw() for better performance
            
        except Exception as e:
            print(f"Error updating preview: {e}")
    
    def get_segment_display_ocr_config(self):
        """Get optimized OCR configuration for 7-segment displays using letsgodigital."""
        # PSM 7: Treat the image as a single text line
        # Use letsgodigital language specifically trained for 7-segment displays
        config = '--psm 7 -l letsgodigital -c tessedit_char_whitelist=0123456789.-'
        return config
    
    def preprocess_roi(self, roi_image, denoise_size, threshold_value):
        """Apply preprocessing to ROI optimized for 8-segment displays."""
        # Convert to grayscale
        gray = cv2.cvtColor(roi_image, cv2.COLOR_RGB2GRAY)
        
        # Apply denoising (Gaussian blur)
        if denoise_size > 1:
            blurred = cv2.GaussianBlur(gray, (denoise_size, denoise_size), 0)
        else:
            blurred = gray
            
        # Apply threshold
        _, thresh = cv2.threshold(blurred, threshold_value, 255, cv2.THRESH_BINARY)
        
        # Additional preprocessing for segment displays
        # Morphological operations to clean up the segments
        kernel = cv2.getStructuringElement(cv2.MORPH_RECT, (2, 2))
        
        # Close small gaps in segments
        thresh = cv2.morphologyEx(thresh, cv2.MORPH_CLOSE, kernel, iterations=1)
        
        # Remove small noise
        thresh = cv2.morphologyEx(thresh, cv2.MORPH_OPEN, kernel, iterations=1)
        
        # Scale up the image for better OCR (segment displays benefit from larger size)
        height, width = thresh.shape
        if height < 50 or width < 100:  # If image is small, scale it up
            scale_factor = max(2, 50 // height, 100 // width)
            new_width = int(width * scale_factor)
            new_height = int(height * scale_factor)
            thresh = cv2.resize(thresh, (new_width, new_height), interpolation=cv2.INTER_CUBIC)
        
        return thresh
    
    def extract_decimal_from_text(self, text):
        """Extract decimal numbers from OCR text, optimized for segment displays."""
        # Clean the text - segment displays often have OCR artifacts
        # Remove common OCR mistakes for segment displays
        cleaned_text = text.strip()
        
        # Common OCR corrections for segment displays
        corrections = {
            'O': '0', 'o': '0', 'I': '1', 'l': '1', '|': '1',
            'S': '5', 's': '5', 'G': '6', 'B': '8', 'D': '0'
        }
        
        for wrong, correct in corrections.items():
            cleaned_text = cleaned_text.replace(wrong, correct)
        
        # Remove everything except digits, decimal points, and minus signs
        cleaned_text = re.sub(r'[^\d.\-]', ' ', cleaned_text)
        
        # Find patterns that look like decimal numbers
        # More strict pattern for segment displays
        decimal_pattern = r'-?\d+(?:\.\d+)?'
        matches = re.findall(decimal_pattern, cleaned_text)
        
        numbers = []
        for match in matches:
            if match and match not in ['.', '-', '-.']:
                try:
                    # Validate the number makes sense for a scale/measurement
                    num = float(match)
                    # Filter out obviously wrong numbers (too many digits, etc.)
                    if len(match.replace('.', '').replace('-', '')) <= 10:  # Reasonable length limit
                        numbers.append(num)
                except ValueError:
                    continue
                    
        return numbers
    
    def reset_roi(self):
        """Reset the ROI selection."""
        self.roi_points = []
        self.roi = None
        self.ax.clear()
        self.display_frame()
    
    def finish_roi_selection(self):
        """Finish ROI selection and close the GUI."""
        if self.roi is None:
            messagebox.showerror("Error", "Please select a ROI first!")
            return
            
        print(f"Final parameters:")
        print(f"ROI: {self.roi}")
        print(f"Denoise: {self.denoise_value}")
        print(f"Threshold: {self.threshold_value}")
        
        self.root.quit()
        self.root.destroy()
    
    def process_video(self):
        """Process all frames of the video to extract numbers."""
        if self.video_path is None or self.roi is None:
            raise ValueError("Video and ROI must be set before processing")
            
        cap = cv2.VideoCapture(self.video_path)
        if not cap.isOpened():
            raise ValueError(f"Could not open video file: {self.video_path}")
        
        total_frames = int(cap.get(cv2.CAP_PROP_FRAME_COUNT))
        fps = cap.get(cv2.CAP_PROP_FPS)
        
        print(f"Processing {total_frames} frames...")
        print(f"Video FPS: {fps}")
        
        self.frame_results = []
        x1, y1, x2, y2 = self.roi
        
        frame_number = 0
        while True:
            ret, frame = cap.read()
            if not ret:
                break
                
            # Convert BGR to RGB
            frame_rgb = cv2.cvtColor(frame, cv2.COLOR_BGR2RGB)
            
            # Extract ROI
            roi_image = frame_rgb[y1:y2, x1:x2]
            
            # Preprocess
            processed_roi = self.preprocess_roi(roi_image, self.denoise_value, self.threshold_value)
            
            # Use letsgodigital OCR
            try:
                # Primary recognition using letsgodigital OCR
                detected_number = self.segment_reader.read_display(processed_roi)
                
                # If letsgodigital fails, fallback to standard pytesseract
                if detected_number is None:
                    try:
                        text = pytesseract.image_to_string(processed_roi, config=self.get_segment_display_ocr_config())
                        numbers = self.extract_decimal_from_text(text)
                        if numbers:
                            detected_number = numbers[0]
                            raw_text = text.strip()
                        else:
                            raw_text = 'No OCR fallback result'
                    except:
                        raw_text = 'OCR fallback failed'
                else:
                    raw_text = f'Segment reader: {detected_number}'
                
                self.frame_results.append({
                    'frame': frame_number,
                    'time': frame_number / fps,
                    'number': detected_number,
                    'raw_text': raw_text
                })
                
            except Exception as e:
                print(f"Error processing frame {frame_number}: {e}")
                    
                self.frame_results.append({
                    'frame': frame_number,
                    'time': frame_number / fps,
                    'number': None,
                    'raw_text': f'Error: {str(e)[:50]}'
                })
            
            frame_number += 1
            
            # Progress update
            if frame_number % 100 == 0:
                print(f"Processed {frame_number}/{total_frames} frames ({frame_number/total_frames*100:.1f}%)")
        
        cap.release()
        print(f"Processing complete! Processed {frame_number} frames.")
        
        # Filter out None results and return
        valid_results = [(r['frame'], r['time'], r['number']) for r in self.frame_results if r['number'] is not None]
        print(f"Successfully extracted numbers from {len(valid_results)} frames out of {frame_number} total frames.")
        
        return valid_results


def setup_tesseract():
    """
    Automatically detect and configure Tesseract OCR path for Windows.
    """
    if platform.system() == "Windows":
        # Common Tesseract installation paths on Windows
        possible_paths = [
            r"C:\Program Files\Tesseract-OCR\tesseract.exe",
            r"C:\Program Files (x86)\Tesseract-OCR\tesseract.exe",
            r"C:\Users\{}\AppData\Local\Tesseract-OCR\tesseract.exe".format(os.getenv('USERNAME')),
            r"C:\Tools\tesseract\tesseract.exe"
        ]
        
        for path in possible_paths:
            if os.path.exists(path):
                pytesseract.pytesseract.tesseract_cmd = path
                print(f"Found Tesseract at: {path}")
                return True
                
        # If not found, show error - Tesseract is required for letsgodigital
        warning_msg = r"""
TESSERACT OCR NOT FOUND!

Tesseract OCR is required for 7-segment display recognition.

1. Download from: https://github.com/UB-Mannheim/tesseract/wiki
2. Install to default location (C:\Program Files\Tesseract-OCR\)
3. Download letsgodigital.traineddata from:
   https://github.com/Shreeshrii/tessdata_shreetest/raw/master/letsgodigital.traineddata
4. Copy to: C:\Program Files\Tesseract-OCR\tessdata\
"""
        print(warning_msg)
        return False
    
    else:
        # For Linux/Mac, assume it's in PATH or user has configured it
        try:
            subprocess.run(['tesseract', '--version'], capture_output=True, check=True)
            print("Tesseract found in system PATH")
            return True
        except (subprocess.CalledProcessError, FileNotFoundError):
            warning_msg = """
TESSERACT OCR NOT FOUND!

Tesseract OCR is required for 7-segment display recognition.

Linux: sudo apt-get install tesseract-ocr
macOS: brew install tesseract

Then download letsgodigital.traineddata:
https://github.com/Shreeshrii/tessdata_shreetest/raw/master/letsgodigital.traineddata
Copy to: /usr/share/tesseract-ocr/4.00/tessdata/
"""
            print(warning_msg)
            return False


def extract_numbers_from_video(video_path):
    """
    Main function to extract decimal numbers from video frames.
    
    Parameters:
    video_path (str): Path to the MP4 video file
    
    Returns:
    list: List of tuples (frame_number, time_seconds, decimal_number)
    """
    extractor = VideoNumberExtractor()
    
    # Load video
    print("Loading video...")
    extractor.load_video(video_path)
    
    # Setup GUI for ROI selection
    print("Setting up ROI selection GUI...")
    extractor.setup_roi_selection_gui()
    extractor.root.mainloop()  # This will block until user clicks "Done"
    
    # Process video
    print("Processing video frames...")
    results = extractor.process_video()
    
    return results


def plot_extracted_numbers(results, title="Extracted Numbers from Video"):
    """
    Plot the extracted numbers over time.
    
    Parameters:
    results (list): List of tuples (frame_number, time_seconds, decimal_number)
    title (str): Title for the plot
    """
    if not results:
        print("No results to plot!")
        return
        
    frame_numbers, times, numbers = zip(*results)
    
    # Create figure with subplots
    fig, (ax1, ax2) = plt.subplots(2, 1, figsize=(12, 10))
    
    # Plot vs frame number
    ax1.plot(frame_numbers, numbers, 'b.-', alpha=0.7, markersize=3)
    ax1.set_xlabel('Frame Number')
    ax1.set_ylabel('Extracted Number')
    ax1.set_title(f'{title} - vs Frame Number')
    ax1.grid(True, alpha=0.3)
    
    # Plot vs time
    ax2.plot(times, numbers, 'r.-', alpha=0.7, markersize=3)
    ax2.set_xlabel('Time (seconds)')
    ax2.set_ylabel('Extracted Number')
    ax2.set_title(f'{title} - vs Time')
    ax2.grid(True, alpha=0.3)
    
    plt.tight_layout()
    plt.show()
    
    # Print statistics
    print(f"\nStatistics:")
    print(f"Total data points: {len(results)}")
    print(f"Number range: {min(numbers):.3f} to {max(numbers):.3f}")
    print(f"Time range: {min(times):.2f}s to {max(times):.2f}s")
    print(f"Average value: {np.mean(numbers):.3f}")
    print(f"Standard deviation: {np.std(numbers):.3f}")


def select_video_file():
    """Open file dialog to select video file."""
    root = tk.Tk()
    root.withdraw()  # Hide the root window
    
    file_path = filedialog.askopenfilename(
        title="Select MP4 Video File",
        filetypes=[("MP4 files", "*.mp4"), ("All video files", "*.mp4 *.avi *.mov *.mkv"), ("All files", "*.*")]
    )
    
    root.destroy()
    return file_path


# Example usage and main execution
if __name__ == "__main__":
    try:
        # Setup Tesseract (required for letsgodigital OCR)
        print("Checking Tesseract OCR installation...")
        tesseract_available = setup_tesseract()
        if not tesseract_available:
            print("ERROR: Tesseract OCR is required. Please install it first.")
            exit(1)
        print("✓ Tesseract OCR is ready!")
        
        # Option 1: Select file through GUI
        print("Select your video file...")
        video_file = select_video_file()
        
        if not video_file:
            print("No file selected. Exiting.")
            exit()
            
        print(f"Selected video: {video_file}")
        
        # Option 2: Or specify file path directly
        # video_file = r"C:\path\to\your\video.mp4"
        
        # Extract numbers from video
        results = extract_numbers_from_video(video_file)
        
        # Plot results
        if results:
            plot_extracted_numbers(results, f"Numbers from {os.path.basename(video_file)}")
            
            # Optionally save results to file
            save_path = video_file.replace('.mp4', '_extracted_numbers.txt')
            with open(save_path, 'w') as f:
                f.write("Frame,Time(s),Number\n")
                for frame, time, number in results:
                    f.write(f"{frame},{time:.3f},{number:.6f}\n")
            print(f"Results saved to: {save_path}")
        else:
            print("No numbers were successfully extracted from the video.")
            
    except Exception as e:
        print(f"Error: {e}")
        messagebox.showerror("Error", str(e))
