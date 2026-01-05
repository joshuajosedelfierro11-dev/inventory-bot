from flask import Flask, request, render_template_string, session
from openai import OpenAI
import os, json

client = OpenAI(api_key=os.getenv("OPENAI_INVENTORY_KEY"))

app = Flask(__name__)
app.secret_key = "inventory_secret"

FILE = "inventory.json"

SYSTEM_PROMPT = """
You are Stocky, a polite inventory assistant.

If user wants to delete all inventory, return:
{"action":"wipe","reply":"Are you sure you want to delete ALL inventory? Type YES DELETE to confirm."}

Otherwise return JSON in this format only:
{
  "action": "add" | "sell" | "show" | "low" | null,
  "item": "string" | null,
  "qty": number | null,
  "reply": "string"
}
"""

HTML = """
<!doctype html>
<html>
<head>
<meta name="viewport" content="width=device-width, initial-scale=1.0">
<title>Mr AI Inventory Dashboard</title>
<style>
body {font-family:-apple-system,BlinkMacSystemFont,sans-serif;background:#f3f4f6;margin:0}
.header {background:#111827;color:white;padding:15px 20px;font-size:20px}
.container {padding:20px}
.card {background:white;border-radius:10px;padding:15px;margin-bottom:15px;box-shadow:0 4px 8px rgba(0,0,0,0.05)}
input {width:100%;padding:12px;border-radius:8px;border:1px solid #d1d5db;margin-bottom:10px;font-size:16px}
button {background:#2563eb;color:white;border:none;padding:12px;width:100%;border-radius:8px;font-size:16px}
.reply {margin-top:10px;color:#111827;font-weight:500}
table {width:100%;border-collapse:collapse;margin-top:10px}
th,td {padding:8px;text-align:left;border-bottom:1px solid #e5e7eb}
.low {color:#b91c1c;font-weight:bold}
.footer {text-align:center;color:#9ca3af;font-size:12px}
</style>
</head>
<body>

<div class="header">📦 Mr AI Inventory Dashboard</div>

<div class="container">

  <div class="card">
    <b>Inventory Command</b>
    <form method="post">
      <input name="msg" placeholder="e.g. We received 10 milk tea today">
      <button type="submit">Update Inventory</button>
    </form>
    <div class="reply">{{ reply }}</div>
  </div>

  <div class="card">
    <b>Current Inventory</b>
    <table>
      <tr><th>Item</th><th>Stock</th></tr>
      {% for item, qty in inventory.items() %}
        <tr>
          <td>{{ item }}</td>
          <td class="{% if qty <= 5 %}low{% endif %}">{{ qty }}</td>
        </tr>
      {% endfor %}
    </table>
  </div>

</div>

<div class="footer">Powered by Mr AI Systems</div>

</body>
</html>
"""

def load_inventory():
    if not os.path.exists(FILE):
        return {}
    try:
        with open(FILE) as f:
            return json.load(f)
    except:
        return {}

def save_inventory(data):
    with open(FILE,"w") as f:
        json.dump(data, f, indent=2)

@app.route("/", methods=["GET","POST"])
def chat():
    inv = load_inventory()
    reply = ""

    if request.method == "POST":
        user_msg = request.form["msg"]

        if user_msg.strip().upper() == "YES DELETE" and session.get("wipe_pending"):
            inv = {}
            save_inventory(inv)
            session.pop("wipe_pending")
            reply = "🗑️ All inventory has been permanently deleted."
            return render_template_string(HTML, reply=reply, inventory=inv)

        context = f"""
Inventory: {inv}
User said: {user_msg}
"""

        ai = client.responses.create(
            model="gpt-4.1-mini",
            input=[
                {"role":"system","content":SYSTEM_PROMPT},
                {"role":"user","content":context}
            ]
        ).output_text

        try:
            data = json.loads(ai)

            if data.get("action") == "wipe":
                session["wipe_pending"] = True
                reply = data["reply"]

            elif data.get("action") == "add":
                inv[data["item"]] = inv.get(data["item"],0) + int(data["qty"])
                reply = f"Added {data['qty']} {data['item']} to stock."

            elif data.get("action") == "sell":
                inv[data["item"]] = inv.get(data["item"],0) - int(data["qty"])
                reply = f"Sold {data['qty']} {data['item']}. Stock updated."

            elif data.get("action") == "show":
                reply = f"Here’s your inventory."

            elif data.get("action") == "low":
                low = {k:v for k,v in inv.items() if v <= 5}
                reply = f"Low stock items: {low}"

            else:
                reply = data.get("reply","Sorry, I didn’t understand.")

            save_inventory(inv)

        except:
            reply = "Sorry, I didn’t understand that. Try: 'We received 10 coke today'."

    return render_template_string(HTML, reply=reply, inventory=inv)

if __name__ == "__main__":
    app.run(port=5000)
