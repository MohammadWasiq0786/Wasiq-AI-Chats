import os
import sqlite3
import hashlib
from flask import Flask, render_template, request, jsonify, redirect, session, url_for
from flask_session import Session
from euriai import EuriaiClient
from database_setup import setup_database
   
# Load model
EURI_API_KEY = os.getenv("EURI_API_KEY")
client = EuriaiClient(api_key=EURI_API_KEY, model="gpt-4.1-nano")

app = Flask(__name__)
app.secret_key = "secret"
app.config['SESSION_TYPE'] = 'filesystem'
Session(app)

DB_NAME = "database/chatbot_data.db"

if DB_NAME and not os.path.exists(DB_NAME):
    setup_database()
# Ensure the database is set up


# ---------- Database Helpers ----------
def connect_db():
    return sqlite3.connect(DB_NAME)

def log_action(actor, action):
    with connect_db() as conn:
        conn.execute("INSERT INTO logs (actor, action) VALUES (?, ?)", (actor, action))
        conn.commit()

# ---------- Auth Routes ----------
# @app.route('/')
# def home():
#     return redirect('/login')

@app.route('/')
def home():
    return render_template('index.html')


@app.route('/register', methods=['GET', 'POST'])
def register():
    if request.method == 'POST':
        username = request.form.get('username')
        email = request.form.get('email')
        password = hashlib.sha256(request.form.get('password').encode()).hexdigest()

        if not email or not password:
            return "All fields are required."

        try:
            with connect_db() as conn:
                conn.execute("INSERT INTO users (username, email, password) VALUES (?, ?, ?)",
                             (username, email, password))
                conn.commit()
                return redirect('/login')
        except sqlite3.IntegrityError:
            return "User with this email already exists."
    return render_template('register.html')

@app.route('/login', methods=['GET', 'POST'])
def login():
    if request.method == 'POST':
        email = request.form.get('email')
        password = hashlib.sha256(request.form.get('password').encode()).hexdigest()

        with connect_db() as conn:
            user = conn.execute("SELECT * FROM users WHERE email=? AND password=?", (email, password)).fetchone()
            if user:
                session['user_id'] = user[0]
                session['username'] = user[1]
                session['is_admin'] = user[4]
                log_action(user[1], "Logged in")
                return redirect('/chat')
        return "Invalid credentials"
    return render_template('login.html')

@app.route('/logout')
def logout():
    log_action(session.get('username', 'Unknown'), "Logged out")
    session.clear()
    return redirect('/login')

# ---------- Chat Interface ----------
@app.route('/chat')
def chat():
    if 'user_id' not in session:
        return redirect('/login')
    return render_template('chat.html', username=session['username'])

@app.route('/get_chats')
def get_chats():
    with connect_db() as conn:
        rows = conn.execute("SELECT id, name FROM chats WHERE user_id=?", (session['user_id'],)).fetchall()
        chats = [{'id': row[0], 'name': row[1]} for row in rows]
    return jsonify({'chats': chats})

@app.route('/get_chat_history')
def get_chat_history():
    chat_id = request.args.get('chat_id')
    with connect_db() as conn:
        messages = conn.execute("SELECT sender, text FROM messages WHERE chat_id=?", (chat_id,)).fetchall()
        return jsonify({'messages': [{'text': f'{sender}: {text}'} for sender, text in messages]})

@app.route('/generate', methods=['POST'])
def generate():
    data = request.get_json()
    user_input = data['input']
    chat_id = data['chat_id']

    with connect_db() as conn:
        chat_history = conn.execute("SELECT sender, text FROM messages WHERE chat_id=?", (chat_id,)).fetchall()
        formatted = [f"{s}: {t}" for s, t in chat_history]
        context = "\n".join(formatted)
        prompt = f"{context}\nUser: {user_input}\nAI:"
        response = client.generate_completion(prompt=prompt, temperature=0.5, max_tokens=1000)
        ai_text = response['choices'][0]['message']['content'] if 'choices' in response else ""

        conn.execute("INSERT INTO messages (chat_id, sender, text) VALUES (?, ?, ?)", (chat_id, 'User', user_input))
        conn.execute("INSERT INTO messages (chat_id, sender, text) VALUES (?, ?, ?)", (chat_id, 'AI', ai_text))
        conn.commit()

    return jsonify({'response': ai_text})

@app.route('/new_chat', methods=['POST'])
def new_chat():
    data = request.get_json()
    name = data['chat_name']
    with connect_db() as conn:
        conn.execute("INSERT INTO chats (user_id, name, model) VALUES (?, ?, ?)", (session['user_id'], name, 'gpt-4.1-nano'))
        chat_id = conn.execute("SELECT last_insert_rowid()").fetchone()[0]
        conn.commit()
    return jsonify({'chat_id': chat_id})

@app.route('/delete_chat', methods=['POST'])
def delete_chat():
    data = request.get_json()
    chat_id = data['chat_id']
    with connect_db() as conn:
        conn.execute("DELETE FROM messages WHERE chat_id=?", (chat_id,))
        conn.execute("DELETE FROM chats WHERE id=?", (chat_id,))
        conn.commit()
    return jsonify({'status': 'Chat deleted'})

@app.route('/download_chat')
def download_chat():
    chat_id = request.args.get('chat_id')
    with connect_db() as conn:
        rows = conn.execute("SELECT sender, text, timestamp FROM messages WHERE chat_id=?", (chat_id,)).fetchall()
    content = "Sender,Text,Timestamp\n" + "\n".join([f"{r[0]},{r[1]},{r[2]}" for r in rows])
    return content, 200, {
        'Content-Type': 'text/csv',
        'Content-Disposition': f'attachment; filename={session["username"]}-chat{chat_id}.csv'
    }

# ---------- Admin Dashboard ----------
@app.route('/admin')
def admin():
    if not session.get('is_admin'):
        return "Unauthorized"
    with connect_db() as conn:
        logs = conn.execute("SELECT * FROM logs ORDER BY timestamp DESC").fetchall()
        users = conn.execute("SELECT id, username, email, is_admin FROM users").fetchall()
    return render_template('admin.html', logs=logs, users=users)

if __name__ == '__main__':
    app.run(debug=True)