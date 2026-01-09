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
import tensorflow as tf
from tensorflow import keras
from tensorflow.keras import layers


class CNNDigitRecognizer:
    """CNN-based digit recognition specialized for seven-segment displays."""
    
    def __init__(self):
        self.model = self.build_cnn_model()
        self.detector_model = self.build_detector_model()
        self.img_height = 28
        self.img_width = 28
        
        # Get the script directory for weights file
        self.weights_path = os.path.join(os.path.dirname(os.path.abspath(__file__)), 
                                         'seven_segment_weights.weights.h5')
        self.detector_weights_path = os.path.join(os.path.dirname(os.path.abspath(__file__)), 
                                                  'digit_detector_weights.weights.h5')
        
        # Try to load pre-trained weights if available
        if os.path.exists(self.weights_path):
            try:
                self.model.load_weights(self.weights_path)
                print(f"✓ Loaded pre-trained seven-segment CNN weights from: {self.weights_path}")
            except Exception as e:
                print(f"Error loading weights: {e}")
                print("Training new model on synthetic seven-segment data...")
                self.train_on_seven_segment_data()
        else:
            print(f"No pre-trained weights found at: {self.weights_path}")
            print("Generating synthetic seven-segment display data and training model...")
            self.train_on_seven_segment_data()
        
        # Try to load detector weights
        if os.path.exists(self.detector_weights_path):
            try:
                self.detector_model.load_weights(self.detector_weights_path)
                print(f"✓ Loaded pre-trained detector weights from: {self.detector_weights_path}")
            except Exception as e:
                print(f"Error loading detector weights: {e}")
                print("Training new detector model...")
                self.train_detector()
        else:
            print(f"No pre-trained detector weights found at: {self.detector_weights_path}")
            print("Training digit detector model...")
            self.train_detector()
    
    def build_cnn_model(self):
        """Build a CNN model optimized for seven-segment digit recognition."""
        model = keras.Sequential([
            layers.Input(shape=(28, 28, 1)),
            
            # First convolutional block - designed for segment patterns
            layers.Conv2D(32, (3, 3), activation='relu', padding='same'),
            layers.BatchNormalization(),
            layers.Conv2D(32, (3, 3), activation='relu', padding='same'),
            layers.BatchNormalization(),
            layers.MaxPooling2D((2, 2)),
            layers.Dropout(0.25),
            
            # Second convolutional block - captures segment combinations
            layers.Conv2D(64, (3, 3), activation='relu', padding='same'),
            layers.BatchNormalization(),
            layers.Conv2D(64, (3, 3), activation='relu', padding='same'),
            layers.BatchNormalization(),
            layers.MaxPooling2D((2, 2)),
            layers.Dropout(0.25),
            
            # Dense layers
            layers.Flatten(),
            layers.Dense(128, activation='relu'),
            layers.BatchNormalization(),
            layers.Dropout(0.5),
            layers.Dense(10, activation='softmax')
        ])
        
        model.compile(
            optimizer='adam',
            loss='sparse_categorical_crossentropy',
            metrics=['accuracy']
        )
        
        return model
    
    def build_detector_model(self):
        """Build a CNN model to detect digit vs non-digit regions (binary classification)."""
        model = keras.Sequential([
            layers.Input(shape=(28, 28, 1)),
            
            # Convolutional layers for feature extraction
            layers.Conv2D(32, (3, 3), activation='relu', padding='same'),
            layers.BatchNormalization(),
            layers.MaxPooling2D((2, 2)),
            layers.Dropout(0.25),
            
            layers.Conv2D(64, (3, 3), activation='relu', padding='same'),
            layers.BatchNormalization(),
            layers.MaxPooling2D((2, 2)),
            layers.Dropout(0.25),
            
            # Dense layers for classification
            layers.Flatten(),
            layers.Dense(128, activation='relu'),
            layers.BatchNormalization(),
            layers.Dropout(0.5),
            layers.Dense(1, activation='sigmoid')  # Binary: digit or not
        ])
        
        model.compile(
            optimizer='adam',
            loss='binary_crossentropy',
            metrics=['accuracy']
        )
        
        return model
    
    def generate_seven_segment_digit(self, digit, img_size=28, noise_level=0.1, add_whitespace=False):
        """Generate a synthetic seven-segment display digit with 3D rotation and borders."""
        img = np.zeros((img_size, img_size), dtype=np.float32)
        
        # If add_whitespace is True, add white background to simulate threshold variations
        if add_whitespace and np.random.random() > 0.5:
            # Add varying levels of white background
            whitespace_level = np.random.uniform(0.1, 0.4)
            img = np.full((img_size, img_size), whitespace_level, dtype=np.float32)
        
        # Define segment positions (normalized coordinates)
        # Segments: a(top), b(top-right), c(bottom-right), d(bottom), e(bottom-left), f(top-left), g(middle)
        segment_patterns = {
            0: [1, 1, 1, 1, 1, 1, 0],  # a,b,c,d,e,f
            1: [0, 1, 1, 0, 0, 0, 0],  # b,c
            2: [1, 1, 0, 1, 1, 0, 1],  # a,b,d,e,g
            3: [1, 1, 1, 1, 0, 0, 1],  # a,b,c,d,g
            4: [0, 1, 1, 0, 0, 1, 1],  # b,c,f,g
            5: [1, 0, 1, 1, 0, 1, 1],  # a,c,d,f,g
            6: [1, 0, 1, 1, 1, 1, 1],  # a,c,d,e,f,g
            7: [1, 1, 1, 0, 0, 0, 0],  # a,b,c
            8: [1, 1, 1, 1, 1, 1, 1],  # all segments
            9: [1, 1, 1, 1, 0, 1, 1]   # a,b,c,d,f,g
        }
        
        pattern = segment_patterns[digit]
        thickness = 2
        
        # Draw segments
        margin = 4
        w, h = img_size - 2*margin, img_size - 2*margin
        x_start, y_start = margin, margin
        
        # Segment a (top horizontal)
        if pattern[0]:
            cv2.line(img, (x_start+2, y_start), (x_start+w-2, y_start), 1.0, thickness)
        
        # Segment b (top-right vertical)
        if pattern[1]:
            cv2.line(img, (x_start+w, y_start+2), (x_start+w, y_start+h//2-1), 1.0, thickness)
        
        # Segment c (bottom-right vertical)
        if pattern[2]:
            cv2.line(img, (x_start+w, y_start+h//2+1), (x_start+w, y_start+h-2), 1.0, thickness)
        
        # Segment d (bottom horizontal)
        if pattern[3]:
            cv2.line(img, (x_start+2, y_start+h), (x_start+w-2, y_start+h), 1.0, thickness)
        
        # Segment e (bottom-left vertical)
        if pattern[4]:
            cv2.line(img, (x_start, y_start+h//2+1), (x_start, y_start+h-2), 1.0, thickness)
        
        # Segment f (top-left vertical)
        if pattern[5]:
            cv2.line(img, (x_start, y_start+2), (x_start, y_start+h//2-1), 1.0, thickness)
        
        # Segment g (middle horizontal)
        if pattern[6]:
            cv2.line(img, (x_start+2, y_start+h//2), (x_start+w-2, y_start+h//2), 1.0, thickness)
        
        # Apply 3D rotation (perspective transform) - up to 15 degrees
        if np.random.random() > 0.3:  # Apply to 70% of samples
            # Random rotation angles (in degrees)
            angle_x = np.random.uniform(-15, 15)  # Rotation around X-axis
            angle_y = np.random.uniform(-15, 15)  # Rotation around Y-axis
            angle_z = np.random.uniform(-10, 10)  # Slight Z-axis rotation
            
            # Convert to radians
            angle_x = np.radians(angle_x)
            angle_y = np.radians(angle_y)
            angle_z = np.radians(angle_z)
            
            # Create perspective transformation
            center_x, center_y = img_size / 2, img_size / 2
            focal_length = img_size * 2
            
            # 3D rotation matrices
            rot_x = np.array([
                [1, 0, 0],
                [0, np.cos(angle_x), -np.sin(angle_x)],
                [0, np.sin(angle_x), np.cos(angle_x)]
            ])
            
            rot_y = np.array([
                [np.cos(angle_y), 0, np.sin(angle_y)],
                [0, 1, 0],
                [-np.sin(angle_y), 0, np.cos(angle_y)]
            ])
            
            rot_z = np.array([
                [np.cos(angle_z), -np.sin(angle_z), 0],
                [np.sin(angle_z), np.cos(angle_z), 0],
                [0, 0, 1]
            ])
            
            # Combined rotation
            rotation = rot_z @ rot_y @ rot_x
            
            # Define source and destination points for perspective transform
            pts1 = np.float32([[0, 0], [img_size, 0], [0, img_size], [img_size, img_size]])
            
            # Apply 3D rotation to get destination points
            pts2 = []
            for pt in pts1:
                x, y = pt[0] - center_x, pt[1] - center_y
                vec = np.array([x, y, 0])
                rotated = rotation @ vec
                
                # Perspective projection
                z = rotated[2] + focal_length
                x_proj = (rotated[0] * focal_length / z) + center_x
                y_proj = (rotated[1] * focal_length / z) + center_y
                pts2.append([x_proj, y_proj])
            
            pts2 = np.float32(pts2)
            
            # Apply perspective transformation
            matrix = cv2.getPerspectiveTransform(pts1, pts2)
            img = cv2.warpPerspective(img, matrix, (img_size, img_size))
        
        # Add intermittent black borders (50% chance)
        if np.random.random() > 0.5:
            border_type = np.random.choice(['full_box', 'corners', 'partial'])
            border_thickness = np.random.randint(1, 3)
            
            if border_type == 'full_box':
                # Draw a complete box around the digit
                border_margin = 1
                cv2.rectangle(img, 
                            (border_margin, border_margin), 
                            (img_size - border_margin, img_size - border_margin),
                            1.0, border_thickness)
            
            elif border_type == 'corners':
                # Draw corner brackets
                corner_len = np.random.randint(4, 8)
                border_margin = 1
                
                # Top-left corner
                cv2.line(img, (border_margin, border_margin), 
                        (border_margin + corner_len, border_margin), 1.0, border_thickness)
                cv2.line(img, (border_margin, border_margin), 
                        (border_margin, border_margin + corner_len), 1.0, border_thickness)
                
                # Top-right corner
                cv2.line(img, (img_size - border_margin, border_margin), 
                        (img_size - border_margin - corner_len, border_margin), 1.0, border_thickness)
                cv2.line(img, (img_size - border_margin, border_margin), 
                        (img_size - border_margin, border_margin + corner_len), 1.0, border_thickness)
                
                # Bottom-left corner
                cv2.line(img, (border_margin, img_size - border_margin), 
                        (border_margin + corner_len, img_size - border_margin), 1.0, border_thickness)
                cv2.line(img, (border_margin, img_size - border_margin), 
                        (border_margin, img_size - border_margin - corner_len), 1.0, border_thickness)
                
                # Bottom-right corner
                cv2.line(img, (img_size - border_margin, img_size - border_margin), 
                        (img_size - border_margin - corner_len, img_size - border_margin), 1.0, border_thickness)
                cv2.line(img, (img_size - border_margin, img_size - border_margin), 
                        (img_size - border_margin, img_size - border_margin - corner_len), 1.0, border_thickness)
            
            elif border_type == 'partial':
                # Random partial borders (top, bottom, left, or right)
                sides = np.random.choice(['top', 'bottom', 'left', 'right'], 
                                       size=np.random.randint(1, 3), replace=False)
                border_margin = 1
                
                for side in sides:
                    if side == 'top':
                        cv2.line(img, (border_margin, border_margin), 
                               (img_size - border_margin, border_margin), 1.0, border_thickness)
                    elif side == 'bottom':
                        cv2.line(img, (border_margin, img_size - border_margin), 
                               (img_size - border_margin, img_size - border_margin), 1.0, border_thickness)
                    elif side == 'left':
                        cv2.line(img, (border_margin, border_margin), 
                               (border_margin, img_size - border_margin), 1.0, border_thickness)
                    elif side == 'right':
                        cv2.line(img, (img_size - border_margin, border_margin), 
                               (img_size - border_margin, img_size - border_margin), 1.0, border_thickness)
        
        # Add random noise and variations
        if noise_level > 0:
            noise = np.random.normal(0, noise_level, img.shape)
            img = np.clip(img + noise, 0, 1)
            
            # Random brightness variation
            brightness = np.random.uniform(0.7, 1.0)
            img = img * brightness
            
            # Random blur
            if np.random.random() > 0.5:
                kernel_size = np.random.choice([3, 5])
                img = cv2.GaussianBlur(img, (kernel_size, kernel_size), 0)
        
        return img
    
    def train_on_seven_segment_data(self):
        """Generate synthetic seven-segment data and train the model."""
        try:
            print("Generating synthetic seven-segment display training data (1-5 digits, no decimals)...")
            
            # Generate training data with single digits only
            # The model predicts individual digits, not full numbers
            samples_per_digit = 2000
            x_train = []
            y_train = []
            
            for digit in range(10):
                for _ in range(samples_per_digit):
                    # 30% of samples with whitespace augmentation
                    add_whitespace = np.random.random() < 0.3
                    img = self.generate_seven_segment_digit(digit, noise_level=0.15, add_whitespace=add_whitespace)
                    x_train.append(img)
                    y_train.append(digit)
            
            x_train = np.array(x_train)
            y_train = np.array(y_train)
            
            # Generate test data (less noisy)
            samples_per_digit_test = 400
            x_test = []
            y_test = []
            
            for digit in range(10):
                for _ in range(samples_per_digit_test):
                    img = self.generate_seven_segment_digit(digit, noise_level=0.1)
                    x_test.append(img)
                    y_test.append(digit)
            
            x_test = np.array(x_test)
            y_test = np.array(y_test)
            
            # Reshape for CNN
            x_train = np.expand_dims(x_train, -1)
            x_test = np.expand_dims(x_test, -1)
            
            # Shuffle training data
            indices = np.random.permutation(len(x_train))
            x_train = x_train[indices]
            y_train = y_train[indices]
            
            print(f"Training CNN on {len(x_train)} synthetic seven-segment images...")
            
            # Train the model
            history = self.model.fit(
                x_train, y_train, 
                epochs=10, 
                batch_size=128,
                validation_data=(x_test, y_test),
                verbose=1
            )
            
            # Evaluate on test set
            test_loss, test_accuracy = self.model.evaluate(x_test, y_test, verbose=0)
            print(f"\n✓ Seven-segment CNN model trained successfully!")
            print(f"Test Loss: {test_loss:.4f}")
            print(f"Test Accuracy: {test_accuracy:.4f} ({test_accuracy*100:.2f}%)")
            
            # Save the weights for future use
            self.model.save_weights(self.weights_path)
            print(f"✓ Model weights saved to: {self.weights_path}")
            
        except Exception as e:
            print(f"Warning: Could not train seven-segment model: {e}")
    
    def train_detector(self):
        """Train the digit detector on synthetic data (digit vs non-digit classification)."""
        try:
            print("Generating synthetic training data for digit detector...")
            
            # Generate positive samples (actual digits) with whitespace variations
            positive_samples = 5000
            x_positive = []
            
            for _ in range(positive_samples):
                digit = np.random.randint(0, 10)
                # 50% with whitespace augmentation to handle threshold variations
                add_whitespace = np.random.random() < 0.5
                img = self.generate_seven_segment_digit(digit, noise_level=0.15, add_whitespace=add_whitespace)
                x_positive.append(img)
            
            # Generate negative samples (non-digit regions) - MORE REALISTIC
            negative_samples = 5000
            x_negative = []
            
            for _ in range(negative_samples):
                # Create various non-digit patterns including whitespace artifacts
                img = np.zeros((28, 28), dtype=np.float32)
                pattern_type = np.random.choice(['random_lines', 'random_noise', 'partial_segments', 
                                                'empty', 'whitespace', 'whitespace_with_noise'], 
                                               p=[0.2, 0.15, 0.2, 0.1, 0.2, 0.15])
                
                if pattern_type == 'random_lines':
                    # Random lines that don't form digits
                    num_lines = np.random.randint(1, 5)
                    for _ in range(num_lines):
                        pt1 = (np.random.randint(0, 28), np.random.randint(0, 28))
                        pt2 = (np.random.randint(0, 28), np.random.randint(0, 28))
                        cv2.line(img, pt1, pt2, np.random.uniform(0.5, 1.0), np.random.randint(1, 3))
                
                elif pattern_type == 'random_noise':
                    # Random noise
                    img = np.random.uniform(0, 0.5, (28, 28)).astype(np.float32)
                
                elif pattern_type == 'partial_segments':
                    # Draw incomplete segment patterns (only 1-3 segments, not forming a digit)
                    num_segs = np.random.randint(1, 4)
                    for _ in range(num_segs):
                        pt1 = (np.random.randint(5, 23), np.random.randint(5, 23))
                        pt2 = (pt1[0] + np.random.randint(-5, 5), pt1[1] + np.random.randint(-5, 5))
                        cv2.line(img, pt1, pt2, 1.0, 2)
                
                elif pattern_type == 'whitespace':
                    # Pure whitespace at various levels (common threshold artifact)
                    whitespace_level = np.random.uniform(0.1, 0.6)
                    img = np.full((28, 28), whitespace_level, dtype=np.float32)
                
                elif pattern_type == 'whitespace_with_noise':
                    # Whitespace with small noise particles (very common in thresholded images)
                    whitespace_level = np.random.uniform(0.15, 0.5)
                    img = np.full((28, 28), whitespace_level, dtype=np.float32)
                    
                    # Add small random noise particles
                    num_particles = np.random.randint(1, 8)
                    for _ in range(num_particles):
                        x = np.random.randint(0, 28)
                        y = np.random.randint(0, 28)
                        size = np.random.randint(1, 3)
                        img[max(0, y-size):min(28, y+size), max(0, x-size):min(28, x+size)] = np.random.uniform(0.6, 1.0)
                
                # elif pattern_type == 'empty' - leave as zeros
                
                # Add some noise to make it more realistic
                if np.random.random() > 0.5:
                    noise = np.random.normal(0, 0.1, img.shape)
                    img = np.clip(img + noise, 0, 1)
                
                x_negative.append(img)
            
            # Combine and create labels
            x_train = np.array(x_positive + x_negative)
            y_train = np.array([1] * positive_samples + [0] * negative_samples)
            
            # Reshape for CNN
            x_train = np.expand_dims(x_train, -1)
            
            # Shuffle
            indices = np.random.permutation(len(x_train))
            x_train = x_train[indices]
            y_train = y_train[indices]
            
            # Generate test data
            x_test_pos = [self.generate_seven_segment_digit(np.random.randint(0, 10), noise_level=0.1) 
                          for _ in range(500)]
            x_test_neg = [np.random.uniform(0, 0.3, (28, 28)).astype(np.float32) 
                          for _ in range(500)]
            x_test = np.array(x_test_pos + x_test_neg)
            y_test = np.array([1] * 500 + [0] * 500)
            x_test = np.expand_dims(x_test, -1)
            
            print(f"Training detector on {len(x_train)} samples...")
            
            # Train the detector
            history = self.detector_model.fit(
                x_train, y_train,
                epochs=10,
                batch_size=128,
                validation_data=(x_test, y_test),
                verbose=1
            )
            
            # Evaluate
            test_loss, test_accuracy = self.detector_model.evaluate(x_test, y_test, verbose=0)
            print(f"\n✓ Digit detector trained successfully!")
            print(f"Test Loss: {test_loss:.4f}")
            print(f"Test Accuracy: {test_accuracy:.4f} ({test_accuracy*100:.2f}%)")
            
            # Save weights
            self.detector_model.save_weights(self.detector_weights_path)
            print(f"✓ Detector weights saved to: {self.detector_weights_path}")
            
        except Exception as e:
            print(f"Warning: Could not train detector model: {e}")
        
    def preprocess_for_cnn(self, image):
        """Preprocess image for CNN digit recognition with denoising."""
        # Convert to grayscale if needed
        if len(image.shape) == 3:
            gray = cv2.cvtColor(image, cv2.COLOR_RGB2GRAY)
        else:
            gray = image.copy()
        
        # Apply Gaussian blur for denoising (similar to pytesseract preprocessing)
        # This helps reduce noise while preserving edges
        denoised = cv2.GaussianBlur(gray, (5, 5), 0)
        
        # Apply adaptive threshold to handle varying lighting
        binary = cv2.adaptiveThreshold(denoised, 255, cv2.ADAPTIVE_THRESH_GAUSSIAN_C, 
                                     cv2.THRESH_BINARY, 11, 2)
        
        # Invert if needed (digits should be white on black background for CNN)
        if np.mean(binary) > 127:
            binary = cv2.bitwise_not(binary)
        
        # Morphological operations to clean up noise (similar to pytesseract preprocessing)
        kernel = cv2.getStructuringElement(cv2.MORPH_RECT, (2, 2))
        
        # Close small gaps in segments
        binary = cv2.morphologyEx(binary, cv2.MORPH_CLOSE, kernel, iterations=1)
        
        # Remove small noise particles
        binary = cv2.morphologyEx(binary, cv2.MORPH_OPEN, kernel, iterations=1)
        
        return binary
    
    def find_digit_regions_with_cnn(self, binary_image, original_image):
        """Use CNN detector to find digit regions with sliding window approach."""
        h, w = binary_image.shape
        digit_regions = []
        window_size = 28
        stride = 4  # Pixels to move window each step
        
        # Store detection scores for non-max suppression
        all_detections = []
        
        # Multi-scale sliding window
        for scale in [0.8, 1.0, 1.2, 1.5]:
            scaled_h = int(h * scale)
            scaled_w = int(w * scale)
            
            if scaled_h < window_size or scaled_w < window_size:
                continue
            
            scaled_img = cv2.resize(binary_image, (scaled_w, scaled_h))
            
            for y in range(0, scaled_h - window_size, stride):
                for x in range(0, scaled_w - window_size, stride):
                    # Extract window
                    window = scaled_img[y:y+window_size, x:x+window_size]
                    
                    # Normalize
                    window_norm = window.astype('float32') / 255.0
                    window_input = np.expand_dims(np.expand_dims(window_norm, axis=0), axis=-1)
                    
                    # Predict if this window contains a digit
                    score = self.detector_model.predict(window_input, verbose=0)[0][0]
                    
                    if score > 0.85:  # Higher confidence threshold to reduce false positives
                        # Convert back to original image coordinates
                        orig_x = int(x / scale)
                        orig_y = int(y / scale)
                        orig_w = int(window_size / scale)
                        orig_h = int(window_size / scale)
                        
                        all_detections.append((orig_x, orig_y, orig_w, orig_h, score))
        
        # Apply non-maximum suppression to remove overlapping detections
        if all_detections:
            digit_regions = self.non_max_suppression(all_detections, overlap_thresh=0.3)
        
        # Sort by x-coordinate (left to right)
        digit_regions.sort(key=lambda r: r[0])
        
        return digit_regions
    
    def non_max_suppression(self, detections, overlap_thresh=0.3):
        """Apply non-maximum suppression to remove overlapping bounding boxes."""
        if len(detections) == 0:
            return []
        
        # Convert to numpy array
        boxes = np.array([(x, y, x+w, y+h, score) for x, y, w, h, score in detections])
        
        # Sort by score
        idxs = np.argsort(boxes[:, 4])[::-1]
        
        pick = []
        while len(idxs) > 0:
            i = idxs[0]
            pick.append(i)
            
            # Compute IoU with remaining boxes
            xx1 = np.maximum(boxes[i, 0], boxes[idxs[1:], 0])
            yy1 = np.maximum(boxes[i, 1], boxes[idxs[1:], 1])
            xx2 = np.minimum(boxes[i, 2], boxes[idxs[1:], 2])
            yy2 = np.minimum(boxes[i, 3], boxes[idxs[1:], 3])
            
            w = np.maximum(0, xx2 - xx1)
            h = np.maximum(0, yy2 - yy1)
            
            intersection = w * h
            area_i = (boxes[i, 2] - boxes[i, 0]) * (boxes[i, 3] - boxes[i, 1])
            area_others = (boxes[idxs[1:], 2] - boxes[idxs[1:], 0]) * (boxes[idxs[1:], 3] - boxes[idxs[1:], 1])
            union = area_i + area_others - intersection
            
            iou = intersection / union
            
            # Remove boxes with high overlap
            idxs = np.delete(idxs, np.concatenate(([0], np.where(iou > overlap_thresh)[0] + 1)))
        
        # Convert back to (x, y, w, h) format
        result = []
        for i in pick:
            x1, y1, x2, y2, score = boxes[i]
            result.append((int(x1), int(y1), int(x2-x1), int(y2-y1)))
        
        return result
    
    def find_digit_regions(self, binary_image):
        """Find individual digit regions in the image with support for whitespace between segments."""
        contours, _ = cv2.findContours(binary_image, cv2.RETR_EXTERNAL, cv2.CHAIN_APPROX_SIMPLE)
        
        # First pass: collect all potential segment pieces
        all_boxes = []
        for contour in contours:
            x, y, w, h = cv2.boundingRect(contour)
            area = cv2.contourArea(contour)
            
            # Very lenient filtering - just remove tiny noise
            # Accept even small segments that might be parts of digits with whitespace
            if w > 5 and h > 8 and area > 30:
                all_boxes.append((x, y, w, h))
        
        if not all_boxes:
            return []
        
        # Group nearby boxes that likely belong to the same digit
        # Sort by x-coordinate
        all_boxes.sort(key=lambda b: b[0])
        
        grouped_regions = []
        current_group = [all_boxes[0]]
        
        for i in range(1, len(all_boxes)):
            prev_box = current_group[-1]
            curr_box = all_boxes[i]
            
            # Check if boxes are close enough to be part of same digit
            # Consider horizontal distance and vertical overlap
            horizontal_gap = curr_box[0] - (prev_box[0] + prev_box[2])
            
            # Vertical overlap check
            prev_y_min, prev_y_max = prev_box[1], prev_box[1] + prev_box[3]
            curr_y_min, curr_y_max = curr_box[1], curr_box[1] + curr_box[3]
            vertical_overlap = min(prev_y_max, curr_y_max) - max(prev_y_min, curr_y_min)
            
            # Group if boxes are close horizontally and have vertical overlap
            # Allow larger gaps for whitespace between segments
            if horizontal_gap < 25 and vertical_overlap > 0:
                current_group.append(curr_box)
            else:
                # Finalize current group
                if current_group:
                    grouped_regions.append(current_group)
                current_group = [curr_box]
        
        # Don't forget the last group
        if current_group:
            grouped_regions.append(current_group)
        
        # Create bounding boxes for each grouped region
        digit_regions = []
        for group in grouped_regions:
            if not group:
                continue
            
            # Find bounding box that encompasses all boxes in group
            x_min = min(box[0] for box in group)
            y_min = min(box[1] for box in group)
            x_max = max(box[0] + box[2] for box in group)
            y_max = max(box[1] + box[3] for box in group)
            
            w = x_max - x_min
            h = y_max - y_min
            
            # Final filter: must look somewhat like a digit
            # More lenient aspect ratio to handle 1's and whitespace variations
            if w > 8 and h > 12 and 0.2 < w/h < 1.2:
                digit_regions.append((x_min, y_min, w, h))
        
        # Sort by x-coordinate (left to right)
        digit_regions.sort(key=lambda r: r[0])
        return digit_regions
    
    def predict_digit(self, digit_roi):
        """Use CNN to predict the digit from ROI."""
        try:
            # Resize to model input size
            resized = cv2.resize(digit_roi, (self.img_width, self.img_height))
            
            # Normalize
            normalized = resized.astype('float32') / 255.0
            
            # Reshape for model input
            input_data = np.expand_dims(normalized, axis=0)
            input_data = np.expand_dims(input_data, axis=-1)
            
            # Predict
            predictions = self.model.predict(input_data, verbose=0)
            digit = np.argmax(predictions[0])
            confidence = float(predictions[0][digit])
            
            return str(digit), confidence
        except Exception as e:
            print(f"Error in CNN prediction: {e}")
            return None, 0.0
    
    def read_display(self, image):
        """Read the entire display and return the number using CNN."""
        try:
            # Preprocess
            binary = self.preprocess_for_cnn(image)
            
            # Find digit regions using fast contour-based detection
            # (CNN detector is too slow for video processing)
            digit_regions = self.find_digit_regions(binary)
            
            if not digit_regions:
                return None
            
            # Read each digit using CNN
            digits = []
            confidences = []
            
            for x, y, w, h in digit_regions:
                digit_roi = binary[y:y+h, x:x+w]
                
                if digit_roi.size == 0:
                    continue
                    
                # Use CNN to predict digit
                digit, confidence = self.predict_digit(digit_roi)
                
                if digit is not None and confidence > 0.5:  # Confidence threshold
                    digits.append(digit)
                    confidences.append(confidence)
            
            if not digits:
                return None
            
            # Limit to 4 digits maximum (scale displays up to 9999)
            if len(digits) > 4:
                digits = digits[:4]
                
            # Combine digits into number (no decimal points)
            number_str = ''.join(digits)
                
            try:
                number = float(number_str)
                # Ensure output doesn't exceed 9999
                if number > 9999:
                    return None
                return number
            except ValueError:
                return None
                
        except Exception as e:
            print(f"Error in CNN recognition: {e}")
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
        self.segment_reader = CNNDigitRecognizer()  # Initialize CNN-based digit recognizer
        
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
                # Use simpler contour-based detection during preview (CNN is too slow for real-time)
                # Just show that preprocessing is working, actual detection happens during video processing
                binary = self.segment_reader.preprocess_for_cnn(processed)
                contours, _ = cv2.findContours(binary, cv2.RETR_EXTERNAL, cv2.CHAIN_APPROX_SIMPLE)
                
                # Count potential digit regions
                digit_count = sum(1 for c in contours 
                                if cv2.contourArea(c) > 100 and 
                                10 < cv2.boundingRect(c)[2] < 200 and
                                15 < cv2.boundingRect(c)[3] < 200)
                
                if digit_count > 0:
                    ax_proc.text(0.5, -0.15, f"Found ~{digit_count} potential digit regions", 
                               transform=ax_proc.transAxes, ha='center', va='top',
                               fontsize=9, 
                               bbox=dict(boxstyle="round,pad=0.3", facecolor="lightgreen", alpha=0.8))
                else:
                    ax_proc.text(0.5, -0.15, "No digit regions detected", 
                               transform=ax_proc.transAxes, ha='center', va='top',
                               fontsize=9,
                               bbox=dict(boxstyle="round,pad=0.3", facecolor="orange", alpha=0.8))
            except Exception as e:
                ax_proc.text(0.5, -0.15, f"Preview Error: {str(e)[:20]}", 
                           transform=ax_proc.transAxes, ha='center', va='top',
                           fontsize=9,
                           bbox=dict(boxstyle="round,pad=0.3", facecolor="red", alpha=0.8))
                
            # Update the canvas efficiently
            self.canvas.draw_idle()  # Use draw_idle() instead of draw() for better performance
            
        except Exception as e:
            print(f"Error updating preview: {e}")
    
    def get_segment_display_ocr_config(self):
        """Get optimized OCR configuration for 8-segment displays."""
        # PSM 8 treats the image as a single word
        # PSM 7 treats the image as a single text line
        # PSM 13 is for raw line (useful for digits)
        # For segment displays, we'll try PSM 8 (single word) with digit whitelist
        config = '--psm 8 -c tessedit_char_whitelist=0123456789.- --dpi 150'
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
            
            # Use custom segment reader instead of OCR
            try:
                # Primary recognition using custom segment reader
                detected_number = self.segment_reader.read_display(processed_roi)
                
                # If custom reader fails, fallback to pytesseract as backup
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
                
        # If not found, show warning but don't exit (we have custom segment reader)
        warning_msg = r"""
TESSERACT OCR NOT FOUND (but continuing with custom segment reader)!

For best results, you may want to install Tesseract OCR as a fallback:
1. Download from: https://github.com/UB-Mannheim/tesseract/wiki
2. Install to default location (C:\Program Files\Tesseract-OCR\)

The script will use custom 7-segment recognition primarily.
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
TESSERACT OCR NOT FOUND (but continuing with custom segment reader)!

For best results, you may want to install Tesseract OCR as a fallback:
Linux: sudo apt-get install tesseract-ocr
macOS: brew install tesseract

The script will use custom 7-segment recognition primarily.
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
        # Setup Tesseract (optional, used as fallback)
        print("Checking Tesseract OCR installation (optional)...")
        tesseract_available = setup_tesseract()
        if tesseract_available:
            print("Tesseract is available as fallback!")
        else:
            print("Using custom 7-segment reader (Tesseract not available as fallback).")
        
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
