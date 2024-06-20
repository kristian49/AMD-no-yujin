from pymongo import MongoClient
import jwt
import datetime
import hashlib
from flask import Flask, render_template, jsonify, request, redirect, url_for
from werkzeug.utils import secure_filename
from datetime import datetime, timedelta
from functools import wraps
from bson import ObjectId
import os
import pytz
from os.path import join, dirname
from dotenv import load_dotenv

app = Flask(__name__)

dotenv_path = join(dirname(__file__), '.env')
load_dotenv(dotenv_path)

SECRET_KEY = os.environ.get('SECRET_KEY')
TOKEN_KEY =  os.environ.get('TOKEN_KEY')

MONGODB_URI = os.environ.get('MONGODB_URI')
DB_NAME =  os.environ.get('DB_NAME')

client = MongoClient(MONGODB_URI)
db = client[DB_NAME]

app.config['TEMPLATES_AUTO_RELOAD'] = True
app.config['UPLOAD_FOLDER'] = './static/profile_pics'
app.config['UPLOAD_COLLECTION_FOLDER'] = './static/collection_pics'
app.config['UPLOAD_PAYMENT_FOLDER'] = './static/payment'

# fungsi untuk admin
def admin_required(f):
    @wraps(f)
    def admin_function(*args, **kwargs):
        token_receive = request.cookies.get(TOKEN_KEY)
        if token_receive is not None:
            try:
                payload = jwt.decode(token_receive, SECRET_KEY, algorithms=['HS256'])
                if payload['role'] == 'admin':
                    return f(*args, **kwargs)
                else:
                    return redirect(url_for('home', msg = 'Hanya admin yang dapat mengakses halaman ini'))
            except (jwt.ExpiredSignatureError, jwt.exceptions.DecodeError):
                return redirect(url_for('login', msg ='Token Anda tidak valid atau telah kedaluwarsa'))
        else: 
            return redirect(url_for('login', msg = 'Silakan masuk untuk melihat halaman ini'))
    return admin_function

### home.html atau dashboard.html ###
# menampilkan halaman depan (sebelum pengguna login) atau halaman dashboard (sesudah pengguna login)
@app.route('/')
def home():
    token_receive = request.cookies.get(TOKEN_KEY)
    try:
        title = 'Beranda'
        payload = jwt.decode(token_receive, SECRET_KEY, algorithms=['HS256'])
        user_info = db.users.find_one({'useremail': payload.get('id')})
        account_name = user_info['account_name']

        # Menghitung total pembelian dan total bucket
        payments = list(db.payment.find({'account_name': account_name}))
        total_pembelian = sum(payment['total_price'] for payment in payments)
        total_bucket = sum(payment['quantity'] for payment in payments)
        total_pembelian_rupiah = format_rupiah(total_pembelian)

        return render_template('user/dashboard.html', title = title, user_info = user_info, total_pembelian = total_pembelian, total_bucket = total_bucket, total_pembelian_rupiah = total_pembelian_rupiah)
    except (jwt.ExpiredSignatureError, jwt.exceptions.DecodeError):
        title = 'Beranda'
        return render_template('user/home.html', title = title)

# untuk menampilkan format rupiah
def format_rupiah(value):
    return f'Rp {value:,.0f}'.replace(',', '.')
    
# menyimpan pesan pada hubungi kami
@app.route('/hubungi-kami', methods=['POST'])
def contact_us():
    name_receive = request.form['name_give']
    email_receive = request.form['email_give']
    subject_receive = request.form['subject_give']
    message_receive = request.form['message_give']
    
    timezone = pytz.timezone('Asia/Jakarta')
    current_datetime = datetime.now(timezone)
    tanggal_kirim = current_datetime.strftime('%d/%m/%y - %H:%M')
    timestamp = current_datetime.timestamp()
    doc = {
        'name': name_receive,
        'email': email_receive,
        'subject': subject_receive,
        'message': message_receive,
        'tanggal_kirim' : tanggal_kirim,
        'timestamp': timestamp,
    }
    db.contact_us.insert_one(doc)
    return jsonify({'result': 'success'})

### register.html ###
# menampilkan halaman daftar
@app.route('/daftar')
def register():
    title = 'Daftar'
    return render_template('user/auth/register.html', title = title)

# mengecek nama akun dan email yang sudah terdaftar sebelumnya
@app.route('/cek-nama-akun-dan-email', methods=['POST'])
def check_email_and_account_name():
    account_name_receive = request.form['account_name_give']
    useremail_receive = request.form['useremail_give']
    exists_account_name = bool(db.users.find_one({'account_name': account_name_receive}))
    exists_useremail = bool(db.users.find_one({'useremail': useremail_receive}))
    return jsonify({'result': 'success', 'exists_account_name': exists_account_name, 'exists_useremail': exists_useremail})

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
        'role': 'member',
        'profile_name': ' '.join([first_name_receive, last_name_receive]),
        'profile_pic': '',
        'profile_pic_real': 'profile_pics/profile_placeholder.png'
    }
    db.users.insert_one(doc)
    return jsonify({'result': 'success'})

### login.html ###
# menampilkan halaman masuk
@app.route('/masuk')
def login():
    token_receive = request.cookies.get(TOKEN_KEY)
    try:
        title = 'Masuk'
        if token_receive:
            payload = jwt.decode(token_receive, SECRET_KEY, algorithms = ['HS256'])
            user_info = db.users.find_one({'useremail': payload['id']})
            if user_info:
                return redirect(url_for('home'))
        
        return render_template('user/auth/login.html', title = title)
    
    except (jwt.ExpiredSignatureError, jwt.exceptions.DecodeError):
        title = 'Masuk'
        return render_template('user/auth/login.html', title = title)

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
            'exp': datetime.utcnow() + timedelta(seconds = 60 * 60 * 24),
            'role': result['role']
        }
        token = jwt.encode(payload, SECRET_KEY, algorithm = 'HS256')
        return jsonify({'result': 'success', 'token': token})
    else:
        return jsonify({'result': 'fail'})

### profile.html ###
# menampilkan halaman profil
@app.route('/profil/<account_name>')
def profile(account_name):
    token_receive = request.cookies.get(TOKEN_KEY)
    try:
        payload = jwt.decode(token_receive, SECRET_KEY, algorithms = ['HS256'])
        status = account_name == payload["id"]  
        user_info = db.users.find_one({'account_name': account_name}, {'_id': False})
        return render_template('user/profile.html', user_info = user_info, status = status)
    except (jwt.ExpiredSignatureError, jwt.exceptions.DecodeError):
        return redirect(url_for('home'))

# perbarui profil
@app.route('/perbarui-profil', methods = ['POST'])
def update_profile():
    token_receive = request.cookies.get(TOKEN_KEY)
    try:
        payload = jwt.decode(token_receive, SECRET_KEY, algorithms = ['HS256'])
        useremail = payload['id']

        first_name_receive = request.form['first_name_give']
        last_name_receive = request.form['last_name_give']
        address_receive = request.form['address_give']
        phone_receive = request.form['phone_give']
        bio_receive = request.form['bio_give']

        new_doc = {
            'first_name': first_name_receive,
            'last_name': last_name_receive,
            'profile_name': ' '.join([first_name_receive, last_name_receive]),
            'address': address_receive,
            'phone': phone_receive,
            'bio': bio_receive
        }
        
        if 'profile_picture_give' in request.files:
            file = request.files['profile_picture_give']
            filename = secure_filename(file.filename)
            extension = filename.split('.')[-1]
            file_path = f'profile_pics/{useremail}.{extension}'
            file.save('./static/' + file_path)
            new_doc['profile_pic'] = filename
            new_doc['profile_pic_real'] = file_path

        db.users.update_one({'useremail': payload['id']}, {'$set': new_doc})
        return jsonify({'result': 'success'})
    except (jwt.ExpiredSignatureError, jwt.exceptions.DecodeError):
        return redirect(url_for('home'))

### chat.html ###
# menampilkan halaman chat
@app.route('/obrolan' , methods=['GET', 'POST'])
def obrolan():
    token_receive = request.cookies.get(TOKEN_KEY)
    try:
        title = 'Obrolan'
        payload = jwt.decode(token_receive, SECRET_KEY, algorithms=['HS256'])
        user_info = db.users.find_one({'account_name': payload['id']})
        if request.method == 'POST':
            judul = request.form['judul']
            konten = request.form['konten']
            timezone = pytz.timezone('Asia/Jakarta')
            current_datetime = datetime.now(timezone)
            post_date = current_datetime.strftime('%d/%m/%y - %H:%M')
            timestamp = current_datetime.timestamp()
            doc = {
                'useremail': user_info['useremail'],
                'nama_lengkap': user_info['name'],
                'foto_profil': user_info['profile_pic_real'],
                'role': user_info['role'],
                'judul': judul,
                'konten': konten,
                'post_data': post_date,
                'isCompleted': 'false',
                'timestamp': timestamp,
            }
            db.chats.insert_one(doc)
            return redirect(url_for('forum'))
        chats = list(db.chats.find().sort('timestamp', -1))
        return render_template('user/obrolan.html', title = title, user_info = user_info, chats = chats)
    except (jwt.ExpiredSignatureError, jwt.exceptions.DecodeError):
        return redirect(url_for('login'))
    
@app.route('/chat/<id>')
def isi_chat(id):
    token_receive = request.cookies.get('mytoken')
    try:
        payload = jwt.decode(token_receive, SECRET_KEY, algorithms=['HS256'])
        user_info = db.users.find_one({'account_name': payload['id']})
        chat = db.chats.find_one({'_id': ObjectId(id)})
        user = db.users.find_one({'account_name': chat['account_name']})
        forum['nama_lengkap'] = user['name']
        forum['foto_profil'] = user['profile_pic_real']
        comments = list(db.comments.find({'thread_id': id}))
        for comment in comments:
            user = db.user.find_one({'account_name': comment['account_name']})
            comment['nama_lengkap'] = user['name']
            comment['foto_profil'] = user['profile_pic_real']
        return render_template('isi_forum.html',user_info=user_info,forum=forum,comments=comments)
    except (jwt.ExpiredSignatureError, jwt.exceptions.DecodeError):
        return redirect(url_for('login'))

### collection.html ###
# Endpoint untuk menampilkan halaman koleksi
@app.route('/buket')
def collection():
    token_receive = request.cookies.get(TOKEN_KEY)
    try:
        title = 'Koleksi Buket'
        payload = jwt.decode(token_receive, SECRET_KEY, algorithms=['HS256'])
        user_info = db.users.find_one({'useremail': payload.get('id')})
        collections = list(db.collections.find())
        return render_template('user/bouquet.html', title = title, collections = collections, user_info = user_info)
    except (jwt.ExpiredSignatureError, jwt.exceptions.DecodeError):
        return redirect(url_for('home'))

# untuk menambahkan koleksi
@app.route('/tambah-koleksi', methods = ['POST'])
def tambah_koleksi():
    name_receive = request.form['name']
    description_receive = request.form['description']
    price_receive = request.form['price']
    category_receive = request.form['category']

    if 'image' in request.files:
        image = request.files['image']
        filename = secure_filename(image.filename)
        extension = filename.split('.')[-1]
        file_path = f'collection_pics/{name_receive}.{extension}'
        image.save('./static/' + file_path)
    else:
        file_path = ''

    doc = {
        'name': name_receive,
        'description': description_receive,
        'price': price_receive,
        'category': category_receive,
        'image': file_path
    }
    db.collections.insert_one(doc)
    return redirect(url_for('collection'))

# untuk mengubah koleksi buket
@app.route('/ubah-bucket', methods=['POST'])
def edit_bucket():
    token_receive = request.cookies.get(TOKEN_KEY)
    try:
        payload = jwt.decode(token_receive, SECRET_KEY, algorithms=['HS256'])
        bucket_id = request.form['bucketId']
        name = request.form['name']
        description = request.form['description']
        price = request.form['price']
        category = request.form['category']

        bucket_data = {
            'name': name,
            'description': description,
            'price': price,
            'category': category,
        }

        if 'image' in request.files:
                image = request.files['image']
                filename = secure_filename(image.filename)
                extension = filename.split('.')[-1]
                file_path = f'collection_pics/{name}.{extension}'
                image.save('./static/' + file_path)
                bucket_data['image'] = file_path
        else:
                file_path = ''

        db.collections.update_one({'_id': ObjectId(bucket_id)}, {'$set': bucket_data})
        return redirect(url_for('collection'))
    except (jwt.ExpiredSignatureError, jwt.exceptions.DecodeError):
        return redirect(url_for('home'))

# menghapus bucket
@app.route('/hapus-bucket', methods=['POST'])
def delete_bucket():
    bucket_id = request.form['bucketId']
    db.collections.delete_one({'_id': ObjectId(bucket_id)})
    return redirect(url_for('collection'))

### order_form.html ###
# menampilkan halaman formulir pemesanan
@app.route('/order_form')
def order():
    token_receive = request.cookies.get(TOKEN_KEY)
    try:
        payload = jwt.decode(token_receive, SECRET_KEY, algorithms=['HS256'])
        user_info = db.users.find_one({'useremail': payload.get('id')})
        collection = db.collections.find_one()
        if collection and 'image' in collection:
            collection['image'] = f'static/{collection['image']}'
        
        title = 'Formulir Pemesanan'
        return render_template('user/order_form.html', title = title, collection = collection, user_info = user_info)
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
            collection['image'] = f'/static/{collection['image']}'
        return render_template('user/order_form.html', collection=collection, user_info=user_info)
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
        quantity = request.form.get('quantity')  # Mengambil nilai quantity dari formulir
        total_price = request.form.get('total_price')  # Mengambil total harga dari formulir
        bucket_name = request.form.get('bucket_name')
        name = request.form.get('name')
        email = request.form.get('email')
        phone = request.form.get('phone')
        address = request.form.get('address')

        # Periksa apakah quantity ada dan tidak kosong
        if quantity and quantity.isdigit():
            quantity = int(quantity)  # Konversi quantity menjadi integer jika valid
        else:
            # Quantity tidak valid, kembalikan ke halaman sebelumnya atau lakukan penanganan yang sesuai
            return redirect(url_for('home'))

        # Periksa apakah total_price ada dan tidak kosong
        if total_price:
            total_price = float(total_price)  # Konversi total_price menjadi float jika valid
        else:
            # Jika total_price tidak valid, atur ke nilai default atau lakukan penanganan yang sesuai
            total_price = 0.0  # Atur ke nilai default

        # Ambil harga produk dari database
        collection = db.collections.find_one({'_id': ObjectId(collection_id)})
        if collection:
            # Simpan informasi pemesanan produk ke dalam database
            order_data = {
                'bucket_name': bucket_name,
                'quantity': quantity,
                'total_price': total_price,
                'name': name,
                'useremail': email,
                'phone': phone,
                'address': address,
                'status_order': 'pending',
                'account_name': user_info['account_name']
            }
            # db.orders.insert_one(order_data)
            result = db.orders.insert_one(order_data)

            # Dapatkan order_id dari pesanan yang baru saja disimpan
            order_id = result.inserted_id

            # Redirect ke halaman purchase_form dengan order_id
            return redirect(url_for('purchase_form', order_id=order_id))
        else:
            # Produk tidak ditemukan, redirect ke halaman yang sesuai
            return redirect(url_for('home'))

    except (jwt.ExpiredSignatureError, jwt.exceptions.DecodeError):
        return redirect(url_for('home'))

### payment.html ###
# menampilkan formulir pembayaran
@app.route('/purchase_form/<order_id>')
def purchase_form(order_id):
    token_receive = request.cookies.get(TOKEN_KEY)
    try:
        payload = jwt.decode(token_receive, SECRET_KEY, algorithms=['HS256'])
        user_info = db.users.find_one({'useremail': payload.get('id')})
        order = db.orders.find_one({'_id': ObjectId(order_id)})
        if order:
            title = 'Formulir Pembayaran'
            return render_template('user/purchase_form.html', title = title, user_info = user_info, order = order)
        else:
            return redirect(url_for('home'))
    except (jwt.ExpiredSignatureError, jwt.exceptions.DecodeError):
        return redirect(url_for('home'))

# proses pembayaran
@app.route('/pembayaran', methods=['POST'])
def submit_purchase():
    token_receive = request.cookies.get(TOKEN_KEY)
    try:
        payload = jwt.decode(token_receive, SECRET_KEY, algorithms=['HS256'])
        user_info = db.users.find_one({'useremail': payload.get('id')})

        # Mengambil data dari formulir
        order_id = request.form.get('order_id')
        shipping_method = request.form.get('shippingMethod')
        payment_method = request.form.get('paymentMethod')

        # Mengambil data lain dari database
        order = db.orders.find_one({'_id': ObjectId(order_id)})
        bucket_name = order['bucket_name']
        quantity = order['quantity']
        total_price = order['total_price']
        name = order['name']
        email = order['useremail']
        phone = order['phone']
        address = order['address']

        # Menyimpan bukti pembayaran jika ada
        if 'paymentProof' in request.files:
            payment_proof = request.files['paymentProof']
            filename = secure_filename(payment_proof.filename)
            extension = filename.split('.')[-1]
            file_path = f'payment/{order_id}.{extension}'  
            payment_proof.save('./static/' + file_path)
        else:
            file_path = ''  # Atau nilai default jika tidak ada gambar yang diupload

        # Simpan detail pesanan dan bukti pembayaran ke database
        doc = {
            'order_id': order_id,
            'bucket_name': bucket_name,
            'quantity': quantity,
            'total_price': total_price,
            'name': name,
            'useremail': email,
            'phone': phone,
            'address': address,
            'shipping_method': shipping_method,
            'payment_method': payment_method,
            'payment_proof': file_path,
            'status_order': 'processing',
            'account_name': user_info['account_name']
        }
        db.payment.insert_one(doc)

        # Mengirim respons JSON yang berisi pesan pembayaran berhasil
        return jsonify({'message': 'Pembayaran berhasil!'})
    except (jwt.ExpiredSignatureError, jwt.exceptions.DecodeError):
        return redirect(url_for('home'))

@app.route('/forum' , methods = ['GET', 'POST'])
def forum():
    token_receive = request.cookies.get(TOKEN_KEY)
    try:
        payload = jwt.decode(token_receive, SECRET_KEY, algorithms=['HS256'])
        user_info = db.users.find_one({'useremail': payload['id']})
        if request.method == 'POST':
            judul = request.form['judul']
            konten = request.form['konten']
            timezone = pytz.timezone('Asia/Jakarta')
            current_datetime = datetime.now(timezone)
            post_date = current_datetime.strftime('%d/%m/%y - %H:%M')
            timestamp = current_datetime.timestamp()
            doc = {
                'useremail':user_info['useremail'],
                'nama_lengkap':user_info['name'],
                'foto_profil': user_info['profile_pic_real'],
                'role':user_info['role'],
                'judul':judul,
                'konten':konten,
                'post_data':post_date,
                'isCompleted':'false',
                'timestamp': timestamp,
            }
            db.forums.insert_one(doc)
            return redirect(url_for('forum'))
        forums = list(db.forums.find().sort('timestamp', -1))
        return render_template('forum.html',user_info=user_info,forums=forums)
    except (jwt.ExpiredSignatureError, jwt.exceptions.DecodeError):
        return redirect(url_for('login'))
    
@app.route('/forum/<id>')
def isi_forum(id):
    token_receive = request.cookies.get(TOKEN_KEY)
    try:
        payload = jwt.decode(token_receive, SECRET_KEY, algorithms=['HS256'])
        user_info = db.users.find_one({'useremail': payload['id']})
        forum = db.forums.find_one({'_id': ObjectId(id)})
        user = db.users.find_one({'useremail': forum['useremail']})
        forum['nama_lengkap'] = user['name']
        forum['foto_profil'] = user['profile_pic_real']
        comments = list(db.comments.find({'thread_id': id}))
        for comment in comments:
            user = db.users.find_one({'useremail': comment['useremail']})
            comment['nama_lengkap'] = user['name']
            comment['foto_profil'] = user['profile_pic_real']
        return render_template('isi_forum.html',user_info=user_info,forum=forum,comments=comments)
    except (jwt.ExpiredSignatureError, jwt.exceptions.DecodeError):
        return redirect(url_for('login'))
    
@app.route('/user_forum_komen', methods=['POST'])
def user_forum_komen():
    token_receive = request.cookies.get(TOKEN_KEY)
    try:
        payload = jwt.decode(token_receive, SECRET_KEY, algorithms=['HS256'])
        user_info = db.users.find_one({'useremail': payload['id']})
        id = request.form['id']
        komen = request.form['komen']
        timezone = pytz.timezone('Asia/Jakarta')
        current_datetime = datetime.now(timezone)
        post_date = current_datetime.strftime('%d/%m/%y - %H:%M')
        timestamp = current_datetime.timestamp()
        doc = {
                'useremail':user_info['useremail'],
                'nama_lengkap':user_info['name'],
                'foto_profil': user_info['profile_pic_real'],
                'role':user_info['role'],
                'thread_id': id,
                'komen':komen,
                'post_data':post_date,
                'timestamp': timestamp,
            }
        db.comments.insert_one(doc)
        return redirect(url_for('isi_forum', id=id))
    except (jwt.ExpiredSignatureError, jwt.exceptions.DecodeError):
        return redirect(url_for('login'))
    
@app.route('/edit_forum_post', methods=['POST'])
def edit_forum_post():
    token_receive = request.cookies.get(TOKEN_KEY)
    try:
        payload = jwt.decode(token_receive, SECRET_KEY, algorithms=['HS256'])
        user_info = db.users.find_one({'useremail': payload['id']})
        id = request.form['id']
        judul = request.form['judul']
        konten = request.form['konten']
        db.forums.update_one(
            {'_id': ObjectId(id)},
            {'$set': {'judul': judul, 'konten': konten}}
        )
        return redirect(url_for('isi_forum', id=id))
    except (jwt.ExpiredSignatureError, jwt.exceptions.DecodeError):
        return redirect(url_for('login'))
    
@app.route('/delete_forum_post', methods=['POST'])
def delete_forum_post():
    token_receive = request.cookies.get(TOKEN_KEY)
    try:
        payload = jwt.decode(token_receive, SECRET_KEY, algorithms=['HS256'])
        user_info = db.users.find_one({'useremail': payload['id']})
        id = request.form['id']
        db.forums.delete_one({'_id': ObjectId(id)})
        db.comments.delete_many({'thread_id': id})
        return redirect(url_for('forum'))
    except (jwt.ExpiredSignatureError, jwt.exceptions.DecodeError):
        return redirect(url_for('login'))
    
@app.route('/close_forum_post', methods=['POST'])
def close_forum_post():
    token_receive = request.cookies.get(TOKEN_KEY)
    try:
        payload = jwt.decode(token_receive, SECRET_KEY, algorithms=['HS256'])
        user_info = db.users.find_one({'useremail': payload['id']})
        id = request.form['id']
        db.forums.update_one(
            {'_id': ObjectId(id)},
            {'$set': {'isCompleted': 'true'}}
        )
        return redirect(url_for('isi_forum', id=id))
    except (jwt.ExpiredSignatureError, jwt.exceptions.DecodeError):
        return redirect(url_for('login'))

    

@app.route('/edit_komen', methods=['POST'])
def edit_komen():
    token_receive = request.cookies.get(TOKEN_KEY)
    try:
        payload = jwt.decode(token_receive, SECRET_KEY, algorithms=['HS256'])
        user_info = db.users.find_one({'useremail': payload['id']})
        id = request.form['id']
        url_id = request.form['url_id']
        komen = request.form['komen']
        db.comments.update_one(
            {'_id': ObjectId(id)},
            {'$set': { 'komen': komen}}
        )
        return redirect(url_for('isi_forum', id=url_id))
    except (jwt.ExpiredSignatureError, jwt.exceptions.DecodeError):
        return redirect(url_for('login'))
    
@app.route('/delete_komen', methods=['POST'])
def delete_komen():
    token_receive = request.cookies.get(TOKEN_KEY)
    try:
        payload = jwt.decode(token_receive, SECRET_KEY, algorithms=['HS256'])
        user_info = db.users.find_one({'useremail': payload['id']})
        id = request.form['id']
        url_id = request.form['url_id']
        db.comments.delete_one({'_id': ObjectId(id)})
        return redirect(url_for('isi_forum', id=url_id))
    except (jwt.ExpiredSignatureError, jwt.exceptions.DecodeError):
        return redirect(url_for('login'))
    
@app.route('/riwayat_forum')
def riwayat_forum():
    token_receive = request.cookies.get(TOKEN_KEY)
    try:
        payload = jwt.decode(token_receive, SECRET_KEY, algorithms=['HS256'])
        user_info = db.users.find_one({'useremail': payload['id']})
        forums = list(db.forums.find({'useremail': user_info['useremail']}).sort('timestamp', -1)) 
        for forum in forums:
            forum['jumlah_komen'] = db.comments.count_documents({'thread_id': str(forum['_id'])})
        return render_template('riwayat_forum.html', user_info=user_info,forums=forums)
    except (jwt.ExpiredSignatureError, jwt.exceptions.DecodeError):
        return redirect(url_for('login'))
    

    
@app.route('/buket')
def bouquet():
    token_receive = request.cookies.get(TOKEN_KEY)
    try:
        if token_receive:
            payload = jwt.decode(token_receive, SECRET_KEY, algorithms=['HS256'])
            user_info = db.users.find_one({'useremail': payload['id']})
        else:
            user_info = None

        title = 'Buket'
        query = request.args.get('query', '')
        if query:
            bouquets = db.bouquets.find({'bouquet': {'$regex': query, '$options': 'i'}})
        else:
            bouquets = db.bouquets.find().sort('tanggal', -1)
        return render_template('bouquet.html', title = title, user_info = user_info, bouquets = bouquets)
    except (jwt.ExpiredSignatureError, jwt.exceptions.DecodeError):
        return redirect(url_for('home'))
    
@app.route('/riwayat_pesanan')
def riwayat_pesanan():
    token_receive = request.cookies.get(TOKEN_KEY)
    try:
        title = 'Riwayat Pemesanan'
        payload = jwt.decode(token_receive, SECRET_KEY, algorithms=['HS256'])
        user_info = db.users.find_one({'useremail': payload['id']})
        transactions = list(db.transaksi.find({'useremail': user_info['useremail']}).sort('tanggal', -1)) 
        total_transactions = len(transactions) + 1
        for transaction in transactions:
            tanggal_asli = datetime.fromisoformat(transaction['tanggal']).date()
            transaction['tanggal'] = tanggal_asli.strftime('%d/%m/%Y')
            transaction['nama_produk'] = db.bouquets.find_one({'_id': ObjectId(transaction['bouquet_id'])})['nama_produk']
            testimonial = db.testimoni.find_one({'transaction_id': str(transaction['_id'])})
            transaction['ulasan_produk'] = testimonial['ulasan'] if testimonial else None
        return render_template('riwayat_pesanan.html', title = title, user_info = user_info, transactions = transactions, total_transactions = total_transactions)
    except (jwt.ExpiredSignatureError, jwt.exceptions.DecodeError):
        return redirect(url_for('login'))
    

@app.route('/kirim-testimoni', methods = ['POST'])
def kirim_testimoni():
    token_receive = request.cookies.get(TOKEN_KEY)
    try:
        jwt.decode(token_receive, SECRET_KEY, algorithms=['HS256'])
        id = request.form['id']
        ulasan_produk = request.form['ulasan_produk']
        transaction =  db.transaksi.find_one({'_id': ObjectId(id)})
        bouquet = db.bouquets.find_one({'_id': ObjectId(transaction['bouquet_id'])})['nama_produk']
        current_date = datetime.now().isoformat()
        doc = {
                'transaction_id': str(transaction['_id']),
                'useremail': transaction['useremail'],
                'nama_pembeli': transaction['nama_pembeli'],
                'alamat_pembeli': transaction['alamat_pembeli'],
                'no_pembeli': transaction['nomor_telepon'],
                'produk_yang_dibeli': bouquet,
                'ulasan': ulasan_produk,
                'tanggal': current_date,
            }
        
        db.testimoni.insert_one(doc)
        db.transaksi.update_one({'_id': ObjectId(id)}, {'$set': {'status': 'selesai'}})
        return redirect(url_for('riwayat_pesanan'))
    except (jwt.ExpiredSignatureError, jwt.exceptions.DecodeError):
        return redirect(url_for('login'))
    

@app.route('/bayar', methods=['GET', 'POST'])
def bayar():
    token_receive = request.cookies.get(TOKEN_KEY)
    try:
        payload = jwt.decode(token_receive, SECRET_KEY, algorithms=['HS256'])
        user_info = db.users.find_one({'useremail': payload['id']})
        if request.method == 'GET':
            quantity = request.args.get('quantity', default=1, type=int)
            bouquet_id = request.args.get('bouquet_id')
            bouquet = db.bouquets.find_one({'_id': ObjectId(bouquet_id)})
            price = int(bouquet['harga_produk'])
            print(price)
            return render_template('bayar.html', user_info=user_info, bouquet=bouquet, quantity=quantity, bouquet_id=bouquet_id, price=price)
        elif request.method == 'POST':
           today = datetime.now()
           mytime = today.strftime('%Y-%m-%d-%H-%M-%S')
           useremail = db.users.find_one({'useremail': payload['id']})['useremail']
           quantity = int(request.form['quantity'])
           bouquet_id = request.form['bouquet_id']
           nama_pembeli = request.form['nama_pembeli']
           alamat_pembeli = request.form['alamat_pembeli']
           nomor_telepon = request.form['nomor_telepon']
           catatan_pembelian = request.form['catatan_pembelian']
           bouquet = db.bouquets.find_one({'_id': ObjectId(bouquet_id)})
           harga_per_produk = int(bouquet['harga_produk'])
           total_harga = quantity * harga_per_produk
           file = request.files['bukti_pembayaran']
           filename = secure_filename(file.filename)
           extension = filename.split('.')[-1]
           file_path = f'admin/img/bukti-{useremail}-{mytime}.{extension}'
           file.save('./static/' + file_path)
           current_date = datetime.now().isoformat()
           doc = {
            'useremail' : useremail,
            'bouquet_id':bouquet_id,
            'quantity' : quantity,
            'nama_pembeli' : nama_pembeli,
            'alamat_pembeli' : alamat_pembeli,
            'nomor_telepon' : nomor_telepon,
            'catatan_pembelian' : catatan_pembelian,
            'total_harga' : total_harga,
            'bukti_pembayaran' : file_path,
            'tanggal': current_date,
            'status': 'pending',

          }
           db.transaksi.insert_one(doc)
           return jsonify({'message': 'Order placed successfully'}), 200
         
        
    except (jwt.ExpiredSignatureError, jwt.exceptions.DecodeError):
        return redirect(url_for('login'))

### admin/dashboard.html ###
# menampilkan halaman admin untuk beranda
@app.route('/admin/beranda')
@admin_required
def admin_home():
    token_receive = request.cookies.get(TOKEN_KEY)
    try:
        title = 'Admin'
        payload = jwt.decode(token_receive, SECRET_KEY, algorithms=['HS256'])
        user_info = db.users.find_one({'useremail': payload.get('id')})

        users_count = db.users.count_documents({})
        bouquets_count = db.bouquets.count_documents({})
        transactions_count = db.transactions.count_documents({})
        testimonials_count = db.testimonials.count_documents({})
        pipeline = [
        {
            '$match': {
                'status': 'selesai'
            }
        },
        {
            '$group': {
                '_id': None,
                'total_price': {'$sum': '$total_price'}
            }
        }
        
        ]
        result = db.transactions.aggregate(pipeline)
        income = 0
        for doc in result:
            income = doc['total_price']
            break
        thread_count = db.chats.count_documents({})
        contact_count = db.contact_us.count_documents({})
        return render_template('admin/dashboard.html', title = title, user_info = user_info, users_count = users_count, bouquets_count = bouquets_count, transactions_count = transactions_count, testimonials_count = testimonials_count, income = income, thread_count = thread_count, contact_count = contact_count)
    except (jwt.ExpiredSignatureError, jwt.exceptions.DecodeError):
        return render_template('user/home.html')

### admin.user.html ###
# menampilkan halaman admin untuk pengguna
@app.route('/admin/pengguna')
@admin_required
def admin_user():
    token_receive = request.cookies.get(TOKEN_KEY)
    try:
        title = 'Data Pengguna'
        payload = jwt.decode(token_receive, SECRET_KEY, algorithms=['HS256'])
        user_info = db.users.find_one({'useremail': payload.get('id')})
        users = db.users.find()
        return render_template('admin/user.html', title = title, user_info = user_info, users = users)
    except (jwt.ExpiredSignatureError, jwt.exceptions.DecodeError):
        return render_template('user/home.html')

### admin/bouquet.html ###
# menampilkan halaman admin untuk buket
@app.route('/admin/buket')
@admin_required
def admin_bouquet():
    token_receive = request.cookies.get(TOKEN_KEY)
    try:
        title = 'Data Buket'
        payload = jwt.decode(token_receive, SECRET_KEY, algorithms=['HS256'])
        user_info = db.users.find_one({'useremail': payload.get('id')})
        bouquets = db.bouquets.find()
        return render_template('admin/bouquet.html', title = title, user_info = user_info, bouquets = bouquets)
    except (jwt.ExpiredSignatureError, jwt.exceptions.DecodeError):
        return render_template('user/home.html')

# tambah buket
@app.route('/tambah-buket', methods=['POST'])
@admin_required
def add_bouquet():
    token_receive = request.cookies.get(TOKEN_KEY)
    try:
        payload = jwt.decode(token_receive, SECRET_KEY, algorithms=['HS256'])
        user_info = db.users.find_one({'useremail': payload.get('id')})

        today = datetime.now()
        mytime = today.strftime('%Y-%m-%d_%H.%M.%S')
        name = request.form['name']
        file = request.files['image']
        filename = secure_filename(file.filename)
        extension = filename.split('.')[-1]
        file_path = f'admin/img/bouquet/{mytime}.{extension}'
        file.save('./static/' + file_path)
        flower_color = request.form['flower_color']
        paper_color = request.form['paper_color']
        category = request.form['category']
        description = request.form['description']
        price =int(request.form['price'])
        stock = int(request.form['stock'])

        current_date = datetime.now().isoformat()
        doc = {
            'name' : name,
            'image' : file_path,
            'flower_color' : flower_color,
            'paper_color' : paper_color,
            'category' : category,
            'description' : description,
            'price' : price,
            'stock' : stock,
            'date': current_date
        }
        db.bouquets.insert_one(doc)
        return redirect(url_for('admin_bouquet'))
    except (jwt.ExpiredSignatureError, jwt.exceptions.DecodeError):
        return render_template('user/home.html')

# edit buket
@app.route('/edit-buket', methods=['POST'])
@admin_required
def edit_bouquet():
    id =request.form['id']
    today = datetime.now()
    mytime = today.strftime('%Y-%m-%d_%H.%M.%S')
    name = request.form['name']
    flower_color = request.form['flower_color']
    paper_color = request.form['paper_color']
    category = request.form['category']
    description =request.form['description']
    price =int(request.form['price'])
    stock = int(request.form['stock'])

    current_date = datetime.now().isoformat()
    new_doc = {
        'name' : name,
        'flower_color' : flower_color,
        'paper_color' : paper_color,
        'category' : category,
        'description' : description,
        'price' : price,
        'stock' : stock,
        'date': current_date
    }
    
    if 'image' in request.files and request.files['image'].filename != '':
        bouquet = db.bouquets.find_one({'_id': ObjectId(id)})
        old_photo = bouquet.get('image', '')

        # Menghapus gambar lama
        if old_photo:
            old_file_path = os.path.abspath('./static/' + old_photo)
            if os.path.exists(old_file_path):
                os.remove(old_file_path)

        file = request.files['image']
        filename = secure_filename(file.filename)
        extension = filename.split('.')[-1]
        file_path = f'admin/img/bouquet/{mytime}.{extension}'
        file.save('./static/' + file_path)
        new_doc['image'] = file_path
    else:
        pass
    db.bouquets.update_one(
        {'_id': ObjectId(id)}, 
        {'$set': new_doc}
    )
    return redirect(url_for('admin_bouquet'))

# hapus buket
@app.route('/hapus-buket', methods=['POST'])
@admin_required
def delete_bouquet():
    id = request.form['id']
    bouquet = db.bouquets.find_one({'_id': ObjectId(id)})
    if bouquet:
        foto = bouquet.get('bouquet', '')
        if foto:
            file_path = os.path.abspath('./static/' + foto)
            if os.path.exists(file_path):
                os.remove(file_path)
        db.bouquets.delete_one({'_id': ObjectId(id)})
    else:
        pass
    return redirect(url_for('admin_bouquet'))

### admin/transaction.html ###
# menampilkan halaman admin untuk transaksi
@app.route('/admin/transaksi')
@admin_required
def admin_transaction():
    token_receive = request.cookies.get(TOKEN_KEY)
    try:
        title = 'Data Transaksi'
        transactions = list(db.transactions.find())
        for transaction in transactions:
            transaction['name'] = db.bouquets.find_one({'_id': ObjectId(transaction['bouquet_id'])})['name']
        return render_template('admin/transaction.html', title = title, transactions = transactions)
    except (jwt.ExpiredSignatureError, jwt.exceptions.DecodeError):
        return render_template('user/home.html')

# terima pemesanan
@app.route('/terima-pemesanan', methods=['POST'])
@admin_required
def receive_orders():
    id = request.form['id']
    note = request.form['note']
    transaction =  db.transactions.find_one({'_id': ObjectId(id)})
    quantity = transaction['quantity']

    db.transactions.update_one({'_id': ObjectId(id)}, {'$set': {'status': 'diterima', 'note': note}})
    db.bouquets.update_one({'_id': ObjectId(transaction['bouquet_id'])}, {'$inc': {'stock': -quantity}})

    return redirect(url_for('admin_transaction'))

# tolak pemesanan
@app.route('/tolak-pemesanan', methods=['POST'])
@admin_required
def reject_order():
    id = request.form['id']
    note = request.form['note']
    db.transactions.update_one({'_id': ObjectId(id)}, {'$set': {'status': 'ditolak', 'note': note}})
    return redirect(url_for('admin_transaction'))

# kirim pemesanan
@app.route('/kirim-pemesanan', methods=['POST'])
@admin_required
def send_order():
    id = request.form['id']
    note = request.form['note']
    db.transactions.update_one({'_id': ObjectId(id)}, {'$set': {'status': 'dikirim', 'note': note}})
    return redirect(url_for('admin_transaction'))

### admin/testimonial.html ###
# menampilkan halaman admin untuk testimoni
@app.route('/admin/testimoni')
@admin_required
def admin_testimoni():
    title = 'Data Testimoni'
    testimonials = db.testimonials.find()
    return render_template('admin/testimonial.html', title = title, testimonials = testimonials)

### admin/chat.html ###
# menampilkan halaman admin untuk obrolan
@app.route('/admin/forum')
@admin_required
def admin_forum():
    title = 'Data Obrolan'
    forums= db.chats.find()
    return render_template('admin/forum.html', title = title, forums = forums)

# menghapus obrolan
@app.route('/delete_thread_admin_side', methods = ['POST'])
@admin_required
def delete_thread_admin_side():
    id = request.form['id']
    db.chats.delete_one({'_id': ObjectId(id)})
    db.comments.delete_many({'thread_id': id})
    return redirect(url_for('admin_forum'))

### admin/contact_us.html ###
# menampilkan halaman admin untuk hubungi kami
@app.route('/admin/hubungi-kami')
@admin_required
def admin_contact_us():
    title = 'Data Hubungi Kami'
    contacts = db.contact_us.find()
    return render_template('admin/contact_us.html', title = title, contacts = contacts)

# menghapus hubungi kami
@app.route('/hapus-hubungi-kami', methods = ['POST'])
@admin_required
def delete_contact_us():
    id = request.form['id']
    db.contact_us.delete_one({'_id': ObjectId(id)})
    return redirect(url_for('admin_contact_us'))

if __name__ == '__main__':
    app.run('0.0.0.0', port = 5000, debug = True)