"""Menyiapkan wajah agar sama dengan data saat model dilatih.

Model dilatih pada gambar abu-abu 48 x 48 yang diperbesar ke ukuran masukan dengan
metode nearest (bawaan Keras flow_from_directory). Kamera menghasilkan gambar berwarna
beresolusi tinggi, jadi harus diubah ke bentuk yang sama sebelum diprediksi.
"""
import cv2
import numpy as np

import config

UKURAN_ASLI = 48


def siapkan_wajah(rgb_crop):
    """Menerima potongan wajah RGB, mengembalikan larik float32 ukuran masukan model."""
    abu = cv2.cvtColor(rgb_crop, cv2.COLOR_RGB2GRAY)
    if abu.shape[0] != UKURAN_ASLI or abu.shape[1] != UKURAN_ASLI:
        abu = cv2.resize(abu, (UKURAN_ASLI, UKURAN_ASLI), interpolation=cv2.INTER_AREA)
    besar = cv2.resize(abu, (config.IMG_SIZE, config.IMG_SIZE), interpolation=cv2.INTER_NEAREST)
    return np.stack([besar] * 3, axis=-1).astype(np.float32)
