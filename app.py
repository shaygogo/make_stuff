from flask import Flask, request, jsonify, send_file, render_template
from flask_cors import CORS
from werkzeug.utils import secure_filename
import json
import io
import traceback
from dotenv import load_dotenv

load_dotenv() # Load environment variables from .env file BEFORE importing modules that use them

from migrate_pipedrive import migrate_blueprint

app = Flask(__name__, static_folder='static', template_folder='.')
CORS(app)  # Enable CORS for local development

# Configuration
MAX_FILE_SIZE = 10 * 1024 * 1024  # 10MB
ALLOWED_EXTENSIONS = {'json'}

def allowed_file(filename):
    return '.' in filename and filename.rsplit('.', 1)[1].lower() in ALLOWED_EXTENSIONS

@app.route('/')
def index():
    """Serve the main HTML interface"""
    return render_template('index.html')

@app.route('/api/migrate', methods=['POST'])
def migrate():
    """
    Process uploaded JSON blueprint and return migrated version.
    
    Accepts:
    - file: JSON blueprint file
    - connection_mode: 'preserve' or 'update'
    - new_connection_id: (optional) new connection ID if mode is 'update'
    
    Returns:
    - Migrated JSON file as download
    """
    try:
        # Validate file upload
        if 'file' not in request.files:
            return jsonify({'error': 'No file uploaded'}), 400
        
        file = request.files['file']
        
        if file.filename == '':
            return jsonify({'error': 'No file selected'}), 400
        
        if not allowed_file(file.filename):
            return jsonify({'error': 'Invalid file type. Please upload a JSON file.'}), 400
        
        # Read and parse JSON
        try:
            file_content = file.read()
            
            # Check file size
            if len(file_content) > MAX_FILE_SIZE:
                return jsonify({'error': 'File too large. Maximum size is 10MB.'}), 400
            
            blueprint_data = json.loads(file_content.decode('utf-8'))
        except json.JSONDecodeError as e:
            return jsonify({'error': f'Invalid JSON file: {str(e)}'}), 400
        except Exception as e:
            return jsonify({'error': f'Error reading file: {str(e)}'}), 400
        
        # Get connection mode parameters
        connection_mode = request.form.get('connection_mode', 'preserve')
        new_connection_id = request.form.get('new_connection_id')
        
        # Validate connection ID if update mode
        if connection_mode == 'update':
            if not new_connection_id:
                return jsonify({'error': 'Connection ID is required when using "Update to New Connection" mode'}), 400
            
            try:
                new_connection_id = int(new_connection_id)
            except ValueError:
                return jsonify({'error': 'Connection ID must be a valid number'}), 400
        else:
            new_connection_id = None  # Preserve mode
        
        # Get smart fields flag (convert string "true"/"false" to boolean)
        raw_smart = request.form.get('smart_fields')
        smart_fields = str(raw_smart).lower() == 'true'
        print(f"DEBUG: raw_smart_fields={raw_smart}, parsed={smart_fields}")
        
        # Perform migration
        modified, migrated_data, stats = migrate_blueprint(
            blueprint_data, 
            connection_id=new_connection_id,
            smart_fields=smart_fields
        )
        
        if not modified:
            return jsonify({
                'error': 'No Pipedrive v1 modules found in this blueprint. Nothing to migrate.'
            }), 400
        
        # Generate filename
        original_filename = secure_filename(file.filename)
        base_name = original_filename.rsplit('.', 1)[0] if '.' in original_filename else original_filename
        output_filename = f"{base_name}_v2_migrated.json"
        
        # Convert to JSON bytes
        json_bytes = json.dumps(migrated_data, indent=4, ensure_ascii=False).encode('utf-8')
        json_io = io.BytesIO(json_bytes)
        
        # Return as downloadable file
        return send_file(
            json_io,
            mimetype='application/json',
            as_attachment=True,
            download_name=output_filename
        )
        
    except Exception as e:
        # Log the full traceback for debugging
        print("Migration error:")
        traceback.print_exc()
        
        return jsonify({
            'error': f'Migration failed: {str(e)}'
        }), 500

@app.route('/api/health', methods=['GET'])
def health():
    """Health check endpoint"""
    return jsonify({'status': 'healthy'}), 200

if __name__ == '__main__':
    print("Starting Pipedrive Migration Server...")
    print("Open http://localhost:5000 in your browser")
    app.run(debug=True, host='0.0.0.0', port=5000)
