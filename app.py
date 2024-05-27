from flask import Flask, render_template, jsonify, request, redirect, url_for
from pymongo import MongoClient
from datetime import datetime, timedelta
from werkzeug.utils import secure_filename
import jwt
import hashlib

app = Flask(__name__)

app.config['TEMPLATES_AUTO_RELOAD'] = True
app.config['UPLOAD_FOLDER'] = './static/profile_pics'

MONGODB_CONNECTION_STRING = 'mongodb+srv://test:sparta@cluster0.6vz5zah.mongodb.net/?retryWrites=true&w=majority&appName=Cluster0'
client = MongoClient(MONGODB_CONNECTION_STRING)
db = client.TugasBesar

SECRET_KEY = 'AMDNOYUJIN'
TOKEN_KEY = 'mytoken'

@app.route('/')
def home():
    return render_template('home.html')

@app.route('/daftar')
def daftar():
    return render_template('register.html')

@app.route('/api_daftar/simpan', methods = ['POST'])
def daftar_simpan():
    useremail_receive = request.form['useremail_give']
    username_receive = request.form['username_give']
    password_receive = request.form['password_give']
    password_hash = hashlib.sha256(password_receive.encode('utf-8')).hexdigest()
    doc = {
        'useremail': useremail_receive,
        'username': username_receive,
        'password': password_hash,
        'role': 'Member',
        'profile_name': username_receive,
        'profile_pic': '',
        'profile_pic_real': 'profile_pics/profile_placeholder.png',
        'profile_info': '',
        'full_name': '',
        'address': ''
    }
    db.users.insert_one(doc)
    return jsonify({'result': 'success'})

@app.route('/daftar/check_email_and_username', methods=['POST'])
def check_email_and_username():
    username_receive = request.form['username_give']
    useremail_receive = request.form['useremail_give']
    exists_username = bool(db.users.find_one({'username': username_receive}))
    exists_useremail = bool(db.users.find_one({'useremail': useremail_receive}))
    return jsonify({'result': 'success', 'exists_username': exists_username, 'exists_useremail': exists_useremail})

@app.route('/masuk')
def masuk():
    msg = request.args.get('msg')
    return render_template('login.html', msg = msg)

@app.route('/api_masuk', methods = ['POST'])
def api_masuk():
    useremail_receive = request.form['useremail_give']
    password_receive = request.form['password_give']
    pw_hash = hashlib.sha256(password_receive.encode('utf-8')).hexdigest()
    result = db.users.find_one({'useremail': useremail_receive, 'password': pw_hash})
    if result:
        payload = {
            'id': useremail_receive,
            'exp': datetime.utcnow() + timedelta(seconds = 60 * 60 * 24)
        }
        token = jwt.encode(payload, SECRET_KEY, algorithm = 'HS256')
        return jsonify({'result': 'success', 'token': token})
    else:
        return jsonify({'result': 'fail', 'msg': 'We could not find a user with that id/password combination'})

@app.route('/main', methods = ['GET'])
def dashboard():
    token_receive = request.cookies.get(TOKEN_KEY)
    try:
        payload = jwt.decode(token_receive, SECRET_KEY, algorithms = ['HS256'])
        user_info = db.users.find_one({'useremail': payload.get('id')})
        return render_template("dashboard.html", user_info = user_info)
    except jwt.ExpiredSignatureError:
        return redirect(url_for('masuk', msg = 'Token login Anda telah kedaluwarsa'))
    except jwt.exceptions.DecodeError:
        return redirect(url_for('masuk', msg = 'Ada masalah saat Anda login'))

@app.route('/profilku/<username>', methods = ['GET'])
def profil(username):
    token_receive = request.cookies.get(TOKEN_KEY)
    try:
        payload = jwt.decode(token_receive, SECRET_KEY, algorithms = ['HS256'])
        status = useremail == payload.get('id')
        user_info = db.users.find_one({'useremail': useremail}, {'_id': False})
        return render_template('profilku.html', user_info = user_info, status = status)
    except (jwt.ExpiredSignatureError, jwt.exceptions.DecodeError):
        return redirect(url_for('dashboard'))

if __name__ == '__main__':
    app.run('0.0.0.0', port=5000, debug=True)