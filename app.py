from flask import Flask, render_template, jsonify, request, redirect, url_for
from pymongo import MongoClient
from datetime import datetime, timedelta
from werkzeug.utils import secure_filename
import jwt
import hashlib

app = Flask(__name__)

app.config['TEMPLATES_AUTO_RELOAD'] = True
app.config['UPLOAD_FOLDER'] = './static/profile_pics'

MONGODB_CONNECTION_STRING = 'mongodb+srv://navirins:finalproject@navirins.hlkacsk.mongodb.net/?retryWrites=true&w=majority&appName=Navirins'
client = MongoClient(MONGODB_CONNECTION_STRING)
db = client.kelompok3

SECRET_KEY = 'AMDNOYUJIN'
TOKEN_KEY = 'bouquet'

### home.html ###
# menampilkan halaman depan
@app.route('/main')
def home():
    return render_template('home.html')

@app.route('/bertanya-di-depan')
def ask_in_home():
    name_receive = request.form['name_give']
    email_receive = request.form['email_give']
    subject_receive = request.form['subject_give']
    message_receive = request.form['message_give']

    doc = {
        'name': name_receive,
        'email': email_receive,
        'subject': subject_receive,
        'message': message_receive
    }
    db.ask_in_home.insert_one(doc)
    return jsonify({'result': 'success'})

### register.html ###
# menampilkan halaman daftar
@app.route('/daftar')
def register():
    return render_template('register.html')

# menyimpan pendaftaran akun
@app.route('/mendaftarkan-akun', methods = ['POST'])
def api_register():
    first_name_receive = request.form['first_name_give']
    last_name_receive = request.form['last_name_give']
    account_name_receive = request.form['account_name_give']
    useremail_receive = request.form['useremail_give']
    password_receive = request.form['password_give']
    password_hash = hashlib.sha256(password_receive.encode('utf-8')).hexdigest()
    doc = {
        'first_name': first_name_receive,
        'last_name': last_name_receive,
        'account_name': account_name_receive,
        'useremail': useremail_receive,
        'password': password_hash,
        'role': 'Member',
        'profile_name': " ".join([first_name_receive, last_name_receive]),
        'profile_pic': '',
        'profile_pic_real': 'profile_pics/profile_placeholder.png',
        'profile_info': '',
        'full_name': '',
        'address': ''
    }
    db.users.insert_one(doc)
    return jsonify({'result': 'success'})

# mengecek nama akun dan email yang sudah terdaftar sebelumnya
@app.route('/cek-nama-akun-dan-email', methods=['POST'])
def check_email_and_account_name():
    account_name_receive = request.form['account_name_give']
    useremail_receive = request.form['useremail_give']
    exists_account_name = bool(db.users.find_one({'account_name': account_name_receive}))
    exists_useremail = bool(db.users.find_one({'useremail': useremail_receive}))
    return jsonify({
        'result': 'success',
        'exists_account_name': exists_account_name,
        'exists_useremail': exists_useremail
    })

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

### profile.html ###
# menampilkan halaman profil
@app.route('/profil/<account_name>', methods = ['GET'])
def profile(account_name):
    token_receive = request.cookies.get(TOKEN_KEY)
    try:
        payload = jwt.decode(token_receive, SECRET_KEY, algorithms = ['HS256'])
        status = account_name == payload.get('id')
        user_info = db.users.find_one({'account_name': account_name}, {'_id': False})
        return render_template('profile.html', user_info = user_info, status = status)
    except (jwt.ExpiredSignatureError, jwt.exceptions.DecodeError):
        return redirect(url_for('dashboard'))

# memperbarui/update profile   
@app.route("/update_profile", methods=["POST"])
def save_img():
    token_receive = request.cookies.get(TOKEN_KEY)
    try:
        payload = jwt.decode(token_receive, SECRET_KEY, algorithms=["HS256"])
        useremail = payload.get('id')
        first_name_receive = request.form["first_name_give"]
        last_name_receive = request.form["last_name_give"]
        new_doc = {"first_name": first_name_receive, "last_name": last_name_receive}
        if "file_give" in request.files:
            file = request.files["file_give"]
            filename = secure_filename(file.filename)
            extension = filename.split(".")[-1]
            file_path = f"profile_pics/{useremail}.{extension}"
            file.save("./static/" + file_path)
            new_doc["profile_pic"] = filename
            new_doc["profile_pic_real"] = file_path
        db.users.update_one({"useremail": payload["id"]}, {"$set": new_doc})
        return jsonify({"result": "success", "msg": "Profile updated!"})
    except (jwt.ExpiredSignatureError, jwt.exceptions.DecodeError):
        return redirect(url_for("dashboard"))

### chat.html ###
# menampilkan halaman profil
@app.route('/obrolan/<account_name>', methods = ['GET'])
def chat(account_name):
    token_receive = request.cookies.get(TOKEN_KEY)
    try:
        payload = jwt.decode(token_receive, SECRET_KEY, algorithms = ['HS256'])
        status = account_name == payload.get('id')
        user_info = db.users.find_one({'account_name': account_name}, {'_id': False})
        return render_template('chat.html', user_info = user_info, status = status)
    except (jwt.ExpiredSignatureError, jwt.exceptions.DecodeError):
        return redirect(url_for('dashboard'))

# memasukkan obrolan
@app.route('/memasukkan-obrolan', methods = ['POST'])
def enter_chat():
    token_receive = request.cookies.get(TOKEN_KEY)
    try:
        payload = jwt.decode(token_receive, SECRET_KEY, algorithms = ['HS256'])
        user_info = db.users.find_one({'account_name': payload['id']})
        message_receive = request.form['message_give']
        date_receive = request.form['date_give']
        doc = {
            'account_name': user_info['account_name'],
            'profile_name': user_info['profile_name'],
            'profile_pic_real': user_info['profile_pic_real'],
            'message': message_receive,
            'date': date_receive
        }
        db.chats.insert_one(doc)
        return jsonify({'result': 'success', 'msg': 'Posting successful!'})
    except (jwt.ExpiredSignatureError, jwt.exceptions.DecodeError):
        return redirect(url_for('dashboard'))

# mendapatkan obrolan
@app.route('/mendapatkan-obrolan', methods = ['GET'])
def get_chats():
    token_receive = request.cookies.get(TOKEN_KEY)
    try:
        payload = jwt.decode(token_receive, SECRET_KEY, algorithms = ['HS256'])
        account_name_receive = request.args['account_name_give']
        if account_name_receive == '':
            chats = list(db.chats.find({}).sort('date', -1).limit(20))
        else:
            chats = list(db.chats.find({'account_name': account_name_receive}).sort('date', -1).limit(20))
        for post in chats:
            post['_id'] = str(post['_id'])
        return jsonify({'result': 'success', 'msg': 'Successfully fetched all chats!', 'chats': chats})
    except (jwt.ExpiredSignatureError, jwt.exceptions.DecodeError):
        return redirect(url_for('dashboard'))

### purchase_history.html ###


### delivery_status.html ###


### collection.html ###
@app.route('/koleksi')
def collection():
    token_receive = request.cookies.get(TOKEN_KEY)
    try:
        payload = jwt.decode(token_receive, SECRET_KEY, algorithms=['HS256'])
        user_info = db.users.find_one({'useremail': payload.get('id')})
        collections = list(db.collections.find())
        return render_template('collection.html', collections=collections, user_info=user_info)
    except jwt.ExpiredSignatureError:
        return redirect(url_for('home'))
    except jwt.exceptions.DecodeError:
        return redirect(url_for('home'))

### order_form.html ###


### payment ###


if __name__ == '__main__':
    app.run('0.0.0.0', port=5000, debug=True)