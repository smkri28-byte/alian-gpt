from flask import Flask, render_template_string, request, redirect, url_for, session, flash
from google import genai
import sqlite3
import PyPDF2
import json
from datetime import datetime
import graphviz
import base64
import os

app = Flask(__name__)

# Fetch the secret key safely from the hosting environment
app.secret_key = os.environ.get("ae1ca680b123bd6926b1ad5ce228071c0d632b2ad2827e37")

# Fetch your Gemini API key safely from the hosting environment
API_KEY = os.environ.get("GEMINI_API_KEY")

# Fallback check to avoid server crashes if you forget to add the key to Render
if not API_KEY:
    client = None
else:
    client = genai.Client(api_key=API_KEY)

DB_FILE = "users_database.db"

def init_db():
    conn = sqlite3.connect(DB_FILE)
    cursor = conn.cursor()
    cursor.execute('''
        CREATE TABLE IF NOT EXISTS users (
            username TEXT PRIMARY KEY,
            password TEXT NOT NULL
        )
    ''')
    try:
        cursor.execute("INSERT INTO users VALUES (?, ?)", ("admin", "password123"))
    except sqlite3.IntegrityError:
        pass
    conn.commit()
    conn.close()

init_db()

def get_ai_response(prompt):
    if not client:
        return "Error: Gemini API Key is missing. Please add it to your Render Environment Variables."
    try:
        response = client.models.generate_content(
            model="gemini-2.5-flash",
            contents=prompt
        )
        return response.text.strip()
    except Exception as e:
        return f"Error connecting to Gemini AI: {str(e)}"

BASE_STYLE = """
<style>
    body { background-color: #000000; color: #FFFFFF; font-family: 'Arial', sans-serif; margin: 0; padding: 20px; }
    .auth-container { max-width: 400px; margin: 100px auto; padding: 30px; background-color: #111111; border: 1px solid #222222; border-radius: 8px; text-align: center; }
    .dashboard-container { max-width: 1200px; margin: 0 auto; }
    h1 { color: #FFFFFF; font-weight: bold; }
    .headline { font-size: 36px; font-weight: bold; color: #00FFCC; margin-bottom: 30px; }
    .form-group { margin-bottom: 15px; text-align: left; }
    label { display: block; margin-bottom: 5px; font-weight: bold; }
    input[type="text"], input[type="password"], textarea, select { width: 100%; padding: 10px; background: #222; border: 1px solid #333; color: white; border-radius: 4px; box-sizing: border-box; }
    button, input[type="submit"] { background-color: #222222; color: white; padding: 10px 20px; border: 1px solid #444; border-radius: 4px; cursor: pointer; font-weight: bold; }
    button:hover, input[type="submit"]:hover { background-color: #333333; }
    .btn-green { background-color: #27ae60 !important; border: none; }
    .btn-green:hover { background-color: #219653 !important; }
    .alert { padding: 10px; background-color: #e74c3c; color: white; border-radius: 4px; margin-bottom: 15px; font-size: 14px; }
    .menu-box { background: #111111; padding: 20px; border-radius: 8px; border: 1px solid #222222; margin-bottom: 20px; }
    .output-box { background: #111111; padding: 20px; border-radius: 8px; border: 1px solid #222222; white-space: pre-wrap; font-family: 'Century Gothic', sans-serif; min-height: 200px; }
    .nav-bar { display: flex; justify-content: space-between; align-items: center; border-bottom: 1px solid #222222; padding-bottom: 10px; margin-bottom: 20px; }
    .quiz-option { display: block; margin: 10px 0; background: #222; padding: 10px; border-radius: 4px; }
</style>
"""

LOGIN_HTML = BASE_STYLE + """
<div class="auth-container">
    <h2>AlianGPT Login</h2>
    {% with messages = get_flashed_messages() %}
      {% if messages %}
        {% for message in messages %}
          <div class="alert">{{ message }}</div>
        {% endfor %}
      {% endif %}
    {% endwith %}
    <form method="POST" action="/login">
        <div class="form-group">
            <label>Username</label>
            <input type="text" name="username" required>
        </div>
        <div class="form-group">
            <label>Password</label>
            <input type="password" name="password" required>
        </div>
        <input type="submit" value="Log In" style="width: 100%;">
    </form>
    <p style="margin-top:20px; font-size:14px;">
        <a href="/register" style="color: #00FFCC; text-decoration: none;">Create New Account</a>
    </p>
</div>
"""

REGISTER_HTML = BASE_STYLE + """
<div class="auth-container">
    <h2>Create New Account</h2>
    {% with messages = get_flashed_messages() %}
      {% if messages %}
        {% for message in messages %}
          <div class="alert">{{ message }}</div>
        {% endfor %}
      {% endif %}
    {% endwith %}
    <form method="POST" action="/register">
        <div class="form-group">
            <label>Choose Username</label>
            <input type="text" name="username" required>
        </div>
        <div class="form-group">
            <label>Choose Password</label>
            <input type="password" name="password" required>
        </div>
        <input type="submit" value="Sign Up" style="width: 100%; background-color: #27ae60;">
    </form>
    <p style="margin-top:20px; font-size:14px;">
        <a href="/login" style="color: #00FFCC; text-decoration: none;">Back to Login</a>
    </p>
</div>
"""

DASHBOARD_HTML = BASE_STYLE + """
<div class="dashboard-container">
    <div class="nav-bar">
        <h1>AlianGPT, AI assistant for studies</h1>
        <a href="/logout"><button>Log Out</button></a>
    </div>
    
    <div class="headline">I am here Where are you? [{{ username }}]</div>

    <div class="menu-box">
        <h3>🛠️ Select Study Tool</h3>
        <form method="POST" action="/run-feature" enctype="multipart/form-data">
            <div class="form-group" style="display: flex; gap: 10px;">
                <select name="feature" style="width: 30%;">
                    <option value="ask_ai">Ask AI</option>
                    <option value="pdf_reader">Open PDF</option>
                    <option value="generate_quiz">Generate Quiz</option>
                    <option value="sample_paper">Sample Paper</option>
                    <option value="generate_code">Generate Code</option>
                    <option value="mind_map">Mind Map</option>
                    <option value="periodic_table">Periodic Table</option>
                    <option value="analytics">Analytics</option>
                </select>
                <input type="text" name="query" placeholder="Enter topic, question, or text here..." value="{{ prev_query }}">
            </div>
            
            <div class="form-group">
                <label>PDF Upload (Required only for 'Open PDF'):</label>
                <input type="file" name="pdf_file" accept=".pdf">
            </div>
            
            <button type="submit" class="btn-green">Execute Feature</button>
        </form>
    </div>

    <h3>🖥️ Output Console</h3>
    <div class="output-box">
        {% if feature_type == "text" %}
            {{ output_data | safe }}
        {% elif feature_type == "image" %}
            <img src="data:image/png;base64,{{ output_data }}" style="max-width: 100%; border-radius: 8px;">
        {% elif feature_type == "quiz" %}
            <form method="POST" action="/evaluate-quiz">
                <h4>Interactive Quiz Questions:</h4>
                {% for q in output_data %}
                    <div style="margin-bottom: 20px;">
                        <p><strong>Q{{ loop.index }}: {{ q.question }}</strong></p>
                        <input type="hidden" name="ans_{{ loop.index0 }}" value="{{ q.answer }}">
                        {% for opt in q.options %}
                            <label class="quiz-option">
                                <input type="radio" name="user_ans_{{ loop.index0 }}" value="{{ opt }}"> {{ opt }}
                            </label>
                        {% endfor %}
                    </div>
                {% endfor %}
                <button type="submit" class="btn-green">Submit Quiz Answers</button>
            </form>
        {% else %}
            Console waiting for execution command...
        {% endif %}
    </div>
</div>
"""

@app.route('/')
def home():
    if "username" in session:
        return redirect(url_for('dashboard'))
    return redirect(url_for('login'))

@app.route('/login', methods=['GET', 'POST'])
def login():
    if request.method == 'POST':
        username = request.form['username']
        password = request.form['password']
        
        conn = sqlite3.connect(DB_FILE)
        cursor = conn.cursor()
        cursor.execute("SELECT * FROM users WHERE username = ? AND password = ?", (username, password))
        user_found = cursor.fetchone()
        conn.close()
        
        if user_found:
            session['username'] = username
            return redirect(url_for('dashboard'))
        else:
            flash("Invalid username or password.")
    return render_template_string(LOGIN_HTML)

@app.route('/register', methods=['GET', 'POST'])
def register():
    if request.method == 'POST':
        username = request.form['username']
        password = request.form['password']
        
        if not username or not password:
            flash("Fields cannot be empty.")
            return render_template_string(REGISTER_HTML)
            
        conn = sqlite3.connect(DB_FILE)
        cursor = conn.cursor()
        try:
            cursor.execute("INSERT INTO users (username, password) VALUES (?, ?)", (username, password))
            conn.commit()
            flash("Account created successfully! Please log in.")
            conn.close()
            return redirect(url_for('login'))
        except sqlite3.IntegrityError:
            flash("Username already exists. Try another one.")
        finally:
            conn.close()
            
    return render_template_string(REGISTER_HTML)

@app.route('/logout')
def logout():
    session.pop('username', None)
    return redirect(url_for('login'))

@app.route('/dashboard')
def dashboard():
    if "username" not in session:
        return redirect(url_for('login'))
    return render_template_string(DASHBOARD_HTML, username=session['username'], feature_type="none", prev_query="")

@app.route('/run-feature', methods=['POST'])
def run_feature():
    if "username" not in session:
        return redirect(url_for('login'))
    
    feature = request.form.get('feature')
    query = request.form.get('query', '').strip()
    feature_type = "text"
    output_data = ""

    if feature == "ask_ai":
        if not query: 
            output_data = "Error: Question required"
        else:
            prompt = f"You are AlianGPT, a CBSE AI Assistant. Explain simply with step-by-step logic. Question: {query}"
            output_data = get_ai_response(prompt)
            
    elif feature == "pdf_reader":
        file = request.files.get('pdf_file')
        if not file or file.filename == '':
            output_data = "Error: Please upload a physical PDF file using the file selector bar."
        else:
            try:
                reader = PyPDF2.PdfReader(file)
                text = ""
                for page in reader.pages:
                    text += page.extract_text() or ""
                output_data = f"--- PDF CONTENT SUMMARY ---\n\n" + get_ai_response(f"Summarize this text in simple language:\n\n{text[:10000]}")
            except Exception as e:
                output_data = f"Failed to parse PDF: {str(e)}"
                
    elif feature == "generate_quiz":
        if not query: 
            output_data = "Error: Topic required"
        else:
            prompt = f"""Create a quiz on '{query}' with exactly 3 multiple-choice questions. Return strictly valid JSON array format.
            Format: [{{"question": "...", "options": ["A) ..", "B) .."], "answer": "B"}}]"""
            raw = get_ai_response(prompt).replace("```json", "").replace("```", "").strip()
            try:
                output_data = json.loads(raw)
                feature_type = "quiz"
            except Exception:
                output_data = "Failed to compile structured quiz format. Try again."
                
    elif feature == "sample_paper":
        if not query: 
            output_data = "Error: Subject required"
        else:
            output_data = get_ai_response(f"Create a CBSE Model Question Paper for {query}. Include markings.")
            
    elif feature == "generate_code":
        if not query: 
            output_data = "Error: Code concept required"
        else:
            output_data = get_ai_response(f'Generate clean Python code for: {query}')
            
    elif feature == "mind_map":
        if not query: 
            output_data = "Error: Map topic required"
        else:
            structure = get_ai_response(f"Create a short structural hierarchy mindmap overview for: {query}. Keep it short.")
            try:
                dot = graphviz.Digraph(comment=query, format='png')
                dot.attr(rankdir='LR')
                dot.node('Center', query, shape='box', style='filled', fillcolor='lightblue')
                lines = structure.split('\n')
                for line in lines:
                    if '-' in line:
                        node_name = line.replace('-', '').replace(':', '').strip()
                        if node_name:
                            dot.node(node_name, node_name)
                            dot.edge('Center', node_name)
                img_bytes = dot.pipe(format='png')
                output_data = base64.b64encode(img_bytes).decode('utf-8')
                feature_type = "image"
            except Exception as e:
                output_data = f"Graphviz layout execution failed: {str(e)}. Ensure Graphviz binary is configured on system."
                
    elif feature == "periodic_table":
        periodic_table = {"H": "Hydrogen", "He": "Helium", "Li": "Lithium", "Be": "Beryllium", "B": "Boron", "C": "Carbon"}
        output_data = "🧪 Fast Chemical Elements Reference\n\n"
        for k, v in periodic_table.items():
            output_data += f"{k}: {v}\n"
            
    elif feature == "analytics":
        output_data = "📊 Study Logs Counter\nDatabase connectivity: Connected to SQLite. Account registries are permanently active."

    return render_template_string(DASHBOARD_HTML, username=session['username'], feature_type=feature_type, output_data=output_data, prev_query=query)

@app.route('/evaluate-quiz', methods=['POST'])
def evaluate_quiz():
    score = 0
    total = 3
    for idx in range(total):
        correct = request.form.get(f'ans_{idx}')
        user_choice = request.form.get(f'user_ans_{idx}')
        if user_choice and user_choice.startswith(correct):
            score += 1
    result = f"🏁 Quiz Evaluation Complete\nYou answered {score} out of {total} questions correctly!"
    return render_template_string(DASHBOARD_HTML, username=session.get('username', 'Student'), feature_type="text", output_data=result, prev_query="")

if __name__ == '__main__':
    port = int(os.environ.get("PORT", 5000))
    app.run(debug=False, host='0.0.0.0', port=port)
