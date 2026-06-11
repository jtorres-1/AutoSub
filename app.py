from flask import Flask, render_template, request, redirect, url_for, session, flash
from werkzeug.security import generate_password_hash, check_password_hash
from models import db, User
from bot_runner import start_bot, stop_bot, is_running, get_stats, get_log_tail
import stripe
import os

app = Flask(__name__)
app.secret_key = os.environ.get("SECRET_KEY", "autosub-secret-change-this")
app.config["SQLALCHEMY_DATABASE_URI"] = "sqlite:///autosub.db"
app.config["SQLALCHEMY_TRACK_MODIFICATIONS"] = False

db.init_app(app)

stripe.api_key = os.environ.get("STRIPE_SECRET_KEY", "")
STRIPE_PRICE_ID = os.environ.get("STRIPE_PRICE_ID", "")
STRIPE_WEBHOOK_SECRET = os.environ.get("STRIPE_WEBHOOK_SECRET", "")

with app.app_context():
    db.create_all()

def current_user():
    if "user_id" not in session:
        return None
    return User.query.get(session["user_id"])

@app.route("/")
def index():
    return render_template("index.html")

@app.route("/signup", methods=["GET", "POST"])
def signup():
    if request.method == "POST":
        email = request.form.get("email", "").strip().lower()
        password = request.form.get("password", "")
        if not email or not password:
            flash("Email and password required.")
            return redirect(url_for("signup"))
        if User.query.filter_by(email=email).first():
            flash("Email already registered.")
            return redirect(url_for("signup"))
        user = User(email=email, password_hash=generate_password_hash(password))
        db.session.add(user)
        db.session.commit()
        session["user_id"] = user.id
        return redirect(url_for("setup"))
    return render_template("signup.html")

@app.route("/login", methods=["GET", "POST"])
def login():
    if request.method == "POST":
        email = request.form.get("email", "").strip().lower()
        password = request.form.get("password", "")
        user = User.query.filter_by(email=email).first()
        if not user or not check_password_hash(user.password_hash, password):
            flash("Invalid email or password.")
            return redirect(url_for("login"))
        session["user_id"] = user.id
        return redirect(url_for("dashboard"))
    return render_template("login.html")

@app.route("/logout")
def logout():
    session.clear()
    return redirect(url_for("index"))

@app.route("/setup", methods=["GET", "POST"])
def setup():
    user = current_user()
    if not user:
        return redirect(url_for("login"))
    if request.method == "POST":
        user.reddit_username = request.form.get("reddit_username", "").strip()
        user.reddit_password = request.form.get("reddit_password", "").strip()
        user.reddit_client_id = request.form.get("reddit_client_id", "").strip()
        user.reddit_client_secret = request.form.get("reddit_client_secret", "").strip()
        user.offer_text = request.form.get("offer_text", "").strip()
        user.keywords = request.form.get("keywords", "").strip()
        user.dm_subject = request.form.get("dm_subject", "quick question").strip()
        db.session.commit()
        flash("Settings saved.")
        return redirect(url_for("subscribe"))
    return render_template("setup.html", user=user)

@app.route("/subscribe")
def subscribe():
    user = current_user()
    if not user:
        return redirect(url_for("login"))
    if user.subscription_status == "active":
        return redirect(url_for("dashboard"))
    return render_template("subscribe.html", user=user)

@app.route("/create-checkout", methods=["POST"])
def create_checkout():
    user = current_user()
    if not user:
        return redirect(url_for("login"))
    try:
        checkout = stripe.checkout.Session.create(
            payment_method_types=["card"],
            mode="subscription",
            line_items=[{"price": STRIPE_PRICE_ID, "quantity": 1}],
            success_url=request.host_url + "dashboard?success=1",
            cancel_url=request.host_url + "subscribe",
            metadata={"user_id": user.id},
        )
        return redirect(checkout.url)
    except Exception as e:
        flash(f"Checkout error: {e}")
        return redirect(url_for("subscribe"))

@app.route("/webhook", methods=["POST"])
def webhook():
    payload = request.data
    sig_header = request.headers.get("Stripe-Signature")
    try:
        event = stripe.Webhook.construct_event(payload, sig_header, STRIPE_WEBHOOK_SECRET)
    except Exception as e:
        return str(e), 400
    if event["type"] == "checkout.session.completed":
        session_obj = event["data"]["object"]
        user_id = session_obj.get("metadata", {}).get("user_id")
        if user_id:
            user = User.query.get(int(user_id))
            if user:
                user.stripe_customer_id = session_obj.get("customer")
                user.stripe_subscription_id = session_obj.get("subscription")
                user.subscription_status = "active"
                db.session.commit()
                pid = start_bot(user)
                user.bot_pid = pid
                user.bot_running = True
                db.session.commit()
    elif event["type"] in ("customer.subscription.deleted", "customer.subscription.paused"):
        sub = event["data"]["object"]
        user = User.query.filter_by(stripe_subscription_id=sub["id"]).first()
        if user:
            if user.bot_pid and is_running(user.bot_pid):
                stop_bot(user.bot_pid)
            user.bot_running = False
            user.subscription_status = "inactive"
            db.session.commit()
    return "", 200

@app.route("/dashboard")
def dashboard():
    user = current_user()
    if not user:
        return redirect(url_for("login"))
    if user.subscription_status != "active":
        return redirect(url_for("subscribe"))
    if user.bot_running and not is_running(user.bot_pid):
        pid = start_bot(user)
        user.bot_pid = pid
        db.session.commit()
    stats = get_stats(user.id)
    logs = get_log_tail(user.id, 30)
    return render_template("dashboard.html", user=user, stats=stats, logs=logs)

@app.route("/settings", methods=["GET", "POST"])
def settings():
    user = current_user()
    if not user:
        return redirect(url_for("login"))
    if request.method == "POST":
        user.offer_text = request.form.get("offer_text", "").strip()
        user.keywords = request.form.get("keywords", "").strip()
        user.dm_subject = request.form.get("dm_subject", "quick question").strip()
        db.session.commit()
        if user.bot_pid and is_running(user.bot_pid):
            stop_bot(user.bot_pid)
        if user.subscription_status == "active":
            pid = start_bot(user)
            user.bot_pid = pid
            user.bot_running = True
            db.session.commit()
        flash("Settings updated. Bot restarted.")
        return redirect(url_for("dashboard"))
    return render_template("settings.html", user=user)

if __name__ == "__main__":
    app.run(host="0.0.0.0", port=5002, debug=False)
