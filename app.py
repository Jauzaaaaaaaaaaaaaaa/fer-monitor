import json
import os
import time

from flask import Flask, render_template, Response, jsonify, request, send_file, abort

import config
from camera import Camera
from logger import SessionLogger


app    = Flask(__name__)
camera = Camera()
logger = SessionLogger()

# Start webcam saat app dijalankan
try:
    camera.start()
except RuntimeError as e:
    print(f"[App] Warning: webcam belum aktif - {e}")

# ─── Routes ───────────────────────────────────────────────────────

@app.route('/')
def index():
    return render_template('index.html', cache_bust=int(time.time()))

@app.route('/model')
def model_info():
    with open(os.path.join(config.BASE_DIR, 'model', 'metrik.json'), encoding='utf-8') as f:
        metrik = json.load(f)
    metrik['smoothing'] = config.SMOOTHING_WINDOW
    return render_template('model.html', m=metrik)

@app.route('/history')
def history():
    sessions = logger.get_all_sessions()
    return render_template('history.html', sessions=sessions)

@app.route('/history/<int:session_id>')
def history_detail(session_id):
    session = logger.get_session_detail(session_id)
    if not session:
        abort(404)
    return render_template('detail.html', session=session)

# ─── API routes ───────────────────────────────────────────────────

@app.route('/video_feed')
def video_feed():
    response = Response(
        camera.generate_frames(),
        mimetype='multipart/x-mixed-replace; boundary=frame'
    )
    response.headers['Cache-Control'] = 'no-cache, no-store, must-revalidate'
    response.headers['Pragma']        = 'no-cache'
    response.headers['Expires']       = '0'
    return response

@app.route('/api/start', methods=['POST'])
def start_session():
    logger.start()
    camera.start_session(log_callback=logger.log)
    return jsonify({'status': 'started'})

@app.route('/api/stop', methods=['POST'])
def stop_session():
    duration = camera.stop_session()
    result   = logger.stop(duration)
    if not result:
        return jsonify({'status': 'no_data'})
    return jsonify({'status': 'stopped', 'result': result})

@app.route('/api/status')
def status():
    return jsonify(camera.get_status())

@app.route('/api/cameras')
def list_cameras():
    cameras = camera.list_available_cameras(skip_index=camera.current_source)
    return jsonify({
        'cameras': cameras,
        'current': camera.current_source
    })

@app.route('/api/camera/switch', methods=['POST'])
def switch_camera():
    data = request.get_json(silent=True) or {}
    try:
        source_index = int(data.get('source', 0))
        camera.switch_source(source_index)
        return jsonify({'status': 'ok', 'current': source_index})
    except (RuntimeError, ValueError) as e:
        return jsonify({'status': 'error', 'message': str(e)}), 400

@app.route('/api/timeline')
def timeline():
    return jsonify(camera.get_recent_distribution())

@app.route('/api/health')
def health():
    return jsonify({
        'model_loaded'   : camera.model is not None,
        'model_error'    : camera.model_error,
        'camera_running' : camera.is_running
    })

@app.route('/api/camera/start', methods=['POST'])
def camera_start():
    data   = request.get_json(silent=True) or {}
    source = int(data.get('source', camera.current_source))
    try:
        camera.start(source)
        return jsonify({'status': 'ok'})
    except RuntimeError as e:
        return jsonify({'status': 'error', 'message': str(e)}), 400

@app.route('/download/<int:session_id>')
def download_csv(session_id):
    session = logger.get_session_detail(session_id)
    if not session or not os.path.exists(session['csv_path']):
        abort(404)
    return send_file(session['csv_path'], as_attachment=True)

@app.route('/api/session/<int:session_id>/delete', methods=['POST'])
def delete_session_route(session_id):
    success = logger.delete_session(session_id)
    if success:
        return jsonify({'status': 'deleted'})
    return jsonify({'status': 'error'}), 404

# ─── Run ──────────────────────────────────────────────────────────

if __name__ == '__main__':
    app.run(host=config.HOST, port=config.PORT, debug=config.DEBUG, use_reloader=False, threaded=True)
