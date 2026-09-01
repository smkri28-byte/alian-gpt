from flask import Flask, render_template_string, request, redirect, url_for, session, flash
from google import genai
import sqlite3
import PyPDF2
import json
import os

app = Flask(__name__)

app.secret_key = os.environ.get("ae1ca680b123bd6926b1ad5ce228071c0d632b2ad2827e37")
API_KEY = os.environ.get("GEMINI_API_KEY")

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
            password TEXT NOT NULL,
            role TEXT DEFAULT 'user'
        )
    ''')
    # Safely migrate older database versions missing the 'role' column
    try:
        cursor.execute("ALTER TABLE users ADD COLUMN role TEXT DEFAULT 'user'")
    except sqlite3.OperationalError:
        pass 
        
    try:
        cursor.execute("INSERT INTO users VALUES (?, ?, ?)", ("admin", "password123", "admin"))
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
    .auth-container { max-width: 400px; margin: 50px auto; padding: 30px; background-color: #111111; border: 1px solid #222222; border-radius: 8px; text-align: center; }
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
    .btn-admin { background-color: #e67e22 !important; border: none; }
    .btn-admin:hover { background-color: #d35400 !important; }
    .alert { padding: 10px; background-color: #e74c3c; color: white; border-radius: 4px; margin-bottom: 15px; font-size: 14px; }
    .menu-box { background: #111111; padding: 20px; border-radius: 8px; border: 1px solid #222222; margin-bottom: 20px; }
    .output-box { background: #111111; padding: 20px; border-radius: 8px; border: 1px solid #222222; white-space: pre-wrap; font-family: 'Century Gothic', sans-serif; min-height: 200px; }
    .nav-bar { display: flex; justify-content: space-between; align-items: center; border-bottom: 1px solid #222222; padding-bottom: 10px; margin-bottom: 20px; }
    .quiz-option { display: block; margin: 10px 0; background: #222; padding: 10px; border-radius: 4px; }
    table { width: 100%; border-collapse: collapse; margin-top: 10px; }
    th, td { border: 1px solid #333; padding: 10px; text-align: left; }
    th { background-color: #222; }
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

    <div style="margin-top: 25px; border-top: 1px solid #222; padding-top: 20px;">
        <form method="POST" action="/admin-login-direct">
            <div class="form-group">
                <label style="font-size: 13px; color: #e67e22;">Admin Panel Key (Password 2014)</label>
                <input type="password" name="admin_key" placeholder="Enter Admin Password" required>
            </div>
            <input type="submit" value="Access Admin Panel" class="btn-admin" style="width: 100%;">
        </form>
    </div>
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
        <div>
            {% if role == 'admin' %}
                <a href="/admin"><button class="btn-admin" style="margin-right: 10px;">Admin Panel</button></a>
            {% endif %}
            <a href="/logout"><button>Log Out</button></a>
        </div>
    </div>
    
    <div class="headline">I am here Where are you? [{{ username }}]</div>

    <div class="menu-box">
        <h3>🛠️ Select Study Tool</h3>
        <form method="POST" action="/run-feature" enctype="multipart/form-data">
            <div class="form-group" style="display: flex; gap: 10px;">
                <select name="feature" style="width: 30%;">
                    <option value="ask_ai">Ask AI</option>
                    <option value="text_mindmap">Text Mindmap</option>
                    <option value="pdf_reader">Open PDF</option>
                    <option value="generate_quiz">Generate Quiz</option>
                    <option value="sample_paper">Sample Paper</option>
                    <option value="generate_code">Generate Code</option>
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

ADMIN_HTML = BASE_STYLE + """
<div class="dashboard-container">
    <div class="nav-bar">
        <h1>🛠️ Admin Control Panel</h1>
        <a href="/dashboard"><button>Back to Dashboard</button></a>
    </div>

    <div class="menu-box">
        <h3>📊 System Overview</h3>
        <p>Total Registered Accounts: <strong>{{ total_users }}</strong></p>
    </div>

    <div class="menu-box">
        <h3>👥 Manage User Accounts</h3>
        <table>
            <tr>
                <th>Username</th>
                <th>Role</th>
                <th>Actions</th>
            </tr>
            {% for u in users %}
            <tr>
                <td>{{ u[0] }}</td>
                <td>{{ u[1] }}</td>
                <td>
                    {% if u[0] != 'admin' %}
                    <form action="/admin/delete-user" method="POST" style="display:inline;">
                        <input type="hidden" name="username" value="{{ u[0] }}">
                        <input type="submit" value="Delete" style="background-color: #e74c3c; padding: 5px 10px; font-size: 12px;">
                    </form>
                    {% else %}
                    <em>Protected Admin</em>
                    {% endif %}
                </td>
            </tr>
            {% endfor %}
        </table>
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
        username = request.form['username'].strip()
        password = request.form['password']
        
        conn = sqlite3.connect(DB_FILE)
        cursor = conn.cursor()
        cursor.execute("SELECT username, role FROM users WHERE username = ? AND password = ?", (username, password))
        user_found = cursor.fetchone()
        conn.close()
        
        if user_found:
            session['username'] = user_found[0]
            session['role'] = user_found[1]
            return redirect(url_for('dashboard'))
        else:
            flash("Invalid username or password.")
    return render_template_string(LOGIN_HTML)

@app.route('/admin-login-direct', methods=['POST'])
def admin_login_direct():
    admin_key = request.form.get('admin_key')
    if admin_key == "2014":
        session['username'] = "admin"
        session['role'] = "admin"
        flash("Logged into Admin Panel successfully.")
        return redirect(url_for('admin_panel'))
    else:
        flash("Incorrect Admin Key Password.")
        return redirect(url_for('login'))

@app.route('/register', methods=['GET', 'POST'])
def register():
    if request.method == 'POST':
        username = request.form['username'].strip()
        password = request.form['password']
        
        if not username or not password:
            flash("Fields cannot be empty.")
            return render_template_string(REGISTER_HTML)
            
        conn = sqlite3.connect(DB_FILE)
        cursor = conn.cursor()
        try:
            cursor.execute("INSERT INTO users (username, password, role) VALUES (?, ?, ?)", (username, password, 'user'))
            conn.commit()
            flash("Account created successfully! Please log in.")
            conn.close()
            return redirect(url_for('login'))
        except sqlite3.IntegrityError:
            flash("Username already exists. Try another one.")
        finally:
            if conn:
                conn.close()
            
    return render_template_string(REGISTER_HTML)

@app.route('/logout')
def logout():
    session.clear()
    return redirect(url_for('login'))

@app.route('/dashboard')
def dashboard():
    if "username" not in session:
        return redirect(url_for('login'))
    
    try:
        conn = sqlite3.connect(DB_FILE)
        cursor = conn.cursor()
        cursor.execute("SELECT role FROM users WHERE username = ?", (session['username'],))
        row = cursor.fetchone()
        conn.close()
        role = row[0] if row else 'user'
    except Exception:
        role = 'user'
        
    session['role'] = role
    return render_template_string(DASHBOARD_HTML, username=session['username'], role=role, feature_type="none", prev_query="")

@app.route('/admin')
def admin_panel():
    if session.get('role') != 'admin':
        flash("Unauthorized access restricted to administrators.")
        return redirect(url_for('dashboard'))
        
    conn = sqlite3.connect(DB_FILE)
    cursor = conn.cursor()
    cursor.execute("SELECT username, role FROM users")
    users = cursor.fetchall()
    cursor.execute("SELECT COUNT(*) FROM users")
    total_users = cursor.fetchone()[0]
    conn.close()
    
    return render_template_string(ADMIN_HTML, users=users, total_users=total_users)

@app.route('/admin/delete-user', methods=['POST'])
def delete_user():
    if session.get('role') != 'admin':
        return redirect(url_for('dashboard'))
        
    target_user = request.form.get('username')
    if target_user != 'admin':
        conn = sqlite3.connect(DB_FILE)
        cursor = conn.cursor()
        cursor.execute("DELETE FROM users WHERE username = ?", (target_user,))
        conn.commit()
        conn.close()
        flash(f"User {target_user} deleted successfully.")
    
    return redirect(url_for('admin_panel'))

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
            
    elif feature == "text_mindmap":
        if not query:
            output_data = "Error: Topic required for mindmap"
        else:
            prompt = f"Create a structured text-based hierarchical mindmap using bullet points and indentation for the topic: {query}"
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
            
    elif feature == "periodic_table":
        periodic_table = {"H": "Hydrogen", "He": "Helium", "Li": "Lithium", "Be": "Beryllium", "B": "Boron", "C": "Carbon"}
        output_data = "🧪 Fast Chemical Elements Reference\n\n"
        for k, v in periodic_table.items():
            output_data += f"{k}: {v}\n"
            
    elif feature == "analytics":
        try:
            conn = sqlite3.connect(DB_FILE)
            cursor = conn.cursor()
            cursor.execute("SELECT COUNT(*) FROM users")
            count = cursor.fetchone()[0]
            conn.close()
        except Exception:
            count = "Unavailable"
        output_data = f"📊 Study Logs Counter\nDatabase connectivity: Connected to SQLite.\nTotal Registered Accounts: {count}"

    return render_template_string(DASHBOARD_HTML, username=session.get('username', 'Student'), role=session.get('role', 'user'), feature_type=feature_type, output_data=output_data, prev_query=query)

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
    return render_template_string(DASHBOARD_HTML, username=session.get('username', 'Student'), role=session.get('role', 'user'), feature_type="text", output_data=result, prev_query="")

if __name__ == '__main__':
    port = int(os.environ.get("PORT", 5000))
    app.run(debug=False, host='0.0.0.0', port=port)
