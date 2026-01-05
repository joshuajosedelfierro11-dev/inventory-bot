from flask import Flask, request, render_template_string, session
from openai import OpenAI
import os, json

client = OpenAI(api_key=os.getenv("OPENAI_INVENTORY_KEY"))

app = Flask(__name__)
app.secret_key = "inventory_secret"

FILE = "inventory.json"
MIN_FILE = "min_levels.json"
CAT_FILE = "categories.json"

SYSTEM_PROMPT = """
You are Stocky, a polite inventory assistant.

Actions: add, sell, show, low, wipe, setmin, setcat

setmin:
{"action":"setmin","item":"string","qty":number,"reply":"string"}

setcat:
{"action":"setcat","item":"string","category":"string","reply":"string"}

wipe:
{"action":"wipe","reply":"Are you sure you want to delete ALL inventory? Type YES DELETE to confirm."}
"""

HTML = """
<!doctype html>
<html>
<head>
<meta name="viewport" content="width=device-width, initial-scale=1.0">
<title>Mr AI Inventory</title>
<style>
body {font-family:-apple-system,BlinkMacSystemFont,sans-serif;background:#0f172a;margin:0;color:#e5e7eb}
.header {background:linear-gradient(90deg,#1e3a8a,#2563eb);padding:20px;font-size:22px;font-weight:600}
.container {padding:20px}
.card {background:#020617;border-radius:14px;padding:18px;margin-bottom:18px;box-shadow:0 8px 25px rgba(0,0,0,.4)}
input,button{padding:14px;border-radius:12px;border:none;font-size:15px}
input{width:100%;background:#020617;color:#e5e7eb;border:1px solid #1e293b}
button{width:100%;margin-top:10px;background:#2563eb;color:white}
table{width:100%;border-collapse:collapse;margin-top:10px}
th{color:#94a3b8;text-align:left;padding:10px}
td{padding:10px;border-top:1px solid #1e293b}
.badge{background:#1e293b;color:#93c5fd;padding:4px 12px;border-radius:20px;font-size:12px}
.low{background:#7f1d1d;color:#fecaca;padding:4px 12px;border-radius:20px;font-weight:600}
.ok{background:#14532d;color:#bbf7d0;padding:4px 12px;border-radius:20px}
.footer{text-align:center;color:#475569;font-size:12px;margin-top:20px}
</style>
</head>
<body>

<div class="header">📦 Mr AI Inventory</div>
<div class="container">

<div class="card">
<form method="post">
<input name="msg" placeholder="Type command e.g. Set minimum coke to 15">
<button>Send Command</button>
</form>
<div style="margin-top:10px;">{{ reply }}</div>
</div>

<div class="card">
<b>🧭 Keyword Guide</b>
<table>
<tr><th>What you type</th><th>What happens</th></tr>
<tr><td>We received 10 coke</td><td>Adds stock</td></tr>
<tr><td>Sold 3 bottled water</td><td>Deducts stock</td></tr>
<tr><td>Set minimum coke to 15</td><td>Sets low stock alert</td></tr>
<tr><td>Set category coke to Drinks</td><td>Assigns category</td></tr>
<tr><td>Delete everything</td><td>Wipes inventory</td></tr>
</table>
</div>

<div class="card">
<table>
<tr><th>Item</th><th>Category</th><th>Stock</th><th>Min</th></tr>
{% for item, qty in inventory.items() %}
<tr>
<td>{{ item }}</td>
<td><span class="badge">{{ categories.get(item,"Uncategorized") }}</span></td>
<td>
{% if qty <= min_levels.get(item,5) %}
<span class="low">LOW {{ qty }}</span>
{% else %}
<span class="ok">{{ qty }}</span>
{% endif %}
</td>
<td>{{ min_levels.get(item,5) }}</td>
</tr>
{% endfor %}
</table>
</div>

</div>
<div class="footer">Premium Inventory Intelligence System</div>
</body>
</html>
"""

def load_json(path):
    if not os.path.exists(path):
        return {}
    try:
        with open(path) as f:
            return json.load(f)
    except:
        return {}

def save_json(path,data):
    with open(path,"w") as f:
        json.dump(data,f,indent=2)

@app.route("/", methods=["GET","POST"])
def chat():
    inv = load_json(FILE)
    mins = load_json(MIN_FILE)
    cats = load_json(CAT_FILE)
    reply=""

    if request.method=="POST":
        msg=request.form["msg"]

        ai=client.responses.create(model="gpt-4.1-mini",input=[
            {"role":"system","content":SYSTEM_PROMPT},
            {"role":"user","content":f"Inventory:{inv} Min:{mins} Cat:{cats} User:{msg}"}
        ]).output_text

        try:
            d=json.loads(ai)

            if d["action"]=="setcat": cats[d["item"]]=d["category"]
            elif d["action"]=="setmin": mins[d["item"]]=int(d["qty"])
            elif d["action"]=="add": inv[d["item"]]=inv.get(d["item"],0)+int(d["qty"])
            elif d["action"]=="sell": inv[d["item"]]=inv.get(d["item"],0)-int(d["qty"])

            save_json(FILE,inv); save_json(MIN_FILE,mins); save_json(CAT_FILE,cats)
            reply=d.get("reply","Done.")

        except: reply="Try again using commands from the guide."

    return render_template_string(HTML,reply=reply,inventory=inv,min_levels=mins,categories=cats)

if __name__=="__main__":
    app.run(port=5000)
