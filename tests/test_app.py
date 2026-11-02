"""Uji rute dan pencatatan sesi tanpa webcam dan tanpa memuat model.

Jalankan dari folder proyek: python -m unittest discover -s tests -v
"""
import csv
import os
import shutil
import sqlite3
import sys
import tempfile
import types
import unittest

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, ROOT)

import config  # noqa: E402

TMP = tempfile.mkdtemp(prefix='fer-test-')
config.DB_PATH = os.path.join(TMP, 'database', 'fer.db')
config.SESSIONS_DIR = os.path.join(TMP, 'sessions')


class KameraTiruan:
    model = object()
    model_error = None
    is_running = True
    current_source = 0

    def start(self, source=0):
        pass

    def start_session(self, log_callback=None):
        self.cb = log_callback

    def stop_session(self):
        return 12

    @staticmethod
    def list_available_cameras(max_check=5, skip_index=None):
        return [{'index': 0, 'name': 'Camera 0 (aktif)'}]

    def switch_source(self, i):
        if i == 9:
            raise RuntimeError('tidak ada')

    def generate_frames(self):
        return iter(())

    def get_status(self):
        return {'session_active': False, 'emotion': 'happy', 'confidence': 80.0, 'elapsed': 0, 'face_count': 1}

    def get_recent_distribution(self):
        return {'happy': 100.0}


tiruan = types.ModuleType('camera')
tiruan.Camera = KameraTiruan
sys.modules['camera'] = tiruan

import app as fer  # noqa: E402
import logger as lg  # noqa: E402


def tearDownModule():
    shutil.rmtree(TMP, ignore_errors=True)


class Dasar(unittest.TestCase):
    def setUp(self):
        self.c = fer.app.test_client()
        conn = sqlite3.connect(config.DB_PATH)
        conn.execute('DELETE FROM sessions')
        conn.commit()
        conn.close()

    def rekam(self, *emosi):
        self.c.post('/api/start')
        for e in emosi:
            fer.logger.log(e, 0.9)
        return self.c.post('/api/stop').get_json()


class TesHalaman(Dasar):
    def test_semua_halaman_terbuka(self):
        for p in ('/', '/history', '/model'):
            self.assertEqual(self.c.get(p).status_code, 200, p)

    def test_halaman_model_menyebut_akurasi_sebenarnya(self):
        self.assertIn('Tebakan acak', self.c.get('/model').get_data(as_text=True))
        self.assertNotIn('42,5%', self.c.get('/model').get_data(as_text=True))

    def test_sesi_tidak_dikenal_404(self):
        self.assertEqual(self.c.get('/history/999').status_code, 404)
        self.assertEqual(self.c.get('/download/999').status_code, 404)
        self.assertEqual(self.c.post('/api/session/999/delete').status_code, 404)


class TesApi(Dasar):
    def test_status_memuat_jumlah_wajah(self):
        self.assertEqual(self.c.get('/api/status').get_json()['face_count'], 1)

    def test_sumber_kamera_tidak_valid_mengembalikan_400(self):
        self.assertEqual(self.c.post('/api/camera/switch', json={'source': 'abc'}).status_code, 400)
        self.assertEqual(self.c.post('/api/camera/switch', json={'source': 9}).status_code, 400)
        self.assertEqual(self.c.post('/api/camera/switch', json={'source': 0}).status_code, 200)


class TesSesi(Dasar):
    def test_sesi_tanpa_log_tidak_disimpan(self):
        self.assertEqual(self.rekam()['status'], 'no_data')
        self.assertEqual(fer.logger.get_all_sessions(), [])

    def test_sesi_mengembalikan_id_dan_ekspresi_dominan(self):
        hasil = self.rekam('happy', 'happy', 'sad')['result']
        self.assertEqual(hasil['dominant'], 'happy')
        self.assertEqual(hasil['total_logs'], 3)
        halaman = self.c.get(f"/history/{hasil['id']}")
        self.assertEqual(halaman.status_code, 200)
        self.assertIn('Garis waktu', halaman.get_data(as_text=True))

    def test_waktu_awal_log_tidak_negatif(self):
        hasil = self.rekam('happy')['result']
        detail = fer.logger.get_session_detail(hasil['id'])
        self.assertEqual(detail['timeline'][0]['start'], '00:00')

    def test_unduh_dan_hapus(self):
        sid = self.rekam('sad')['result']['id']
        self.assertEqual(self.c.get(f'/download/{sid}').status_code, 200)
        self.assertEqual(self.c.post(f'/api/session/{sid}/delete').get_json()['status'], 'deleted')
        self.assertEqual(self.c.get(f'/history/{sid}').status_code, 404)

    def test_path_csv_dari_komputer_lain_tetap_terbaca(self):
        nama = 'session_lama.csv'
        with open(os.path.join(config.SESSIONS_DIR, nama), 'w', newline='') as f:
            w = csv.DictWriter(f, fieldnames=['start', 'end', 'emotion', 'confidence'])
            w.writeheader()
            w.writerow({'start': '00:00', 'end': '00:05', 'emotion': 'neutral', 'confidence': 0.4})
        conn = sqlite3.connect(config.DB_PATH)
        cur = conn.execute('INSERT INTO sessions (date, duration, dominant, csv_path, created_at) VALUES (?,?,?,?,?)',
                           ('19 Jun 2026', 5, 'neutral', 'D:\\Tugas\\citra-digital\\sessions\\' + nama, '2026-06-19'))
        sid = cur.lastrowid
        conn.commit()
        conn.close()
        self.assertEqual(fer.logger.get_session_detail(sid)['total_logs'], 1)
        self.assertEqual(self.c.get(f'/download/{sid}').status_code, 200)

    def test_nama_berkas_tidak_bisa_keluar_dari_folder_sessions(self):
        hasil = lg.resolve_csv_path('..\\..\\rahasia.csv')
        self.assertEqual(os.path.dirname(hasil), config.SESSIONS_DIR)


if __name__ == '__main__':
    unittest.main()
