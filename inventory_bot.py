from flask import Flask, request, render_template_string
from openai import OpenAI
import os, json, datetime, collections

client = OpenAI(api_key=os.getenv("OPENAI_INVENTORY_KEY"))

app = Flask(__name__)
app.secret_key = "inventory_secret"

FILE="inventory.json"
MIN_FILE="min_levels.json"
CAT_FILE="categories.json"
HISTORY_FILE="stock_history.json"
SUP_FILE="suppliers.json"

SYSTEM_PROMPT = """
You are Stocky, a polite inventory assistant.

Return ONLY valid JSON.

Actions:
add, sell, setmin, setcat, setsupplier

add/sell:
{"action":"add|sell","item":"string","qty":number,"reply":"string"}

setmin:
{"action":"setmin","item":"string","qty":number,"reply":"string"}

setcat:
{"action":"setcat","item":"string","category":"string","reply":"string"}

setsupplier:
{"action":"setsupplier","item":"string","supplier":"string","contact":"string","reply":"string"}
"""

# ---------------- HTML ----------------

MAIN_HTML = """
<!doctype html>
<html><head>
<meta name="viewport" content="width=device-width, initial-scale=1.0">
<title>Mr AI Inventory</title>
<style>
body{font-family:'Segoe UI',sans-serif;background:#f1f5f9;margin:0;color:#1f2937}
.header{background:linear-gradient(90deg,#111827,#1f2937);color:white;padding:20px;font-size:22px;font-weight:600}
.container{padding:20px;max-width:1200px;margin:auto}
.alert{background:#fee2e2;color:#991b1b;padding:12px;border-radius:8px;margin-bottom:15px}
.grid{display:grid;grid-template-columns:1fr 1fr;gap:20px}
.card{background:white;border-radius:14px;padding:20px;box-shadow:0 10px 25px rgba(0,0,0,.1)}
input,button{padding:12px;border-radius:8px;border:1px solid #e5e7eb;font-size:15px}
button{background:#2563eb;color:white;border:none;width:100%;margin-top:8px}
table{width:100%;border-collapse:collapse;margin-top:10px}
th{background:#f8fafc;padding:10px;text-align:left}
td{padding:10px;border-top:1px solid #e5e7eb}
.low{background:#fecaca;color:#7f1d1d;padding:4px 10px;border-radius:999px}
.ok{background:#bbf7d0;color:#065f46;padding:4px 10px;border-radius:999px}
</style></head><body>

<div class="header">📦 Mr AI Inventory Dashboard</div>
<div class="container">

{% if alerts %}
<div class="alert">⚠ Low stock: {{ alerts }}</div>
{% endif %}

<div class="grid">
<div class="card">
<h3>Command Center</h3>
<form method="post">
<input name="msg" placeholder="We received 10 coke today">
<button>Submit</button>
</form>
<p>{{ reply }}</p>
<a href="/dashboard"><button style="background:#16a34a">📊 View Sales Dashboard</button></a>
<a href="/suppliers"><button style="background:#9333ea">🏭 Supplier Manager</button></a>
</div>

<div class="card">
<h3>Keyword Guide</h3>
<table>
<tr><th>Type</th><th>Result</th></tr>
<tr><td>We received 10 coke</td><td>Add stock</td></tr>
<tr><td>Sold 3 bottled water</td><td>Deduct stock</td></tr>
<tr><td>Set minimum coke to 15</td><td>Low-stock alert</td></tr>
<tr><td>Set category coke to Drinks</td><td>Assign category</td></tr>
<tr><td>Set supplier coke to ABC Corp contact 09171234567</td><td>Assign supplier</td></tr>
</table>
</div>
</div>

<div class="card">
<h3>Current Inventory</h3>
<table>
<tr><th>Item</th><th>Category</th><th>Supplier</th><th>Stock</th><th>Min</th></tr>
{% for item,qty in inventory.items() %}
<tr>
<td>{{ item }}</td>
<td>{{ categories.get(item,"-") }}</td>
<td>{{ suppliers.get(item,{}).get("name","-") }}</td>
<td>{% if qty <= min_levels.get(item,5) %}<span class="low">{{ qty }}</span>{% else %}<span class="ok">{{ qty }}</span>{% endif %}</td>
<td>{{ min_levels.get(item,5) }}</td>
</tr>{% endfor %}
</table>
</div>

<div class="card">
<h3>Stock History</h3>
<table>
<tr><th>Time</th><th>Item</th><th>Action</th><th>Qty</th></tr>
{% for h in history %}
<tr><td>{{ h.time }}</td><td>{{ h.item }}</td><td>{{ h.action }}</td><td>{{ h.qty }}</td></tr>
{% endfor %}
</table>
</div>

</div></body></html>
"""

DASHBOARD_HTML = """
<!doctype html><html><head>
<title>Sales Dashboard</title>
<style>
body{font-family:Segoe UI;background:#f1f5f9;margin:0}
.header{background:#111827;color:white;padding:20px;font-size:22px}
.container{padding:30px;max-width:1200px;margin:auto}
.card{background:white;border-radius:16px;padding:25px;margin-bottom:20px;
box-shadow:0 10px 30px rgba(0,0,0,.12)}
.grid{display:grid;grid-template-columns:repeat(3,1fr);gap:20px}
</style></head><body>

<div class="header">📊 Mr AI Sales Intelligence</div>
<div class="container">

<div class="grid">
<div class="card"><h3>🔥 Most Sold</h3><p>{{ top_items }}</p></div>
<div class="card"><h3>📆 Monthly Transactions</h3><p>{{ monthly }}</p></div>
<div class="card"><h3>🔁 Inventory Turnover</h3><p>{{ turnover }}</p></div>
</div>

<a href="/"><button style="padding:14px;background:#2563eb;color:white;border:none;border-radius:10px">⬅ Back</button></a>

</div></body></html>
"""

SUPPLIER_HTML = """
<!doctype html><html><head>
<title>Supplier Manager</title>
<style>
body{font-family:Segoe UI;background:#f1f5f9;margin:0}
.header{background:#4c1d95;color:white;padding:20px;font-size:22px}
.container{padding:30px;max-width:1100px;margin:auto}
table{width:100%;border-collapse:collapse;background:white;border-radius:16px;
overflow:hidden;box-shadow:0 10px 30px rgba(0,0,0,.12)}
th{background:#ede9fe;padding:14px;text-align:left}
td{padding:14px;border-top:1px solid #ddd}
</style></head><body>

<div class="header">🏭 Supplier Management</div>
<div class="container">

<table>
<tr><th>Item</th><th>Supplier</th><th>Contact Number</th></tr>
{% for i,s in suppliers.items() %}
<tr>
<td>{{ i }}</td>
<td>{{ s["name"] }}</td>
<td>{{ s["contact"] }}</td>
</tr>
{% endfor %}
</table>

<a href="/"><button style="margin-top:20px;padding:14px;background:#4c1d95;color:white;border:none;border-radius:10px">⬅ Back</button></a>

</div></body></html>
"""

# ---------------- HELPERS ----------------

def load(p):
    if not os.path.exists(p): return {} if p!=HISTORY_FILE else []
    try: return json.load(open(p))
    except: return {} if p!=HISTORY_FILE else []

def save(p,d): open(p,"w").write(json.dumps(d,indent=2))

def log(item,action,qty):
    hist=load(HISTORY_FILE)
    hist.append({"time":str(datetime.datetime.now()),"item":item,"action":action,"qty":qty})
    save(HISTORY_FILE,hist)

# ---------------- ROUTES ----------------

@app.route("/",methods=["GET","POST"])
def home():
    inv,mins,cats,sups,hist = load(FILE),load(MIN_FILE),load(CAT_FILE),load(SUP_FILE),load(HISTORY_FILE)
    last_hist = hist[-15:]
    reply=""
    alerts=[i for i,q in inv.items() if q <= mins.get(i,5)]

    if request.method=="POST":
        try:
            ai=client.responses.create(model="gpt-4.1-mini",input=[
                {"role":"system","content":SYSTEM_PROMPT},
                {"role":"user","content":request.form["msg"]}
            ]).output_text
            d=json.loads(ai)

            if d["action"]=="add": inv[d["item"]]=inv.get(d["item"],0)+int(d["qty"]); log(d["item"],"IN",d["qty"])
            if d["action"]=="sell": inv[d["item"]]=inv.get(d["item"],0)-int(d["qty"]); log(d["item"],"OUT",d["qty"])
            if d["action"]=="setmin": mins[d["item"]]=int(d["qty"])
            if d["action"]=="setcat": cats[d["item"]]=d["category"]
            if d["action"]=="setsupplier": sups[d["item"]]={"name":d["supplier"],"contact":d["contact"]}

            save(FILE,inv); save(MIN_FILE,mins); save(CAT_FILE,cats); save(SUP_FILE,sups)
            reply=d.get("reply","Updated.")
        except:
            reply="Try: We received 10 coke"

    return render_template_string(MAIN_HTML,reply=reply,inventory=inv,min_levels=mins,categories=cats,suppliers=sups,history=last_hist,alerts=alerts)

@app.route("/dashboard")
def dashboard():
    hist=load(HISTORY_FILE)
    counter=collections.Counter(h["item"] for h in hist if h["action"]=="OUT")
    monthly=len(hist)
    turnover=sum(counter.values())
    return render_template_string(DASHBOARD_HTML,top_items=counter.most_common(5),monthly=monthly,turnover=turnover)

@app.route("/suppliers")
def suppliers():
    return render_template_string(SUPPLIER_HTML,suppliers=load(SUP_FILE))

if __name__=="__main__":
    app.run(port=5000)
