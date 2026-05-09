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

async def generate_tts(text, voice, rate, file_path):
    """Generate TTS audio file with detailed logging"""
    print(f"=" * 50)
    print(f"🎤 Starting TTS Generation")
    print(f"   Text: '{text}'")
    print(f"   Text length: {len(text)} chars")
    print(f"   Voice: {voice}")
    print(f"   Rate: {rate}")
    print(f"   File path: {file_path}")
    
    try:
        # Create communicate object based on voice type
        if voice.startswith('km-'):
            print(f"   Using Khmer voice (no rate parameter)")
            communicate = edge_tts.Communicate(text=text, voice=voice)
        else:
            print(f"   Using Chinese voice with rate parameter")
            # Format rate properly
            formatted_rate = rate
            if rate and rate != "0%":
                if rate == "-20":
                    formatted_rate = "-20%"
                elif rate == "20":
                    formatted_rate = "+20%"
                elif rate == "-50":
                    formatted_rate = "-50%"
                elif rate == "50":
                    formatted_rate = "+50%"
            print(f"   Formatted rate: {formatted_rate}")
            communicate = edge_tts.Communicate(text=text, voice=voice, rate=formatted_rate)
        
        print(f"   ✅ Communicate object created, calling save()...")
        
        # Save with timeout
        await asyncio.wait_for(communicate.save(file_path), timeout=30.0)
        
        print(f"   ✅ save() completed successfully")
        
        # Verify file
        if os.path.exists(file_path):
            file_size = os.path.getsize(file_path)
            print(f"   File created! Size: {file_size} bytes")
            
            if file_size > 1000:
                print(f"   ✅ File size OK (>1KB)")
                return True
            else:
                print(f"   ❌ File too small: {file_size} bytes")
                return False
        else:
            print(f"   ❌ File was not created at {file_path}")
            return False
            
    except asyncio.TimeoutError:
        print(f"   ❌ TIMEOUT: TTS took longer than 30 seconds")
        return False
    except Exception as e:
        print(f"   ❌ EXCEPTION: {type(e).__name__}: {str(e)}")
        traceback.print_exc()
        
        # Try fallback without rate for Chinese voices
        if not voice.startswith('km-'):
            print(f"   🔄 Trying fallback without rate parameter...")
            try:
                communicate = edge_tts.Communicate(text=text, voice=voice)
                await asyncio.wait_for(communicate.save(file_path), timeout=30.0)
                print(f"   ✅ Fallback successful!")
                return True
            except Exception as e2:
                print(f"   ❌ Fallback also failed: {e2}")
                return False
        return False

def run_async(coro):
    """Run async function safely"""
    try:
        # Try to get existing event loop
        loop = asyncio.get_event_loop()
        if loop.is_closed():
            raise RuntimeError
        return loop.run_until_complete(coro)
    except RuntimeError:
        # Create new event loop if needed
        loop = asyncio.new_event_loop()
        asyncio.set_event_loop(loop)
        return loop.run_until_complete(coro)

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
    
    print(f"📨 Request: text='{text[:50]}', voice='{voice}', rate='{rate}'")
    
    if not text:
        return jsonify({"error": "No text provided"}), 400
    
    # Create temporary file
    temp_dir = tempfile.gettempdir()
    filename = f"tts_{uuid.uuid4().hex}.mp3"
    file_path = os.path.join(temp_dir, filename)
    
    try:
        # Generate TTS
        success = run_async(generate_tts(text, voice, rate, file_path))
        
        if not success or not os.path.exists(file_path):
            print(f"❌ TTS generation failed for: {text}")
            return jsonify({"error": "TTS generation failed"}), 500
        
        # Send the audio file
        response = send_file(
            file_path, 
            mimetype="audio/mpeg",
            as_attachment=False
        )
        
        # Clean up temp file after sending
        @response.call_on_close
        def cleanup():
            try:
                if os.path.exists(file_path):
                    os.unlink(file_path)
                    print(f"🧹 Cleaned up: {file_path}")
            except Exception as e:
                print(f"Cleanup error: {e}")
        
        return response
        
    except Exception as e:
        print(f"❌ Server error: {e}")
        traceback.print_exc()
        return jsonify({"error": str(e)}), 500

@app.route("/debug-tts", methods=["GET"])
def debug_tts():
    """Debug endpoint to test edge-tts connectivity"""
    result = {"status": "testing", "voices_found": 0, "khmer_voices": [], "error": None}
    
    try:
        loop = asyncio.new_event_loop()
        asyncio.set_event_loop(loop)
        voices = loop.run_until_complete(edge_tts.list_voices())
        result["voices_found"] = len(voices)
        
        # Look for Khmer voices
        khmer_voices = []
        for v in voices:
            if 'Khmer' in v.get('Locale', '') or v.get('ShortName', '').startswith('km-'):
                khmer_voices.append(v.get('ShortName', 'unknown'))
        result["khmer_voices"] = khmer_voices
        result["status"] = "success"
    except Exception as e:
        result["error"] = f"Voice list failed: {str(e)}"
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

@app.route("/test", methods=["GET"])
def test():
    """Simple test endpoint"""
    return jsonify({
        "status": "healthy",
        "message": "TTS API is working!",
        "endpoints": ["/", "/speak", "/test", "/health", "/debug-tts", "/test-simple"]
    })

@app.route("/health", methods=["GET"])
def health():
    return jsonify({"status": "healthy", "service": "Edge TTS Studio"}), 200

if __name__ == "__main__":
    port = int(os.environ.get("PORT", 5000))
    print(f"🚀 Server starting on port {port}")
    print(f"📍 URL: http://0.0.0.0:{port}")
    print(f"🔧 Debug endpoint: /debug-tts")
    app.run(debug=False, host='0.0.0.0', port=port)