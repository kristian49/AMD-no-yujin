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
        title = 'Profil'
        payload = jwt.decode(token_receive, SECRET_KEY, algorithms = ['HS256'])
        user_info = db.users.find_one({'account_name': account_name}, {'_id': False})
        return render_template('user/profile.html', title = title, user_info = user_info)
    except (jwt.ExpiredSignatureError, jwt.exceptions.DecodeError):
        return redirect(url_for('home'))

# perbarui profil
@app.route('/perbarui-profil', methods = ['POST'])
def update_profile():
    token_receive = request.cookies.get(TOKEN_KEY)
    try:
        payload = jwt.decode(token_receive, SECRET_KEY, algorithms = ['HS256'])
        account_name = payload['id']

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

        db.users.update_one({'account_name': payload['id']}, {'$set': new_doc})
        return jsonify({'result': 'success'})
    except (jwt.ExpiredSignatureError, jwt.exceptions.DecodeError):
        return redirect(url_for('home'))

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

### admin/dashboard.html ###
# menampilkan halaman admin untuk beranda
@app.route('/admin/beranda')
@admin_required
def admin_home():
    title = 'Admin'
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
    return render_template('admin/dashboard.html', title = title, users_count = users_count, bouquets_count = bouquets_count, transactions_count = transactions_count, testimonials_count = testimonials_count, income = income, thread_count = thread_count, contact_count = contact_count)

### admin.user.html ###
# menampilkan halaman admin untuk pengguna
@app.route('/admin/pengguna')
@admin_required
def admin_user():
    title = 'Data Pengguna'
    users = db.users.find()
    return render_template('admin/user.html', title = title, users = users)
    
### admin/bouquet.html ###
# menampilkan halaman admin untuk buket
@app.route('/admin/buket')
@admin_required
def admin_bouquet():
    title = 'Data Buket'
    bouquets = db.bouquets.find()
    return render_template('admin/bouquet.html', title = title, bouquets = bouquets)

# tambah buket
@app.route('/tambah-buket', methods=['POST'])
@admin_required
def add_bouquet():
    today = datetime.now()
    mytime = today.strftime('%Y-%m-%d_%H-%M-%S')
    
    name = request.form['name']
    flower_color = request.form['flower_color']
    paper_color = request.form['paper_color']
    category = request.form['category']
    price = int(request.form['price'])
    stock = int(request.form['stock'])

    file = request.files['image']
    filename = secure_filename(file.filename)
    extension = filename.split('.')[-1]
    file_path = f'admin/img/bouquet/{mytime}.{extension}'
    # file_path = f'admin/img/{mytime}.{extension}'
    file.save('./static/' + file_path)

    current_date = datetime.now().isoformat()
    doc = {
        'name': name,
        'image': file_path,
        'flower_color': flower_color,
        'paper_color': paper_color,
        'category': category,
        'description': description,
        'price': price,
        'stock': stock,
        'date': current_date
    }
    db.bouquets.insert_one(doc)
    return redirect(url_for('admin_bouquet'))

# edit buket
@app.route('/edit-buket', methods=['POST'])
@admin_required
def edit_bouquet():
    id = request.form['id']

    today = datetime.now()
    mytime = today.strftime('%Y-%m-%d_%H-%M-%S')

    name = request.form['name']
    flower_color = request.form['flower_color']
    paper_color = request.form['paper_color']
    category = request.form['category']
    price = int(request.form['price'])
    stock = int(request.form['stock'])

    current_date = datetime.now().isoformat()
    new_doc = {
        'name': name,
        'flower_color': flower_color,
        'paper_color': paper_color,
        'category': category,
        'description': description,
        'price': price,
        'stock': stock,
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
        # file_path = f'admin/img/{mytime}.{extension}'
        file.save('./static/' + file_path)
        new_doc['image'] = file_path
    else:
        pass

    db.bouquets.update_one({'_id': ObjectId(id)}, {'$set': new_doc})
    return redirect(url_for('admin_bouquet'))

# hapus buket
@app.route('/hapus-buket', methods=['POST'])
@admin_required
def delete_bouquet():
    id = request.form['id']
    bouquet = db.bouquets.find_one({'_id': ObjectId(id)})
    if bouquet:
        photo = bouquet.get('bouquet', '')
        if photo:
            file_path = os.path.abspath('./static/' + photo)
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
    title = 'Data Transaksi'
    transactions = list(db.transactions.find())
    for transaction in transactions:
        transaction['name'] = db.bouquets.find_one({'_id': ObjectId(transaction['bouquet_id'])})['name']
    return render_template('admin/transaction.html', title = title, transactions = transactions)
    
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
    chats = db.chats.find()
    return render_template('admin/forum.html', title = title, chats = chats)

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