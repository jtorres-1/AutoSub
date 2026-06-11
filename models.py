from flask_sqlalchemy import SQLAlchemy
from datetime import datetime

db = SQLAlchemy()

class User(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    email = db.Column(db.String(120), unique=True, nullable=False)
    password_hash = db.Column(db.String(256), nullable=False)
    reddit_username = db.Column(db.String(100), nullable=True)
    reddit_password = db.Column(db.String(256), nullable=True)
    reddit_client_id = db.Column(db.String(100), nullable=True)
    reddit_client_secret = db.Column(db.String(256), nullable=True)
    offer_text = db.Column(db.Text, nullable=True)
    keywords = db.Column(db.Text, nullable=True)
    dm_subject = db.Column(db.String(200), nullable=True, default="quick question")
    stripe_customer_id = db.Column(db.String(100), nullable=True)
    stripe_subscription_id = db.Column(db.String(100), nullable=True)
    subscription_status = db.Column(db.String(50), nullable=True, default="inactive")
    bot_pid = db.Column(db.Integer, nullable=True)
    bot_running = db.Column(db.Boolean, default=False)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
