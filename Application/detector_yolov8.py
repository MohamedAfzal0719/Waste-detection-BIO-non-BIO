import cv2
import numpy as np
import threading
import os

try:
    from ultralytics import YOLO
    YOLOV8_AVAILABLE = True
except ImportError:
    YOLOV8_AVAILABLE = False
    print("⚠ YOLOv8 not available, falling back to basic mode")

# =========================================================
# GLOBALS
# =========================================================
running = False
camera = None
last_frame = None
model = None
YOLOV8_MODE = False

# ROI Configuration (Region of Interest for detection)
# Define as percentage of frame dimensions
ROI_X_START = 0.15  # Start at 15% from left
ROI_X_END = 0.85    # End at 85% from left
ROI_Y_START = 0.1   # Start at 10% from top
ROI_Y_END = 0.9     # End at 90% from top
SHOW_ROI = True     # Draw ROI rectangle on display

# =========================================================
# MODEL LOAD
# =========================================================
CLASSES = ["bio", "non_bio", "trash1", "trash2"]
IMG_SIZE = (416, 416)

print("\n" + "=" * 60)
print("🤖 Initializing Waste Detection System")
print("=" * 60)

if YOLOV8_AVAILABLE:
    try:
        print("\n📥 Loading YOLOv8 Model...")
        model_path = "yolov8_model.pt"
        
        if os.path.exists(model_path):
            model = YOLO(model_path)
            YOLOV8_MODE = True
            print(f"✓ YOLOv8 Model loaded successfully!")
            print(f"  Model: {model_path}")
        else:
            print(f"⚠ YOLOv8 model not found at {model_path}")
            print("  Please train the model first using train_yolov8.py")
    except Exception as e:
        print(f"⚠ Failed to load YOLOv8: {str(e)[:100]}...")
        YOLOV8_MODE = False

if not YOLOV8_MODE:
    print("\n⚠ CRITICAL: YOLOv8 model not found!")
    print("  The system will not be able to perform detection.")

print("\n" + "=" * 60)

# =========================================================
# ROI HELPER FUNCTIONS
# =========================================================
def get_roi_coordinates(frame_height, frame_width):
    """Calculate ROI coordinates based on frame dimensions."""
    x_start = int(frame_width * ROI_X_START)
    x_end = int(frame_width * ROI_X_END)
    y_start = int(frame_height * ROI_Y_START)
    y_end = int(frame_height * ROI_Y_END)
    return (x_start, y_start, x_end, y_end)

def crop_to_roi(frame):
    """Crop frame to ROI region."""
    if frame is None:
        return None
    h, w = frame.shape[:2]
    x_start, y_start, x_end, y_end = get_roi_coordinates(h, w)
    return frame[y_start:y_end, x_start:x_end]

def draw_roi_on_frame(frame):
    """Draw ROI rectangle on frame."""
    if frame is None or not SHOW_ROI:
        return frame
    
    frame_copy = frame.copy()
    h, w = frame.shape[:2]
    x_start, y_start, x_end, y_end = get_roi_coordinates(h, w)
    
    # Draw ROI rectangle in green
    cv2.rectangle(frame_copy, (x_start, y_start), (x_end, y_end), (0, 255, 0), 2)
    # Add ROI label
    cv2.putText(frame_copy, "ROI", (x_start + 10, y_start + 25), 
                cv2.FONT_HERSHEY_SIMPLEX, 0.7, (0, 255, 0), 2)
    
    return frame_copy

# =========================================================
# RULE-BASED COLOR CLASSIFIER
# =========================================================
def rule_based_bio_check(frame):
    """
    Analyzes dominant colors to determine if waste is likely BIO.
    Bio/organic waste has natural earth tones:
      - Greens  : leaves, vegetables, unripe fruit
      - Reds    : apples, tomatoes, strawberries, raspberries
      - Yellows : bananas, lemons, corn
      - Oranges : oranges, carrots, mangoes
      - Browns  : cardboard, soil, coffee grounds
    Returns (is_bio: bool, bio_ratio: float 0-1)
    """
    import sys
    try:
        if frame is None or frame.size == 0:
            return False, 0.0

        hsv = cv2.cvtColor(frame, cv2.COLOR_BGR2HSV)
        total_pixels = frame.shape[0] * frame.shape[1]

        # --- Bio color masks (HSV ranges) ---
        masks = [
            # Greens (leaves, vegetables)
            cv2.inRange(hsv, np.array([35, 40, 40]),  np.array([85, 255, 255])),
            # Yellows / light oranges (bananas, lemons)
            cv2.inRange(hsv, np.array([20, 80, 80]),  np.array([35, 255, 255])),
            # Deep oranges (oranges, carrots, mangoes)
            cv2.inRange(hsv, np.array([10, 100, 100]), np.array([20, 255, 255])),
            # Reds – lower wrap (strawberries, raspberries, tomatoes)
            cv2.inRange(hsv, np.array([0,  80, 60]),  np.array([10, 255, 255])),
            # Reds – upper wrap
            cv2.inRange(hsv, np.array([170, 80, 60]), np.array([180, 255, 255])),
            # Browns (cardboard, soil, coffee)
            cv2.inRange(hsv, np.array([10, 40, 30]),  np.array([20, 180, 160])),
        ]

        bio_pixels = sum(cv2.countNonZero(m) for m in masks)
        bio_ratio  = bio_pixels / total_pixels if total_pixels > 0 else 0.0

        # Consider BIO if >28% of pixels fall in natural-organic color ranges
        BIO_COLOR_THRESHOLD = 0.28
        is_bio = bio_ratio >= BIO_COLOR_THRESHOLD

        sys.stderr.write(
            f"DEBUG: Rule-Based - bio_pixels={bio_pixels}, "
            f"total={total_pixels}, bio_ratio={bio_ratio:.2%}, is_bio={is_bio}\n"
        )
        sys.stderr.flush()
        return is_bio, bio_ratio

    except Exception as e:
        import sys
        sys.stderr.write(f"DEBUG: Rule-Based Error - {str(e)}\n")
        sys.stderr.flush()
        return False, 0.0


# =========================================================
# CLASSIFY ONE FRAME (YOLOv8)
# =========================================================
def classify_frame_yolov8(frame):
    """Returns label & confidence using YOLOv8."""
    if model is None:
        return "UNKNOWN", 0.0
    
    try:
        # Ensure frame is valid
        if frame is None or frame.size == 0:
            return "UNKNOWN", 0.0
        
        # Crop to ROI before detection
        frame_roi = crop_to_roi(frame)
        if frame_roi is None or frame_roi.size == 0:
            return "UNKNOWN", 0.0
        
        # Convert BGR to RGB if needed
        if len(frame_roi.shape) == 3 and frame_roi.shape[2] == 3:
            frame_rgb = cv2.cvtColor(frame_roi, cv2.COLOR_BGR2RGB)
        else:
            frame_rgb = frame_roi
        
        # Resize for YOLOv8 (interpolate better for quality)
        img = cv2.resize(frame_rgb, (416, 416), interpolation=cv2.INTER_LINEAR)
        
        # Run inference
        results = model(img, verbose=False)
        
        # Get the top prediction
        if results and len(results) > 0:
            result = results[0]
            if hasattr(result, 'probs') and result.probs is not None:
                # Get top class
                top_idx = result.probs.top1
                confidence = float(result.probs.top1conf) * 100
                label = CLASSES[top_idx] if top_idx < len(CLASSES) else "UNKNOWN"
                
                import sys
                sys.stderr.write(f"DEBUG: YOLOv8 - Class={label} (Index={top_idx}), Confidence={confidence:.2f}%\n")
                sys.stderr.flush()
                
                # Map to BIO/NONBIO for waste sorting
                # BIO: organic waste (bio=food/leaves, trash2=cardboard - both compostable)
                # NONBIO: inorganic waste (trash1=glass, non_bio=metal/plastic)
                
                # Confidence threshold check
                CONFIDENCE_THRESHOLD = 55.0  # Only accept predictions above 55%
                if confidence < CONFIDENCE_THRESHOLD:
                    sys.stderr.write(f"DEBUG: Confidence too low ({confidence:.1f}% < {CONFIDENCE_THRESHOLD}%) - treating as uncertain\n")
                    sys.stderr.flush()
                    return "UNCERTAIN", confidence
                
                if label in ["bio", "trash2"]:
                    return "BIO", confidence
                else:
                    # ── Rule-based cross-check ──────────────────────────
                    # YOLO said NONBIO; verify with color analysis before
                    # accepting — catches fruits/vegetables misclassified
                    # as non-organic due to limited training data.
                    is_bio_by_color, bio_ratio = rule_based_bio_check(frame_roi)
                    if is_bio_by_color:
                        sys.stderr.write(
                            f"DEBUG: Rule-Based OVERRIDE – YOLO said NONBIO "
                            f"but color analysis shows BIO (ratio={bio_ratio:.2%})\n"
                        )
                        sys.stderr.flush()
                        return "BIO", confidence
                    return "NONBIO", confidence
    except Exception as e:
        import sys
        sys.stderr.write(f"DEBUG: YOLOv8 Error - {str(e)}\n")
        sys.stderr.flush()
    
    return "UNKNOWN", 0.0


def classify_frame(frame):
    """Unified detection using YOLOv8."""
    return classify_frame_yolov8(frame)

# =========================================================
# CAMERA THREAD LOOP
# =========================================================
def camera_loop():
    """Continuously captures frames in background."""
    global camera, running, last_frame

    # IMPORTANT: CAP_DSHOW fixes Windows no-camera issue
    camera = cv2.VideoCapture(0, cv2.CAP_DSHOW)
    # Increase resolution for better detection accuracy
    camera.set(cv2.CAP_PROP_FRAME_WIDTH, 1280)
    camera.set(cv2.CAP_PROP_FRAME_HEIGHT, 720)
    # Optimize for real-time performance
    camera.set(cv2.CAP_PROP_BUFFERSIZE, 1)

    while running:
        ret, frame = camera.read()
        if ret:
            last_frame = frame
        else:
            print("❌ Failed to capture frame")

    camera.release()

# =========================================================
# PUBLIC API
# =========================================================
def start_camera():
    """Start camera in background thread."""
    global running, camera
    if running:
        return

    running = True
    thread = threading.Thread(target=camera_loop, daemon=True)
    thread.start()
    print("📷 Camera thread started")

def stop_camera():
    """Stop camera."""
    global running
    running = False

def get_frame():
    """Get latest frame from camera with ROI overlay."""
    if last_frame is not None:
        # Draw ROI on frame
        frame_with_roi = draw_roi_on_frame(last_frame)
        ret, buffer = cv2.imencode('.jpg', frame_with_roi)
        if ret:
            return buffer.tobytes()
    return None
