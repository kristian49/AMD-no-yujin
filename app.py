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

# fungsi untuk admin
def admin_required(f):
    @wraps(f)
    def admin_function(*args, **kwargs):
        token_receive = request.cookies.get(TOKEN_KEY)
        if token_receive is not None:
            try:
                payload = jwt.decode(token_receive, SECRET_KEY, algorithms = ['HS256'])
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
        useremail = user_info['useremail']

        # Menghitung total pembelian dan total bucket hanya jika statusnya 'diterima'
        payments = list(db.transactions.find({'useremail': useremail, 'status': 'selesai'}))
        total_pembelian = sum(payment['total_price'] for payment in payments)
        total_bucket = sum(payment['quantity'] for payment in payments)
        total_pembelian_rupiah = format_rupiah(total_pembelian)

        return render_template('user/dashboard.html', title = title, user_info = user_info, total_pembelian = total_pembelian, total_bucket = total_bucket, total_pembelian_rupiah = total_pembelian_rupiah)
    except (jwt.ExpiredSignatureError, jwt.exceptions.DecodeError):
        title = 'Beranda'
        bouquets = list(db.bouquets.find())
        faqs = list(db.faqs.find())
        return render_template('user/home.html', title = title, bouquets = bouquets, faqs = faqs)

# untuk menampilkan format rupiah
def format_rupiah(value):
    return f'Rp {value:,.0f}'.replace(',', '.')
    
# menyimpan pesan pada hubungi kami
@app.route('/hubungi-kami', methods = ['POST'])
def contact_us():
    name_receive = request.form['name_give']
    email_receive = request.form['email_give']
    subject_receive = request.form['subject_give']
    message_receive = request.form['message_give']
    
    timezone = pytz.timezone('Asia/Jakarta')
    current_datetime = datetime.now(timezone)
    sent_date = current_datetime.strftime('%d/%m/%y - %H:%M')
    timestamp = current_datetime.timestamp()
    doc = {
        'name': name_receive,
        'email': email_receive,
        'subject': subject_receive,
        'message': message_receive,
        'sent_date' : sent_date,
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
@app.route('/profil')
def profile():
    token_receive = request.cookies.get(TOKEN_KEY)
    try:
        title = 'Profil'
        payload = jwt.decode(token_receive, SECRET_KEY, algorithms = ['HS256'])
        user_info = db.users.find_one({'useremail': payload['id']})
        return render_template('user/profile.html', title = title, user_info = user_info)
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

### collection.html ###
# Endpoint untuk menampilkan halaman koleksi
@app.route('/koleksi')
def bouquet_collection():
    token_receive = request.cookies.get(TOKEN_KEY)
    try:
        title = 'Koleksi Buket'
        payload = jwt.decode(token_receive, SECRET_KEY, algorithms = ['HS256'])
        user_info = db.users.find_one({'useremail': payload['id']})
        bouquets = list(db.bouquets.find())
        return render_template('user/collection.html', title = title, user_info = user_info, bouquets = bouquets)
    except (jwt.ExpiredSignatureError, jwt.exceptions.DecodeError):
        return redirect(url_for('home'))

### payment.html ###
# menampilkan halaman pembayaran
@app.route('/pembayaran', methods = ['GET', 'POST'])
def pay():
    token_receive = request.cookies.get(TOKEN_KEY)
    try:
        title = 'Pemesanan Buket'
        payload = jwt.decode(token_receive, SECRET_KEY, algorithms = ['HS256'])
        user_info = db.users.find_one({'useremail': payload['id']})
        if request.method == 'GET':
            quantity = request.args.get('quantity', default = 1, type = int)
            bouquet_id = request.args.get('bouquet_id')
            bouquet = db.bouquets.find_one({'_id': ObjectId(bouquet_id)})
            price = int(bouquet['price'])
            return render_template('user/payment.html', title = title, user_info = user_info, quantity = quantity, bouquet_id = bouquet_id, bouquet = bouquet, price = price)
        elif request.method == 'POST':
            today = datetime.now()
            mytime = today.strftime('%Y-%m-%d-%H-%M-%S')
            useremail = db.users.find_one({'useremail': payload['id']})['useremail']
            quantity = int(request.form['quantity'])
            bouquet_id = request.form['bouquet_id']
            flower_and_paper_color = request.form['flower_and_paper_color']
            note_of_buyer = request.form['note_of_buyer']
            delivery_date = request.form['delivery_date']
            delivery_time = request.form['delivery_time']
            greeting_card = request.form['greeting_card']
            name_of_buyer = request.form['name_of_buyer']
            phone_of_buyer = request.form['phone_of_buyer']
            address_of_buyer = request.form['address_of_buyer']
            shipping_method = request.form['shipping_method']
            bouquet = db.bouquets.find_one({'_id': ObjectId(bouquet_id)})
            bouquet_image = bouquet['image']
            name_of_the_bouquet = bouquet['name']
            price_per_bouquet = int(bouquet['price'])
            total_price = quantity * price_per_bouquet
            file = request.files['proof_of_payment']
            filename = secure_filename(file.filename)
            extension = filename.split('.')[-1]
            file_path = f'admin/img/proof_of_payment/{name_of_buyer}-{name_of_the_bouquet}-{mytime}.{extension}'
            file.save('./static/' + file_path)
            order_date = today.strftime('%Y-%m-%d')
            order_time = today.strftime('%H:%M')
            current_date = datetime.now().isoformat()
            doc = {
                'useremail': useremail,
                'bouquet_id': bouquet_id,
                'quantity': quantity,
                'flower_and_paper_color': flower_and_paper_color,
                'note_of_buyer': note_of_buyer,
                'delivery_date': delivery_date,
                'delivery_time': delivery_time,
                'greeting_card': greeting_card,
                'name_of_buyer': name_of_buyer,
                'phone_of_buyer': phone_of_buyer,
                'address_of_buyer': address_of_buyer,
                'shipping_method': shipping_method,
                'bouquet_image': bouquet_image,
                'name_of_the_bouquet': name_of_the_bouquet,
                'total_price': total_price,
                'proof_of_payment': file_path,
                'order_date': order_date,
                'order_time': order_time,
                'date': current_date,
                'status': 'pending'
            }
            db.transactions.insert_one(doc)
            return jsonify({'result': 'success'})
    except (jwt.ExpiredSignatureError, jwt.exceptions.DecodeError):
        return redirect(url_for('login'))

### order_history.html ###
# menampilkan riwayat pemesanan
@app.route('/riwayat-pemesanan')
def order_history():
    token_receive = request.cookies.get(TOKEN_KEY)
    try:
        title = 'Riwayat Pemesanan'
        payload = jwt.decode(token_receive, SECRET_KEY, algorithms = ['HS256'])
        user_info = db.users.find_one({'useremail': payload['id']})
        transactions = list(db.transactions.find({'useremail': user_info['useremail']}).sort('date', -1)) 
        total_transactions = len(transactions) + 1
        for transaction in transactions:
            original_date = datetime.fromisoformat(transaction['date']).date()
            transaction['date'] = original_date.strftime('%d/%m/%Y')
            transaction['name_of_the_bouquet'] = db.bouquets.find_one({'_id': ObjectId(transaction['bouquet_id'])})['name']
            testimonial = db.testimonials.find_one({'transaction_id': str(transaction['_id'])})
            transaction['bouquet_review'] = testimonial['review'] if testimonial else None
        return render_template('user/order_history.html', title = title, user_info = user_info, transactions = transactions, total_transactions = total_transactions)
    except (jwt.ExpiredSignatureError, jwt.exceptions.DecodeError):
        return redirect(url_for('login'))

### chat.html ###
# menampilkan halaman obrolan
@app.route('/riwayat-pemesanan/<id>')
def chat_order(id):
    token_receive = request.cookies.get(TOKEN_KEY)
    try:
        title = 'Obrolan dalam Pemesanan'
        payload = jwt.decode(token_receive, SECRET_KEY, algorithms = ['HS256'])
        user_info = db.users.find_one({'useremail': payload['id']})
        # user_info = db.users.find_one({'useremail': {'useremail': payload['id']}})
        transaction_id = db.transactions.find_one({'_id': ObjectId(id)})
        # forum = db.forums.find_one({'_id': ObjectId(id)})
        # user = db.users.find_one({"useremail": transaction["useremail"]})
        # transaction_id = ObjectId(transaction_id)
        transaction_info = db.transactions.find_one({'_id' : transaction_id})
        transaction_chat = list(db.chats.find({'transaction_id' : transaction_id}).sort('date', -1).limit(10))
        for chat in transaction_chat:
            chat['date'] = chat['date'].split('-')[0]
        number_of_chats = len(transaction_chat)

        return render_template('user/chat_order.html', title = title, user_info = user_info, transaction_info = transaction_info, transaction_chat = transaction_chat, number_of_chats = number_of_chats)
    except(jwt.ExpiredSignatureError, jwt.exceptions.DecodeError):
        return redirect(url_for('home'))
    
@app.route('/mengobrol', methods = ['POST'])
def chat_in_ordering():
    token_receive = request.cookies.get(TOKEN_KEY)
    try:
        payload = jwt.decode(token_receive, SECRET_KEY, algorithms = ['HS256'])
        user_info = db.users.find_one({'useremail': {'useremail': payload['id']}})

        transaction_id = request.form['transaction_id_give']
        message_receive = request.form.get('message_give')

        doc = {
            'transaction_id': transaction_id,
            # 'useremail': useremail,
            # 'account_name': account_name,
            # 'profile_name': profile_name,
            'message': message_receive,
            'date': datetime.now().strftime('%d/%m/%Y-%H:%M:%S')
        }
        db.chats.insert_one(doc)
        return jsonify({'result': 'success', 'msg': 'Berhasil menambahkan komentar'})
    except(jwt.ExpiredSignatureError, jwt.exceptions.DecodeError):
        return redirect(url_for('home'))

# kirim testimoni
@app.route('/kirim-testimoni', methods = ['POST'])
def send_testimonials():
    token_receive = request.cookies.get(TOKEN_KEY)
    try:
        jwt.decode(token_receive, SECRET_KEY, algorithms = ['HS256'])
        id = request.form['id']
        bouquet_review = request.form['bouquet_review']
        transaction =  db.transactions.find_one({'_id': ObjectId(id)})
        bouquet = db.bouquets.find_one({'_id': ObjectId(transaction['bouquet_id'])})['name']
        current_date = datetime.now().isoformat()
        doc = {
            'transaction_id': str(transaction['_id']),
            'useremail': transaction['useremail'],
            'name_of_buyer': transaction['name_of_buyer'],
            'phone_of_buyer': transaction['phone_of_buyer'],
            'address_of_buyer': transaction['address_of_buyer'],
            'purchased_bouquet': bouquet,
            'review': bouquet_review,
            'date': current_date
        }
        db.testimonials.insert_one(doc)
        db.transactions.update_one({'_id': ObjectId(id)}, {'$set': {'status': 'selesai'}})
        return jsonify({'result': 'success'})
    except (jwt.ExpiredSignatureError, jwt.exceptions.DecodeError):
        return redirect(url_for('login'))

### admin/dashboard.html ###
# menampilkan halaman admin untuk beranda
@app.route('/admin-beranda')
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
    chats_count = db.chats.count_documents({})
    faqs_count = db.faqs.count_documents({})
    contact_count = db.contact_us.count_documents({})
    return render_template('admin/dashboard.html', title = title, users_count = users_count, bouquets_count = bouquets_count, transactions_count = transactions_count, testimonials_count = testimonials_count, income = income, chats_count = chats_count, faqs_count = faqs_count, contact_count = contact_count)

### admin.user.html ###
# menampilkan halaman admin untuk pengguna
@app.route('/admin-pengguna')
@admin_required
def admin_user():
    title = 'Data Pengguna'
    users = db.users.find()
    return render_template('admin/user.html', title = title, users = users)
    
### admin/bouquet.html ###
# menampilkan halaman admin untuk buket
@app.route('/admin-buket')
@admin_required
def admin_bouquet():
    title = 'Data Buket'
    bouquets = db.bouquets.find()
    return render_template('admin/bouquet.html', title = title, bouquets = bouquets)

# tambah buket
@app.route('/tambah-buket', methods = ['POST'])
@admin_required
def add_bouquet():
    today = datetime.now()
    mytime = today.strftime('%Y-%m-%d-%H-%M-%S')
    name = request.form['name']
    file = request.files['image']
    filename = secure_filename(file.filename)
    extension = filename.split('.')[-1]
    file_path = f'admin/img/bouquet/{name}-{mytime}.{extension}'
    file.save('./static/' + file_path)
    flower_and_paper_color = request.form['flower_and_paper_color']
    category = request.form['category']
    price = int(request.form['price'])
    stock = int(request.form['stock'])

    current_date = datetime.now().isoformat()
    doc = {
        'name': name,
        'image': file_path,
        'flower_and_paper_color': flower_and_paper_color,
        'category': category,
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
    flower_and_paper_color = request.form['flower_and_paper_color']
    category = request.form['category']
    price = int(request.form['price'])
    stock = int(request.form['stock'])

    current_date = datetime.now().isoformat()
    new_doc = {
        'name': name,
        'flower_and_paper_color': flower_and_paper_color,
        'category': category,
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
        file_path = f'admin/img/bouquet/{name}-{mytime}.{extension}'
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
@app.route('/admin-transaksi')
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
@app.route('/admin-testimoni')
@admin_required
def admin_testimonials():
    title = 'Data Testimoni'
    testimonials = db.testimonials.find()
    return render_template('admin/testimonial.html', title = title, testimonials = testimonials)

@app.route("/admin-obrolan")
@admin_required
def admin_forum():
    title = 'Data Obrolan'
    chats = db.chats.find()
    return render_template("admin/chat_order.html", title = title, chats = chats)

### admin/faq.html ###
# menampilkan halaman admin untuk pertanyaan dan jawaban
@app.route('/admin-pertanyaan-dan-jawaban')
@admin_required
def admin_faq():
    faqs = db.faqs.find()
    return render_template('admin/faq.html', faqs = faqs)

# tambah pertanyaan dan jawaban
@app.route('/tambah-pertanyaan-dan-jawaban', methods = ['POST'])
@admin_required
def add_faq():
    question = request.form['question']
    answer = request.form['answer']
    current_date = datetime.now().isoformat()
    doc = {
        'question': question,
        'answer': answer,
        'date': current_date
    }
    db.faqs.insert_one(doc)
    return redirect(url_for('admin_faq'))

# edit pertanyaan dan jawaban
@app.route('/edit-pertanyaan-dan-jawaban', methods = ['POST'])
@admin_required
def edit_faq():
    id = request.form['id']
    question = request.form['question']
    answer = request.form['answer']
    new_doc = {
        'question': question,
        'answer': answer
    }
    db.faqs.update_one({'_id': ObjectId(id)}, {'$set': new_doc})
    return redirect(url_for('admin_faq'))

# hapus pertanyaan dan jawaban
@app.route('/hapus-pertanyaan-dan-jawaban', methods = ['POST'])
@admin_required
def delete_faq():
    id = request.form['id']
    db.faqs.delete_one({'_id': ObjectId(id)})
    return redirect(url_for('admin_faq'))

### admin/contact_us.html ###
# menampilkan halaman admin untuk hubungi kami
@app.route('/admin-hubungi-kami')
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