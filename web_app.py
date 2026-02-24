from flask import Flask, render_template, send_file, abort, jsonify, request, session, redirect, url_for, Response
from pathlib import Path
import json
from datetime import datetime
import requests
from config import WEB_HOST, WEB_PORT, DATABASE_DIR, BOT_TOKEN
from dataset_manager import dataset_manager

app = Flask(__name__)
app.secret_key = 'hamster_admin_secret_key_2026'

def get_file_from_telegram(file_id: str):
    """Получить файл из Telegram по file_id"""
    try:
        # Получаем информацию о файле
        get_file_url = f"https://api.telegram.org/bot{BOT_TOKEN}/getFile?file_id={file_id}"
        response = requests.get(get_file_url)
        
        if response.status_code != 200:
            return None
        
        file_info = response.json()
        if not file_info.get('ok'):
            return None
        
        file_path = file_info['result']['file_path']
        
        # Скачиваем файл
        download_url = f"https://api.telegram.org/file/bot{BOT_TOKEN}/{file_path}"
        file_response = requests.get(download_url)
        
        if file_response.status_code == 200:
            return file_response.content
        
        return None
    except Exception as e:
        print(f"Ошибка получения файла из Telegram: {e}")
        return None

def load_session(session_id: str):
    sessions_file = DATABASE_DIR / "sessions.json"
    if not sessions_file.exists():
        return None
    
    with open(sessions_file, 'r', encoding='utf-8') as f:
        sessions = json.load(f)
    
    return sessions.get(session_id)

@app.route('/')
def index():
    return render_template('index.html')

@app.route('/admin')
def admin():
    return render_template('admin.html')

@app.route('/admin/panel')
def admin_panel():
    if not session.get('admin_logged_in'):
        return redirect(url_for('admin_login'))
    
    users_file = DATABASE_DIR / "users.json"
    sessions_file = DATABASE_DIR / "sessions.json"
    
    users_data = {}
    sessions_data = {}
    
    if users_file.exists():
        with open(users_file, 'r', encoding='utf-8') as f:
            users_data = json.load(f)
    
    if sessions_file.exists():
        with open(sessions_file, 'r', encoding='utf-8') as f:
            sessions_data = json.load(f)
    
    users = []
    for user_id, user_info in users_data.items():
        users.append(user_info)
    
    all_sessions = []
    for session_id, session_info in sessions_data.items():
        user_id = str(session_info.get('user_id', ''))
        user_name = 'неизвестно'
        if user_id in users_data:
            user_name = users_data[user_id].get('first_name', 'неизвестно')
        
        created_at = session_info.get('created_at', 'н/д')
        if created_at != 'н/д':
            try:
                dt = datetime.fromisoformat(created_at)
                created_at = dt.strftime('%d.%m.%Y %H:%M')
            except:
                pass
        
        all_sessions.append({
            'session_id': session_id,
            'user_name': user_name,
            'voiced_count': len(session_info.get('voiced_images', [])),
            'completed': session_info.get('completed', False),
            'created_at': created_at
        })
    
    all_sessions.sort(key=lambda x: x['created_at'], reverse=True)
    
    total_users = len(users)
    total_sessions = len(all_sessions)
    completed_sessions = sum(1 for s in all_sessions if s['completed'])
    active_sessions = total_sessions - completed_sessions
    
    return render_template('admin.html',
                         users=users,
                         all_sessions=all_sessions,
                         total_users=total_users,
                         total_sessions=total_sessions,
                         completed_sessions=completed_sessions,
                         active_sessions=active_sessions)

@app.route('/admin/login', methods=['GET', 'POST'])
def admin_login():
    if request.method == 'POST':
        password = request.form.get('password', '')
        if password == os.environ.get('ADMIN_PASSWORD', 'change_me'):
            session['admin_logged_in'] = True
            return redirect(url_for('admin_panel'))
        else:
            return render_template('admin_login.html', error=True)
    return render_template('admin_login.html', error=False)

@app.route('/admin/logout')
def admin_logout():
    session.pop('admin_logged_in', None)
    return redirect(url_for('admin_login'))

@app.route('/session/<session_id>')
def view_session(session_id):
    session = load_session(session_id)
    
    if not session:
        return render_template('not_found.html'), 404
    
    voiced_images = session.get("voiced_images", [])
    
    if len(voiced_images) == 0:
        return render_template('empty_session.html', session_id=session_id)
    
    images_data = []
    for item in voiced_images:
        index = item["index"]
        voice_file = item["voice_file"]
        
        image_data = dataset_manager.get_image_data(index)
        if image_data:
            images_data.append({
                "index": index,
                "comment": image_data["comment"],
                "emotion": image_data["emotion"],
                "voice_file": voice_file
            })
    
    return render_template('session.html', 
                         session_id=session_id,
                         images=images_data,
                         total=len(images_data))

@app.route('/api/session/<session_id>')
def api_session(session_id):
    session = load_session(session_id)
    
    if not session or not session.get("completed", False):
        return jsonify({"error": "Session not found or not completed"}), 404
    
    voiced_images = session.get("voiced_images", [])
    images_data = []
    
    for item in voiced_images:
        index = item["index"]
        voice_file = item["voice_file"]
        image_data = dataset_manager.get_image_data(index)
        
        if image_data:
            images_data.append({
                "index": index,
                "filename": image_data["file"],
                "comment": image_data["comment"],
                "emotion": image_data["emotion"],
                "voice_file": voice_file
            })
    
    return jsonify({
        "session_id": session_id,
        "total": len(images_data),
        "images": images_data
    })

@app.route('/voice/<file_id>')
def serve_voice(file_id):
    """
    Получает аудио из Telegram по file_id
    """
    audio_data = get_file_from_telegram(file_id)
    
    if audio_data:
        return Response(audio_data, mimetype='audio/ogg')
    
    abort(404)

@app.route('/image/<int:image_index>')
def serve_image(image_index):
    """
    Получает картинку из Telegram по индексу из dataset
    """
    image_data = dataset_manager.get_image_data(image_index)
    
    if not image_data or 'file_id' not in image_data:
        abort(404)
    
    file_id = image_data['file_id']
    
    # Получаем файл из Telegram
    try:
        get_file_url = f"https://api.telegram.org/bot{BOT_TOKEN}/getFile?file_id={file_id}"
        response = requests.get(get_file_url)
        
        if response.status_code != 200:
            abort(404)
        
        file_info = response.json()
        if not file_info.get('ok'):
            abort(404)
        
        file_path = file_info['result']['file_path']
        
        # Скачиваем файл
        download_url = f"https://api.telegram.org/file/bot{BOT_TOKEN}/{file_path}"
        file_response = requests.get(download_url)
        
        if file_response.status_code == 200:
            return Response(file_response.content, mimetype='image/png')
        
        abort(404)
    except Exception as e:
        print(f"Ошибка получения картинки из Telegram: {e}")
        abort(404)

if __name__ == '__main__':
    app.run(host=WEB_HOST, port=WEB_PORT, debug=False)
