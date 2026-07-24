"""
Lightweight image analysis for the recommender.

Three signals extracted from an uploaded image:
    - image_colour_theme  : dominant colour palette named in project vocabulary
    - has_face_in_image   : Haar cascade face detection
    - text_on_image       : edge-density heuristic (upper half + centre band)

Deliberately simple. No vision model, no download. Everything runs on the
image bytes in memory. Under 200ms per image on a typical laptop.

The named palette maps to the vocabulary already used in the tagging file so
downstream models don't need retraining.
"""

import io
import numpy as np
from PIL import Image
import cv2
from sklearn.cluster import KMeans


# Some OpenCV builds (5.x headless in particular) shipped without the classic
# Haar cascade module. Detect that once at import so we don't crash the whole
# analysis flow when only face detection is unavailable.
_FACE_CASCADE = None
_FACE_UNAVAILABLE_REASON = None
try:
    if hasattr(cv2, "CascadeClassifier"):
        _cascade_path = cv2.data.haarcascades + "haarcascade_frontalface_default.xml"
        _cascade = cv2.CascadeClassifier(_cascade_path)
        if not _cascade.empty():
            _FACE_CASCADE = _cascade
        else:
            _FACE_UNAVAILABLE_REASON = "cascade file missing or empty"
    else:
        _FACE_UNAVAILABLE_REASON = (
            f"cv2 {cv2.__version__} has no CascadeClassifier. Install "
            "opencv-python-headless<5 to enable face detection.")
except Exception as e:
    _FACE_UNAVAILABLE_REASON = f"could not init cascade ({e})"


def face_detection_available():
    """Report whether face detection can run in this environment."""
    return _FACE_CASCADE is not None, _FACE_UNAVAILABLE_REASON


# Mapping from a colour classification to the palette phrases the tagging file
# actually uses. The predictor's OneHotEncoder was fitted on these strings.
KNOWN_PALETTES = [
    "brand-teal + accent-purple + photographic",
    "brand-teal + cream + photographic",
    "brand-teal + gold + photographic",
    "brand-teal + gold + cream",
    "brand-teal + white + photographic",
    "brand-teal + cream + white",
    "cream + brand-teal + gold",
    "dark navy + brand-teal + white",
    "photographic + brand-teal",
    "orange + white + brand-teal",
    "brand-teal + gold + accent-red",
    "brand-teal (dark) + white",
]


def _load(image_input):
    """Accept UploadedFile / BytesIO / bytes / path. Return an RGB numpy array,
    resized so the long edge is 640 px for speed."""
    if hasattr(image_input, "read"):
        data = image_input.read()
        # rewind so the caller can reuse the file for preview
        try:
            image_input.seek(0)
        except Exception:
            pass
        img = Image.open(io.BytesIO(data)).convert("RGB")
    elif isinstance(image_input, (bytes, bytearray)):
        img = Image.open(io.BytesIO(image_input)).convert("RGB")
    else:
        img = Image.open(image_input).convert("RGB")
    img.thumbnail((640, 640))
    return np.array(img)


def _dominant_colours(arr, k=5):
    pixels = arr.reshape(-1, 3).astype(np.float32)
    if len(pixels) > 20000:
        rng = np.random.default_rng(0)
        idx = rng.choice(len(pixels), 20000, replace=False)
        pixels = pixels[idx]
    km = KMeans(n_clusters=k, n_init=3, random_state=0)
    km.fit(pixels)
    counts = np.bincount(km.labels_, minlength=k)
    order = np.argsort(-counts)
    return km.cluster_centers_[order], counts[order] / counts.sum()


def _classify(rgb):
    """Return a rough named tag for a single dominant colour."""
    r, g, b = [float(v) for v in rgb]
    lo = min(r, g, b)
    hi = max(r, g, b)
    sat = hi - lo
    # near-neutral (grey / photographic)
    if sat < 22:
        if hi < 70:
            return "dark"
        if hi > 200:
            return "cream" if r > g + 5 else "white"
        return "photographic"
    # cream / warm off-white
    if r > 210 and g > 195 and b > 155 and r >= g >= b:
        return "cream"
    # gold / warm yellow
    if r > 190 and g > 140 and b < 120 and r > b and g > b:
        return "gold"
    # orange
    if r > 200 and 90 < g < 175 and b < 100:
        return "accent-orange"
    # accent red
    if r > 170 and g < 90 and b < 90:
        return "accent-red"
    # teal / green-blue (GrantsNow brand)
    if g > 70 and b > 55 and g > r + 15 and b > r + 10:
        if hi < 130:
            return "brand-teal (dark)"
        return "brand-teal"
    # purple
    if r > 90 and b > 130 and b > g and r > g:
        return "accent-purple"
    # blue navy
    if b > r + 25 and b > g + 15:
        return "dark navy" if b < 150 else "blue"
    # bright / light
    if lo > 175:
        return "cream" if r > b else "white"
    return "photographic"


def _match_known_palette(named):
    """Best-match against the vocabulary the model was trained on."""
    named_set = set(named)
    best = None
    best_hit = -1
    for candidate in KNOWN_PALETTES:
        tokens = [t.strip() for t in candidate.split("+")]
        hit = sum(1 for t in tokens if t in named_set)
        if hit > best_hit:
            best_hit = hit
            best = candidate
    return best if best_hit >= 1 else " + ".join(named[:3])


def detect_palette(arr):
    colours, weights = _dominant_colours(arr, k=5)
    named = []
    for c in colours:
        tag = _classify(c)
        if tag not in named:
            named.append(tag)
        if len(named) >= 3:
            break
    return _match_known_palette(named), named


def detect_face(arr):
    """Returns True if a face is detected. Returns False silently when the
    OpenCV build does not include the Haar cascade module (e.g. cv2 5.x
    headless). Check face_detection_available() to know which case applied."""
    if _FACE_CASCADE is None:
        return False
    gray = cv2.cvtColor(arr, cv2.COLOR_RGB2GRAY)
    faces = _FACE_CASCADE.detectMultiScale(
        gray, scaleFactor=1.1, minNeighbors=4,
        minSize=(40, 40))
    return len(faces) > 0


def detect_text_on_image(arr):
    """Edge density in the middle band of the image. Overlaid text has many
    small edges packed together which pushes the density well above a plain
    solid-colour panel or a photo without text."""
    gray = cv2.cvtColor(arr, cv2.COLOR_RGB2GRAY)
    edges = cv2.Canny(gray, 100, 200) / 255.0
    h, w = edges.shape
    centre = edges[h // 6: h * 5 // 6, w // 6: w * 5 // 6]
    # 0.025 was tuned on synthetic and real posts: solid card ~0.01,
    # card with prominent overlay text ~0.04+
    return float(centre.mean()) > 0.025


def analyze(image_input):
    """One call, returns everything the predictor needs."""
    arr = _load(image_input)
    palette, raw_named = detect_palette(arr)
    face = detect_face(arr)
    text = detect_text_on_image(arr)
    return {
        "image_colour_theme": palette,
        "has_face_in_image": "yes" if face else "no",
        "text_on_image": "yes" if text else "no",
        "raw_colours": raw_named,
        "face_detection_available": _FACE_CASCADE is not None,
        "face_detection_note": _FACE_UNAVAILABLE_REASON,
    }
