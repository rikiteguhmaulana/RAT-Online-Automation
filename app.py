"""
RAT Online Automation - Web Interface
======================================
Simple Flask web app untuk upload PDF dan menjalankan automation script.
"""

import os
import threading
import time
from datetime import datetime
from flask import Flask, render_template, request, jsonify, redirect, url_for
from werkzeug.utils import secure_filename

# Import automation functions
from rat_automation import extract_users_from_pdf, setup_driver, process_user, WAIT_BETWEEN_USERS

app = Flask(__name__)
app.config['SECRET_KEY'] = 'rat-online-automation-secret-key'
app.config['UPLOAD_FOLDER'] = os.path.join(os.path.dirname(__file__), 'uploads')
app.config['MAX_CONTENT_LENGTH'] = 16 * 1024 * 1024  # 16MB max file size

# Ensure upload folder exists
os.makedirs(app.config['UPLOAD_FOLDER'], exist_ok=True)

# Global state for tracking automation progress
automation_status = {
    'running': False,
    'total_users': 0,
    'current_user': 0,
    'current_username': '',
    'results': [],
    'completed': False,
    'error': None,
    'cancel_requested': False
}


def allowed_file(filename):
    """Check if file extension is allowed."""
    return '.' in filename and filename.rsplit('.', 1)[1].lower() == 'pdf'


def run_automation(pdf_paths):
    """Run automation in background thread."""
    global automation_status
    
    automation_status['running'] = True
    automation_status['results'] = []
    automation_status['error'] = None
    automation_status['cancel_requested'] = False
    
    try:
        # Extract users from all PDF files
        all_users = []
        for pdf_path in pdf_paths:
            users = extract_users_from_pdf(pdf_path)
            if users:
                all_users.extend(users)
        
        if not all_users:
            automation_status['error'] = 'Tidak ada data user ditemukan dalam PDF!'
            automation_status['running'] = False
            automation_status['completed'] = True
            return
        
        automation_status['total_users'] = len(all_users)
        
        # Setup driver
        driver = setup_driver()
        
        try:
            for idx, user in enumerate(all_users, 1):
                # Check for cancellation
                if automation_status['cancel_requested']:
                    automation_status['error'] = 'Proses dibatalkan oleh pengguna.'
                    break
                
                username = user['username']
                password = user['password']
                
                automation_status['current_user'] = idx
                automation_status['current_username'] = username
                
                start_time = datetime.now().strftime('%H:%M:%S')
                result = {
                    'user_number': idx,
                    'username': username,
                    'status': 'processing',
                    'message': 'Sedang memproses...',
                    'start_time': start_time,
                    'end_time': '-'
                }
                automation_status['results'].append(result)
                
                try:
                    status, success = process_user(driver, username, password)
                    result['end_time'] = datetime.now().strftime('%H:%M:%S')
                    
                    if status == 'success':
                        result['status'] = 'success'
                        result['message'] = 'Berhasil diisi'
                    elif status == 'already_filled':
                        result['status'] = 'skipped'
                        result['message'] = 'Sudah pernah diisi sebelumnya'
                    else:
                        result['status'] = 'failed'
                        result['message'] = 'Gagal saat proses'
                except Exception as e:
                    result['end_time'] = datetime.now().strftime('%H:%M:%S')
                    result['status'] = 'failed'
                    result['message'] = str(e)
                
                # Wait between users
                if idx < len(all_users):
                    time.sleep(WAIT_BETWEEN_USERS)
        
        finally:
            driver.quit()
    
    except Exception as e:
        automation_status['error'] = str(e)
    
    finally:
        automation_status['running'] = False
        automation_status['completed'] = True
        
        # Clean up uploaded files
        for pdf_path in pdf_paths:
            try:
                os.remove(pdf_path)
            except:
                pass


@app.route('/')
def index():
    """Render main upload page."""
    return render_template('index.html')


@app.route('/upload', methods=['POST'])
def upload_file():
    """Handle PDF file upload and start automation."""
    global automation_status
    
    # Check if automation is already running
    if automation_status['running']:
        return jsonify({
            'success': False,
            'message': 'Proses otomatisasi sedang berjalan. Silakan tunggu hingga selesai.'
        })
    
    # Check if files are in request
    if 'pdf_files' not in request.files:
        return jsonify({
            'success': False,
            'message': 'Tidak ada file yang dipilih!'
        })
    
    files = request.files.getlist('pdf_files')
    
    if not files or files[0].filename == '':
        return jsonify({
            'success': False,
            'message': 'Tidak ada file yang dipilih!'
        })
    
    if len(files) > 10:
        return jsonify({
            'success': False,
            'message': 'Maksimum 10 file sekaligus!'
        })
    
    filepaths = []
    for file in files:
        if not allowed_file(file.filename):
            continue
            
        # Save uploaded file
        filename = secure_filename(file.filename)
        timestamp = datetime.now().strftime('%Y%m%d_%H%M%S_%f')
        filename = f"{timestamp}_{filename}"
        filepath = os.path.join(app.config['UPLOAD_FOLDER'], filename)
        file.save(filepath)
        filepaths.append(filepath)
    
    if not filepaths:
        return jsonify({
            'success': False,
            'message': 'Format file tidak didukung (harus PDF)!'
        })
    
    # Reset status
    automation_status = {
        'running': True,
        'total_users': 0,
        'current_user': 0,
        'current_username': '',
        'results': [],
        'completed': False,
        'error': None
    }
    
    # Start automation in background thread
    thread = threading.Thread(target=run_automation, args=(filepaths,))
    thread.daemon = True
    thread.start()
    
    return jsonify({
        'success': True,
        'message': f'{len(filepaths)} file berhasil diupload! Proses otomatisasi dimulai...'
    })


@app.route('/status')
def get_status():
    """Get current automation status."""
    return jsonify(automation_status)


@app.route('/cancel', methods=['POST'])
def cancel_automation():
    """Request to cancel running automation."""
    global automation_status
    if automation_status['running']:
        automation_status['cancel_requested'] = True
        return jsonify({'success': True, 'message': 'Membatalkan proses...'})
    return jsonify({'success': False, 'message': 'Tidak ada proses yang berjalan.'})


@app.route('/reset')
def reset_status():
    """Reset automation status."""
    global automation_status
    
    if not automation_status['running']:
        automation_status = {
            'running': False,
            'total_users': 0,
            'current_user': 0,
            'current_username': '',
            'results': [],
            'completed': False,
            'error': None
        }
    
    return redirect(url_for('index'))


if __name__ == '__main__':
    print("=" * 50)
    print("RAT Online Automation - Web Interface")
    print("=" * 50)
    
    port = int(os.environ.get('PORT', 5000))
    print(f"\nServer berjalan di port: {port}")
    print(f"Akses: http://localhost:{port}")
    print("\nTekan CTRL+C untuk menghentikan server")
    print("=" * 50)
    
    app.run(debug=False, host='0.0.0.0', port=port)
