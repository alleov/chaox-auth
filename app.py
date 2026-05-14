
#Librerias
import cv2
import mediapipe as mp
import os, time, threading, uuid, io
from datetime import datetime
from dotenv import load_dotenv
from cryptography.fernet import Fernet
from flask import Flask, render_template, Response, redirect, url_for, request, flash, session, send_file, abort
from flask_sqlalchemy import SQLAlchemy
from flask_login import LoginManager, UserMixin, login_user, login_required, logout_user, current_user 
from mediapipe.tasks import python
from mediapipe.tasks.python import vision 
from sqlalchemy import text
import requests
import random


load_dotenv()
app = Flask(__name__)
app.secret_key = os.getenv('SECRET_KEY')
APP_NAME = os.getenv('APP_NAME')

# Configuracion
CAMERA_INDEX = int(os.getenv('CAMERA_INDEX', 0))
MAX_ATTEMPTS = int(os.getenv('MAX_ATTEMPTS', 3))
LOCK_TIME = int(os.getenv('LOCK_TIME', 60))
CAMERA_WIDTH = int(os.getenv('CAMERA_WIDTH', 640))
CAMERA_HEIGHT = int(os.getenv('CAMERA_HEIGHT', 480))
JPEG_QUALITY = int(os.getenv('JPEG_QUALITY', 35))
INFERENCE_INTERVAL = float(os.getenv('INFERENCE_INTERVAL', 0.15))
MODEL_FACE = os.getenv('MODEL_FACE', 'face_landmarker.task')
MODEL_GESTURE = os.getenv('MODEL_GESTURE', 'gesture_recognizer.task')
DEFAULT_USER_IMG = os.getenv('DEFAULT_USER_IMG', 'default_user.png')

# Cifrado
cipher_suite = Fernet(os.getenv('ENCRYPTION_KEY', '').encode())

# Base de Datos
BASE_DIR = os.path.abspath(os.path.dirname(__file__))
app.config['SQLALCHEMY_DATABASE_URI'] = f"sqlite:///{os.path.join(BASE_DIR, os.getenv('DB_NAME', 'app.db'))}"
app.config['SQLALCHEMY_TRACK_MODIFICATIONS'] = False
db = SQLAlchemy(app)

# Tablas
class Usuario(db.Model, UserMixin):
    id = db.Column(db.Integer, primary_key=True)
    username = db.Column(db.String(50), unique=True, nullable=False)
    nombre = db.Column(db.String(100), nullable=False)
    foto_perfil = db.Column(db.String(200), default=DEFAULT_USER_IMG)
    gesto1 = db.Column(db.String(50), nullable=False)
    gesto2 = db.Column(db.String(50), nullable=False)
    intentos_fallidos = db.Column(db.Integer, default=0)
    bloqueado = db.Column(db.Boolean, default=False)
    is_admin = db.Column(db.Boolean, default=False) # NUEVA COLUMNA
    ultimo_intento = db.Column(db.DateTime, default=datetime.now)
    accesos = db.relationship('Acceso', backref='operador', lazy=True)

class Acceso(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    usuario_id = db.Column(db.Integer, db.ForeignKey('usuario.id'))
    fecha = db.Column(db.DateTime, default=datetime.now)
    foto_path = db.Column(db.String(200))
    tipo = db.Column(db.String(20)) # 'Exitoso' / 'Fallido'
    ip_address = db.Column(db.String(50)) # NUEVA COLUMNA
    pais = db.Column(db.String(50), default='Desconocido') # NUEVA COLUMNA DE PAIS

with app.app_context():
    db.create_all()
    try:
        db.session.execute(text("ALTER TABLE acceso ADD COLUMN pais VARCHAR(50) DEFAULT 'Desconocido'"))
        db.session.commit()
    except Exception:
        db.session.rollback()
        pass
    for d in ['perfiles', 'evidencias', 'intrusos']:
        os.makedirs(os.path.join(BASE_DIR, 'static/uploads', d), exist_ok=True)

login_manager = LoginManager()
login_manager.init_app(app)
login_manager.login_view = 'login'  # type: ignore[assignment]

@login_manager.user_loader
def load_user(user_id): return Usuario.query.get(int(user_id))

def get_country_from_ip(ip):
    if not ip or ip == '127.0.0.1' or ip.startswith('192.168.'):
        return random.choice(['MX', 'US', 'ES', 'CO', 'AR']) 
    try:
        r = requests.get(f'http://ip-api.com/json/{ip}', timeout=2)
        if r.status_code == 200:
            return r.json().get('countryCode', 'Desconocido')
    except:
        pass
    return 'Desconocido'

# Ayudantes de imagen
def save_secure_image(frame_or_file, folder, prefix, is_upload=False):
    unique_name = f"{prefix}_{uuid.uuid4().hex}.bin"
    filepath = os.path.join(folder, unique_name)
    
    if is_upload:
        raw_data = frame_or_file.read()
    else:
        _, buffer = cv2.imencode('.jpg', frame_or_file)
        raw_data = buffer.tobytes()
        
    encrypted_data = cipher_suite.encrypt(raw_data)
    with open(filepath, 'wb') as f: f.write(encrypted_data)
    return unique_name

@app.route('/get_image/<path:subdir>/<filename>')
def get_image(subdir, filename):
    if subdir != 'perfiles' and not current_user.is_authenticated:
        return abort(401)
    try:
        path = os.path.join(BASE_DIR, 'static/uploads', subdir, filename)
        with open(path, 'rb') as f: data = cipher_suite.decrypt(f.read())
        return send_file(io.BytesIO(data), mimetype='image/jpeg')
    except: return abort(404)

# Deteccion de Rostro & Gestos
class CameraThread:
    def __init__(self):
        self.cap = cv2.VideoCapture(CAMERA_INDEX)
        self.cap.set(cv2.CAP_PROP_FRAME_WIDTH, CAMERA_WIDTH)
        self.cap.set(cv2.CAP_PROP_FRAME_HEIGHT, CAMERA_HEIGHT)
        self.frame = None
        self.lock = threading.Lock()
    def start(self):
        threading.Thread(target=self.update, daemon=True).start()
        return self
    def update(self):
        while True:
            ret, f = self.cap.read()
            if ret:
                with self.lock: self.frame = f
    def read(self):
        with self.lock: return self.frame

cam = CameraThread().start()

# Cargar modelos Mediapipe
face_landmarker = vision.FaceLandmarker.create_from_options(
    vision.FaceLandmarkerOptions(
        base_options=python.BaseOptions(model_asset_path=MODEL_FACE), 
        running_mode=vision.RunningMode.VIDEO
    )
)
gesture_recognizer = vision.GestureRecognizer.create_from_options(
    vision.GestureRecognizerOptions(
        base_options=python.BaseOptions(model_asset_path=MODEL_GESTURE), 
        running_mode=vision.RunningMode.VIDEO
    )
)

# Variables globales de estado
STATUS = {"gesture": "None", "face": False, "latest": None}

def gen_frames():
    last_p = 0
    while True:
        frame = cam.read()
        if frame is None: continue
        frame = cv2.flip(frame, 1)
        STATUS["latest"] = frame.copy()
        
        now = time.time()
        if now - last_p > INFERENCE_INTERVAL:
            rgb = cv2.cvtColor(frame, cv2.COLOR_BGR2RGB)
            mp_i = mp.Image(image_format=mp.ImageFormat.SRGB, data=rgb)
            f_res = face_landmarker.detect_for_video(mp_i, int(now*1000))
            g_res = gesture_recognizer.recognize_for_video(mp_i, int(now*1000))
            STATUS["face"] = True if f_res.face_landmarks else False
            STATUS["gesture"] = g_res.gestures[0][0].category_name if g_res.gestures else "None"
            last_p = now

        _, buffer = cv2.imencode('.jpg', frame, [cv2.IMWRITE_JPEG_QUALITY, JPEG_QUALITY])
        yield (b'--frame\r\n' b'Content-Type: image/jpeg\r\n\r\n' + buffer.tobytes() + b'\r\n')

# Rutas
@app.route('/')
def index(): return render_template('index.html', app_name=APP_NAME)

@app.route('/video_feed')
def video_feed(): return Response(gen_frames(), mimetype='multipart/x-mixed-replace; boundary=frame')

@app.route('/login', methods=['GET', 'POST'])
def login():
    if 'step' not in session: session['step'] = 1
    user = Usuario.query.filter_by(username=session.get('auth_user')).first() if 'auth_user' in session else None
    
    if request.method == 'POST':
        u = Usuario.query.filter_by(username=session.get('auth_user') if session.get('step') == 2 else request.form.get('usuario')).first()
        if not u: flash("Usuario no encontrado"); return redirect('/login')
        
        # Bloqueo
        if u.bloqueado:
            diff = (datetime.now() - u.ultimo_intento).total_seconds()
            if diff < LOCK_TIME:
                return render_template('login.html', step=session.get('step'), user=u, app_name=APP_NAME, locked_remaining=int(LOCK_TIME - diff))
            else: 
                u.bloqueado = False
                u.intentos_fallidos = 0
                db.session.commit()

        # Validación Biométrica
        valid = STATUS["face"] and ((session['step'] == 1 and STATUS["gesture"] == u.gesto1) or (session['step'] == 2 and STATUS["gesture"] == u.gesto2))
        
        if valid:
            if session['step'] == 1:
                session['step'] = 2; session['auth_user'] = u.username
                return redirect('/login')
            else:
                fn = save_secure_image(STATUS["latest"], os.path.join(BASE_DIR, 'static/uploads/evidencias'), 'ok')
                pais = get_country_from_ip(request.remote_addr)
                db.session.add(Acceso(usuario_id=u.id, foto_path=fn, tipo='Exitoso', ip_address=request.remote_addr, pais=pais))  # type: ignore[call-arg]
                u.intentos_fallidos = 0; db.session.commit(); session.clear(); login_user(u)
                return redirect('/dashboard')
        else:
            u.intentos_fallidos += 1; u.ultimo_intento = datetime.now()
            fn = save_secure_image(STATUS["latest"], os.path.join(BASE_DIR, 'static/uploads/intrusos'), 'fail')
            pais = get_country_from_ip(request.remote_addr)
            db.session.add(Acceso(usuario_id=u.id, foto_path=fn, tipo='Fallido', ip_address=request.remote_addr, pais=pais))  # type: ignore[call-arg]
            if u.intentos_fallidos >= MAX_ATTEMPTS:
                u.bloqueado = True
                db.session.commit()
                return render_template('login.html', step=session.get('step'), user=u, app_name=APP_NAME, locked_remaining=LOCK_TIME)
            db.session.commit()
            if session['step'] == 2:
                flash("Credenciales incorrectas")
            else:
                flash("Fallo Biométrico")
            session.clear(); session['step'] = 1
            return redirect('/login')
            
    return render_template('login.html', step=session.get('step'), user=user, app_name=APP_NAME)

@app.route('/dashboard')
@login_required
def dashboard():
    exitos = Acceso.query.filter_by(usuario_id=current_user.id, tipo='Exitoso').order_by(Acceso.fecha.desc()).all()
    fails = Acceso.query.filter_by(usuario_id=current_user.id, tipo='Fallido').order_by(Acceso.fecha.desc()).all()
    return render_template('dashboard.html', user=current_user, exitosos=exitos, fallidos=fails, app_name=APP_NAME)

@app.route('/admin')
@login_required
def admin():
    if not current_user.is_admin: abort(403)
    usuarios = Usuario.query.all()
    stats = {
        "ok": Acceso.query.filter_by(tipo='Exitoso').count(),
        "bad": Acceso.query.filter_by(tipo='Fallido').count()
    }
    from sqlalchemy import func
    country_data = db.session.query(Acceso.pais, func.count(Acceso.id)).group_by(Acceso.pais).all()
    map_data = {c[0]: c[1] for c in country_data if c[0] and c[0] != 'Desconocido'}
    
    return render_template('admin.html', usuarios=usuarios, stats=stats, map_data=map_data, app_name=APP_NAME)

@app.route('/registro', methods=['GET', 'POST'])
def registro():
    if request.method == 'POST':
        if Usuario.query.filter_by(username=request.form['usuario']).first(): flash("Matrícula duplicada"); return redirect('/registro')
        u = Usuario(username=request.form['usuario'], nombre=request.form['nombre'], gesto1=request.form['gesto1'], gesto2=request.form['gesto2'])  # type: ignore[call-arg]
        db.session.add(u); db.session.commit(); return redirect('/login')
    return render_template('registro.html', app_name=APP_NAME)

@app.route('/ajustes', methods=['GET', 'POST'])
@login_required
def ajustes():
    if request.method == 'POST':
        u: Usuario | None = Usuario.query.get(current_user.id)
        if u is None:
            flash("Usuario no encontrado"); return redirect('/dashboard')
        u.nombre, u.gesto1, u.gesto2 = request.form['nombre'], request.form['gesto1'], request.form['gesto2']
        f = request.files.get('foto')
        if f and f.filename != '':
            u.foto_perfil = save_secure_image(f, os.path.join(BASE_DIR, 'static/uploads/perfiles'), 'perf', is_upload=True)
        db.session.commit(); return redirect('/dashboard')
    return render_template('ajustes.html', user=current_user, app_name=APP_NAME)

@app.route('/logout')
def logout(): session.clear(); logout_user(); return redirect('/')

if __name__ == "__main__":
    app.run(host='0.0.0.0', port=int(os.getenv('FLASK_PORT', 5000)), debug=True, use_reloader=False)