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

# ============ HELPER FUNCTIONS ============
def run_async(coro):
    """Run async function in a new event loop"""
    loop = asyncio.new_event_loop()
    asyncio.set_event_loop(loop)
    try:
        return loop.run_until_complete(coro)
    finally:
        loop.close()

def generate_tts_sync(text, voice, rate, file_path):
    """Generate TTS - synchronous wrapper with logging"""
    try:
        print(f"🔵 TTS: voice={voice}, text={text[:30]}, rate={rate}")
        
        async def _generate():
            if voice.startswith('km-'):
                communicate = edge_tts.Communicate(text=text, voice=voice)
            else:
                # Format rate for Chinese
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
        
        run_async(_generate())
        
        if os.path.exists(file_path) and os.path.getsize(file_path) > 1000:
            print(f"✅ TTS Success: {os.path.getsize(file_path)} bytes")
            return True
        return False
    except Exception as e:
        print(f"❌ TTS Error: {e}")
        traceback.print_exc()
        return False

# ============ ROUTES ============
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
        success = generate_tts_sync(text, voice, rate, file_path)
        
        if not success:
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
        return jsonify({"error": str(e)}), 500

@app.route("/test-simple")
def test_simple():
    """Simple test endpoint - Hello World"""
    text = "Hello world. This is a test of the text to speech system."
    voice = "en-US-JennyNeural"
    
    temp_dir = tempfile.gettempdir()
    filename = f"tts_{uuid.uuid4().hex}.mp3"
    file_path = os.path.join(temp_dir, filename)
    
    success = generate_tts_sync(text, voice, "0%", file_path)
    
    if not success:
        return jsonify({"error": "TTS failed"}), 500
    
    response = send_file(file_path, mimetype="audio/mpeg")
    
    @response.call_on_close
    def cleanup():
        try:
            if os.path.exists(file_path):
                os.unlink(file_path)
        except:
            pass
    
    return response

@app.route("/test-tts-debug")
def test_tts_debug():
    """Ultra-simple TTS test"""
    result = {"steps": [], "success": False}
    
    try:
        result["steps"].append("Starting test")
        
        # Create temp file
        fd, path = tempfile.mkstemp(suffix='.mp3')
        os.close(fd)
        result["steps"].append(f"Temp file: {path}")
        
        # Simple test with English
        text = "test"
        voice = "en-US-JennyNeural"
        
        async def simple_tts():
            result["steps"].append("Creating communicate object")
            comm = edge_tts.Communicate(text=text, voice=voice)
            result["steps"].append("Calling save()")
            await comm.save(path)
            result["steps"].append("Save() completed")
        
        run_async(simple_tts())
        
        if os.path.exists(path):
            size = os.path.getsize(path)
            result["steps"].append(f"File created! Size: {size}")
            result["success"] = True
        else:
            result["steps"].append("File not created")
            
        # Cleanup
        try:
            os.unlink(path)
        except:
            pass
            
        return jsonify(result)
        
    except Exception as e:
        result["error"] = str(e)
        result["steps"].append(f"Exception: {e}")
        return jsonify(result), 500

@app.route("/test")
def test():
    return jsonify({"status": "healthy", "message": "Server running"})

@app.route("/debug-tts")
def debug_tts():
    """Debug endpoint to test edge-tts connectivity"""
    try:
        voices = run_async(edge_tts.list_voices())
        khmer_voices = [v['ShortName'] for v in voices if v['ShortName'].startswith('km-')]
        return jsonify({
            "status": "success",
            "voices_found": len(voices),
            "khmer_voices": khmer_voices
        })
    except Exception as e:
        return jsonify({"status": "error", "message": str(e)}), 500

if __name__ == "__main__":
    port = int(os.environ.get("PORT", 5000))
    print(f"🚀 Server starting on port {port}")
    app.run(debug=False, host='0.0.0.0', port=port)