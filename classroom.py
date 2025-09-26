"""
EduCoin – Classroom Cryptocurrency
-----------------------------------
A Flask web app where teachers can mint coins and students can transfer them.
This is a self-contained example with SQLite.

Run:
    pip install flask
    export TEACHER_PASSWORD=yourpass   # or set TEACHER_PASSWORD=yourpass on Windows
    python educoin_flask_app.py
"""

from flask import Flask, request, jsonify, render_template_string, g
import sqlite3
import os
import uuid
import datetime

DB_PATH = os.path.join(os.path.dirname(__file__), 'educoin.db')
TEACHER_PASSWORD = os.environ.get('TEACHER_PASSWORD', 'teacherpass')  # change for production

app = Flask(__name__)
app.config['JSON_SORT_KEYS'] = False

# ------------------ Database helpers ------------------
def get_db():
    db = getattr(g, '_database', None)
    if db is None:
        db = g._database = sqlite3.connect(DB_PATH)
        db.row_factory = sqlite3.Row
    return db

@app.teardown_appcontext
def close_connection(exception):
    db = getattr(g, '_database', None)
    if db is not None:
        db.close()

def init_db():
    db = sqlite3.connect(DB_PATH)
    c = db.cursor()
    c.execute('''
        CREATE TABLE IF NOT EXISTS users (
            id TEXT PRIMARY KEY,
            name TEXT NOT NULL,
            public_address TEXT NOT NULL UNIQUE,
            pin TEXT NOT NULL,
            balance INTEGER NOT NULL DEFAULT 0,
            created_at TEXT NOT NULL
        )
    ''')
    c.execute('''
        CREATE TABLE IF NOT EXISTS transactions (
            id TEXT PRIMARY KEY,
            timestamp TEXT NOT NULL,
            from_addr TEXT,
            to_addr TEXT,
            amount INTEGER NOT NULL,
            note TEXT
        )
    ''')
    db.commit()
    db.close()

def now_iso():
    return datetime.datetime.utcnow().isoformat() + 'Z'

def create_user(name):
    uid = str(uuid.uuid4())
    addr = 'EDU-' + uid[:8]
    pin = str(uuid.uuid4())[:4]
    db = get_db()
    db.execute(
        'INSERT INTO users (id, name, public_address, pin, balance, created_at) VALUES (?, ?, ?, ?, ?, ?)',
        (uid, name, addr, pin, 0, now_iso())
    )
    db.commit()
    return {'id': uid, 'name': name, 'public_address': addr, 'pin': pin, 'balance': 0}

def get_user_by_addr(addr):
    db = get_db()
    return db.execute('SELECT * FROM users WHERE public_address = ?', (addr,)).fetchone()

def update_balance(addr, new_balance):
    db = get_db()
    db.execute('UPDATE users SET balance = ? WHERE public_address = ?', (new_balance, addr))
    db.commit()

def add_transaction(from_addr, to_addr, amount, note=None):
    tid = str(uuid.uuid4())
    db = get_db()
    db.execute(
        'INSERT INTO transactions (id, timestamp, from_addr, to_addr, amount, note) VALUES (?, ?, ?, ?, ?, ?)',
        (tid, now_iso(), from_addr, to_addr, amount, note)
    )
    db.commit()
    return tid

init_db()

# ------------------ Routes ------------------
@app.route('/')
def index():
    db = get_db()
    users = db.execute('SELECT name, public_address, balance FROM users ORDER BY name').fetchall()
    ledger = db.execute(
        'SELECT timestamp, from_addr, to_addr, amount, note FROM transactions ORDER BY timestamp DESC LIMIT 20'
    ).fetchall()
    html = '''
    <h1>EduCoin Classroom Dashboard</h1>
    <h2>Students</h2>
    <table border="1" cellpadding="6">
      <tr><th>Name</th><th>Address</th><th>Balance</th></tr>
      {% for u in users %}
        <tr><td>{{u['name']}}</td><td>{{u['public_address']}}</td><td>{{u['balance']}}</td></tr>
      {% endfor %}
    </table>
    <h2>Ledger (latest 20)</h2>
    <table border="1" cellpadding="6">
      <tr><th>Time</th><th>From</th><th>To</th><th>Amount</th><th>Note</th></tr>
      {% for t in ledger %}
        <tr><td>{{t['timestamp']}}</td><td>{{t['from_addr'] or 'MINT'}}</td>
            <td>{{t['to_addr']}}</td><td>{{t['amount']}}</td><td>{{t['note']}}</td></tr>
      {% endfor %}
    </table>
    <p>Use API endpoints to create wallets, mint coins, and transfer coins.</p>
    '''
    return render_template_string(html, users=users, ledger=ledger)

# Create wallet
@app.route('/create_wallet', methods=['POST'])
def route_create_wallet():
    data = request.get_json() or {}
    name = data.get('name')
    if not name:
        return jsonify({'error': 'name required'}), 400
    user = create_user(name)
    return jsonify({'user': user}), 201

# Mint coins (teacher only)
@app.route('/mint', methods=['POST'])
def route_mint():
    data = request.get_json() or {}
    pwd = data.get('teacher_password')
    to_addr = data.get('to')
    amount = int(data.get('amount', 1))
    note = data.get('note', 'minted by teacher')

    if pwd != TEACHER_PASSWORD:
        return jsonify({'error': 'invalid teacher password'}), 403
    if not to_addr:
        return jsonify({'error': 'to address required'}), 400

    user = get_user_by_addr(to_addr)
    if not user:
        return jsonify({'error': 'recipient not found'}), 404

    new_balance = user['balance'] + amount
    update_balance(to_addr, new_balance)
    tid = add_transaction(None, to_addr, amount, note)
    return jsonify({
        'tx_id': tid,
        'to': to_addr,
        'amount': amount,
        'new_balance': new_balance
    }), 200

# Transfer between students
@app.route('/transfer', methods=['POST'])
def route_transfer():
    data = request.get_json() or {}
    from_addr = data.get('from')
    to_addr = data.get('to')
    amount = int(data.get('amount', 0))
    pin = data.get('pin')
    note = data.get('note', '')

    if not all([from_addr, to_addr]) or amount <= 0:
        return jsonify({'error': 'from, to, and positive amount required'}), 400

    sender = get_user_by_addr(from_addr)
    receiver = get_user_by_addr(to_addr)
    if not sender or not receiver:
        return jsonify({'error': 'sender or receiver not found'}), 404

    if pin != sender['pin']:
        return jsonify({'error': 'invalid PIN'}), 403

    if sender['balance'] < amount:
        return jsonify({'error': 'insufficient balance'}), 400

    update_balance(from_addr, sender['balance'] - amount)
    update_balance(to_addr, receiver['balance'] + amount)
    tid = add_transaction(from_addr, to_addr, amount, note)
    return jsonify({
        'tx_id': tid,
        'from': from_addr,
        'to': to_addr,
        'amount': amount
    }), 200

# Balances
@app.route('/balances', methods=['GET'])
def route_balances():
    db = get_db()
    rows = db.execute(
        'SELECT name, public_address, balance FROM users ORDER BY balance DESC'
    ).fetchall()
    out = [{'name': r['name'], 'address': r['public_address'], 'balance': r['balance']} for r in rows]
    return jsonify({'balances': out})

# Leaderboard
@app.route('/leaderboard', methods=['GET'])
def route_leaderboard():
    db = get_db()
    rows = db.execute(
        'SELECT name, public_address, balance FROM users ORDER BY balance DESC LIMIT 10'
    ).fetchall()
    out = [{'name': r['name'], 'address': r['public_address'], 'balance': r['balance']} for r in rows]
    return jsonify({'leaderboard': out})

# Ledger
@app.route('/ledger', methods=['GET'])
def route_ledger():
    db = get_db()
    rows = db.execute(
        'SELECT timestamp, from_addr, to_addr, amount, note FROM transactions '
        'ORDER BY timestamp DESC LIMIT 200'
    ).fetchall()
    out = [dict(r) for r in rows]
    return jsonify({'ledger': out})

# ------------------ Run ------------------
if __name__ == '__main__':
    app.run(debug=True)
