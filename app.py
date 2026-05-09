from flask import Flask, request, send_file, jsonify
from flask_cors import CORS
import edge_tts
import os
import tempfile
import uuid
import asyncio
import traceback

app = Flask(__name__)
CORS(app)

# Create a persistent event loop for the entire application
loop = asyncio.new_event_loop()
asyncio.set_event_loop(loop)

async def generate_tts(text, voice, rate, file_path):
    """Generate TTS audio file"""
    try:
        print(f"🎤 Starting TTS: voice={voice}, rate={rate}, text={text[:50]}")
        
        # Remove rate parameter for Khmer voices
        if voice.startswith('km-'):
            communicate = edge_tts.Communicate(text=text, voice=voice)
        else:
            # Format rate properly for Chinese
            if rate and rate != "0%":
                if rate == "-20":
                    rate = "-20%"
                elif rate == "20":
                    rate = "+20%"
                elif rate == "-50":
                    rate = "-50%"
                elif rate == "50":
                    rate = "+50%"
            communicate = edge_tts.Communicate(text=text, voice=voice, rate=rate)
        
        await communicate.save(file_path)
        
        # Verify file
        if os.path.exists(file_path) and os.path.getsize(file_path) > 1000:
            print(f"✅ TTS Success! Size: {os.path.getsize(file_path)} bytes")
            return True
        return False
        
    except Exception as e:
        print(f"❌ TTS Error: {type(e).__name__}: {str(e)}")
        traceback.print_exc()
        
        # Fallback without rate
        try:
            communicate = edge_tts.Communicate(text=text, voice=voice)
            await communicate.save(file_path)
            return True
        except:
            return False

def run_async(coro):
    """Run async coroutine in the persistent event loop"""
    future = asyncio.run_coroutine_threadsafe(coro, loop)
    return future.result(timeout=60)

@app.route("/")
def home():
    try:
        with open("index.html", encoding="utf-8") as f:
            return f.read()
    except FileNotFoundError:
        return "index.html not found", 404

@app.route("/speak", methods=["POST", "GET"])
def speak():
    if request.method == "POST":
        text = request.form.get("text", "")
        voice = request.form.get("voice", "zh-CN-XiaoxiaoNeural")
        rate = request.form.get("rate", "0%")
    else:
        text = request.args.get("text", "")
        voice = request.args.get("voice", "zh-CN-XiaoxiaoNeural")
        rate = request.args.get("rate", "0%")
    
    if not text:
        return jsonify({"error": "No text provided"}), 400
    
    temp_dir = tempfile.gettempdir()
    filename = f"tts_{uuid.uuid4().hex}.mp3"
    file_path = os.path.join(temp_dir, filename)
    
    try:
        success = run_async(generate_tts(text, voice, rate, file_path))
        
        if not success or not os.path.exists(file_path):
            return jsonify({"error": "TTS generation failed"}), 500
        
        response = send_file(file_path, mimetype="audio/mpeg")
        
        @response.call_on_close
        def cleanup():
            try:
                if os.path.exists(file_path):
                    os.unlink(file_path)
            except:
                pass
        
        return response
        
    except Exception as e:
        print(f"Server error: {e}")
        traceback.print_exc()
        return jsonify({"error": str(e)}), 500

@app.route("/debug-tts", methods=["GET"])
def debug_tts():
    """Debug endpoint to test edge-tts connectivity"""
    result = {"status": "testing", "voices_found": 0, "khmer_voices": [], "error": None}
    
    try:
        voices = run_async(edge_tts.list_voices())
        result["voices_found"] = len(voices)
        
        khmer_voices = []
        for v in voices:
            if v.get('ShortName', '').startswith('km-'):
                khmer_voices.append(v.get('ShortName'))
        result["khmer_voices"] = khmer_voices
        result["status"] = "success"
    except Exception as e:
        result["error"] = str(e)
        result["status"] = "failed"
    
    return jsonify(result)

@app.route("/test-simple", methods=["GET"])
def test_simple():
    """Test with hardcoded English text"""
    text = "Hello world"
    voice = "en-US-JennyNeural"
    rate = "0%"
    
    temp_dir = tempfile.gettempdir()
    filename = f"tts_{uuid.uuid4().hex}.mp3"
    file_path = os.path.join(temp_dir, filename)
    
    try:
        success = run_async(generate_tts(text, voice, rate, file_path))
        
        if not success:
            return jsonify({"error": "TTS failed", "text": text}), 500
        
        response = send_file(file_path, mimetype="audio/mpeg")
        
        @response.call_on_close
        def cleanup():
            try:
                if os.path.exists(file_path):
                    os.unlink(file_path)
            except:
                pass
        
        return response
    except Exception as e:
        return jsonify({"error": str(e)}), 500

@app.route("/test", methods=["GET"])
def test():
    return jsonify({
        "status": "healthy",
        "message": "TTS API is working!",
        "endpoints": ["/", "/speak", "/test", "/health", "/debug-tts", "/test-simple"]
    })

@app.route("/health", methods=["GET"])
def health():
    return jsonify({"status": "healthy"}), 200

if __name__ == "__main__":
    port = int(os.environ.get("PORT", 5000))
    print(f"🚀 Server starting on port {port}")
    app.run(debug=False, host='0.0.0.0', port=port)