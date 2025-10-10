"""Simple API for viewing and solving CAPTCHAs detected during automation.

Usage:
    python -m calico.api.captcha_api

Then visit:
    http://localhost:5000/captcha/{session_id}           - List all captchas
    http://localhost:5000/captcha/{session_id}/{captcha_id}  - View specific captcha
    POST /captcha/{session_id}/{captcha_id}/solve with {"solution": "..."}
"""
from __future__ import annotations

import json
import logging
from pathlib import Path
from typing import Optional

from flask import Flask, jsonify, request, send_file, render_template_string
from flask_cors import CORS

from calico.utils.session_storage import SessionStorage

logger = logging.getLogger(__name__)

app = Flask(__name__)
CORS(app)  # Enable CORS for all routes


# HTML template for captcha viewing
CAPTCHA_VIEW_TEMPLATE = """
<!DOCTYPE html>
<html>
<head>
    <title>Captcha Viewer - {{ captcha_id }}</title>
    <style>
        body {
            font-family: Arial, sans-serif;
            max-width: 1200px;
            margin: 0 auto;
            padding: 20px;
            background: #f5f5f5;
        }
        .container {
            background: white;
            padding: 30px;
            border-radius: 8px;
            box-shadow: 0 2px 4px rgba(0,0,0,0.1);
        }
        h1 {
            color: #333;
            border-bottom: 3px solid #e74c3c;
            padding-bottom: 10px;
        }
        .info {
            background: #ecf0f1;
            padding: 15px;
            border-radius: 5px;
            margin: 20px 0;
        }
        .info-item {
            margin: 10px 0;
        }
        .label {
            font-weight: bold;
            color: #2c3e50;
        }
        img {
            max-width: 100%;
            border: 2px solid #ddd;
            border-radius: 5px;
            margin: 20px 0;
        }
        .solved {
            background: #2ecc71;
            color: white;
            padding: 10px;
            border-radius: 5px;
            text-align: center;
            font-weight: bold;
        }
        .unsolved {
            background: #e74c3c;
            color: white;
            padding: 10px;
            border-radius: 5px;
            text-align: center;
            font-weight: bold;
        }
        form {
            margin: 20px 0;
        }
        input[type="text"] {
            width: 300px;
            padding: 10px;
            border: 2px solid #ddd;
            border-radius: 5px;
            font-size: 16px;
        }
        button {
            padding: 10px 20px;
            background: #3498db;
            color: white;
            border: none;
            border-radius: 5px;
            font-size: 16px;
            cursor: pointer;
        }
        button:hover {
            background: #2980b9;
        }
        .back-link {
            display: inline-block;
            margin-top: 20px;
            color: #3498db;
            text-decoration: none;
        }
        .back-link:hover {
            text-decoration: underline;
        }
    </style>
</head>
<body>
    <div class="container">
        <h1>🤖 CAPTCHA Detected</h1>
        
        <div class="info">
            <div class="info-item">
                <span class="label">Captcha ID:</span> {{ captcha_id }}
            </div>
            <div class="info-item">
                <span class="label">Type:</span> {{ type }}
            </div>
            <div class="info-item">
                <span class="label">URL:</span> <a href="{{ url }}" target="_blank">{{ url }}</a>
            </div>
            <div class="info-item">
                <span class="label">Timestamp:</span> {{ timestamp }}
            </div>
        </div>
        
        {% if solved %}
        <div class="solved">
            ✓ SOLVED
        </div>
        {% else %}
        <div class="unsolved">
            ⚠ UNSOLVED - Automation is paused
        </div>
        {% endif %}
        
        <h2>Screenshot</h2>
        <img src="/captcha/{{ session_id }}/{{ captcha_id }}/image" alt="Captcha Screenshot">
        
        {% if not solved %}
        <h2>Mark as Solved</h2>
        <form method="POST" action="/captcha/{{ session_id }}/{{ captcha_id }}/solve">
            <input type="text" name="solution" placeholder="Enter solution (optional)" />
            <button type="submit">Mark Solved</button>
        </form>
        {% endif %}
        
        <a href="/captcha/{{ session_id }}" class="back-link">← Back to all captchas</a>
    </div>
</body>
</html>
"""

CAPTCHA_LIST_TEMPLATE = """
<!DOCTYPE html>
<html>
<head>
    <title>Captchas - Session {{ session_id }}</title>
    <style>
        body {
            font-family: Arial, sans-serif;
            max-width: 1200px;
            margin: 0 auto;
            padding: 20px;
            background: #f5f5f5;
        }
        .container {
            background: white;
            padding: 30px;
            border-radius: 8px;
            box-shadow: 0 2px 4px rgba(0,0,0,0.1);
        }
        h1 {
            color: #333;
            border-bottom: 3px solid #3498db;
            padding-bottom: 10px;
        }
        .captcha-list {
            list-style: none;
            padding: 0;
        }
        .captcha-item {
            background: #ecf0f1;
            padding: 15px;
            margin: 10px 0;
            border-radius: 5px;
            display: flex;
            justify-content: space-between;
            align-items: center;
        }
        .captcha-info {
            flex: 1;
        }
        .status {
            padding: 5px 15px;
            border-radius: 3px;
            font-weight: bold;
            margin-left: 10px;
        }
        .status-solved {
            background: #2ecc71;
            color: white;
        }
        .status-unsolved {
            background: #e74c3c;
            color: white;
        }
        a {
            color: #3498db;
            text-decoration: none;
        }
        a:hover {
            text-decoration: underline;
        }
        .empty {
            text-align: center;
            padding: 40px;
            color: #95a5a6;
        }
    </style>
</head>
<body>
    <div class="container">
        <h1>📋 CAPTCHAs for Session {{ session_id[:8] }}...</h1>
        
        {% if captchas %}
        <ul class="captcha-list">
            {% for captcha in captchas %}
            <li class="captcha-item">
                <div class="captcha-info">
                    <strong>{{ captcha.type }}</strong> - 
                    <a href="/captcha/{{ session_id }}/{{ captcha.captcha_id }}">{{ captcha.captcha_id }}</a>
                    <br>
                    <small>{{ captcha.url }} - {{ captcha.timestamp }}</small>
                </div>
                <span class="status {% if captcha.solved %}status-solved{% else %}status-unsolved{% endif %}">
                    {% if captcha.solved %}SOLVED{% else %}UNSOLVED{% endif %}
                </span>
            </li>
            {% endfor %}
        </ul>
        {% else %}
        <div class="empty">
            No captchas detected yet for this session.
        </div>
        {% endif %}
    </div>
</body>
</html>
"""


@app.route('/captcha/<session_id>', methods=['GET'])
def list_captchas(session_id: str):
    """List all captchas for a session."""
    try:
        storage = SessionStorage(session_id=session_id)
        captchas = storage.list_captchas()
        
        # Return HTML by default, JSON if requested
        if request.headers.get('Accept') == 'application/json':
            return jsonify({
                'session_id': session_id,
                'captchas': captchas,
                'count': len(captchas)
            })
        
        return render_template_string(
            CAPTCHA_LIST_TEMPLATE,
            session_id=session_id,
            captchas=captchas
        )
    except Exception as e:
        logger.error(f"Error listing captchas: {e}")
        return jsonify({'error': str(e)}), 500


@app.route('/captcha/<session_id>/<captcha_id>', methods=['GET'])
def view_captcha(session_id: str, captcha_id: str):
    """View a specific captcha."""
    try:
        storage = SessionStorage(session_id=session_id)
        captcha = storage.get_captcha(captcha_id)
        
        if not captcha:
            return jsonify({'error': 'Captcha not found'}), 404
        
        # Return HTML by default, JSON if requested
        if request.headers.get('Accept') == 'application/json':
            return jsonify(captcha)
        
        return render_template_string(
            CAPTCHA_VIEW_TEMPLATE,
            session_id=session_id,
            captcha_id=captcha_id,
            **captcha
        )
    except Exception as e:
        logger.error(f"Error viewing captcha: {e}")
        return jsonify({'error': str(e)}), 500


@app.route('/captcha/<session_id>/<captcha_id>/image', methods=['GET'])
def get_captcha_image(session_id: str, captcha_id: str):
    """Get the captcha screenshot image."""
    try:
        storage = SessionStorage(session_id=session_id)
        captcha = storage.get_captcha(captcha_id)
        
        if not captcha:
            return jsonify({'error': 'Captcha not found'}), 404
        
        screenshot_path = Path(captcha['screenshot_path'])
        if not screenshot_path.exists():
            return jsonify({'error': 'Screenshot not found'}), 404
        
        return send_file(screenshot_path, mimetype='image/png')
    except Exception as e:
        logger.error(f"Error getting captcha image: {e}")
        return jsonify({'error': str(e)}), 500


@app.route('/captcha/<session_id>/<captcha_id>/solve', methods=['POST'])
def solve_captcha(session_id: str, captcha_id: str):
    """Mark a captcha as solved."""
    try:
        storage = SessionStorage(session_id=session_id)
        
        # Get solution from form or JSON
        if request.is_json:
            solution = request.json.get('solution')
        else:
            solution = request.form.get('solution')
        
        success = storage.mark_captcha_solved(captcha_id, solution=solution)
        
        if not success:
            return jsonify({'error': 'Captcha not found'}), 404
        
        # Redirect to captcha view if HTML form, return JSON otherwise
        if request.is_json or request.headers.get('Accept') == 'application/json':
            return jsonify({
                'success': True,
                'captcha_id': captcha_id,
                'message': 'Captcha marked as solved'
            })
        else:
            # Redirect back to captcha view
            from flask import redirect, url_for
            return redirect(url_for('view_captcha', session_id=session_id, captcha_id=captcha_id))
    except Exception as e:
        logger.error(f"Error solving captcha: {e}")
        return jsonify({'error': str(e)}), 500


@app.route('/health', methods=['GET'])
def health():
    """Health check endpoint."""
    return jsonify({'status': 'ok', 'service': 'captcha-api'})


@app.route('/', methods=['GET'])
def index():
    """Index page with instructions."""
    html = """
    <!DOCTYPE html>
    <html>
    <head>
        <title>Calico Captcha API</title>
        <style>
            body {
                font-family: Arial, sans-serif;
                max-width: 800px;
                margin: 50px auto;
                padding: 20px;
                background: #f5f5f5;
            }
            .container {
                background: white;
                padding: 30px;
                border-radius: 8px;
                box-shadow: 0 2px 4px rgba(0,0,0,0.1);
            }
            h1 { color: #3498db; }
            code {
                background: #ecf0f1;
                padding: 2px 6px;
                border-radius: 3px;
                font-family: monospace;
            }
            pre {
                background: #2c3e50;
                color: #ecf0f1;
                padding: 15px;
                border-radius: 5px;
                overflow-x: auto;
            }
        </style>
    </head>
    <body>
        <div class="container">
            <h1>🔓 Calico CAPTCHA API</h1>
            <p>This API allows you to view and solve CAPTCHAs detected during browser automation.</p>
            
            <h2>Endpoints</h2>
            <ul>
                <li><code>GET /captcha/{session_id}</code> - List all captchas for a session</li>
                <li><code>GET /captcha/{session_id}/{captcha_id}</code> - View specific captcha</li>
                <li><code>GET /captcha/{session_id}/{captcha_id}/image</code> - Get captcha image</li>
                <li><code>POST /captcha/{session_id}/{captcha_id}/solve</code> - Mark captcha as solved</li>
            </ul>
            
            <h2>Example Usage</h2>
            <pre>
# List all captchas
curl http://localhost:5000/captcha/your-session-id

# View captcha in browser
http://localhost:5000/captcha/your-session-id/captcha-id

# Mark as solved via API
curl -X POST http://localhost:5000/captcha/your-session-id/captcha-id/solve \\
     -H "Content-Type: application/json" \\
     -d '{"solution": "optional solution text"}'
            </pre>
            
            <p><strong>Note:</strong> Replace <code>your-session-id</code> and <code>captcha-id</code> with actual values from your session.</p>
        </div>
    </body>
    </html>
    """
    return render_template_string(html)


def main(host: str = '0.0.0.0', port: int = 5000, debug: bool = False):
    """Run the CAPTCHA API server."""
    logger.info(f"Starting CAPTCHA API server on {host}:{port}")
    app.run(host=host, port=port, debug=debug)


if __name__ == '__main__':
    import sys
    
    # Simple argument parsing
    host = sys.argv[1] if len(sys.argv) > 1 else '0.0.0.0'
    port = int(sys.argv[2]) if len(sys.argv) > 2 else 5000
    
    logging.basicConfig(level=logging.INFO)
    main(host=host, port=port, debug=True)
