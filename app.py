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

### dashboard.html ###
# menampilkan halaman dashboard
@app.route('/')
def dashboard():
    token_receive = request.cookies.get(TOKEN_KEY)
    try:
        payload = jwt.decode(token_receive, SECRET_KEY, algorithms = ['HS256'])
        user_info = db.users.find_one({'useremail': payload.get('id')})
        return render_template("dashboard.html", user_info = user_info)
    except jwt.ExpiredSignatureError:
        return redirect(url_for('home'))
    except jwt.exceptions.DecodeError:
        return redirect(url_for('home'))

### home.html ###
# menampilkan halaman home
@app.route('/main')
def home():
    return render_template('home.html')

### register.html ###
# menampilkan halaman daftar
@app.route('/daftar')
def register():
    return render_template('register.html')

# menyimpan pendaftaran akun
@app.route('/mendaftarkan-akun', methods = ['POST'])
def api_register():
    username_receive = request.form['username_give']
    useremail_receive = request.form['useremail_give']
    password_receive = request.form['password_give']
    password_hash = hashlib.sha256(password_receive.encode('utf-8')).hexdigest()
    doc = {
        'username': username_receive,
        'useremail': useremail_receive,
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

# mengecek email dan nama pengguna yang sudah terdaftar sebelumnya
@app.route('/mengecek-nama-pengguna-dan-email', methods=['POST'])
def api_register_valid():
    username_receive = request.form['username_give']
    useremail_receive = request.form['useremail_give']
    exists_username = bool(db.users.find_one({'username': username_receive}))
    exists_useremail = bool(db.users.find_one({'useremail': useremail_receive}))
    return jsonify({'result': 'success', 'exists_username': exists_username, 'exists_useremail': exists_useremail})

### login.html ###
# menampilkan halaman masuk
@app.route('/masuk')
def login():
    msg = request.args.get('msg')
    return render_template('login.html', msg = msg)

# menerima masuknya pengguna
@app.route('/memasukkan-akun', methods = ['POST'])
def api_login():
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

@app.route('/profil/<username>', methods = ['GET'])
def profile(username):
    # an endpoint for retrieving a user's profile information
    # and all of their posts
    token_receive = request.cookies.get(TOKEN_KEY)
    try:
        payload = jwt.decode(token_receive, SECRET_KEY, algorithms = ['HS256'])
        # if this is my own profile, True
        # if this is somebody else's profile, False
        status = username == payload.get('id')
        user_info = db.users.find_one({'username': username}, {'_id': False})
        return render_template('profile.html', user_info = user_info, status = status)
    except (jwt.ExpiredSignatureError, jwt.exceptions.DecodeError):
        return redirect(url_for('home'))

### chat.html ###

### purchase_history.html ###

### delivery_status.html ###

### collection.html ###

### order_form.html ###

### payment ###

if __name__ == '__main__':
    app.run('0.0.0.0', port=5000, debug=True)