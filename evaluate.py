"""Mengukur model yang dipakai aplikasi pada folder uji berstruktur <folder>/<ekspresi>/*.jpg.

Pemakaian: python evaluate.py <folder_uji> [berkas_hasil.json]
Prapemrosesan sama dengan camera.py, lewat preprocess.siapkan_wajah.
"""
import json
import os
import sys

os.environ.setdefault('TF_CPP_MIN_LOG_LEVEL', '3')

import cv2
import numpy as np
from tensorflow.keras.applications.mobilenet_v2 import preprocess_input
from tensorflow.keras.models import load_model

import config
from preprocess import siapkan_wajah


def muat_gambar(path):
    img = cv2.imread(path)
    if img is None:
        return None
    return siapkan_wajah(cv2.cvtColor(img, cv2.COLOR_BGR2RGB))


def evaluasi(folder):
    with open(config.LABEL_MAP_PATH, encoding='utf-8') as f:
        label_map = {int(k): v for k, v in json.load(f).items()}
    kelas = [label_map[i] for i in sorted(label_map)]
    model = load_model(config.MODEL_PATH)

    benar, tebakan = [], []
    for idx, nama in enumerate(kelas):
        d = os.path.join(folder, nama)
        if not os.path.isdir(d):
            continue
        files = sorted(os.listdir(d))
        for i in range(0, len(files), 128):
            imgs = [muat_gambar(os.path.join(d, n)) for n in files[i:i + 128]]
            imgs = [m for m in imgs if m is not None]
            if not imgs:
                continue
            pred = model.predict(preprocess_input(np.stack(imgs)), verbose=0).argmax(1)
            tebakan.extend(pred.tolist())
            benar.extend([idx] * len(imgs))
        print(f'{nama}: selesai, total {len(benar)}', flush=True)

    y, p, n = np.array(benar), np.array(tebakan), len(kelas)
    cm = np.zeros((n, n), dtype=int)
    for a, b in zip(y, p):
        cm[a, b] += 1
    per_kelas = {}
    for i, nama in enumerate(kelas):
        tp = cm[i, i]
        prec = tp / cm[:, i].sum() if cm[:, i].sum() else 0.0
        rec = tp / cm[i].sum() if cm[i].sum() else 0.0
        f1 = 2 * prec * rec / (prec + rec) if prec + rec else 0.0
        per_kelas[nama] = {'precision': round(float(prec), 3), 'recall': round(float(rec), 3),
                           'f1': round(float(f1), 3), 'support': int(cm[i].sum())}
    return {
        'kelas': kelas,
        'jumlah': int(len(y)),
        'accuracy': round(float((y == p).mean()), 4),
        'macro_f1': round(float(np.mean([v['f1'] for v in per_kelas.values()])), 4),
        'per_kelas': per_kelas,
        'confusion': cm.tolist(),
    }


if __name__ == '__main__':
    hasil = evaluasi(sys.argv[1])
    keluaran = sys.argv[2] if len(sys.argv) > 2 else os.path.join(config.BASE_DIR, 'model', 'evaluasi.json')
    with open(keluaran, 'w', encoding='utf-8') as f:
        json.dump(hasil, f, indent=1)
    print(json.dumps({k: hasil[k] for k in ('jumlah', 'accuracy', 'macro_f1')}))
    for k, v in hasil['per_kelas'].items():
        print(k, v)
