from flask import Flask, render_template, jsonify, request, redirect, url_for
from pymongo import MongoClient
from werkzeug.utils import secure_filename
from datetime import datetime, timedelta
from bson import ObjectId
from functools import wraps
import pytz
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
SECRET_KEY = os.environ.get('SECRET_KEY')
TOKEN_KEY =  os.environ.get('TOKEN_KEY')

client = MongoClient(MONGODB_URI)
db = client[DB_NAME]

app.config['TEMPLATES_AUTO_RELOAD'] = True
app.config['UPLOAD_FOLDER'] = './static/profile_pics'
app.config['UPLOAD_COLLECTION_FOLDER'] = './static/collection_pics'
app.config['UPLOAD_PAYMENT_FOLDER'] = './static/payment'

# fungsi untuk admin
def admin_required(f):
    @wraps(f)
    def decorated_function(*args, **kwargs):
        token_receive = request.cookies.get(TOKEN_KEY)
        if token_receive is not None:
            try:
                payload = jwt.decode(token_receive, SECRET_KEY, algorithms=['HS256'])
                if payload['role'] == 'Admin':
                    return f(*args, **kwargs)
                else:
                    return redirect(url_for('home', msg='Only admin can access this page'))
            except (jwt.ExpiredSignatureError, jwt.exceptions.DecodeError):
                return redirect(url_for('login', msg='Your token is invalid or has expired'))
        else:
            return redirect(url_for('login', msg='Please login to view this page'))
    return decorated_function

### home.html atau dashboard.html ###
# menampilkan halaman depan (sebelum pengguna login) atau halaman dashboard (sesudah pengguna login)
@app.route('/')
def home():
    token_receive = request.cookies.get(TOKEN_KEY)
    try:
        payload = jwt.decode(token_receive, SECRET_KEY, algorithms=['HS256'])
        user_info = db.users.find_one({'useremail': payload.get('id')})

        account_name = user_info['account_name']

        # Menghitung total pembelian dan total bucket
        payments = list(db.payment.find({'account_name': account_name}))

        total_pembelian = sum(payment['total_price'] for payment in payments)
        total_bucket = sum(payment['quantity'] for payment in payments)

        total_pembelian_rupiah = format_rupiah(total_pembelian)

        return render_template('dashboard.html', user_info = user_info, total_pembelian = total_pembelian, total_bucket = total_bucket, total_pembelian_rupiah = total_pembelian_rupiah)
    except (jwt.ExpiredSignatureError, jwt.exceptions.DecodeError):
        return render_template('home.html')

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
    return render_template('register.html')

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
        'role': 'Member',
        'profile_name': ' '.join([first_name_receive, last_name_receive]),
        'profile_pic': '',
        'profile_pic_real': 'profile_pics/profile_placeholder.png',
        'address': '',
        'phone': '',
        'bio': ''
    }
    db.users.insert_one(doc)
    return jsonify({'result': 'success'})

### login.html ###
# menampilkan halaman masuk
@app.route('/masuk')
def login():
    return render_template('login.html')

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
@app.route('/profil/<account_name>', methods = ['GET'])
def profile(account_name):
    token_receive = request.cookies.get(TOKEN_KEY)
    try:
        payload = jwt.decode(token_receive, SECRET_KEY, algorithms = ['HS256'])
        status = account_name == payload.get('id')
        user_info = db.users.find_one({'account_name': account_name}, {'_id': False})
        return render_template('profile.html', user_info = user_info, status = status)
    except (jwt.ExpiredSignatureError, jwt.exceptions.DecodeError):
        return redirect(url_for('home'))

# memperbarui profil
@app.route('/memperbarui-profil', methods=['POST'])
def update_profile():
    token_receive = request.cookies.get(TOKEN_KEY)
    try:
        payload = jwt.decode(token_receive, SECRET_KEY, algorithms = ['HS256'])
        account_name = payload.get('id')

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
            file_path = f'profile_pics/{account_name}.{extension}'
            file.save('./static/' + file_path)
            new_doc['profile_pic'] = filename
            new_doc['profile_pic_real'] = file_path
        
        db.users.update_one({'account_name': payload['id']}, {'$set': new_doc})
        return jsonify({'result': 'success'})
    except (jwt.ExpiredSignatureError, jwt.exceptions.DecodeError):
        return redirect(url_for('home'))

### chat.html ###
# menampilkan halaman chat
@app.route('/obrolan' , methods=['GET', 'POST'])
def obrolan():
    token_receive = request.cookies.get(TOKEN_KEY)
    try:
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
                'username': user_info['username'],
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
        return render_template('obrolan.html',user_info=user_info,chats=chats)
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
    
@app.route('/user_forum_komen', methods=['POST'])
def user_forum_komen():
    token_receive = request.cookies.get('mytoken')
    try:
        payload = jwt.decode(token_receive, SECRET_KEY, algorithms=['HS256'])
        user_info = db.user.find_one({'username': payload['id']})
        id = request.form['id']
        komen = request.form['komen']
        timezone = pytz.timezone('Asia/Jakarta')
        current_datetime = datetime.now(timezone)
        post_date = current_datetime.strftime('%d/%m/%y - %H:%M')
        timestamp = current_datetime.timestamp()
        doc = {
                'username':user_info['username'],
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
    token_receive = request.cookies.get('mytoken')
    try:
        payload = jwt.decode(token_receive, SECRET_KEY, algorithms=['HS256'])
        user_info = db.user.find_one({'username': payload['id']})
        id = request.form['id']
        judul = request.form['judul']
        print(judul)
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
    token_receive = request.cookies.get('mytoken')
    try:
        payload = jwt.decode(token_receive, SECRET_KEY, algorithms=['HS256'])
        user_info = db.user.find_one({'username': payload['id']})
        id = request.form['id']
        db.forums.delete_one({'_id': ObjectId(id)})
        db.comments.delete_many({'thread_id': id})
        return redirect(url_for('forum'))
    except (jwt.ExpiredSignatureError, jwt.exceptions.DecodeError):
        return redirect(url_for('login'))
    
@app.route('/close_forum_post', methods=['POST'])
def close_forum_post():
    token_receive = request.cookies.get('mytoken')
    try:
        payload = jwt.decode(token_receive, SECRET_KEY, algorithms=['HS256'])
        user_info = db.user.find_one({'username': payload['id']})
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
    token_receive = request.cookies.get('mytoken')
    try:
        payload = jwt.decode(token_receive, SECRET_KEY, algorithms=['HS256'])
        user_info = db.user.find_one({'username': payload['id']})
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
    token_receive = request.cookies.get('mytoken')
    try:
        payload = jwt.decode(token_receive, SECRET_KEY, algorithms=['HS256'])
        user_info = db.user.find_one({'username': payload['id']})
        id = request.form['id']
        url_id = request.form['url_id']
        db.comments.delete_one({'_id': ObjectId(id)})
        return redirect(url_for('isi_forum', id=url_id))
    except (jwt.ExpiredSignatureError, jwt.exceptions.DecodeError):
        return redirect(url_for('login'))
    
@app.route('/riwayat_forum')
def riwayat_forum():
    token_receive = request.cookies.get('mytoken')
    try:
        payload = jwt.decode(token_receive, SECRET_KEY, algorithms=['HS256'])
        user_info = db.user.find_one({'username': payload['id']})
        forums = list(db.forums.find({'username': user_info['username']}).sort('timestamp', -1)) 
        for forum in forums:
            forum['jumlah_komen'] = db.comments.count_documents({'thread_id': str(forum['_id'])})
        return render_template('riwayat_forum.html', user_info=user_info,forums=forums)
    except (jwt.ExpiredSignatureError, jwt.exceptions.DecodeError):
        return redirect(url_for('login'))

### purchase_history.html ###


### delivery_status.html ###


### collection.html ###
# Endpoint untuk menampilkan halaman koleksi
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

# untuk menambahkan koleksi
@app.route('/tambah-koleksi', methods=['POST'])
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
            collection['image'] = f'/static/{collection['image']}'
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
            return render_template('purchase_form.html', user_info=user_info, order=order)
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

# @app.route('/admin')
# def admin():
#     token_receive = request.cookies.get(TOKEN_KEY)
#     try:
#         payload = jwt.decode(token_receive, SECRET_KEY, algorithms=['HS256'])
#         user_info = db.users.find_one({'useremail': payload.get('id')})
#         user_role = user_info['role']

#         account_name = user_info['account_name']
#         return render_template('admin/dashboard_admin.html', user_info=user_info, user_role=user_role)
#     except (jwt.ExpiredSignatureError, jwt.exceptions.DecodeError):
#         return render_template('home.html')


@app.route('/admin')
def admin():
    token_receive = request.cookies.get(TOKEN_KEY)
    try:
        payload = jwt.decode(token_receive, SECRET_KEY, algorithms=['HS256'])
        user_info = db.users.find_one({'useremail': payload.get('id')})
        user_role = user_info['role']

        account_name = user_info['account_name']
<<<<<<< HEAD
        return render_template('admin/admin_dashboard.html', user_info=user_info, user_role=user_role)
    except (jwt.ExpiredSignatureError, jwt.exceptions.DecodeError):
        return render_template('home.html')

@app.route('/admin')
@admin_required
def admin_dashboard():
    # users_count = db.users.count_documents({})
    # buckets_count = db.buckets.count_documents({})
    # transactions_count = db.transaksi.count_documents({})
    # testimony_count = db.testimoni.count_documents({})
    # pipeline = [
    # {
    #     '$match': {
    #         'status': 'selesai'
    #     }
    # },
    # {
    #     '$group': {
    #         '_id': None,
    #         'total_harga': {'$sum': '$total_harga'}
    #     }
    # }
    
    # ]
    # result = db.transaksi.aggregate(pipeline)
    # income = 0
    # for doc in result:
    #     income = doc['total_harga']
    #     break
    chats_count = db.chats.count_documents({})
    contact_us_count = db.contact_us.count_documents({})
    return render_template('admin/admin_dashboard.html',articles_count=articles_count, products_count = products_count, transactions_count = transactions_count,testimony_count=testimony_count,income=income,thread_count=thread_count,contact_count=contact_count)

@app.route('/admin/daftar-pengguna')
@admin_required
def user_list():
    articles= db.articles.find()
    return render_template('admin/users.html',articles=articles)

@app.route('/tambah_artikel', methods=['POST'])
@admin_required
def tambah_artikel():
    today = datetime.now()
    mytime = today.strftime('%Y-%m-%d-%H-%M-%S')
    judul =request.form['nama_artikel']
    file = request.files['gambar_artikel']
    filename = secure_filename(file.filename)
    extension = filename.split('.')[-1]
    file_path = f'administrator/assets/image/article-{mytime}.{extension}'
    file.save('./static/' + file_path)
    keterangan_gambar =request.form['keterangan_gambar']
    keterangan_artikel =request.form['keterangan_artikel']
    current_date = datetime.now().isoformat()
    doc = {
        'judul_artikel' : judul,
        'gambar_artikel' : file_path,
        'keterangan_gambar' : keterangan_gambar,
        'keterangan_artikel' : keterangan_artikel,
        'tanggal': current_date,
    }
    db.articles.insert_one(doc)
    return redirect(url_for('admin_artikel'))


@app.route('/edit_artikel', methods=['POST'])
@admin_required
def edit_artikel():
    id =request.form['id']
    today = datetime.now()
    mytime = today.strftime('%Y-%m-%d-%H-%M-%S')
    judul =request.form['nama_artikel']
    keterangan_gambar =request.form['keterangan_gambar']
    keterangan_artikel =request.form['keterangan_artikel']
    new_doc = {
        'judul_artikel' : judul,
        'keterangan_gambar' : keterangan_gambar,
        'keterangan_artikel' : keterangan_artikel,
        }
    
    if 'gambar_artikel' in request.files and request.files['gambar_artikel'].filename != '':
        article = db.articles.find_one({'_id': ObjectId(id)})
        foto_lama = article.get('gambar_artikel', '')

        # Menghapus gambar lama
        if foto_lama:
            old_file_path = os.path.abspath('./static/' + foto_lama)
            if os.path.exists(old_file_path):
                os.remove(old_file_path)
        file = request.files['gambar_artikel']
        print(file)
        filename = secure_filename(file.filename)
        extension = filename.split('.')[-1]
        file_path = f'administrator/assets/image/article-{mytime}.{extension}'
        file.save('./static/' + file_path)
        new_doc['gambar_artikel'] = file_path
    else:
        pass
    db.articles.update_one(
            {'_id': ObjectId(id)}, 
            {'$set': new_doc})
    return redirect(url_for('admin_artikel'))


@app.route('/delete_artikel', methods=['POST'])
@admin_required
def delete_artikel():
    id =request.form['id']
    article = db.articles.find_one({'_id': ObjectId(id)})
   
    if article:
        foto = article.get('gambar_artikel', '')
        if foto:
            file_path = os.path.abspath('./static/' + foto)
            if os.path.exists(file_path):
                os.remove(file_path)
        db.articles.delete_one({'_id': ObjectId(id)})
    else:
        pass
    return redirect(url_for('admin_artikel'))



@app.route('/administrator/produk')
@admin_required
def admin_produk():
    products= db.products.find()
    return render_template('administrator/produk.html', products = products)



@app.route('/tambah_produk', methods=['POST'])
@admin_required
def tambah_produk():
    today = datetime.now()
    mytime = today.strftime('%Y-%m-%d-%H-%M-%S')
    nama_produk =request.form['nama_produk']
    file = request.files['gambar_produk']
    filename = secure_filename(file.filename)
    extension = filename.split('.')[-1]
    file_path = f'administrator/assets/image/product-{mytime}.{extension}'
    file.save('./static/' + file_path)
    deskripsi_produk =request.form['deskripsi_produk']
    harga_produk =int(request.form['harga_produk'])
    stok_produk = int(request.form['stok'])

    current_date = datetime.now().isoformat()
    doc = {
        'nama_produk' : nama_produk,
        'gambar_produk' : file_path,
        'deskripsi_produk' : deskripsi_produk,
        'harga_produk' : harga_produk,
        'stok_produk' : stok_produk,
        'tanggal': current_date,
    }
    db.products.insert_one(doc)
    return redirect(url_for('admin_produk'))


@app.route('/edit_produk', methods=['POST'])
@admin_required
def edit_produk():
    id =request.form['id']
    today = datetime.now()
    mytime = today.strftime('%Y-%m-%d-%H-%M-%S')
    nama_produk =request.form['nama_produk']
    deskripsi_produk =request.form['deskripsi_produk']
    harga_produk =int(request.form['harga_produk'])
    stok_produk = int(request.form['stok'])

    current_date = datetime.now().isoformat()
    new_doc = {
        'nama_produk' : nama_produk,
        'deskripsi_produk' : deskripsi_produk,
        'harga_produk' : harga_produk,
        'stok_produk' : stok_produk,
        'tanggal': current_date,
        }
    
    if 'gambar_produk' in request.files and request.files['gambar_produk'].filename != '':
        product = db.products.find_one({'_id': ObjectId(id)})
        foto_lama = product.get('gambar_produk', '')

        # Menghapus gambar lama
        if foto_lama:
            old_file_path = os.path.abspath('./static/' + foto_lama)
            if os.path.exists(old_file_path):
                os.remove(old_file_path)

        file = request.files['gambar_produk']
        filename = secure_filename(file.filename)
        extension = filename.split('.')[-1]
        file_path = f'administrator/assets/image/product-{mytime}.{extension}'
        file.save('./static/' + file_path)
        new_doc['gambar_produk'] = file_path
    else:
        pass
    db.products.update_one(
            {'_id': ObjectId(id)}, 
            {'$set': new_doc})
    return redirect(url_for('admin_produk'))


@app.route('/delete_produk', methods=['POST'])
@admin_required
def delete_produk():
    id = request.form['id']
    product = db.products.find_one({'_id': ObjectId(id)})
    if product:
        foto = product.get('gambar_produk', '')
        if foto:
            file_path = os.path.abspath('./static/' + foto)
            if os.path.exists(file_path):
                os.remove(file_path)
        db.products.delete_one({'_id': ObjectId(id)})
    else:
        pass
    return redirect(url_for('admin_produk'))



@app.route('/administrator/transaksi')
@admin_required
def admin_transaksi():
    transactions= list(db.transaksi.find())
    for transaction in transactions:
        transaction['nama_produk'] = db.products.find_one({'_id': ObjectId(transaction['product_id'])})['nama_produk']
    return render_template('administrator/transaksi.html', transactions = transactions)

@app.route('/terima_pembelian', methods=['POST'])
@admin_required
def terima_pembelian():
    id = request.form['id']
    catatan_admin = request.form['catatan_admin']
    transaction =  db.transaksi.find_one({'_id': ObjectId(id)})
    quantity = transaction['quantity']

    db.transaksi.update_one({'_id': ObjectId(id)}, {'$set': {'status': 'diterima', 'catatan_admin': catatan_admin}})
    db.products.update_one({'_id': ObjectId(transaction['product_id'])}, {'$inc': {'stok_produk': -quantity}})

    return redirect(url_for('admin_transaksi'))


@app.route('/tolak_pembelian', methods=['POST'])
@admin_required
def tolak_pembelian():
    id = request.form['id']
    catatan_admin = request.form['catatan_admin']
    db.transaksi.update_one({'_id': ObjectId(id)}, {'$set': {'status': 'ditolak', 'catatan_admin': catatan_admin}})
    return redirect(url_for('admin_transaksi'))

@app.route('/kirim_pembelian', methods=['POST'])
@admin_required
def kirim_pembelian():
    id = request.form['id']
    catatan_admin = request.form['catatan_admin']
    db.transaksi.update_one({'_id': ObjectId(id)}, {'$set': {'status': 'dikirim', 'catatan_admin': catatan_admin}})
    return redirect(url_for('admin_transaksi'))


@app.route('/administrator/testimoni')
@admin_required
def admin_testimoni():
    testimonies= db.testimoni.find()
    return render_template('administrator/testimoni.html', testimonies = testimonies)

@app.route('/administrator/forum')
@admin_required
def admin_forum():
    forums= db.forums.find()
    return render_template('administrator/forum.html', forums = forums)

@app.route('/delete_thread_admin_side', methods=['POST'])
@admin_required
def delete_thread_admin_side():
    id =request.form['id']
    db.forums.delete_one({'_id': ObjectId(id)})
    db.comments.delete_many({'thread_id': id})
    return redirect(url_for('admin_forum'))


@app.route('/administrator/hubungi')
@admin_required
def admin_hubungi():
    contacts = db.hubungi.find()
    return render_template('administrator/hubungi.html', contacts = contacts)


@app.route('/delete_contact', methods=['POST'])
@admin_required
def delete_contact():
    id =request.form['id']
    db.hubungi.delete_one({'_id': ObjectId(id)})
    return redirect(url_for('admin_hubungi'))

=======

        # Hitung jumlah data bucket
        bucket_count = db.collections.count_documents({})

        # Hitung jumlah data pesanan
        order_count = db.orders.count_documents({})

        # Hitung total penghasilan
        total_income = db.orders.aggregate([
            {"$group": {"_id": None, "total": {"$sum": "$total_price"}}}
        ])
        total_income = list(total_income)  
        if total_income:
            total_income = total_income[0]['total']
            total_income_rupiah = format_rupiah(total_income)
        else:
            total_income = 0
    
        # Hitung total bucket terjual
        total_buckets_sold = db.orders.aggregate([
            {"$group": {"_id": None, "total_buckets_sold": {"$sum": "$quantity"}}}
        ])
        total_buckets_sold = list(total_buckets_sold)
        if total_buckets_sold:
            total_buckets_sold = total_buckets_sold[0]['total_buckets_sold']
        else:
            total_buckets_sold = 0

        return render_template('admin/dashboard_admin.html', 
                               user_info=user_info, 
                               user_role=user_role, 
                               bucket_count=bucket_count, 
                               order_count=order_count, 
                               total_income=total_income, 
                               total_income_rupiah = total_income_rupiah,
                               total_buckets_sold=total_buckets_sold)
    except (jwt.ExpiredSignatureError, jwt.exceptions.DecodeError):
        return render_template('home.html')
>>>>>>> 5783302ba9f82e17e29ec2560c5c19e6ae992910
if __name__ == '__main__':
    app.run('0.0.0.0', port=5000, debug=True)