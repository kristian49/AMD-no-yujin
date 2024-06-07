from flask import Flask, render_template, jsonify, request, redirect, url_for
from pymongo import MongoClient
from werkzeug.utils import secure_filename
from datetime import datetime, timedelta
from bson import ObjectId
from os.path import join, dirname
from dotenv import load_dotenv
import jwt
import hashlib
import os

app = Flask(__name__)

dotenv_path = join(dirname(__file__), '.env')
load_dotenv(dotenv_path)

MONGODB_URI = os.environ.get('MONGODB_URI')
DB_NAME =  os.environ.get('DB_NAME')

client = MongoClient(MONGODB_URI)
db = client[DB_NAME]

app.config['TEMPLATES_AUTO_RELOAD'] = True
app.config['UPLOAD_FOLDER'] = './static/profile_pics'
app.config['UPLOAD_COLLECTION_FOLDER'] = './static/collection_pics'

SECRET_KEY = 'AMDNOYUJIN'
TOKEN_KEY = 'bouquet'

### home.html atau dashboard.html ###
# menampilkan halaman depan (sebelum pengguna login) atau halaman dashboard (sesudah pengguna login)
@app.route('/')
def home():
    token_receive = request.cookies.get(TOKEN_KEY)
    try:
        payload = jwt.decode(token_receive, SECRET_KEY, algorithms = ['HS256'])
        user_info = db.users.find_one({'useremail': payload.get('id')})
        return render_template('dashboard.html', user_info = user_info)
    except (jwt.ExpiredSignatureError, jwt.exceptions.DecodeError):
        return render_template('home.html')
    
# menyimpan pesan pada hubungi kami
@app.route('/hubungi-kami', methods = ['POST'])
def contact_us():
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
    db.contactUs.insert_one(doc)
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
        'profile_name': ' '.join([first_name_receive, last_name_receive]),
        'profile_pic': '',
        'profile_pic_real': 'profile_pics/profile_placeholder.png',
        'neighbourhood': neighbourhood_receive,
        'hamlet': hamlet_receive,
        'village_or_urban_village': village_or_urban_village_receive,
        'sub_district': sub_district_receive,
        'regency_or_town': regency_or_town_receive,
        'province': province_receive,
        'phone': phone_receive,
        'bio': bio_receive
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

### profile.html ###
# menampilkan halaman profil
@app.route('/profil/<account_name>', methods = ['GET'])
def profile(account_name):
    token_receive = request.cookies.get(TOKEN_KEY)
    try:
        payload = jwt.decode(token_receive, SECRET_KEY, algorithms = ['HS256'])
        status = account_name == payload.get('id')
        user_info = db.users.find_one({'account_name': account_name}, {'_id': False})
        # return render_template('profile.html', user_info = user_info, status = status)
        return render_template('profile_coba.html', user_info = user_info, status = status)
    except (jwt.ExpiredSignatureError, jwt.exceptions.DecodeError):
        return redirect(url_for('home'))

# # memperbarui profil
# @app.route('/update_profile', methods=['POST'])
# def save_img():
#     token_receive = request.cookies.get(TOKEN_KEY)
#     try:
#         payload = jwt.decode(token_receive, SECRET_KEY, algorithms=['HS256'])
#         useremail = payload.get('id')
#         first_name_receive = request.form['first_name_give']
#         last_name_receive = request.form['last_name_give']
#         address_receive = request.form['address_give']
#         new_doc = {'first_name': first_name_receive, 'last_name': last_name_receive, 'address': address_receive}
#         if 'file_give' in request.files:
#             file = request.files['file_give']
#             filename = secure_filename(file.filename)
#             extension = filename.split('.')[-1]
#             mungkin pakai account_name aja, agar alamat email lebih privat
#             file_path = f'profile_pics/{useremail}.{extension}'
#             file.save('./static/' + file_path)
#             new_doc['profile_pic'] = filename
#             new_doc['profile_pic_real'] = file_path
#         db.users.update_one({'useremail': payload['id']}, {'$set': new_doc})
#         return jsonify({'result': 'success', 'msg': 'Profile updated!'})
#     except (jwt.ExpiredSignatureError, jwt.exceptions.DecodeError):
#         return redirect(url_for('home'))

# memperbarui profil_coba
@app.route('/memperbarui-profil', methods=['POST'])
def update_profile():
    token_receive = request.cookies.get(TOKEN_KEY)
    try:
        payload = jwt.decode(token_receive, SECRET_KEY, algorithms = ['HS256'])
        account_name = payload.get('id')

        first_name_receive = request.form['first_name_give']
        last_name_receive = request.form['last_name_give']
        neighbourhood_receive = request.form['neighbourhood_give']
        hamlet_receive = request.form['hamlet_give']
        village_or_urban_village_receive = request.form['village_or_urban_village_give']
        sub_district_receive = request.form['sub_district_give']
        regency_or_town_receive = request.form['regency_or_town_give']
        province_receive = request.form['province_give']
        phone_receive = request.form['phone_give']
        bio_receive = request.form['bio_give']

        new_doc = {
            'first_name': first_name_receive,
            'last_name': last_name_receive,
            'neighbourhood': neighbourhood_receive,
            'hamlet': hamlet_receive,
            'village/urban_village': village/urban_village_receive,
            'sub-district': sub-district_receive,
            'regency/town': regency/town_receive,
            'province': province_receive,
            'phone': phone_receive,
            'bio': bio_receive
        }

        if 'file_give' in request.files:
            file = request.files['file_give']
            filename = secure_filename(file.filename)
            extension = filename.split('.')[-1]
            file_path = f'profile_pics/{account_name}.{extension}'
            file.save('./static/' + file_path)
            new_doc['profile_pic'] = filename
            new_doc['profile_pic_real'] = file_path
        
        db.users.update_one({'useremail': payload['id']}, {'$set': new_doc})
        # Kita update profil user disini
        return jsonify({'result': 'success', 'msg': 'Profil Anda telah diperbarui!'})
    except (jwt.ExpiredSignatureError, jwt.exceptions.DecodeError):
        return redirect(url_for('home'))

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
        return redirect(url_for('home'))

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
        return redirect(url_for('home'))

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
        return redirect(url_for('home'))

### purchase_history.html ###


### delivery_status.html ###


# tambah koleksi 
@app.route('/tambah-koleksi', methods=['POST'])
def tambah_koleksi():
    name_receive = request.form['name']
    description_receive = request.form['description']
    price_receive = request.form['price']
    category_receive = request.form['category']
    image = request.files['image']
    image_filename = secure_filename(image.filename)
    image_path = os.path.join(app.config['UPLOAD_COLLECTION_FOLDER'], image_filename)
    image.save(image_path)

    doc = {
        'name': name_receive,
        'description': description_receive,
        'price': price_receive,
        'category': category_receive,
        'image': image_path
    }
    db.collections.insert_one(doc)
    return redirect(url_for('collection'))

# Endpoint untuk menampilkan halaman koleksi
@app.route('/koleksi')
def collection():
    token_receive = request.cookies.get(TOKEN_KEY)
    try:
        payload = jwt.decode(token_receive, SECRET_KEY, algorithms=['HS256'])
        user_info = db.users.find_one({'useremail': payload.get('id')})
        collections = list(db.collections.find())
        return render_template('collection_baru.html', collections=collections, user_info=user_info)
    except jwt.ExpiredSignatureError:
        return redirect(url_for('home'))
    except jwt.exceptions.DecodeError:
        return redirect(url_for('home'))

### order_form.html ###

@app.route('/order_form')
def order():
    token_receive = request.cookies.get(TOKEN_KEY)
    try:
        payload = jwt.decode(token_receive, SECRET_KEY, algorithms=['HS256'])
        user_info = db.users.find_one({'useremail': payload.get('id')})
        collection = db.collections.find_one()
        if collection and 'image' in collection:
            collection['image'] = f'static/{collection["image"]}'
        return render_template('order_form.html', collection=collection, user_info=user_info)
    except (jwt.ExpiredSignatureError, jwt.exceptions.DecodeError):
        return redirect(url_for('home'))
# Menampilkan halaman form pemesanan produk
@app.route('/order_form/<collection_id>')
def order_form(collection_id):
    token_receive = request.cookies.get(TOKEN_KEY)
    try:
        payload = jwt.decode(token_receive, SECRET_KEY, algorithms=['HS256'])
        user_info = db.users.find_one({'useremail': payload.get('id')})
        collection = db.collections.find_one({'_id': ObjectId(collection_id)})
        if collection and 'image' in collection:
            collection['image'] = f'static/{collection['image']}'
        return render_template('order_form.html', collection=collection, user_info=user_info)
    except (jwt.ExpiredSignatureError, jwt.exceptions.DecodeError):
        return redirect(url_for('home'))

# Menyimpan informasi pemesanan produk
@app.route('/process_order', methods=['POST'])
def process_order():
    token_receive = request.cookies.get(TOKEN_KEY)
    try:
        payload = jwt.decode(token_receive, SECRET_KEY, algorithms=['HS256'])
        user_info = db.users.find_one({'useremail': payload.get('id')})
        collection_id = request.form.get('collection_id')
        quantity = request.form.get('quantity')
        name = request.form.get('name')
        email = request.form.get('email')
        address = request.form.get('address')

        # Simpan informasi pemesanan produk ke dalam database
        order_data = {
            'collection_id': ObjectId(collection_id),
            'quantity': quantity,
            'name': name,
            'email': email,
            'address': address,
            'useremail': user_info['useremail']  # Menyimpan email pengguna yang sedang login
        }
        db.orders.insert_one(order_data)

        # Redirect ke halaman terima kasih atau halaman lain yang sesuai
        return redirect(url_for('home'))

    except (jwt.ExpiredSignatureError, jwt.exceptions.DecodeError):
        return redirect(url_for('home'))
### payment ###


if __name__ == '__main__':
    app.run('0.0.0.0', port=5000, debug=True)