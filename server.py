
from flask import Flask, request, jsonify, send_from_directory, send_file, session
from flask_cors import CORS
import json, os, uuid, hashlib
from werkzeug.utils import secure_filename
from datetime import datetime
from functools import wraps
import pandas as pd
import numpy as np
import matplotlib
matplotlib.use('Agg')
import matplotlib.pyplot as plt

app = Flask(__name__)
app.secret_key = os.environ.get("FLASK_SECRET_KEY", os.urandom(24).hex())
CORS(app, supports_credentials=True, origins="*")

BASE_DIR      = os.path.dirname(os.path.abspath(__file__))
LISTINGS_FILE = os.path.join(BASE_DIR, "listings.json")
USERS_FILE    = os.path.join(BASE_DIR, "users.json")
UPLOADS_DIR   = os.path.join(BASE_DIR, "uploads")
ALLOWED_EXT   = {"png", "jpg", "jpeg", "webp", "gif"}
PORT          = 3001

import pandas as pd

os.makedirs(UPLOADS_DIR, exist_ok=True)
for fp in [LISTINGS_FILE, USERS_FILE]:
    if not os.path.exists(fp):
        pd.DataFrame([]).to_json(fp, orient="records", indent=2)

def read_json(path):
    with open(path, "r") as f:
        return json.load(f)

def write_json(path, data):
    df = pd.DataFrame(data)
    df.to_json(path, orient="records", indent=2)

def hash_pw(pw):
    return hashlib.sha256(pw.encode()).hexdigest()

def allowed_file(filename):
    return "." in filename and filename.rsplit(".", 1)[1].lower() in ALLOWED_EXT

def get_current_user():
    uid = session.get("user_id") or request.headers.get("X-User-Id")
    if not uid:
        return None
    return next((u for u in read_json(USERS_FILE) if u["id"] == uid), None)

def login_required(f):
    @wraps(f)
    def decorated(*args, **kwargs):
        if not get_current_user():
            return jsonify({"error": "Not logged in"}), 401
        return f(*args, **kwargs)
    return decorated

def seller_required(f):
    @wraps(f)
    def decorated(*args, **kwargs):
        user = get_current_user()
        if not user:
            return jsonify({"error": "Not logged in"}), 401
        if user["role"] != "seller":
            return jsonify({"error": "Sellers only"}), 403
        return f(*args, **kwargs)
    return decorated



@app.route("/api/auth/register", methods=["POST"])
def register():
    d        = request.get_json()
    username = d.get("username", "").strip().lower()
    password = d.get("password", "").strip()
    name     = d.get("name", "").strip()
    role     = d.get("role", "buyer")
    phone    = d.get("phone", "").strip()

    if not username or not password or not name:
        return jsonify({"error": "All fields required"}), 400
    if role == "seller" and not phone:
        return jsonify({"error": "Phone number is required for sellers"}), 400
    if role not in ("buyer", "seller"):
        return jsonify({"error": "Invalid role"}), 400
    if len(password) < 4:
        return jsonify({"error": "Password min 4 characters"}), 400

    users = read_json(USERS_FILE)
    if any(u["username"] == username for u in users):
        return jsonify({"error": "Username already taken"}), 409

    new_user = {
        "id":       str(uuid.uuid4()),
        "username": username,
        "password": hash_pw(password),
        "role":     role,
        "name":     name,
        "phone":    phone if role == "seller" else "",
        "joined":   datetime.now().strftime("%Y-%m-%d")
    }
    users.append(new_user)
    write_json(USERS_FILE, users)
    session["user_id"] = new_user["id"]
    return jsonify({"id": new_user["id"], "username": new_user["username"],
                    "role": new_user["role"], "name": new_user["name"],
                    "phone": new_user["phone"]}), 201

@app.route("/api/auth/login", methods=["POST"])
def login():
    d        = request.get_json()
    username = d.get("username", "").strip().lower()
    password = d.get("password", "").strip()
    users    = read_json(USERS_FILE)
    user     = next((u for u in users if u["username"] == username
                     and u["password"] == hash_pw(password)), None)
    if not user:
        return jsonify({"error": "Invalid username or password"}), 401
    session["user_id"] = user["id"]
    return jsonify({"id": user["id"], "username": user["username"],
                    "role": user["role"], "name": user["name"],
                    "phone": user.get("phone", "")})

@app.route("/api/auth/logout", methods=["POST"])
def logout():
    session.clear()
    return jsonify({"message": "Logged out"})

@app.route("/api/auth/me")
def me():
    user = get_current_user()
    if not user:
        return jsonify(None)
    return jsonify({"id": user["id"], "username": user["username"],
                    "role": user["role"], "name": user["name"],
                    "phone": user.get("phone", "")})


@app.route("/api/listings")
def get_listings():
    listings = read_json(LISTINGS_FILE)
    q        = request.args.get("q", "").lower()
    category = request.args.get("category", "").lower()
    min_p    = request.args.get("min_price")
    max_p    = request.args.get("max_price")
    mine     = request.args.get("mine")

    if q:
        listings = [l for l in listings if q in l["title"].lower() or q in l["description"].lower()]
    if category and category != "all":
        listings = [l for l in listings if l["category"].lower() == category]
    if min_p:
        listings = [l for l in listings if l["price"] >= float(min_p)]
    if max_p:
        listings = [l for l in listings if l["price"] <= float(max_p)]
    if mine:
        user = get_current_user()
        if user:
            listings = [l for l in listings if l["seller_id"] == user["id"]]
        else:
            listings = []
    return jsonify(listings)

@app.route("/api/listings/<lid>")
def get_listing(lid):
    item = next((l for l in read_json(LISTINGS_FILE) if l["id"] == lid), None)
    return jsonify(item) if item else (jsonify({"error": "Not found"}), 404)

@app.route("/api/listings", methods=["POST"])
@seller_required
def create_listing():
    user     = get_current_user()
    title    = request.form.get("title", "").strip()
    category = request.form.get("category", "").strip()
    price    = request.form.get("price", "0")
    desc     = request.form.get("description", "").strip()
    location = request.form.get("location", "").strip()
    usage_duration = request.form.get("usage_duration", "").strip()

    if not title or not category or not desc:
        return jsonify({"error": "title, category and description required"}), 400

    photos = []
    for f in request.files.getlist("photos"):
        if f and allowed_file(f.filename):
            fname = str(uuid.uuid4()) + "_" + secure_filename(f.filename)
            f.save(os.path.join(UPLOADS_DIR, fname))
            photos.append(f"http://localhost:{PORT}/uploads/{fname}")

    item = {
        "id":              str(uuid.uuid4()),
        "title":           title,
        "category":        category,
        "price":           float(price),
        "description":     desc,
        "seller_id":       user["id"],
        "seller_name":     user["name"],
        "seller_phone":    user.get("phone", ""),
        "location":        location,
        "sold":            False,
        "sold_on":         None,
        "photos":          photos,
        "created_at":      datetime.now().strftime("%Y-%m-%d"),
        "usage_duration":  usage_duration
    }
    listings = read_json(LISTINGS_FILE)
    listings.insert(0, item)
    write_json(LISTINGS_FILE, listings)
    return jsonify(item), 201

@app.route("/api/listings/<lid>", methods=["DELETE"])
@seller_required
def delete_listing(lid):
    user     = get_current_user()
    listings = read_json(LISTINGS_FILE)
    item     = next((l for l in listings if l["id"] == lid), None)
    if not item:
        return jsonify({"error": "Not found"}), 404
    if item["seller_id"] != user["id"]:
        return jsonify({"error": "You can only delete your own listings"}), 403
    write_json(LISTINGS_FILE, [l for l in listings if l["id"] != lid])
    return jsonify({"message": "Deleted"})

@app.route("/api/listings/<lid>/sold", methods=["PATCH"])
@seller_required
def mark_sold(lid):
    user     = get_current_user()
    listings = read_json(LISTINGS_FILE)
    item     = next((l for l in listings if l["id"] == lid), None)
    if not item:
        return jsonify({"error": "Not found"}), 404
    if item["seller_id"] != user["id"]:
        return jsonify({"error": "You can only update your own listings"}), 403

    item["sold"] = not item["sold"]
    item["sold_on"] = datetime.now().strftime("%Y-%m-%d") if item["sold"] else None
    write_json(LISTINGS_FILE, listings)
    return jsonify(item)

@app.route("/api/categories")
def get_categories():
    listings = read_json(LISTINGS_FILE)
    return jsonify(sorted(set(l["category"] for l in listings)))

@app.route("/uploads/<filename>")
def serve_upload(filename):
    return send_from_directory(UPLOADS_DIR, filename)

def generate_analytics_data_and_charts(seller_id):
    all_listings = read_json(LISTINGS_FILE)
    listings = [l for l in all_listings if l.get("seller_id") == seller_id]
    
    df = pd.DataFrame(listings)
    
    if 'sold' not in df.columns:
        df['sold'] = False
    else:
        df['sold'] = df['sold'].fillna(False).astype(bool)
        
    if 'price' not in df.columns:
        df['price'] = 0.0
    else:
        df['price'] = pd.to_numeric(df['price'], errors='coerce').fillna(0.0)
        
    if 'category' not in df.columns:
        df['category'] = 'Other'
    else:
        df['category'] = df['category'].fillna('Other')
        
    if 'location' not in df.columns:
        df['location'] = 'Unknown'
    else:
        df['location'] = df['location'].fillna('Unknown').str.strip()
        
    if 'created_at' not in df.columns:
        df['created_at'] = datetime.now().strftime("%Y-%m-%d")
    else:
        df['created_at'] = df['created_at'].apply(lambda x: str(x)[:10] if pd.notna(x) else datetime.now().strftime("%Y-%m-%d"))

    prices = df['price'].values
    avg_price = float(np.mean(prices)) if len(prices) > 0 else 0.0
    median_price = float(np.median(prices)) if len(prices) > 0 else 0.0
    min_price = float(np.min(prices)) if len(prices) > 0 else 0.0
    max_price = float(np.max(prices)) if len(prices) > 0 else 0.0
    std_price = float(np.std(prices)) if len(prices) > 0 else 0.0
    percentile_25 = float(np.percentile(prices, 25)) if len(prices) > 0 else 0.0
    percentile_75 = float(np.percentile(prices, 75)) if len(prices) > 0 else 0.0
    
    total_listings = len(df)
    sold_listings = int(df['sold'].sum())
    active_listings = total_listings - sold_listings
    
    sold_df = df[df['sold'] == True]
    total_sales_volume = float(sold_df['price'].sum()) if not sold_df.empty else 0.0

    cat_groups = df.groupby('category')
    category_metrics = []
    for cat, group in cat_groups:
        cat_total = len(group)
        cat_sold = int(group['sold'].sum())
        cat_avg_price = float(group['price'].mean())
        cat_sales_rate = float((cat_sold / cat_total) * 100) if cat_total > 0 else 0.0
        category_metrics.append({
            "category": cat,
            "count": cat_total,
            "avg_price": round(cat_avg_price, 2),
            "sold_count": cat_sold,
            "sales_rate": round(cat_sales_rate, 1)
        })
    category_metrics.sort(key=lambda x: x["count"], reverse=True)

    loc_counts = df['location'].value_counts()
    location_metrics = []
    for loc, count in loc_counts.items():
        if loc and loc != 'Unknown' and str(loc).strip() != "":
            location_metrics.append({
                "location": str(loc).strip(),
                "count": int(count)
            })
    location_metrics = location_metrics[:10]  

    bg_color = '#090c15'      
    surface_color = '#0f172a' 
    text_color = '#f8fafc'   
    primary_color = '#818cf8'
    secondary_color = '#38bdf8' 
    muted_color = '#94a3b8' 
    border_color = '#1e293b' 
    accent_color = '#f59e0b' 
    
    matplotlib.rcParams['text.color'] = text_color
    matplotlib.rcParams['axes.labelcolor'] = text_color
    matplotlib.rcParams['xtick.color'] = muted_color
    matplotlib.rcParams['ytick.color'] = muted_color

    os.makedirs(UPLOADS_DIR, exist_ok=True)
    
    fig, ax = plt.subplots(figsize=(7, 4.5), facecolor=bg_color)
    ax.set_facecolor(bg_color)
    
    if category_metrics:
        cats = [m["category"] for m in category_metrics]
        avg_prices = [m["avg_price"] for m in category_metrics]
        cats_labels = [c[:12] + '..' if len(c) > 12 else c for c in cats]
        
        bar_colors = ['#818cf8', '#a78bfa', '#c084fc', '#38bdf8', '#22d3ee', '#f59e0b', '#f472b6', '#34d399', '#fb923c']
        colors_to_use = [bar_colors[i % len(bar_colors)] for i in range(len(cats_labels))]
        
        bars = ax.bar(cats_labels, avg_prices, color=colors_to_use, edgecolor=border_color, width=0.55, zorder=3)
        ax.set_title("Average Price by Category", fontsize=13, fontweight='bold', pad=18, color=text_color)
        ax.set_ylabel("Price (INR)", fontsize=10)
        ax.grid(True, axis='y', linestyle='--', alpha=0.08, color=text_color, zorder=0)
        
        for bar in bars:
            height = bar.get_height()
            ax.annotate(f'{int(height):,}',
                        xy=(bar.get_x() + bar.get_width() / 2, height),
                        xytext=(0, 5),
                        textcoords="offset points",
                        ha='center', va='bottom', fontsize=9, color=text_color, fontweight='bold')
    else:
        ax.text(0.5, 0.5, "No Data Available", ha='center', va='center', fontsize=14, color=muted_color)
        
    ax.spines['top'].set_visible(False)
    ax.spines['right'].set_visible(False)
    ax.spines['left'].set_color(border_color)
    ax.spines['bottom'].set_color(border_color)
    plt.xticks(rotation=15, ha='right', fontsize=9)
    plt.tight_layout()
    cat_chart_path = os.path.join(UPLOADS_DIR, f"analytics_category_prices_{seller_id}.png")
    plt.savefig(cat_chart_path, bbox_inches='tight', dpi=100, facecolor=bg_color)
    plt.close(fig)

    # pie chart
    fig, ax = plt.subplots(figsize=(5.5, 4.5), facecolor=bg_color)
    ax.set_facecolor(bg_color)
    
    if total_listings > 0:
        sizes = [active_listings, sold_listings]
        labels = ['Available', 'Sold']
        colors = ['#34d399', '#f43f5e'] 
        
        wedges, texts, autotexts = ax.pie(
            sizes, labels=labels, autopct='%1.1f%%',
            startangle=90, colors=colors, 
            textprops=dict(color=text_color, fontsize=11),
            wedgeprops=dict(edgecolor=bg_color, width=0.4, linewidth=2)
        )
        for autotext in autotexts:
            autotext.set_color('#ffffff')
            autotext.set_weight('bold')
            autotext.set_fontsize(11)
            
        ax.set_title("Marketplace Inventory Status", fontsize=12, fontweight='bold', pad=15)
    else:
        ax.text(0.5, 0.5, "No Data Available", ha='center', va='center')
        
    plt.tight_layout()
    inv_chart_path = os.path.join(UPLOADS_DIR, f"analytics_inventory_{seller_id}.png")
    plt.savefig(inv_chart_path, bbox_inches='tight', dpi=100, facecolor=bg_color)
    plt.close(fig)

    # (Line Chart)
    fig, ax = plt.subplots(figsize=(10, 4.5), facecolor=bg_color)
    ax.set_facecolor(bg_color)
    
    if total_listings > 0 and 'created_at' in df.columns:
        trend_data = df.groupby('created_at').size().reset_index(name='daily_count')
        trend_data = trend_data.sort_values('created_at')
        trend_data['cumulative'] = trend_data['daily_count'].cumsum()
        
        dates = trend_data['created_at'].tolist()
        cumulative = trend_data['cumulative'].tolist()
        
        date_labels = []
        for d in dates:
            try:
                date_labels.append(datetime.strptime(d, "%Y-%m-%d").strftime("%b %d"))
            except Exception:
                date_labels.append(d)
                
        ax.plot(date_labels, cumulative, color='#38bdf8', marker='o', linewidth=2.5, markersize=7,
                markerfacecolor='#818cf8', markeredgecolor='#38bdf8', markeredgewidth=1.5, zorder=5)
        ax.fill_between(date_labels, cumulative, color='#818cf8', alpha=0.1, zorder=2)
        
        ax.set_title("Market Growth (Cumulative Listings)", fontsize=13, fontweight='bold', pad=18, color=text_color)
        ax.set_ylabel("Total Listings", fontsize=10)
        ax.grid(True, axis='y', linestyle='--', alpha=0.08, color=text_color, zorder=0)
    else:
        ax.text(0.5, 0.5, "No Data Available", ha='center', va='center', fontsize=14, color=muted_color)
        
    ax.spines['top'].set_visible(False)
    ax.spines['right'].set_visible(False)
    ax.spines['left'].set_color(border_color)
    ax.spines['bottom'].set_color(border_color)
    plt.xticks(rotation=15, ha='right', fontsize=9)
    plt.tight_layout()
    trend_chart_path = os.path.join(UPLOADS_DIR, f"analytics_trends_{seller_id}.png")
    plt.savefig(trend_chart_path, bbox_inches='tight', dpi=100, facecolor=bg_color)
    plt.close(fig)

    return {
        "summary": {
            "total_listings": total_listings,
            "active_listings": active_listings,
            "sold_listings": sold_listings,
            "total_sales_volume": round(total_sales_volume, 2),
            "avg_price": round(avg_price, 2),
            "median_price": round(median_price, 2),
            "min_price": round(min_price, 2),
            "max_price": round(max_price, 2),
            "std_price": round(std_price, 2),
            "percentile_25": round(percentile_25, 2),
            "percentile_75": round(percentile_75, 2),
            "sell_through_rate": round((sold_listings / total_listings * 100), 1) if total_listings > 0 else 0.0
        },
        "category_metrics": category_metrics,
        "location_metrics": location_metrics,
        "charts": {
            "category_prices": f"http://localhost:{PORT}/uploads/analytics_category_prices_{seller_id}.png",
            "inventory": f"http://localhost:{PORT}/uploads/analytics_inventory_{seller_id}.png",
            "trends": f"http://localhost:{PORT}/uploads/analytics_trends_{seller_id}.png"
        }
    }

@app.route("/api/analytics")
@seller_required
def get_analytics():
    try:
        user = get_current_user()
        data = generate_analytics_data_and_charts(user["id"])
        return jsonify(data)
    except Exception as e:
        import traceback
        traceback.print_exc()
        return jsonify({"error": str(e)}), 500

@app.route("/", defaults={"path": ""})
@app.route("/<path:path>")
def serve_frontend(path):
    idx = os.path.join(BASE_DIR, "index.html")
    return send_file(idx) if os.path.exists(idx) else ("index.html not found", 404)

if __name__ == "__main__":
    print(f"\n[Campus OLX Marketplace] -> http://localhost:{PORT}\n")
    app.run(debug=True, port=PORT)
