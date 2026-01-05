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
<title>📦 Inventory Assistant</title>
<h2>📦 Mr AI Inventory Assistant</h2>
<form method="post">
  <input name="msg" placeholder="Type naturally..." style="width:80%" autofocus>
  <input type="submit" value="Send">
</form>
<p><b>Stocky:</b> {{ reply }}</p>
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

        # 🔥 FINAL WIPE CONFIRMATION
        if user_msg.strip().upper() == "YES DELETE" and session.get("wipe_pending"):
            inv = {}
            save_inventory(inv)
            session.pop("wipe_pending")
            reply = "🗑️ All inventory has been permanently deleted."
            return render_template_string(HTML, reply=reply)

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
                reply = f"Current inventory: {inv}"

            elif data.get("action") == "low":
                low = {k:v for k,v in inv.items() if v <= 5}
                reply = f"Low stock items: {low}"

            else:
                reply = data.get("reply","Sorry, I didn’t understand.")

            save_inventory(inv)

        except:
            reply = "Sorry, I didn’t understand that. Try: 'Delete everything in my inventory'."

    return render_template_string(HTML, reply=reply)

if __name__ == "__main__":
    app.run(port=5000)
