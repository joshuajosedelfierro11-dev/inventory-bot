from flask import Flask, request, render_template_string
from openai import OpenAI
import os, json, datetime, collections, re

client = OpenAI(api_key=os.getenv("OPENAI_INVENTORY_KEY"))

app = Flask(__name__)
app.secret_key = "inventory_secret"

FILE="inventory.json"
MIN_FILE="min_levels.json"
CAT_FILE="categories.json"
HISTORY_FILE="stock_history.json"
SUP_FILE="suppliers.json"
PRICE_FILE="price_list.json"

# ---- PASTE YOUR HTML HERE ----
MAIN_HTML = """
<!doctype html>
<html>
<head>
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
</style>
</head>
<body>

<div class="header">📦 Mr AI Inventory Dashboard</div>
<div class="container">

{% if alerts %}
<div class="alert">⚠ Low stock: {{ alerts }}</div>
{% endif %}

{% if reorders %}
<div class="alert" style="background:#dcfce7;color:#065f46">
🔁 Smart Reorder Suggestions:
{% for i,q in reorders.items() %}
<br>• {{ i }} → reorder {{ q }} units
{% endfor %}
</div>
{% endif %}

{% if profit is not none %}
<div class="alert" style="background:#e0f2fe;color:#075985">
💰 Total Profit: ₱{{ profit }}
</div>
{% endif %}

<div class="grid">
<div class="card">
<h3>Command Center</h3>
<form method="post">
<input name="msg" placeholder="Sold 3 coke at 20 pesos">
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
<tr><td>We received 10 coke at 15 pesos</td><td>Add stock</td></tr>
<tr><td>Sold 3 coke at 20 pesos</td><td>Deduct stock</td></tr>
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
<td>
{% if qty <= min_levels.get(item,5) %}
<span class="low">{{ qty }}</span>
{% else %}
<span class="ok">{{ qty }}</span>
{% endif %}
</td>
<td>{{ min_levels.get(item,5) }}</td>
</tr>
{% endfor %}
</table>
</div>

<div class="card">
<h3>Stock History</h3>
<table>
<tr><th>Time</th><th>Item</th><th>Action</th><th>Qty</th><th>Price</th></tr>
{% for h in history %}
<tr>
<td>{{ h["time"] }}</td>
<td>{{ h["item"] }}</td>
<td>{{ h["action"] }}</td>
<td>{{ h["qty"] }}</td>
<td>{{ h.get("price",0) }}</td>
</tr>
{% endfor %}
</table>
</div>

</div>
</body>
</html>
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
table{width:100%;border-collapse:collapse;margin-top:10px}
th{background:#f8fafc;padding:10px;text-align:left}
td{padding:10px;border-top:1px solid #e5e7eb}
</style></head><body>

<div class="header">📊 Mr AI Sales Intelligence</div>
<div class="container">

<div class="grid">
<div class="card"><h3>🔥 Most Sold</h3><p>{{ top_items }}</p></div>
<div class="card"><h3>📆 Monthly Transactions</h3><p>{{ monthly }}</p></div>
<div class="card"><h3>🔁 Inventory Turnover</h3><p>{{ turnover }}</p></div>
</div>

<div class="card">
<h3>💰 Profit Tracker</h3>
<table>
<tr><th>Item</th><th>Total Qty Sold</th><th>Total Profit</th></tr>
{% for i,d in profit_table.items() %}
<tr><td>{{ i }}</td><td>{{ d.qty }}</td><td>₱{{ d.profit }}</td></tr>
{% endfor %}
</table>
</div>

<div class="card">
<h3>🏷 Price List Tracker</h3>
<table>
<tr><th>Item</th><th>Last Bought Price</th><th>Last Sold Price</th></tr>
{% for i,p in price_list.items() %}
<tr>
<td>{{ i }}</td>
<td>₱{{ prices.get(i,{}).get("buy",0) }}</td>
<td>₱{{ p }}</td>
</tr>
{% endfor %}
</table>
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
<tr><td>{{ i }}</td><td>{{ s["name"] }}</td><td>{{ s["contact"] }}</td></tr>
{% endfor %}
</table>
<a href="/"><button style="margin-top:20px;padding:14px;background:#4c1d95;color:white;border:none;border-radius:10px">⬅ Back</button></a>
</div></body></html>
"""

SYSTEM_PROMPT = """
You are Stocky, a friendly Filipino store assistant.

Always output VALID JSON ONLY.

Format:
{"actions":[{"action":"add|sell|setmin|setcat|setsupplier",
"item":"","qty":0,"price":0,"category":"","supplier":"","contact":"string or empty","reply":""}]}
"""

def load(p):
    if not os.path.exists(p): return {} if p!=HISTORY_FILE else []
    try: return json.load(open(p))
    except: return {} if p!=HISTORY_FILE else []

def save(p,d):
    with open(p,"w") as f: json.dump(d,f,indent=2)

def log(item,action,qty,price=0):
    hist=load(HISTORY_FILE)
    hist.append({"time":str(datetime.datetime.now()),"item":item,"action":action,"qty":qty,"price":price})
    save(HISTORY_FILE,hist)

def update_price(item, price, mode):
    prices=load(PRICE_FILE)
    prices.setdefault(item,{"buy":0,"sell":0})
    prices[item][mode]=price
    save(PRICE_FILE,prices)

def smart_reorder(inv,mins,hist):
    recent={}
    for h in hist:
        if h.get("action")=="OUT":
            recent[h["item"]]=recent.get(h["item"],0)+h.get("qty",0)
    return {i:max(5,recent[i]//7*10) for i,q in inv.items() if q<=mins.get(i,5) and i in recent}

def resolve_item_keyword(word,inventory):
    word=word.lower()
    matches=[i for i in inventory if i.lower().startswith(word)]
    return matches[0] if matches else word

def resolve_copy_commands(text,cats,sups):
    text=text.lower()
    acts=[]
    def before(k): return text.split(k)[0].strip().split()[-1]
    def after(k): return text.split(k)[1].strip().split()[0]

    for k in ["same category as","same category with"]:
        if k in text:
            item,ref=before(k),after(k)
            if ref in cats:
                acts.append({"action":"setcat","item":item,"category":cats[ref],
                "qty":0,"price":0,"supplier":"","contact":"",
                "reply":f"{item} now uses same category as {ref}."})

    for k in ["same supplier as","same supplier with"]:
        if k in text:
            item,ref=before(k),after(k)
            if ref in sups:
                acts.append({"action":"setsupplier","item":item,
                "supplier":sups[ref]["name"],"contact":sups[ref].get("contact",""),
                "qty":0,"price":0,"category":"",
                "reply":f"{item} now uses same supplier as {ref}."})
    return acts

def detect_stock_query(text,inv):
    text=text.lower()
    patterns=[
        r"how many\s+(\w+)",
        r"(\w+)\s+left",
        r"remaining\s+(\w+)",
        r"stock\s+of\s+(\w+)",
        r"(\w+)\?$"
    ]
    for p in patterns:
        m=re.search(p,text)
        if m:
            key=m.group(1)
            item=resolve_item_keyword(key,inv)
            return item,inv.get(item,0)
    return None,None

@app.route("/",methods=["GET","POST"])
def home():
    inv,mins,cats,sups,hist,prices=load(FILE),load(MIN_FILE),load(CAT_FILE),load(SUP_FILE),load(HISTORY_FILE),load(PRICE_FILE)
    last_hist=hist[-15:]
    alerts=[i for i,q in inv.items() if q<=mins.get(i,5)]
    reorders=smart_reorder(inv,mins,hist)
    profit=sum((h["price"]-prices.get(h["item"],{}).get("buy",0))*h["qty"]
        for h in hist if h.get("action")=="OUT")
    reply=""

    if request.method=="POST":
        text=request.form["msg"]

        item,qty=detect_stock_query(text,inv)
        if item:
            reply=f"📦 You have {qty} stocks left for {item}."
        else:
            try:
                copied=resolve_copy_commands(text,cats,sups)
                ai=client.responses.create(model="gpt-4.1-mini",input=[
                    {"role":"system","content":SYSTEM_PROMPT},
                    {"role":"user","content":text}
                ]).output_text

                data=json.loads(ai)
                data["actions"]+=copied

                for d in data["actions"]:
                    if d.get("item"):
                        d["item"]=resolve_item_keyword(d["item"],inv)

                    if d["action"]=="add":
                        inv[d["item"]]=inv.get(d["item"],0)+int(d["qty"])
                        update_price(d["item"],d["price"],"buy")
                        log(d["item"],"IN",d["qty"],d["price"])
                    elif d["action"]=="sell":
                        inv[d["item"]]=inv.get(d["item"],0)-int(d["qty"])
                        update_price(d["item"],d["price"],"sell")
                        log(d["item"],"OUT",d["qty"],d["price"])
                    elif d["action"]=="setcat":
                        cats[d["item"]]=d["category"]
                    elif d["action"]=="setsupplier":
                        sups[d["item"]]={"name":d.get("supplier",""),"contact":d.get("contact","")}

                save(FILE,inv);save(MIN_FILE,mins);save(CAT_FILE,cats);save(SUP_FILE,sups)
                reply=data["actions"][0]["reply"]
            except:
                reply="Try: coke left? or sold 2 cok"

    return render_template_string(MAIN_HTML,reply=reply,inventory=inv,
        min_levels=mins,categories=cats,suppliers=sups,
        history=last_hist,alerts=alerts,reorders=reorders,profit=profit)

@app.route("/dashboard")
def dashboard():
    hist=load(HISTORY_FILE)
    prices=load(PRICE_FILE)
    counter=collections.Counter(h["item"] for h in hist if h.get("action")=="OUT")
    profit_table={}
    price_list={}
    for h in hist:
        if h.get("action")=="OUT":
            i=h["item"]
            profit_table.setdefault(i,{"qty":0,"profit":0})
            buy=prices.get(i,{}).get("buy",0)
            profit_table[i]["qty"]+=h["qty"]
            profit_table[i]["profit"]+=(h["price"]-buy)*h["qty"]
            price_list[i]=h["price"]

    return render_template_string(
    DASHBOARD_HTML,
    top_items=counter.most_common(5),
    monthly=len(hist),
    turnover=sum(counter.values()),
    profit_table=profit_table,
    price_list=price_list,
    prices=prices
)


@app.route("/suppliers")
def suppliers():
    return render_template_string(SUPPLIER_HTML,suppliers=load(SUP_FILE))

if __name__=="__main__":
    app.run(port=5000)
