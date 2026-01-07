from flask import Flask, request, render_template_string, send_file
from openai import OpenAI
import os, json, datetime, collections
from openpyxl import Workbook
from reportlab.platypus import SimpleDocTemplate, Table, TableStyle, Paragraph
from reportlab.lib.styles import getSampleStyleSheet
from reportlab.lib import colors

client = OpenAI(api_key=os.getenv("OPENAI_INVENTORY_KEY"))

app = Flask(__name__)
app.secret_key = "inventory_secret"

# ---------- STORAGE ----------
BASE = "/data/" if os.path.exists("/data") else "./data/"
os.makedirs(BASE, exist_ok=True)

FILE = BASE+"inventory.json"
MIN_FILE = BASE+"min_levels.json"
CAT_FILE = BASE+"categories.json"
HISTORY_FILE = BASE+"stock_history.json"
SUP_FILE = BASE+"suppliers.json"
PRICE_FILE = BASE+"price_list.json"

# ---------- HTML ----------
# KEEP YOUR HTML AS IS
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

{% if alerts is defined and alerts %}
<div class="alert">⚠ Low stock: {{ alerts }}</div>
{% endif %}

{% if reorders is defined and reorders %}
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
<a href="/report"><button style="background:#065f46">📅 Daily / Weekly Report</button></a>
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

REPORT_HTML = """
<!doctype html><html><head>
<title>Business Report</title>
<style>
body{font-family:Segoe UI;background:#f1f5f9;margin:0}
.header{background:#065f46;color:white;padding:20px;font-size:22px}
.container{padding:30px;max-width:1200px;margin:auto}
.card{background:white;border-radius:16px;padding:25px;margin-bottom:20px;
box-shadow:0 10px 30px rgba(0,0,0,.12)}
table{width:100%;border-collapse:collapse;margin-top:10px}
th,td{padding:10px;border-top:1px solid #ddd;text-align:left}
button{padding:12px;border:none;border-radius:10px;background:#065f46;color:white;margin-right:10px}
.scroll-box{max-height:300px;overflow-y:auto;}
</style></head><body>

<div class="header">📑 Daily & Weekly Business Report</div>
<div class="container">

<div class="card">
<h3>📊 Sales Summary</h3>
<p>
Today:
{{ today_summary.qty if today_summary is defined else 0 }} items sold |
₱{{ today_summary.sales if today_summary is defined else 0 }} sales |
₱{{ today_summary.profit if today_summary is defined else 0 }} profit<br>
This Week:
{{ week_summary.qty if week_summary is defined else 0 }} items sold |
₱{{ week_summary.sales if week_summary is defined else 0 }} sales |
₱{{ week_summary.profit if week_summary is defined else 0 }} profit
</p>
</div>

<div class="card">
<h3>🔥 Top Selling Items (This Week)</h3>
<table>
<tr><th>Item</th><th>Qty Sold</th></tr>
{% if week_summary is defined %}
{% for i,q in week_summary.top_items %}
<tr><td>{{ i }}</td><td>{{ q }}</td></tr>
{% endfor %}
{% endif %}
</table>
</div>

<div class="card">
<h3>📅 Today Transactions</h3>
<div class="scroll-box">
<table>
<tr><th>Time</th><th>Item</th><th>Qty</th><th>Price</th></tr>
{% if today is defined %}
{% for h in today %}
<tr><td>{{ h["time"] }}</td><td>{{ h["item"] }}</td><td>{{ h["qty"] }}</td><td>{{ h["price"] }}</td></tr>
{% endfor %}
{% endif %}
</table>
</div>
</div>

<div class="card">
<h3>🗓 Weekly Transactions</h3>
<div class="scroll-box">
<table>
<tr><th>Time</th><th>Item</th><th>Qty</th><th>Price</th></tr>
{% if week is defined %}
{% for h in week %}
<tr><td>{{ h["time"] }}</td><td>{{ h["item"] }}</td><td>{{ h["qty"] }}</td><td>{{ h["price"] }}</td></tr>
{% endfor %}
{% endif %}
</table>
</div>
</div>

<a href="/export_report/xlsx"><button>⬇ Export Excel</button></a>
<a href="/export_report/pdf"><button>⬇ Export PDF</button></a>
<br><br>
<a href="/"><button>⬅ Back</button></a>

</div></body></html>
"""

SYSTEM_PROMPT = """
You are Stocky, a friendly inventory assistant.
If user asks about stock quantity, return:
{"actions":[{"action":"query","item":"coke","reply":"You have 10 bottles of coke left."}]}
Return JSON only.
"""

# ---------- HELPERS ----------
def load(p):
    if not os.path.exists(p):
        return {} if p!=HISTORY_FILE else []
    try: return json.load(open(p))
    except: return {} if p!=HISTORY_FILE else []

def save(p,d):
    with open(p,"w") as f: json.dump(d,f,indent=2)

def log(item,action,qty,price):
    hist=load(HISTORY_FILE)
    hist.append({"time":str(datetime.datetime.now()),
                 "item":item,"action":action,"qty":qty,"price":price})
    save(HISTORY_FILE,hist)

def find_item(k,inv):
    k=k.lower()
    for i in inv:
        if k in i.lower(): return i
    return k

def build_summary(hist,days):
    now=datetime.datetime.now()
    prices=load(PRICE_FILE)
    qty=sales=profit=0
    counter=collections.Counter()

    for h in hist:
        try:
            t=datetime.datetime.fromisoformat(h["time"].split('.')[0])
            if h["action"]=="OUT" and (now-t).days<days:
                qty+=h["qty"]
                sales+=h["qty"]*h["price"]
                buy=prices.get(h["item"],{}).get("buy",0)
                profit+=(h["price"]-buy)*h["qty"]
                counter[h["item"]]+=h["qty"]
        except: pass

    return {"qty":qty,"sales":sales,"profit":profit,
            "top_items":counter.most_common(5)}

# ---------- ROUTES ----------
@app.route("/",methods=["GET","POST"])
def home():
    inv,mins,cats,sups,prices,hist = load(FILE),load(MIN_FILE),load(CAT_FILE),load(SUP_FILE),load(PRICE_FILE),load(HISTORY_FILE)
    alerts=[i for i,q in inv.items() if q<=mins.get(i,5)]
    profit=sum(h["qty"]*h["price"] for h in hist if h.get("action")=="OUT")
    reply=""

    if request.method=="POST":
        try:
            ai=client.responses.create(model="gpt-4.1-mini",input=[
                {"role":"system","content":SYSTEM_PROMPT},
                {"role":"user","content":request.form["msg"]}
            ]).output_text
            data=json.loads(ai)

            for d in data["actions"]:
                item=find_item(d.get("item",""),inv)
                if d["action"]=="query":
                    reply=d.get("reply",f"You have {inv.get(item,0)} stocks of {item}.")
                elif d["action"]=="add":
                    inv[item]=inv.get(item,0)+d["qty"]
                    prices.setdefault(item,{})["buy"]=d["price"]
                    log(item,"IN",d["qty"],d["price"])
                elif d["action"]=="sell":
                    inv[item]=inv.get(item,0)-d["qty"]
                    prices.setdefault(item,{})["sell"]=d["price"]
                    log(item,"OUT",d["qty"],d["price"])
                elif d["action"]=="remove":
                    inv.pop(item,None); mins.pop(item,None)

            save(FILE,inv); save(MIN_FILE,mins)
            save(CAT_FILE,cats); save(SUP_FILE,sups); save(PRICE_FILE,prices)

        except:
            reply="❌ Try: how many coke left?"

    return render_template_string(MAIN_HTML,reply=reply,inventory=inv,
        min_levels=mins,categories=cats,suppliers=sups,
        history=hist[-15:],alerts=alerts,reorders={},profit=profit)

@app.route("/dashboard")
def dashboard():
    hist=load(HISTORY_FILE); prices=load(PRICE_FILE)
    counter=collections.Counter(h["item"] for h in hist if h.get("action")=="OUT")
    profit_table={}; price_list={}
    for h in hist:
        if h.get("action")=="OUT":
            profit_table.setdefault(h["item"],{"qty":0,"profit":0})
            profit_table[h["item"]]["qty"]+=h["qty"]
            profit_table[h["item"]]["profit"]+=h["qty"]*h["price"]
            price_list[h["item"]]=h["price"]

    return render_template_string(DASHBOARD_HTML,
        top_items=counter.most_common(5),
        monthly=len(hist),
        turnover=sum(counter.values()),
        profit_table=profit_table,
        price_list=price_list,
        prices=prices)

@app.route("/report")
def report():
    hist=load(HISTORY_FILE)
    today=[]; week=[]; now=datetime.datetime.now()
    for h in hist:
        try:
            t=datetime.datetime.fromisoformat(h["time"].split('.')[0])
            if h["action"]=="OUT":
                if (now-t).days<1: today.append(h)
                if (now-t).days<7: week.append(h)
        except: pass

    return render_template_string(REPORT_HTML,today=today,week=week,
        today_summary=build_summary(hist,1),
        week_summary=build_summary(hist,7))

@app.route("/suppliers")
def suppliers():
    return render_template_string(SUPPLIER_HTML,suppliers=load(SUP_FILE))

@app.route("/export_report/xlsx")
def export_xlsx():
    week=build_summary(load(HISTORY_FILE),7)
    wb=Workbook(); ws=wb.active
    ws.append(["Item","Qty Sold"])
    for i,q in week["top_items"]: ws.append([i,q])
    path=BASE+"weekly_sales.xlsx"; wb.save(path)
    return send_file(path,as_attachment=True)

@app.route("/export_report/pdf")
def export_pdf():
    week=build_summary(load(HISTORY_FILE),7)
    rows=[["Item","Qty Sold"]]+week["top_items"]
    doc=SimpleDocTemplate(BASE+"weekly_sales.pdf")
    title=Paragraph("Jnel Bibingka & Food House Inc – Weekly Sales Report",
                    getSampleStyleSheet()["Title"])
    t=Table(rows); t.setStyle(TableStyle([('GRID',(0,0),(-1,-1),0.5,colors.black)]))
    doc.build([title,t])
    return send_file(BASE+"weekly_sales.pdf",as_attachment=True)

if __name__=="__main__":
    app.run(port=5000,debug=True)
