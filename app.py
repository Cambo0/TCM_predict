# app.py

from flask import Flask, request, jsonify
from flask_sqlalchemy import SQLAlchemy
from flask_jwt_extended import JWTManager, create_access_token, jwt_required, get_jwt_identity
from flask_marshmallow import Marshmallow
from marshmallow import ValidationError, fields
from werkzeug.security import generate_password_hash, check_password_hash
from sklearn.ensemble import RandomForestClassifier
from sklearn.feature_extraction.text import TfidfVectorizer
from sklearn.pipeline import Pipeline
from sklearn.multiclass import OneVsRestClassifier
import jieba
import re
from datetime import datetime

app = Flask(__name__)
app.config['SQLALCHEMY_DATABASE_URI'] = 'postgresql://username:password@localhost/tcm_db'
app.config['JWT_SECRET_KEY'] = 'your-secret-key'  # Change this!
app.config['SQLALCHEMY_TRACK_MODIFICATIONS'] = False

db = SQLAlchemy(app)
ma = Marshmallow(app)
jwt = JWTManager(app)

# Models
class User(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    username = db.Column(db.String(80), unique=True, nullable=False)
    password_hash = db.Column(db.String(120), nullable=False)
    is_admin = db.Column(db.Boolean, default=False)

    def set_password(self, password):
        self.password_hash = generate_password_hash(password)

    def check_password(self, password):
        return check_password_hash(self.password_hash, password)

class Herb(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    name = db.Column(db.String(100), unique=True, nullable=False)
    description = db.Column(db.Text)

class Disease(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    name = db.Column(db.String(100), unique=True, nullable=False)
    description = db.Column(db.Text)

class Prescription(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    herbs = db.relationship('Herb', secondary='prescription_herbs')
    diseases = db.relationship('Disease', secondary='prescription_diseases')

prescription_herbs = db.Table('prescription_herbs',
    db.Column('prescription_id', db.Integer, db.ForeignKey('prescription.id'), primary_key=True),
    db.Column('herb_id', db.Integer, db.ForeignKey('herb.id'), primary_key=True)
)

prescription_diseases = db.Table('prescription_diseases',
    db.Column('prescription_id', db.Integer, db.ForeignKey('prescription.id'), primary_key=True),
    db.Column('disease_id', db.Integer, db.ForeignKey('disease.id'), primary_key=True)
)

class DiagnosisLog(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    user_id = db.Column(db.Integer, db.ForeignKey('user.id'), nullable=False)
    prescription = db.Column(db.Text, nullable=False)
    predicted_disease = db.Column(db.String(100), nullable=False)
    confidence = db.Column(db.Float, nullable=False)
    timestamp = db.Column(db.DateTime, default=datetime.utcnow)

    user = db.relationship('User', backref=db.backref('diagnosis_logs', lazy=True))

# Schemas
class UserSchema(ma.Schema):
    class Meta:
        fields = ("id", "username", "is_admin")

class HerbSchema(ma.Schema):
    class Meta:
        fields = ("id", "name", "description")

class DiseaseSchema(ma.Schema):
    class Meta:
        fields = ("id", "name", "description")

class PrescriptionSchema(ma.Schema):
    herbs = fields.Nested(HerbSchema, many=True)
    diseases = fields.Nested(DiseaseSchema, many=True)

    class Meta:
        fields = ("id", "herbs", "diseases")

class DiagnosisLogSchema(ma.Schema):
    class Meta:
        fields = ("id", "user_id", "prescription", "predicted_disease", "confidence", "timestamp")

user_schema = UserSchema()
herb_schema = HerbSchema()
disease_schema = DiseaseSchema()
prescription_schema = PrescriptionSchema()
diagnosis_log_schema = DiagnosisLogSchema()

# Machine Learning Model
class ImprovedModel:
    def __init__(self):
        self.vectorizer = TfidfVectorizer()
        self.classifier = OneVsRestClassifier(RandomForestClassifier(n_estimators=100))
        self.pipeline = Pipeline([
            ('tfidf', self.vectorizer),
            ('clf', self.classifier),
        ])

    def train(self, X, y):
        self.pipeline.fit(X, y)

    def predict(self, herbs):
        return self.pipeline.predict_proba([' '.join(herbs)])[0]

model = ImprovedModel()

# Prescription Processor
class PrescriptionProcessor:
    def __init__(self):
        self.herb_names = set(Herb.query.with_entities(Herb.name).all())
        for herb in self.herb_names:
            jieba.add_word(herb)

    def process_prescription(self, text):
        text = re.sub(r'[^\w\s]', '', text)
        words = jieba.cut(text)
        herbs = [word for word in words if word in self.herb_names]
        return herbs

processor = PrescriptionProcessor()

# Routes
@app.route('/register', methods=['POST'])
def register():
    username = request.json.get('username', None)
    password = request.json.get('password', None)
    if not username or not password:
        return jsonify({"msg": "Missing username or password"}), 400
    
    if User.query.filter_by(username=username).first():
        return jsonify({"msg": "Username already exists"}), 400
    
    user = User(username=username)
    user.set_password(password)
    db.session.add(user)
    db.session.commit()
    
    return jsonify({"msg": "User created successfully"}), 201

@app.route('/login', methods=['POST'])
def login():
    username = request.json.get('username', None)
    password = request.json.get('password', None)
    user = User.query.filter_by(username=username).first()
    if user and user.check_password(password):
        access_token = create_access_token(identity=username)
        return jsonify(access_token=access_token), 200
    return jsonify({"msg": "Bad username or password"}), 401

@app.route('/predict', methods=['POST'])
@jwt_required()
def predict_disease():
    current_user = User.query.filter_by(username=get_jwt_identity()).first()
    
    try:
        data = prescription_schema.load(request.json)
    except ValidationError as err:
        return jsonify(err.messages), 400

    try:
        herbs = processor.process_prescription(data['prescription'])
        probabilities = model.predict(herbs)
        diseases = model.classifier.classes_
        
        result = sorted(zip(diseases, probabilities), key=lambda x: x[1], reverse=True)
        
        # Log the diagnosis
        top_prediction = result[0]
        log_entry = DiagnosisLog(
            user_id=current_user.id,
            prescription=data['prescription'],
            predicted_disease=top_prediction[0],
            confidence=float(top_prediction[1])
        )
        db.session.add(log_entry)
        db.session.commit()
        
        return jsonify({
            'predictions': [{'disease': d, 'probability': float(p)} for d, p in result[:5]]
        })
    except Exception as e:
        app.logger.error(f"Error during prediction: {str(e)}")
        return jsonify({"msg": "An error occurred during prediction"}), 500

@app.route('/diagnosis-history', methods=['GET'])
@jwt_required()
def get_diagnosis_history():
    current_user = User.query.filter_by(username=get_jwt_identity()).first()
    logs = DiagnosisLog.query.filter_by(user_id=current_user.id).order_by(DiagnosisLog.timestamp.desc()).all()
    return jsonify(diagnosis_log_schema.dump(logs, many=True))

# Admin routes
@app.route('/admin/herbs', methods=['POST'])
@jwt_required()
def add_herb():
    if not is_admin():
        return jsonify({"msg": "Admin access required"}), 403
    
    try:
        data = herb_schema.load(request.json)
    except ValidationError as err:
        return jsonify(err.messages), 400
    
    new_herb = Herb(**data)
    db.session.add(new_herb)
    db.session.commit()
    return jsonify(herb_schema.dump(new_herb)), 201

@app.route('/admin/herbs/<int:id>', methods=['PUT'])
@jwt_required()
def update_herb(id):
    if not is_admin():
        return jsonify({"msg": "Admin access required"}), 403
    
    herb = Herb.query.get(id)
    if not herb:
        return jsonify({"msg": "Herb not found"}), 404
    
    try:
        data = herb_schema.load(request.json, partial=True)
    except ValidationError as err:
        return jsonify(err.messages), 400
    
    for key, value in data.items():
        setattr(herb, key, value)
    
    db.session.commit()
    return jsonify(herb_schema.dump(herb))

@app.route('/admin/diseases', methods=['POST'])
@jwt_required()
def add_disease():
    if not is_admin():
        return jsonify({"msg": "Admin access required"}), 403
    
    try:
        data = disease_schema.load(request.json)
    except ValidationError as err:
        return jsonify(err.messages), 400
    
    new_disease = Disease(**data)
    db.session.add(new_disease)
    db.session.commit()
    return jsonify(disease_schema.dump(new_disease)), 201

@app.route('/admin/diseases/<int:id>', methods=['PUT'])
@jwt_required()
def update_disease(id):
    if not is_admin():
        return jsonify({"msg": "Admin access required"}), 403
    
    disease = Disease.query.get(id)
    if not disease:
        return jsonify({"msg": "Disease not found"}), 404
    
    try:
        data = disease_schema.load(request.json, partial=True)
    except ValidationError as err:
        return jsonify(err.messages), 400
    
    for key, value in data.items():
        setattr(disease, key, value)
    
    db.session.commit()
    return jsonify(disease_schema.dump(disease))

def is_admin():
    current_user = User.query.filter_by(username=get_jwt_identity()).first()
    return current_user and current_user.is_admin

if __name__ == '__main__':
    db.create_all()
    app.run(debug=True)