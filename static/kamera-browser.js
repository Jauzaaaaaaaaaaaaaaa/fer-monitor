/* Demo tanpa server: kamera dibuka di browser pengunjung dan model berjalan di perangkatnya.
   Tidak ada video atau gambar yang dikirim ke mana pun. Halaman ini memanggil /api/* seperti
   aplikasi Flask, jadi jawabannya disediakan di sini dengan alur yang sama seperti camera.py. */
(function () {
  /* Gambar pengganti di halaman demo selesai dimuat sebelum fungsi aslinya terdefinisi. */
  window.hideLoading = window.hideLoading || function () {};
  var DASAR = document.currentScript.src.replace(/[^/]+$/, '');
  var CDN = 'https://cdn.jsdelivr.net/npm/';
  var LITERT = CDN + '@litertjs/core@2.6.0/';
  var MEDIAPIPE = CDN + '@mediapipe/tasks-vision@0.10.14/';
  var LABEL = ['angry', 'disgust', 'fear', 'happy', 'neutral', 'sad', 'surprise'];
  var WARNA = { happy: '#2fbf5b', sad: '#3f8fe0', angry: '#e24b4b', fear: '#b04fd0', surprise: '#e0a52f', disgust: '#2f9f9f', neutral: '#a0a0a0' };
  var SMOOTHING = 15, TIMELINE = 60, UKURAN_ASLI = 48, UKURAN = 96, LOG_DETIK = 5;

  var video, kanvas, ctx, tombol, pesan;
  var TensorLiteRt = null, model = null, detektor = null, aliran = null, berjalan = false, siap = false;
  var terakhir = [], riwayat = [], jejak = [], emosi = null, keyakinan = 0, jumlahWajah = 0;
  var sesi = null, kameraAktif = '', potong = document.createElement('canvas');
  potong.width = potong.height = UKURAN_ASLI;
  var ctxPotong = potong.getContext('2d', { willReadFrequently: true });

  function jawab(o, kode) {
    return Promise.resolve(new Response(JSON.stringify(o), { status: kode || 200, headers: { 'content-type': 'application/json' } }));
  }

  function susunTampilan() {
    var wadah = document.querySelector('.video-wrapper');
    var feed = document.getElementById('video-feed');
    var muat = document.getElementById('video-loading');
    if (feed) feed.style.display = 'none';
    if (muat) muat.classList.add('hidden');
    video = document.createElement('video');
    video.id = 'kamera-video';
    video.muted = true; video.playsInline = true; video.setAttribute('playsinline', '');
    video.style.cssText = 'width:100%;height:100%;object-fit:cover;display:block;';
    kanvas = document.createElement('canvas');
    kanvas.style.cssText = 'position:absolute;inset:0;width:100%;height:100%;pointer-events:none;';
    ctx = kanvas.getContext('2d');
    wadah.insertBefore(video, wadah.firstChild);
    wadah.insertBefore(kanvas, video.nextSibling);

    var lapisan = document.createElement('div');
    lapisan.id = 'kamera-mulai';
    lapisan.style.cssText = 'position:absolute;inset:0;display:flex;flex-direction:column;align-items:center;justify-content:center;gap:12px;padding:24px;text-align:center;';
    tombol = document.createElement('button');
    tombol.type = 'button';
    tombol.className = 'btn-primary';
    tombol.textContent = 'Nyalakan Kamera';
    tombol.style.width = 'auto';
    pesan = document.createElement('p');
    pesan.style.cssText = 'margin:0;max-width:44ch;color:#d7e3e0;font-size:.82rem;line-height:1.5;';
    pesan.textContent = 'Model berjalan di browser Anda. Video tidak dikirim atau disimpan.';
    lapisan.appendChild(tombol);
    lapisan.appendChild(pesan);
    wadah.appendChild(lapisan);
    tombol.addEventListener('click', function () { mulai(); });
  }

  function tulisPesan(teks, salah) {
    pesan.textContent = teks;
    pesan.style.color = salah ? '#ffb4ab' : '#d7e3e0';
  }

  async function muatModel() {
    if (siap) return;
    tulisPesan('Memuat model, sekitar 5 MB...');
    var litert = await import(LITERT + '+esm');
    await litert.loadLiteRt(LITERT + 'wasm/');
    TensorLiteRt = litert.Tensor;
    model = await litert.loadAndCompile(DASAR + 'model-browser/fer_model.tflite', { accelerator: 'wasm' });
    var vision = await import(MEDIAPIPE + 'vision_bundle.mjs');
    var berkas = await vision.FilesetResolver.forVisionTasks(MEDIAPIPE + 'wasm');
    detektor = await vision.FaceDetector.createFromOptions(berkas, {
      baseOptions: { modelAssetPath: DASAR + 'model-browser/blaze_face_short_range.tflite', delegate: 'CPU' },
      runningMode: 'VIDEO',
      minDetectionConfidence: 0.5
    });
    siap = true;
  }

  async function bukaKamera(idPerangkat) {
    if (aliran) aliran.getTracks().forEach(function (t) { t.stop(); });
    var syarat = { width: { ideal: 640 }, height: { ideal: 480 } };
    if (idPerangkat) syarat.deviceId = { exact: idPerangkat };
    aliran = await navigator.mediaDevices.getUserMedia({ video: syarat, audio: false });
    video.srcObject = aliran;
    await video.play();
    kanvas.width = video.videoWidth;
    kanvas.height = video.videoHeight;
    kameraAktif = aliran.getVideoTracks()[0].getSettings().deviceId || '';
  }

  async function mulai() {
    if (!navigator.mediaDevices || !navigator.mediaDevices.getUserMedia) {
      tulisPesan('Browser ini tidak mendukung akses kamera.', true);
      return;
    }
    tombol.disabled = true;
    try {
      await bukaKamera();
      await muatModel();
      document.getElementById('kamera-mulai').style.display = 'none';
      berjalan = true;
      if (typeof window.loadCameraList === 'function') window.loadCameraList();
      setTimeout(putaran, 0);
    } catch (e) {
      tombol.disabled = false;
      if (aliran) aliran.getTracks().forEach(function (t) { t.stop(); });
      if (e.name === 'NotAllowedError') tulisPesan('Izin kamera ditolak. Izinkan kamera di pengaturan browser, lalu coba lagi.', true);
      else if (e.name === 'NotFoundError') tulisPesan('Kamera tidak ditemukan di perangkat ini.', true);
      else if (e.name === 'NotReadableError') tulisPesan('Kamera sedang dipakai aplikasi lain. Tutup aplikasi itu, lalu coba lagi.', true);
      else tulisPesan('Gagal memulai: ' + e.message, true);
    }
  }

  /* Sama dengan preprocess.py dan preprocess_input MobileNetV2: abu-abu 48 x 48,
     diperbesar nearest ke 96 x 96, tiga kanal, lalu skala -1 sampai 1. */
  function siapkanWajah(k) {
    ctxPotong.imageSmoothingEnabled = true;
    ctxPotong.imageSmoothingQuality = 'high';
    ctxPotong.drawImage(video, k.x, k.y, k.w, k.h, 0, 0, UKURAN_ASLI, UKURAN_ASLI);
    var d = ctxPotong.getImageData(0, 0, UKURAN_ASLI, UKURAN_ASLI).data;
    var abu = new Float32Array(UKURAN_ASLI * UKURAN_ASLI);
    for (var i = 0; i < abu.length; i++) abu[i] = 0.299 * d[i * 4] + 0.587 * d[i * 4 + 1] + 0.114 * d[i * 4 + 2];
    var keluar = new Float32Array(UKURAN * UKURAN * 3);
    for (var y = 0; y < UKURAN; y++) {
      for (var x = 0; x < UKURAN; x++) {
        var nilai = abu[(y >> 1) * UKURAN_ASLI + (x >> 1)] / 127.5 - 1;
        var p = (y * UKURAN + x) * 3;
        keluar[p] = keluar[p + 1] = keluar[p + 2] = nilai;
      }
    }
    return keluar;
  }

  async function prediksi(k) {
    var masuk = new TensorLiteRt(siapkanWajah(k), [1, UKURAN, UKURAN, 3]);
    var hasil = await model.run(masuk);
    var keluaran = await hasil[0].moveTo('wasm');
    var nilai = keluaran.toTypedArray().slice();
    masuk.delete();
    keluaran.delete();
    var terbaik = 0;
    for (var i = 1; i < nilai.length; i++) if (nilai[i] > nilai[terbaik]) terbaik = i;
    return { emosi: LABEL[terbaik], yakin: nilai[terbaik] };
  }

  function gambar() {
    ctx.clearRect(0, 0, kanvas.width, kanvas.height);
    var utama = terakhir.length ? terakhir.reduce(function (a, b) { return a.w * a.h >= b.w * b.h ? a : b; }) : null;
    terakhir.forEach(function (w) {
      var warna = WARNA[w.emosi] || '#ccc';
      ctx.strokeStyle = warna;
      ctx.lineWidth = w === utama ? 3 : 1;
      ctx.strokeRect(w.x, w.y, w.w, w.h);
      var teks = (w === utama ? '* ' : '') + w.emosi.toUpperCase() + '  ' + Math.round(w.yakin * 100) + '%';
      ctx.font = '600 15px system-ui, sans-serif';
      var lebar = ctx.measureText(teks).width + 12, atas = Math.max(0, w.y - 24);
      ctx.fillStyle = warna;
      ctx.fillRect(w.x, atas, lebar, 24);
      ctx.fillStyle = '#fff';
      ctx.fillText(teks, w.x + 6, atas + 17);
    });
  }

  function haluskan() {
    var hitung = {};
    riwayat.forEach(function (r) { hitung[r.emosi] = (hitung[r.emosi] || 0) + 1; });
    var mayoritas = Object.keys(hitung).sort(function (a, b) { return hitung[b] - hitung[a]; })[0];
    var sama = riwayat.filter(function (r) { return r.emosi === mayoritas; });
    emosi = mayoritas;
    keyakinan = sama.reduce(function (s, r) { return s + r.yakin; }, 0) / sama.length;
  }

  async function putaran() {
    if (!berjalan) return;
    try {
      if (video.readyState >= 2) {
        var deteksi = detektor.detectForVideo(video, performance.now()).detections || [];
        var wajah = [];
        for (var i = 0; i < Math.min(deteksi.length, 4); i++) {
          var b = deteksi[i].boundingBox;
          var x = Math.max(0, b.originX), y = Math.max(0, b.originY);
          var k = { x: x, y: y, w: Math.min(b.width, video.videoWidth - x), h: Math.min(b.height, video.videoHeight - y) };
          if (k.w <= 0 || k.h <= 0) continue;
          var h = await prediksi(k);
          k.emosi = h.emosi; k.yakin = h.yakin;
          wajah.push(k);
        }
        terakhir = wajah;
        jumlahWajah = wajah.length;
        if (wajah.length) {
          var utama = wajah.reduce(function (a, c) { return a.w * a.h >= c.w * c.h ? a : c; });
          riwayat.push({ emosi: utama.emosi, yakin: utama.yakin });
          if (riwayat.length > SMOOTHING) riwayat.shift();
          jejak.push(utama.emosi);
          if (jejak.length > TIMELINE) jejak.shift();
          haluskan();
        } else {
          riwayat = [];
          emosi = null;
          keyakinan = 0;
        }
        if (sesi && emosi && performance.now() - sesi.logTerakhir >= LOG_DETIK * 1000) {
          sesi.logTerakhir = performance.now();
          sesi.log.push(emosi);
        }
        gambar();
      }
    } catch (e) {
      console.error('[kamera-browser] ' + (e && e.stack || e));
    }
    setTimeout(putaran, 120);
  }

  function distribusi() {
    var hasil = {};
    jejak.forEach(function (e) { hasil[e] = (hasil[e] || 0) + 1; });
    Object.keys(hasil).forEach(function (k) { hasil[k] = Math.round(hasil[k] / jejak.length * 1000) / 10; });
    return hasil;
  }

  async function daftarKamera() {
    if (!navigator.mediaDevices || !navigator.mediaDevices.enumerateDevices) return [];
    var alat = await navigator.mediaDevices.enumerateDevices();
    return alat.filter(function (a) { return a.kind === 'videoinput'; }).map(function (a, i) {
      return { index: a.deviceId || String(i), name: a.label || 'Kamera ' + (i + 1) };
    });
  }

  function selesaiSesi() {
    var durasi = Math.round((performance.now() - sesi.mulai) / 1000);
    var hitung = {};
    sesi.log.forEach(function (e) { hitung[e] = (hitung[e] || 0) + 1; });
    var dominan = Object.keys(hitung).sort(function (a, b) { return hitung[b] - hitung[a]; })[0];
    var jumlah = sesi.log.length;
    sesi = null;
    /* Riwayat di demo berisi contoh, jadi sesi pengunjung hanya diringkas dan tidak disimpan. */
    setTimeout(function () {
      var tautan = document.getElementById('result-link');
      if (tautan) tautan.classList.add('hidden');
    }, 300);
    if (!jumlah) return { status: 'no_data', durasi: durasi };
    return { status: 'stopped', result: { dominant: dominan, total_logs: jumlah } };
  }

  var fetchLama = window.fetch;
  window.fetch = function (u, o) {
    var alamat = String(u);
    if (alamat.indexOf('/api/status') > -1) {
      return jawab({
        session_active: !!sesi,
        emotion: emosi,
        confidence: Math.round(keyakinan * 1000) / 10,
        elapsed: sesi ? Math.round((performance.now() - sesi.mulai) / 1000) : 0,
        face_count: jumlahWajah
      });
    }
    if (alamat.indexOf('/api/timeline') > -1) return jawab(distribusi());
    if (alamat.indexOf('/api/health') > -1) return jawab({ model_loaded: true, model_error: null, camera_running: true });
    if (alamat.indexOf('/api/cameras') > -1) {
      return daftarKamera().then(function (d) {
        return jawab({ cameras: d.length ? d : [{ index: '', name: 'Kamera belum dinyalakan' }], current: kameraAktif });
      });
    }
    if (alamat.indexOf('/api/camera/switch') > -1) {
      var sumber = JSON.parse((o && o.body) || '{}').source;
      if (!berjalan) return jawab({ status: 'error', message: 'Nyalakan kamera dulu.' }, 400);
      return bukaKamera(sumber).then(function () { return jawab({ status: 'ok', current: sumber }); })
        .catch(function (e) { return jawab({ status: 'error', message: e.message }, 400); });
    }
    if (alamat.indexOf('/api/start') > -1) {
      if (!berjalan) return jawab({ status: 'error', message: 'Nyalakan kamera dulu.' }, 400);
      sesi = { mulai: performance.now(), logTerakhir: -Infinity, log: [] };
      return jawab({ status: 'started' });
    }
    if (alamat.indexOf('/api/stop') > -1) return jawab(sesi ? selesaiSesi() : { status: 'no_data' });
    return fetchLama.apply(this, arguments);
  };

  document.addEventListener('DOMContentLoaded', function () {
    susunTampilan();
    /* Ketika kamera belum menyala, tombol sesi memberi tahu langkahnya. */
    var mulaiLama = document.getElementById('btn-start');
    if (mulaiLama) {
      mulaiLama.addEventListener('click', function (e) {
        if (!berjalan) {
          e.stopImmediatePropagation();
          tulisPesan('Nyalakan kamera dulu sebelum memulai sesi.', true);
        }
      }, true);
    }
    var pita = document.querySelector('#pv-bar span');
    if (pita) pita.textContent = 'Model berjalan di browser Anda';
  });
})();
