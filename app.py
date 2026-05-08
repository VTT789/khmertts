from flask import Flask, request, send_file
import asyncio
import edge_tts
import os

app = Flask(__name__)

async def tts(text, path):
    communicate = edge_tts.Communicate(text, "km-KH-SreymomNeural")
    await communicate.save(path)

@app.route("/")
def home():
    return open("index.html", encoding="utf-8").read()

@app.route("/speak", methods=["POST"])
def speak():
    text = request.form["text"]

    file = "output.mp3"

    asyncio.run(tts(text, file))

    return send_file(file, mimetype="audio/mpeg")

if __name__ == "__main__":
    app.run(debug=True)