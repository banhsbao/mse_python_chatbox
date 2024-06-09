from flask import Flask, render_template, request, jsonify
import requests
import json
import os
from langchain_google_genai import ChatGoogleGenerativeAI
from langchain_core.messages import HumanMessage
import helper

VERIFY_TOKEN = os.environ.get("VERIFY_TOKEN")
PAGE_ACCESS_TOKEN = os.environ.get("PAGE_ACCESS_TOKEN")
GOOGLE_API_KEY = os.environ.get("GOOGLE_API_KEY")
VERCEL_KV_URL = os.environ.get("VERCEL_KV_URL")
VERCEL_KV_TOKEN = os.environ.get("VERCEL_KV_TOKEN")

app = Flask(__name__)

llm = ChatGoogleGenerativeAI(model="gemini-pro", convert_system_message_to_human=True)

retriever = helper.createRetriever()
docs = retriever.invoke("Học phí thạc sĩ FSB FPT là bao nhiêu?")
# docs = helper.load_data_from_web()

document_chain = helper.document_chains(llm=llm)


@app.route("/")
def hello():
    return "Hello, world"


@app.route("/webhook", methods=["GET", "POST"])
def get_method():
    print("request: ", request)
    if request.method == "GET":
        return handle_get(request)
    elif request.method == "POST":
        return handle_post(request)
    else:
        return jsonify({"status": 405, "body": "Method Not Allowed"}), 405


def handle_get(request):
    query_params = request.args
    if query_params and query_params.get("hub.verify_token") == VERIFY_TOKEN:
        return query_params["hub.challenge"], 200
    else:
        return jsonify({"status": 403, "body": "Forbidden"}), 403


def handle_post(request):
    try:
        body = request.get_json()
        print("handle Message: ", body)
        for entry in body.get("entry", []):
            for messaging_event in entry.get("messaging", []):
                if "message" in messaging_event:
                    sender_id = messaging_event["sender"]["id"]
                    message_text = messaging_event["message"].get("text")
                    if message_text:
                        # send_typing_indicator(sender_id, "typing_on")
                        response_text = generate_response(message_text)
                        return jsonify({"status": 200, "body": response_text}), 200
                        # store_chat_history(
                        #     sender_id, {"user": message_text, "bot": response_text}
                        # )
                        # send_message(sender_id, response_text)
                        # send_typing_indicator(sender_id, "typing_off")
        return jsonify({"status": 200, "body": "EVENT_RECEIVED"}), 200
    except Exception as e:
        return jsonify({"status": 500, "body": str(e)}), 500


def generate_response(message_text):

    res = document_chain.invoke(
        {
            "context": docs,
            "messages": [
                HumanMessage(
                    content=[
                        {
                            "type": "text",
                            "text": message_text,
                        }
                    ]
                )
            ],
        }
    )
    print("response: ", res)
    return res



def store_chat_history(user_id, message):
    url = f"{VERCEL_KV_URL}/keys/{user_id}"
    headers = {
        "Authorization": f"Bearer {VERCEL_KV_TOKEN}",
        "Content-Type": "application/json",
    }
    current_history = get_chat_history(user_id) or []
    current_history.append(message)
    data = {"value": json.dumps(current_history)}
    response = requests.put(url, headers=headers, data=json.dumps(data))
    if response.status_code not in [200, 204]:
        print("Failed to store chat history:", response.status_code, response.text)


def get_chat_history(user_id):
    url = f"{VERCEL_KV_URL}/keys/{user_id}"
    headers = {"Authorization": f"Bearer {VERCEL_KV_TOKEN}"}
    response = requests.get(url, headers=headers)
    if response.status_code == 200:
        return json.loads(response.json().get("value", "[]"))
    elif response.status_code == 404:
        return []
    else:
        print("Failed to get chat history:", response.status_code, response.text)
        return []


def send_typing_indicator(recipient_id, action):
    params = {"access_token": PAGE_ACCESS_TOKEN}
    headers = {"Content-Type": "application/json"}
    data = json.dumps({"recipient": {"id": recipient_id}, "sender_action": action})
    response = requests.post(
        "https://graph.facebook.com/v12.0/me/messages",
        params=params,
        headers=headers,
        data=data,
    )
    if response.status_code != 200:
        print("Failed to send typing indicator:", response.status_code, response.text)


def send_message(recipient_id, message_text):
    params = {"access_token": PAGE_ACCESS_TOKEN}
    headers = {"Content-Type": "application/json"}
    data = json.dumps(
        {"recipient": {"id": recipient_id}, "message": {"text": message_text}}
    )
    response = requests.post(
        "https://graph.facebook.com/v12.0/me/messages",
        params=params,
        headers=headers,
        data=data,
    )
    if response.status_code != 200:
        print("Failed to send message:", response.status_code, response.text)
    return response.json()


@app.route("/test")
def test():
    return "Test"


@app.route("/result")
def result():
    dict = {"phy": 50, "che": 60, "maths": 70}
    return render_template("result.html", result=dict)


if __name__ == "__main__":
    app.run(port=8000, debug=True)
