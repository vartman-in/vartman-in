import os
from dotenv import load_dotenv
from flask import Flask, request, jsonify
import requests
from openai import OpenAI

# Load the secrets from your .env file into the environment
load_dotenv()

app = Flask(__name__)

# Load OpenAI client (will automatically pick up OPENAI_API_KEY from environment)
client = OpenAI(api_key=os.environ.get("OPENAI_API_KEY"))

# Load Green API settings from environment variables
GREEN_API_HOST = os.environ.get("GREEN_API_HOST", "https://api.green-api.com")
INSTANCE_ID = os.environ.get("INSTANCE_ID")
INSTANCE_TOKEN = os.environ.get("INSTANCE_TOKEN")

# In-memory memory storage for conversations (resets on server restart)
chat_memory = {}

SYSTEM_PROMPT = (
    "You are an expert PC and laptop sales assistant for a tech retail store. "
    "Your goal is to help customers find the ideal laptop or PC for their budget and needs, then guide them to buy. "
    "Keep responses helpful, brief, friendly, and formatted using bullet points for easy scanning on WhatsApp. "
    "If a customer asks about gaming, ask what titles they play. If they ask about work, ask what software they use. "
    "When they are ready to order, inform them that a human team member will contact them shortly to complete the payment and shipping."
)

def get_ai_response(sender_id, user_message):
    # Initialize history if this is a new customer
    if sender_id not in chat_memory:
        chat_memory[sender_id] = [
            {"role": "system", "content": SYSTEM_PROMPT}
        ]
    
    # Append the user's latest message to their chat history
    chat_memory[sender_id].append({"role": "user", "content": user_message})

    # Call OpenAI API to generate a response
    response = client.chat.completions.create(
        model="gpt-4o-mini",
        messages=chat_memory[sender_id]
    )
    
    ai_reply = response.choices[0].message.content
    
    # Store AI response in chat history so it remembers the context
    chat_memory[sender_id].append({"role": "assistant", "content": ai_reply})
    
    return ai_reply

def send_whatsapp_message(chat_id, text):
    url = f"{GREEN_API_HOST}/waInstance{INSTANCE_ID}/sendMessage/{INSTANCE_TOKEN}"
    payload = {
        "chatId": chat_id,
        "message": text
    }
    headers = {"Content-Type": "application/json"}
    try:
        requests.post(url, json=payload, headers=headers, timeout=10)
    except Exception as e:
        print(f"Error sending message via Green API: {e}")

@app.route("/", methods=["GET"])
def health_check():
    # Render hits this route to verify your web service is alive and hasn't crashed
    return "WhatsApp PC Sales Bot is live!", 200

@app.route("/webhook", methods=["POST"])
def webhook():
    data = request.json or {}
    
    # Process incoming text messages only
    if "messageData" in data and data["messageData"].get("typeMessage") == "textMessage":
        sender_data = data.get("senderData", {})
        sender_id = sender_data.get("sender")
        user_message = data["messageData"]["textMessageData"].get("textMessage")
        
        # Ensure it's a valid message and not a message sent by the bot itself
        if sender_id and user_message and not sender_data.get("isSelf", False):
            ai_reply = get_ai_response(sender_id, user_message)
            send_whatsapp_message(sender_id, ai_reply)
        
    return jsonify({"status": "success"}), 200

if __name__ == "__main__":
    # Web hosts like Render provide a PORT environment variable dynamically
    port = int(os.environ.get("PORT", 5000))
    app.run(host="0.0.0.0", port=port)