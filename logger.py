import sqlite3
import csv
import os
import config
from datetime import datetime

DB_PATH      = config.DB_PATH
SESSIONS_DIR = config.SESSIONS_DIR

def init_db():
    os.makedirs(os.path.dirname(DB_PATH), exist_ok=True)
    os.makedirs(SESSIONS_DIR, exist_ok=True)
    conn = sqlite3.connect(DB_PATH)
    conn.execute('''
        CREATE TABLE IF NOT EXISTS sessions (
            id         INTEGER PRIMARY KEY AUTOINCREMENT,
            date       TEXT NOT NULL,
            duration   INTEGER NOT NULL,
            dominant   TEXT NOT NULL,
            csv_path   TEXT NOT NULL,
            created_at TEXT NOT NULL
        )
    ''')
    conn.commit()
    conn.close()
    print("[Logger] Database initialized.")


def resolve_csv_path(stored_path):
    """Basis data bisa berisi path absolut dari komputer lain. Berkas CSV selalu
    dicari di folder sessions proyek ini berdasarkan nama berkasnya."""
    return os.path.join(SESSIONS_DIR, os.path.basename(stored_path.replace('\\', '/')))


class SessionLogger:
    def __init__(self):
        init_db()
        self.logs      = []   # buffer log sementara
        self.start_time = None
        self.csv_path   = None

    def start(self):
        self.logs       = []
        self.start_time = datetime.now()
        session_id      = self.start_time.strftime('%Y%m%d_%H%M%S')
        self.csv_path   = os.path.join(SESSIONS_DIR, f"session_{session_id}.csv")
        print(f"[Logger] Session log started: {self.csv_path}")

    def log(self, emotion, confidence):
        if not self.start_time:
            return
        elapsed  = int((datetime.now() - self.start_time).total_seconds())
        begin    = max(0, elapsed - config.LOG_INTERVAL)
        start_ts = f"{begin//60:02d}:{begin%60:02d}"
        end_ts   = f"{elapsed//60:02d}:{elapsed%60:02d}"
        entry    = {
            'start'      : start_ts,
            'end'        : end_ts,
            'emotion'    : emotion,
            'confidence' : round(confidence, 3)
        }
        self.logs.append(entry)
        print(f"[Logger] Logged: {entry}")

    def stop(self, duration):
        if not self.logs:
            return None

        # Hitung ekspresi dominan
        emotion_counts = {}
        for entry in self.logs:
            e = entry['emotion']
            emotion_counts[e] = emotion_counts.get(e, 0) + 1
        dominant = max(emotion_counts, key=emotion_counts.get)

        # Simpan CSV
        with open(self.csv_path, 'w', newline='') as f:
            writer = csv.DictWriter(f, fieldnames=['start','end','emotion','confidence'])
            writer.writeheader()
            writer.writerows(self.logs)
        print(f"[Logger] CSV saved: {self.csv_path}")

        # Simpan metadata ke SQLite
        conn = sqlite3.connect(DB_PATH)
        cursor = conn.execute('''
            INSERT INTO sessions (date, duration, dominant, csv_path, created_at)
            VALUES (?, ?, ?, ?, ?)
        ''', (
            self.start_time.strftime('%d %b %Y'),
            duration,
            dominant,
            os.path.basename(self.csv_path),
            datetime.now().isoformat()
        ))
        new_id = cursor.lastrowid
        conn.commit()
        conn.close()
        print(f"[Logger] Metadata saved. Dominant: {dominant}")

        return {
            'id'              : new_id,
            'dominant'        : dominant,
            'emotion_counts'  : emotion_counts,
            'total_logs'      : len(self.logs),
            'csv_path'        : os.path.basename(self.csv_path)
        }

    def get_all_sessions(self):
        conn  = sqlite3.connect(DB_PATH)
        conn.row_factory = sqlite3.Row
        rows  = conn.execute(
            'SELECT * FROM sessions ORDER BY id DESC'
        ).fetchall()
        conn.close()
        return [dict(r) for r in rows]

    def get_session_detail(self, session_id):
        conn = sqlite3.connect(DB_PATH)
        conn.row_factory = sqlite3.Row
        row  = conn.execute(
            'SELECT * FROM sessions WHERE id = ?', (session_id,)
        ).fetchone()
        conn.close()
        if not row:
            return None

        session = dict(row)
        session['csv_path'] = resolve_csv_path(session['csv_path'])

        # Baca CSV untuk distribusi ekspresi
        emotion_counts = {}
        total_logs     = 0
        timeline       = []
        if os.path.exists(session['csv_path']):
            with open(session['csv_path'], 'r') as f:
                reader = csv.DictReader(f)
                for entry in reader:
                    e = entry['emotion']
                    emotion_counts[e] = emotion_counts.get(e, 0) + 1
                    total_logs += 1
                    timeline.append(entry)

        # Hitung persentase
        distribution = {}
        if total_logs > 0:
            for e, count in emotion_counts.items():
                distribution[e] = round(count / total_logs * 100, 1)

        session['distribution'] = distribution
        session['total_logs']   = total_logs
        session['timeline']     = timeline
        return session
    
    def delete_session(self, session_id):
        session = self.get_session_detail(session_id)
        if not session:
            return False
        if os.path.exists(session['csv_path']):
            os.remove(session['csv_path'])
        conn = sqlite3.connect(DB_PATH)
        conn.execute('DELETE FROM sessions WHERE id = ?', (session_id,))
        conn.commit()
        conn.close()
        return True