from flask import Flask, request, send_file, jsonify
from flask_cors import CORS
import asyncio
import edge_tts
import os
import tempfile
import uuid
import traceback

app = Flask(__name__)
CORS(app)  # Enable CORS for all routes

async def tts(text, voice, rate, path):
    """Generate TTS audio with optional rate adjustment"""
    try:
        print(f"🎤 Generating TTS: voice={voice}, rate={rate}, text={text[:50]}...")
        
        # For Khmer voices, don't use rate parameter
        if voice.startswith('km-'):
            communicate = edge_tts.Communicate(text=text, voice=voice)
        else:
            # For Chinese voices, use rate
            if not rate.endswith('%'):
                rate = f"{rate}%"
            if rate != "0%" and not rate.startswith('+') and not rate.startswith('-'):
                val = int(rate.replace('%', ''))
                if val > 0:
                    rate = f"+{rate}"
            
            print(f"📊 Using rate: {rate}")
            communicate = edge_tts.Communicate(text=text, voice=voice, rate=rate)
        
        await communicate.save(path)
        print(f"✅ TTS saved to {path}")
        
        # Verify file was created
        if os.path.exists(path) and os.path.getsize(path) > 0:
            print(f"📁 File size: {os.path.getsize(path)} bytes")
            return True
        else:
            print(f"❌ File is empty or doesn't exist")
            return False
            
    except Exception as e:
        print(f"❌ TTS Error: {e}")
        traceback.print_exc()
        # Fallback without rate
        try:
            print("🔄 Trying fallback without rate...")
            communicate = edge_tts.Communicate(text=text, voice=voice)
            await communicate.save(path)
            print(f"✅ Fallback TTS saved to {path}")
            return True
        except Exception as e2:
            print(f"❌ Fallback also failed: {e2}")
            traceback.print_exc()
            return False

@app.route("/")
def home():
    try:
        with open("index.html", encoding="utf-8") as f:
            return f.read()
    except FileNotFoundError:
        return "index.html not found", 404

@app.route("/speak", methods=["POST", "GET"])
def speak():
    # Handle both POST and GET for testing
    if request.method == "GET":
        text = request.args.get("text", "")
        voice = request.args.get("voice", "zh-CN-XiaoxiaoNeural")
        rate = request.args.get("rate", "0%")
    else:
        text = request.form.get("text", "")
        voice = request.form.get("voice", "zh-CN-XiaoxiaoNeural")
        rate = request.form.get("rate", "0%")
    
    print(f"📨 Request received: text={text[:50]}..., voice={voice}, rate={rate}")
    
    if not text:
        return jsonify({"error": "No text provided"}), 400
    
    # Create temp file
    temp_dir = tempfile.gettempdir()
    filename = f"tts_{uuid.uuid4().hex}.mp3"
    file_path = os.path.join(temp_dir, filename)
    
    try:
        # Run TTS
        success = asyncio.run(tts(text, voice, rate, file_path))
        
        if not success or not os.path.exists(file_path) or os.path.getsize(file_path) == 0:
            return jsonify({"error": "TTS generation failed"}), 500
        
        # Send file
        response = send_file(
            file_path, 
            mimetype="audio/mpeg",
            as_attachment=False,
            download_name="speech.mp3"
        )
        
        # Cleanup after sending
        @response.call_on_close
        def cleanup():
            try:
                if os.path.exists(file_path):
                    os.unlink(file_path)
                    print(f"🧹 Cleaned up {file_path}")
            except Exception as e:
                print(f"Cleanup error: {e}")
        
        return response
        
    except Exception as e:
        print(f"❌ Error in /speak: {e}")
        traceback.print_exc()
        return jsonify({"error": str(e)}), 500

@app.route("/test")
def test():
    """Test endpoint to verify the API is working"""
    return jsonify({
        "status": "healthy",
        "message": "TTS API is working",
        "endpoints": ["/", "/speak", "/test", "/health"]
    })

@app.route("/health")
def health():
    return jsonify({"status": "healthy", "service": "Edge TTS Studio"}), 200

if __name__ == "__main__":
    port = int(os.environ.get("PORT", 5000))
    print(f"🚀 Starting server on port {port}")
    app.run(debug=False, host='0.0.0.0', port=port)