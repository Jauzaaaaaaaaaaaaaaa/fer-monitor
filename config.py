import os

# Paths
BASE_DIR        = os.path.dirname(os.path.abspath(__file__))
MODEL_PATH       = os.path.join(BASE_DIR, 'model', 'fer_model_best.keras')
LABEL_MAP_PATH   = os.path.join(BASE_DIR, 'model', 'label_map.json')
DB_PATH          = os.path.join(BASE_DIR, 'database', 'fer.db')
SESSIONS_DIR     = os.path.join(BASE_DIR, 'sessions')
LOG_FILE         = os.path.join(BASE_DIR, 'app.log')

# Model & detection
IMG_SIZE         = 96
DETECT_WIDTH     = 320
SMOOTHING_WINDOW = 15      # jumlah frame untuk temporal smoothing
TIMELINE_WINDOW  = 60      # jumlah deteksi untuk live timeline chart

# Session
LOG_INTERVAL     = 5       # detik antar log CSV

# Flask
HOST  = '127.0.0.1'
PORT  = 5000
DEBUG = False