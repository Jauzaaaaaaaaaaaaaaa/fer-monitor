import cv2
import numpy as np
import json
import threading
import time
import config
from preprocess import siapkan_wajah
from mtcnn import MTCNN
from collections import deque, Counter
from tensorflow.keras.models import load_model
from tensorflow.keras.applications.mobilenet_v2 import preprocess_input

class Camera:

    def __init__(self, model_path=config.MODEL_PATH,
                 label_map_path=config.LABEL_MAP_PATH):

        print("[Camera] Loading model...")
        try:
            self.model     = load_model(model_path)
            self.detector  = MTCNN()
            with open(label_map_path, 'r') as f:
                raw = json.load(f)
            self.label_map = {int(k): v for k, v in raw.items()}
            self.model_error = None
            print("[Camera] Model & label map loaded:", self.label_map)
        except Exception as e:
            self.model       = None
            self.detector    = None
            self.label_map   = {}
            self.model_error = str(e)
            print(f"[Camera] ERROR loading model: {e}")

        self.IMG_SIZE      = config.IMG_SIZE

        # State webcam
        self.cap            = None
        self.is_running     = False
        self.current_frame  = None
        self.raw_frame      = None     # frame mentah tanpa anotasi
        self.current_source = 0 
        self.lock           = threading.Lock()
        self.detect_lock    = threading.Lock()

        # State sesi
        self.session_active = False
        self.session_start  = None
        self.last_log_time  = None
        self.log_callback   = None

        # State prediksi terakhir (shared antar thread)
        self.last_emotion    = None
        self.last_confidence = 0.0
        self.last_faces      = []
        self.last_preds      = []
        self.recent_preds  = deque(maxlen=config.SMOOTHING_WINDOW)

        # Resize untuk deteksi (lebih kecil = lebih cepat)
        self.DETECT_WIDTH  = config.DETECT_WIDTH
        
        self.history_buffer = deque(maxlen=config.TIMELINE_WINDOW)
        
        self.face_count      = 0

# ─── Camera source management ──────────────────────────────────

    @staticmethod
    def list_available_cameras(max_check=5, skip_index=None):
        """Scan index kamera, tapi skip index yang sedang aktif dipakai."""
        available = []
        for i in range(max_check):
            if i == skip_index:
                continue
            cap = cv2.VideoCapture(i)
            if cap.isOpened():
                ret, _ = cap.read()
                if ret:
                    available.append({'index': i, 'name': f'Camera {i}'})
                cap.release()

        # Tambahkan index aktif tanpa perlu dites ulang
        if skip_index is not None:
            available.insert(0, {'index': skip_index, 'name': f'Camera {skip_index} (aktif)'})

        return available

    def switch_source(self, source_index):
        """Ganti sumber kamera tanpa restart aplikasi."""
        was_running = self.is_running
        self.is_running = False
        time.sleep(0.2)  # beri waktu thread lama berhenti

        if self.cap:
            self.cap.release()

        self.cap = cv2.VideoCapture(source_index)
        self.cap.set(cv2.CAP_PROP_FRAME_WIDTH, 640)
        self.cap.set(cv2.CAP_PROP_FRAME_HEIGHT, 480)
        self.cap.set(cv2.CAP_PROP_FPS, 30)

        if not self.cap.isOpened():
            raise RuntimeError(f"Tidak bisa membuka kamera index {source_index}.")

        self.current_source = source_index

        if was_running:
            self.is_running = True
            threading.Thread(target=self._capture_loop, daemon=True).start()
            threading.Thread(target=self._detect_loop, daemon=True).start()

        print(f"[Camera] Switched to source: {source_index}")
        return True

    # ─── Webcam thread ────────────────────────────────────────────


    def start(self, source=0):
        if self.is_running:
            return
        self.current_source = source
        self.cap = cv2.VideoCapture(source)
        self.cap.set(cv2.CAP_PROP_FRAME_WIDTH, 640)
        self.cap.set(cv2.CAP_PROP_FRAME_HEIGHT, 480)
        self.cap.set(cv2.CAP_PROP_FPS, 30)

        if not self.cap.isOpened():
            raise RuntimeError("Webcam tidak bisa dibuka.")
        self.is_running = True

        threading.Thread(target=self._capture_loop, daemon=True).start()
        threading.Thread(target=self._detect_loop, daemon=True).start()

        print(f"[Camera] Webcam started (source: {source}).")

    def stop(self):
        self.is_running = False
        if self.cap:
            self.cap.release()
        print("[Camera] Webcam stopped.")

    def _capture_loop(self):
        """Loop cepat: cuma baca frame & gambar anotasi terakhir."""
        while self.is_running:
            ret, frame = self.cap.read()
            if not ret:
                time.sleep(0.05)
                continue

            with self.detect_lock:
                self.raw_frame = frame.copy()

            annotated = self._draw_last_annotations(frame)

            # Logging sesi
            if self.session_active and self.last_log_time:
                elapsed = time.time() - self.last_log_time
                if elapsed >= config.LOG_INTERVAL and self.last_emotion:
                    self.last_log_time = time.time()
                    if self.log_callback:
                        self.log_callback(
                            emotion    = self.last_emotion,
                            confidence = self.last_confidence
                        )

            with self.lock:
                self.current_frame = annotated

            time.sleep(0.01)  # ~max 100fps cap, webcam yang akan limit sebenarnya




    def _detect_loop(self):
        """Loop lambat: MTCNN + prediksi, jalan independen di background."""
        while self.is_running:
            with self.detect_lock:
                frame = self.raw_frame.copy() if self.raw_frame is not None else None

            if frame is None or self.detector is None:
                time.sleep(0.05)
                continue

            h, w = frame.shape[:2]
            scale = self.DETECT_WIDTH / w
            small = cv2.resize(frame, (self.DETECT_WIDTH, int(h * scale)))
            rgb_small = cv2.cvtColor(small, cv2.COLOR_BGR2RGB)

            faces = self.detector.detect_faces(rgb_small)
            preds = []
            rgb_full = cv2.cvtColor(frame, cv2.COLOR_BGR2RGB)

            for face in faces:
                x, y, fw, fh = face['box']
                face['box'] = [int(x/scale), int(y/scale), int(fw/scale), int(fh/scale)]
                emotion, confidence = self._predict_emotion(rgb_full, face)
                preds.append((emotion, confidence))

            self.last_faces = faces
            self.last_preds = preds
            self.face_count = len(faces)

            if preds:
                raw_emotion, raw_confidence = preds[0]
                self.recent_preds.append((raw_emotion, raw_confidence))
                self.history_buffer.append(raw_emotion)
                self.last_emotion, self.last_confidence = self._get_smoothed_emotion()
            else:
                self.recent_preds.clear()
                self.last_emotion, self.last_confidence = None, 0.0

            time.sleep(0.05)

    def _get_smoothed_emotion(self):
        """Majority voting dari beberapa deteksi terakhir untuk stabilkan hasil."""
        if not self.recent_preds:
            return None, 0.0

        emotions = [e for e, c in self.recent_preds]
        majority = Counter(emotions).most_common(1)[0][0]

        confidences = [c for e, c in self.recent_preds if e == majority]
        avg_confidence = sum(confidences) / len(confidences)

        return majority, avg_confidence

    # ─── Proses & anotasi ─────────────────────────────────────────

    def _draw_last_annotations(self, frame):
        annotated   = frame.copy()
        primary_idx = self._get_primary_face_index(self.last_faces)

        for i, face in enumerate(self.last_faces):
            if i < len(self.last_preds):
                emotion, confidence = self.last_preds[i]
                is_primary = (i == primary_idx)
                annotated  = self._draw_annotation(annotated, face, emotion, confidence, is_primary)

        if self.session_active:
            elapsed = int(time.time() - self.session_start)
            label   = f"REC  {elapsed//60:02d}:{elapsed%60:02d}"
            cv2.putText(annotated, label, (10, 30),
                        cv2.FONT_HERSHEY_SIMPLEX, 0.7, (0, 0, 255), 2)

        return annotated

    def _predict_emotion(self, rgb_frame, face):
        if self.model is None:
            return "model_error", 0.0

        x, y, w, h = face['box']
        x, y = max(0, x), max(0, y)
        face_crop = rgb_frame[y:y+h, x:x+w]
        if face_crop.size == 0:
            return "unknown", 0.0

        face_input = preprocess_input(np.expand_dims(siapkan_wajah(face_crop), axis=0))

        preds      = self.model.predict(face_input, verbose=0)[0]
        class_idx  = int(np.argmax(preds))
        confidence = float(np.max(preds))
        emotion    = self.label_map.get(class_idx, "unknown")

        return emotion, confidence
    
    @staticmethod
    def _get_primary_face_index(faces):
        """Pilih wajah dengan area bounding box terbesar sebagai subjek utama
        yang dicatat ke logging. Lebih stabil dibanding index pertama yang
        urutannya bisa berubah antar frame pada deteksi multi-wajah."""
        if not faces:
            return None
        areas = [f['box'][2] * f['box'][3] for f in faces]
        return int(np.argmax(areas))


    def _draw_annotation(self, frame, face, emotion, confidence, is_primary=False):
        x, y, w, h = face['box']
        x, y = max(0, x), max(0, y)

        colors = {
            'happy':    (0, 200, 0),
            'sad':      (200, 100, 0),
            'angry':    (0, 0, 220),
            'fear':     (180, 0, 180),
            'surprise': (0, 180, 220),
            'disgust':  (0, 140, 140),
            'neutral':  (160, 160, 160)
        }
        color     = colors.get(emotion, (200, 200, 200))
        thickness = 3 if is_primary else 1   # subjek utama lebih tebal

        cv2.rectangle(frame, (x, y), (x+w, y+h), color, thickness)

        prefix = "* " if is_primary else ""   # tanda subjek yang dicatat
        label  = f"{prefix}{emotion.upper()}  {confidence*100:.0f}%"
        (lw, lh), _ = cv2.getTextSize(label, cv2.FONT_HERSHEY_SIMPLEX, 0.6, 2)
        cv2.rectangle(frame, (x, y-lh-12), (x+lw+8, y), color, -1)
        cv2.putText(frame, label, (x+4, y-6),
                    cv2.FONT_HERSHEY_SIMPLEX, 0.6, (255, 255, 255), 2)

        return frame

    # ─── MJPEG generator ──────────────────────────────────────────

    def generate_frames(self):
        while True:
            with self.lock:
                frame = self.current_frame
            if frame is None:
                time.sleep(0.03)
                continue
            _, buffer = cv2.imencode('.jpg', frame, [cv2.IMWRITE_JPEG_QUALITY, 75])
            yield (b'--frame\r\n'
                   b'Content-Type: image/jpeg\r\n\r\n' +
                   buffer.tobytes() + b'\r\n')
            time.sleep(0.03)

    # ─── Session control ──────────────────────────────────────────

    def start_session(self, log_callback=None):
        self.session_active = True
        self.session_start  = time.time()
        self.last_log_time  = time.time()
        self.log_callback   = log_callback
        print("[Camera] Session started.")

    def stop_session(self):
        self.session_active = False
        duration = int(time.time() - self.session_start) if self.session_start else 0
        self.log_callback = None
        print(f"[Camera] Session stopped. Duration: {duration}s")
        return duration

    def get_status(self):
        elapsed = 0
        if self.session_active and self.session_start:
            elapsed = int(time.time() - self.session_start)
        return {
            'session_active': self.session_active,
            'emotion'       : self.last_emotion,
            'confidence'    : round(self.last_confidence * 100, 1),
            'elapsed'       : elapsed,
            'face_count'    : self.face_count        
        }
        
    def get_recent_distribution(self):
        if not self.history_buffer:
            return {}
        counts = Counter(self.history_buffer)
        total  = sum(counts.values())
        return {k: round(v / total * 100, 1) for k, v in counts.items()}
