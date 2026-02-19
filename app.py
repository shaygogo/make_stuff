from flask import Flask, request, jsonify, send_file, render_template
from flask_cors import CORS
from werkzeug.utils import secure_filename
import json
import io
import traceback
import os
import urllib.request
from dotenv import load_dotenv

load_dotenv() # Load environmental variables

from migrate_pipedrive import migrate_blueprint
import database

app = Flask(__name__, static_folder='static', template_folder='.')
CORS(app)  # Enable CORS

# Configuration
MAX_FILE_SIZE = 10 * 1024 * 1024  # 10MB
ALLOWED_EXTENSIONS = {'json'}
ADMIN_SECRET = os.getenv('ADMIN_SECRET', 'admin123') # Simple protection for admin routes
MAKE_WEBHOOK_URL = os.getenv('MAKE_NOTIFY_WEBHOOK', '') # Webhook to notify you
MASTER_TOKEN = os.getenv('MASTER_TOKEN', 'godmode') # <--- Master Token for you

def allowed_file(filename):
    return '.' in filename and filename.rsplit('.', 1)[1].lower() in ALLOWED_EXTENSIONS

def notify_webhook(agency_name, action, token):
    """Fire and forget webhook to Make.com"""
    if not MAKE_WEBHOOK_URL:
        return
    
    try:
        data = json.dumps({
            "agency": agency_name,
            "action": action,
            "token": token,
            "timestamp": str(datetime.datetime.now())
        }).encode('utf-8')
        
        req = urllib.request.Request(MAKE_WEBHOOK_URL, data=data, headers={'Content-Type': 'application/json'})
        urllib.request.urlopen(req)
    except Exception as e:
        print(f"Webhook error: {e}")

@app.route('/')
def index():
    """Serve the main HTML interface"""
    return render_template('index.html')

@app.route('/api/migrate', methods=['POST'])
def migrate():
    """
    Process uploaded JSON blueprint and return migrated version.
    REQUIRES: 'token' in form data or query string.
    """
    try:
        # 1. Verify Token & Credits
        token = request.form.get('token') or request.args.get('token')
        
        if not token:
            return jsonify({'error': 'Missing access token. Please use the link provided in your email.'}), 401
            
        token_info = None
        is_master = (token == MASTER_TOKEN)
        
        if not is_master:
            token_info = database.get_token_info(token)
            if not token_info:
                 return jsonify({'error': 'Invalid access token.'}), 403
                 
            if token_info['credits'] <= 0:
                 # Notify you that they hit the limit (Hot Lead!)
                 notify_webhook(token_info['agency_name'], 'limit_reached', token)
                 return jsonify({
                     'error': 'Trial limit reached (3/3 scnarios). Please contact us to unlock the Full Account Migration feature.'
                 }), 402
        else:
             # Master User Context
             token_info = {'agency_name': 'Admin (You)', 'credits': 9999}

        # 2. Validate file
        if 'file' not in request.files:
            return jsonify({'error': 'No file uploaded'}), 400
        
        file = request.files['file']
        if file.filename == '':
            return jsonify({'error': 'No file selected'}), 400
        
        if not allowed_file(file.filename):
            return jsonify({'error': 'Invalid file type. Please upload a JSON file.'}), 400
        
        # 3. Read File
        try:
            file_content = file.read()
            if len(file_content) > MAX_FILE_SIZE:
                return jsonify({'error': 'File too large. Maximum size is 10MB.'}), 400
            blueprint_data = json.loads(file_content.decode('utf-8'))
        except Exception as e:
            return jsonify({'error': f'Invalid JSON file: {str(e)}'}), 400
        
        # 4. Perform Migration
        new_connection_id = request.form.get('new_connection_id')
        if new_connection_id:
             try: new_connection_id = int(new_connection_id)
             except: pass
             
        smart_fields = True
        modified, migrated_data, stats = migrate_blueprint(
            blueprint_data, 
            connection_id=new_connection_id,
            smart_fields=smart_fields
        )
        
        if not modified:
            return jsonify({'error': 'No Pipedrive v1 modules found. No credit deducted.'}), 400
            
        # 5. Success! Deduct Credit & Notify
        if not is_master:
            database.decrement_credits(token, file.filename)
            notify_webhook(token_info['agency_name'], 'migration_success', token)
        
        # 6. Return File
        original_filename = secure_filename(file.filename)
        base_name = original_filename.rsplit('.', 1)[0] if '.' in original_filename else original_filename
        output_filename = f"{base_name}_v2_migrated.json"
        
        json_bytes = json.dumps(migrated_data, indent=4, ensure_ascii=False).encode('utf-8')
        json_io = io.BytesIO(json_bytes)
        
        response = send_file(
            json_io,
            mimetype='application/json',
            as_attachment=True,
            download_name=output_filename
        )
        
        # Add field ID warnings as custom header for the frontend
        field_warnings = stats.get('field_id_warnings', [])
        trigger_warnings = stats.get('trigger_warnings', [])
        exposed_headers = []
        
        if field_warnings:
            import urllib.parse
            response.headers['X-Field-Warnings'] = urllib.parse.quote(json.dumps(field_warnings, ensure_ascii=False))
            exposed_headers.append('X-Field-Warnings')
        
        if trigger_warnings:
            import urllib.parse
            response.headers['X-Trigger-Warnings'] = urllib.parse.quote(json.dumps(trigger_warnings, ensure_ascii=False))
            exposed_headers.append('X-Trigger-Warnings')
        
        if exposed_headers:
            response.headers['Access-Control-Expose-Headers'] = ', '.join(exposed_headers)
        
        return response
        
    except Exception as e:
        traceback.print_exc()
        return jsonify({'error': f'Migration failed: {str(e)}'}), 500

# --- Admin Routes ---

@app.route('/api/admin/create_token', methods=['POST'])
def create_token():
    """Create a new access token for an agency"""
    secret = request.json.get('secret')
    if secret != ADMIN_SECRET:
        return jsonify({'error': 'Unauthorized'}), 401
    
    agency = request.json.get('agency')
    email = request.json.get('email')
    credits = request.json.get('credits', 3)
    
    token = database.create_token(agency, email, credits)
    return jsonify({'token': token, 'link': f'http://localhost:5000/?token={token}'})

@app.route('/api/credits', methods=['GET'])
def check_credits():
    token = request.args.get('token')
    if token == MASTER_TOKEN:
         return jsonify({'credits': 'Unlimited (God Mode)', 'agency': 'Admin'})
         
    info = database.get_token_info(token)
    if info:
        return jsonify({'credits': info['credits'], 'agency': info['agency_name']})
    return jsonify({'error': 'Invalid token'}), 404

@app.route('/api/health', methods=['GET'])
def health():
    return jsonify({'status': 'healthy'}), 200

if __name__ == '__main__':
    print("Starting Migration Server with Token Auth...")
    app.run(debug=True, host='0.0.0.0', port=5000)
