# (Removed the stray opening triple quotes)

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
    out = [{'name': r['name'], 'address': r['public_address'], 'balance': r['balance']}
           for r in rows]
    return jsonify({'balances': out})


# Leaderboard
@app.route('/leaderboard', methods=['GET'])
def route_leaderboard():
    db = get_db()
    rows = db.execute(
        'SELECT name, public_address, balance FROM users ORDER BY balance DESC LIMIT 10'
    ).fetchall()
    out = [{'name': r['name'], 'address': r['public_address'], 'balance': r['balance']}
           for r in rows]
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


if __name__ == '__main__':
    app.run(debug=True)
  
