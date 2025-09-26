"""
Single-file Flask app: InstaMuse
Features:
- Upload an image and select options (caption length, tone, genres, region)
- Preview image client-side
- Generate captions + song suggestions (uses a placeholder function to call Gemini API)
- Beautiful, responsive UI using inline CSS + vanilla JS

How to run:
1. Save this file as app.py
2. Create a virtualenv: python -m venv venv && source venv/bin/activate (or venv\Scripts\activate on Windows)
3. pip install flask pillow python-dotenv requests
4. Create a .env file with GEMINI_API_KEY=your_key (optional; the app will run with mocked outputs if missing)
5. flask run --host=0.0.0.0 --port=5000

Notes about Gemini integration:
- There's a function `call_gemini(prompt, image_bytes)` below. I intentionally left it as a clear integration point. Implement the actual HTTP request to Google Gemini or your preferred model there using your pro key.
- If GEMINI_API_KEY is present, the app will attempt a "fake" call here for safety. Replace with your real HTTP client code.

This design keeps everything in one file so you can experiment quickly. If you want, I can split into templates/static files next.
"""

from flask import Flask, request, render_template_string, jsonify
from werkzeug.utils import secure_filename
from io import BytesIO
from PIL import Image
import os
import base64
from dotenv import load_dotenv
import secrets
import google.generativeai as genai
import json

load_dotenv()
GEMINI_API_KEY = os.getenv('GEMINI_API_KEY')

# Configure Gemini API
if GEMINI_API_KEY:
    genai.configure(api_key=GEMINI_API_KEY)

app = Flask(__name__)
app.config['MAX_CONTENT_LENGTH'] = 8 * 1024 * 1024  # 8 MB
app.config['UPLOAD_EXTENSIONS'] = ['.jpg', '.jpeg', '.png']

# -----------------
# Helper functions
# -----------------

def image_to_data_url(image_bytes):
    b64 = base64.b64encode(image_bytes).decode('utf-8')
    return f"data:image/jpeg;base64,{b64}"


def call_gemini(prompt, image_bytes=None, max_outputs=3):
    """
    Real implementation for calling Gemini API with image and text.
    - prompt: string with instructions
    - image_bytes: bytes of the uploaded image
    - max_outputs: number of outputs to generate
    """
    if not GEMINI_API_KEY:
        # Fallback to mock data if no API key
        return get_mock_response(prompt, max_outputs)
    
    try:
        # Use Gemini Pro Vision model for image + text
        model = genai.GenerativeModel('gemini-2.0-flash')
        
        # Convert image bytes to PIL Image for Gemini
        image = Image.open(BytesIO(image_bytes))
        
        # Parse the prompt to extract specific parameters
        region = "any"
        mood = "chill"
        tone = "aesthetic"
        length = "medium"
        
        # Extract parameters from prompt
        if "Song region: " in prompt:
            region = prompt.split("Song region: ")[1].split(".")[0].strip()
        if "Song mood: " in prompt:
            mood = prompt.split("Song mood: ")[1].split(".")[0].strip()
        if "Tone: " in prompt:
            tone = prompt.split("Tone: ")[1].split(".")[0].strip()
        if "Caption length: " in prompt:
            length = prompt.split("Caption length: ")[1].split(".")[0].strip()

        # Enhanced prompt for better results with stronger region emphasis
        enhanced_prompt = f"""
        Analyze this image and generate {max_outputs} Instagram captions and {max_outputs} song suggestions.

        IMPORTANT REQUIREMENTS:
        1. For SONGS: The region "{region}" is MANDATORY. Only suggest songs from this region:
           - If bollywood: Only Hindi/Bollywood songs (artists like Arijit Singh, Shreya Ghoshal, A.R. Rahman, etc.)
           - If hollywood: Only English/Western songs
           - If tollywood: Only Telugu songs
           - If kpop: Only Korean pop songs
           - If any: Mix of popular songs from different regions

        2. Song mood should be: {mood}
        3. Caption tone should be: {tone}
        4. Caption length should be: {length}

        Please respond in this EXACT JSON format:
        {{
            "captions": ["caption 1", "caption 2", "caption 3"],
            "songs": [
                {{"title": "Song Title", "artist": "Artist Name"}},
                {{"title": "Song Title", "artist": "Artist Name"}},
                {{"title": "Song Title", "artist": "Artist Name"}}
            ]
        }}

        Guidelines:
        - Analyze the image mood, colors, and setting
        - STRICTLY follow the region requirement for songs
        - Make captions engaging and Instagram-ready
        - Ensure songs are real and match the specified region
        - Match the mood and vibe of the image
        """
        
        # Generate content with image and text
        response = model.generate_content([enhanced_prompt, image])
        
        # Parse the response
        response_text = response.text.strip()
        
        # Try to extract JSON from the response
        try:
            # Look for JSON in the response
            start_idx = response_text.find('{')
            end_idx = response_text.rfind('}') + 1
            
            if start_idx != -1 and end_idx != 0:
                json_str = response_text[start_idx:end_idx]
                result = json.loads(json_str)
                
                # Validate the structure
                if 'captions' in result and 'songs' in result:
                    # Ensure we have the right number of items
                    captions = result['captions'][:max_outputs]
                    songs = result['songs'][:max_outputs]
                    
                    # Ensure songs have proper structure
                    formatted_songs = []
                    for song in songs:
                        if isinstance(song, dict) and 'title' in song and 'artist' in song:
                            formatted_songs.append(song)
                        elif isinstance(song, str):
                            # If it's just a string, try to parse it
                            parts = song.split(' - ')
                            if len(parts) >= 2:
                                formatted_songs.append({"title": parts[0].strip(), "artist": parts[1].strip()})
                            else:
                                formatted_songs.append({"title": song.strip(), "artist": "Unknown Artist"})
                    
                    return {
                        'captions': captions,
                        'songs': formatted_songs
                    }
        except json.JSONDecodeError:
            pass
        
        # If JSON parsing fails, try to extract content manually
        return parse_gemini_response(response_text, max_outputs)
        
    except Exception as e:
        print(f"Gemini API error: {e}")
        # Fallback to mock data on error
        return get_mock_response(prompt, max_outputs)


def parse_gemini_response(response_text, max_outputs):
    """Parse Gemini response when JSON format is not followed"""
    captions = []
    songs = []
    
    lines = response_text.split('\n')
    current_section = None
    
    for line in lines:
        line = line.strip()
        if not line:
            continue
            
        if 'caption' in line.lower() and len(captions) == 0:
            current_section = 'captions'
            continue
        elif 'song' in line.lower() and len(songs) == 0:
            current_section = 'songs'
            continue
        
        if current_section == 'captions' and len(captions) < max_outputs:
            # Clean up caption formatting
            caption = line.replace('*', '').replace('-', '').replace('•', '').strip()
            if caption and len(caption) > 5:
                captions.append(caption)
        
        elif current_section == 'songs' and len(songs) < max_outputs:
            # Try to extract song title and artist
            song_line = line.replace('*', '').replace('-', '').replace('•', '').strip()
            if ' by ' in song_line:
                parts = song_line.split(' by ')
                songs.append({"title": parts[0].strip(), "artist": parts[1].strip()})
            elif ' - ' in song_line:
                parts = song_line.split(' - ')
                songs.append({"title": parts[0].strip(), "artist": parts[1].strip()})
            elif song_line and len(song_line) > 3:
                songs.append({"title": song_line, "artist": "Unknown Artist"})
    
    # If we didn't get enough results, fill with mock data
    if len(captions) < max_outputs or len(songs) < max_outputs:
        mock_data = get_mock_response("", max_outputs)
        while len(captions) < max_outputs:
            captions.append(mock_data['captions'][len(captions) % len(mock_data['captions'])])
        while len(songs) < max_outputs:
            songs.append(mock_data['songs'][len(songs) % len(mock_data['songs'])])
    
    return {
        'captions': captions[:max_outputs],
        'songs': songs[:max_outputs]
    }


def get_mock_response(prompt, max_outputs):
    """Fallback mock response when API is unavailable"""
    base_captions = [
        "Stolen moments under golden skies",
        "When the world felt like a soft melody",
        "Sunlit streets and quiet thoughts",
        "Lost in the little things",
        "Weekend chapters written in sunlight",
        "Chasing light and finding magic",
        "Simple moments, infinite beauty"
    ]
    
    # Region-specific song suggestions
    bollywood_songs = [
        {"title": "Tum Hi Ho", "artist": "Arijit Singh"},
        {"title": "Raabta", "artist": "Arijit Singh"},
        {"title": "Channa Mereya", "artist": "Arijit Singh"},
        {"title": "Tera Ban Jaunga", "artist": "Tulsi Kumar & Akhil Sachdeva"},
        {"title": "Kesariya", "artist": "Arijit Singh"},
        {"title": "Phir Bhi Tumko Chaahunga", "artist": "Arijit Singh"},
        {"title": "Dil Diyan Gallan", "artist": "Atif Aslam"}
    ]
    
    hollywood_songs = [
        {"title": "Golden Hour", "artist": "Joji"},
        {"title": "Sunflower", "artist": "Post Malone"},
        {"title": "Levitating", "artist": "Dua Lipa"},
        {"title": "Blinding Lights", "artist": "The Weeknd"},
        {"title": "Watermelon Sugar", "artist": "Harry Styles"},
        {"title": "Good 4 U", "artist": "Olivia Rodrigo"},
        {"title": "Stay", "artist": "The Kid LAROI & Justin Bieber"}
    ]
    
    tollywood_songs = [
        {"title": "Ala Vaikunthapurramuloo", "artist": "Armaan Malik"},
        {"title": "Inkem Inkem", "artist": "Sid Sriram"},
        {"title": "Samajavaragamana", "artist": "Sid Sriram"},
        {"title": "Vachinde", "artist": "Madhu Priya"},
        {"title": "Rangamma Mangamma", "artist": "MM Manasi"},
        {"title": "Buttabomma", "artist": "Armaan Malik"},
        {"title": "Ramuloo Ramulaa", "artist": "Anurag Kulkarni"}
    ]
    
    kpop_songs = [
        {"title": "Dynamite", "artist": "BTS"},
        {"title": "Butter", "artist": "BTS"},
        {"title": "How You Like That", "artist": "BLACKPINK"},
        {"title": "Gangnam Style", "artist": "PSY"},
        {"title": "Next Level", "artist": "aespa"},
        {"title": "Savage", "artist": "aespa"},
        {"title": "LALISA", "artist": "LISA"}
    ]

    # Determine which songs to use based on prompt
    base_songs = hollywood_songs  # default
    if "bollywood" in prompt.lower():
        base_songs = bollywood_songs
    elif "tollywood" in prompt.lower():
        base_songs = tollywood_songs
    elif "kpop" in prompt.lower() or "k-pop" in prompt.lower():
        base_songs = kpop_songs
    elif "hollywood" in prompt.lower():
        base_songs = hollywood_songs

    # Simple deterministic pick seeded by prompt length
    seed = sum(ord(c) for c in prompt) % len(base_captions) if prompt else 0
    captions = []
    songs = []
    for i in range(max_outputs):
        captions.append(base_captions[(seed + i) % len(base_captions)])
        songs.append(base_songs[(seed + i) % len(base_songs)])

    return {
        'captions': captions,
        'songs': songs
    }


# -----------------
# Templates (render_template_string to keep single-file)
# -----------------

INDEX_HTML = '''
<!doctype html>
<html lang="en">
<head>
  <meta charset="utf-8">
  <meta name="viewport" content="width=device-width, initial-scale=1">
  <title>InstaMuse — caption & song suggester</title>
  <link href="https://fonts.googleapis.com/css2?family=Inter:wght@300;400;600;700;800&display=swap" rel="stylesheet">
  <style>
    :root{
      --bg:#0a0e1a;
      --card:#0f1419;
      --card2:#141b26;
      --muted:#8b9bb3;
      --accent1:#8b5cf6;
      --accent2:#06b6d4;
      --accent3:#f59e0b;
      --success:#10b981;
      --text:#f8fafc;
      --border:rgba(255,255,255,0.08);
    }
    
    *{
      box-sizing:border-box;
      font-family:'Inter',system-ui,-apple-system,'Segoe UI',Roboto,'Helvetica Neue',Arial;
    }
    
    body{
      margin:0;
      min-height:100vh;
      background:radial-gradient(ellipse at top, #1e1b4b 0%, #0f172a 50%, #020617 100%);
      color:var(--text);
      line-height:1.6;
    }
    
    .container{
      max-width:1200px;
      margin:20px auto;
      padding:20px;
    }
    
    .top{
      display:flex;
      gap:24px;
      align-items:center;
      margin-bottom:32px;
    }
    
    .logo{
      display:flex;
      align-items:center;
      gap:16px;
    }
    
    .logo .mark{
      width:64px;
      height:64px;
      border-radius:16px;
      background:linear-gradient(135deg,var(--accent1),var(--accent2),var(--accent3));
      display:flex;
      align-items:center;
      justify-content:center;
      font-weight:900;
      font-size:24px;
      color:white;
      box-shadow:0 8px 32px rgba(139,92,246,0.3);
      animation:glow 3s ease-in-out infinite alternate;
    }
    
    @keyframes glow {
      from { box-shadow:0 8px 32px rgba(139,92,246,0.3); }
      to { box-shadow:0 8px 48px rgba(139,92,246,0.5); }
    }
    
    h1{
      margin:0;
      font-size:36px;
      font-weight:800;
      background:linear-gradient(135deg,var(--accent1),var(--accent2));
      -webkit-background-clip:text;
      -webkit-text-fill-color:transparent;
      background-clip:text;
    }
    
    p.lead{
      margin:8px 0 0;
      color:var(--muted);
      font-size:16px;
    }

    .grid{
      display:grid;
      grid-template-columns:1fr 480px;
      gap:32px;
    }

    .card{
      background:linear-gradient(145deg, rgba(255,255,255,0.05), rgba(255,255,255,0.02));
      backdrop-filter:blur(20px);
      border:1px solid var(--border);
      padding:24px;
      border-radius:20px;
      box-shadow:0 10px 40px rgba(0,0,0,0.3);
      transition:transform 0.2s ease, box-shadow 0.2s ease;
    }
    
    .card:hover{
      transform:translateY(-2px);
      box-shadow:0 15px 50px rgba(0,0,0,0.4);
    }

    .uploader{
      border:2px dashed var(--border);
      padding:24px;
      text-align:center;
      border-radius:16px;
      background:linear-gradient(145deg, rgba(139,92,246,0.05), rgba(6,182,212,0.05));
      transition:all 0.3s ease;
    }
    
    .uploader:hover{
      border-color:var(--accent1);
      background:linear-gradient(145deg, rgba(139,92,246,0.1), rgba(6,182,212,0.1));
    }
    
    input[type=file]{display:none}
    
    .upload-btn{
      display:inline-block;
      padding:12px 24px;
      border-radius:12px;
      background:linear-gradient(135deg,var(--accent1),var(--accent2));
      cursor:pointer;
      font-weight:700;
      color:white;
      transition:transform 0.2s ease, box-shadow 0.2s ease;
      box-shadow:0 4px 16px rgba(139,92,246,0.3);
    }
    
    .upload-btn:hover{
      transform:translateY(-1px);
      box-shadow:0 6px 20px rgba(139,92,246,0.4);
    }
    
    .preview{
      margin-top:16px;
      border-radius:16px;
      overflow:hidden;
      box-shadow:0 8px 32px rgba(0,0,0,0.3);
    }
    
    .preview img{
      width:100%;
      height:auto;
      display:block;
      transition:transform 0.3s ease;
    }
    
    .preview:hover img{
      transform:scale(1.02);
    }

    .form-row{
      display:flex;
      gap:12px;
      margin-top:16px;
    }
    
    select, input[type=number]{
      width:100%;
      padding:12px 16px;
      border-radius:12px;
      border:1px solid var(--border);
      background:var(--card2);
      color:var(--text);
      font-size:14px;
      transition:border-color 0.2s ease, background 0.2s ease;
    }
    
    select:focus, input[type=number]:focus{
      outline:none;
      border-color:var(--accent1);
      background:var(--card);
    }
    
    select:hover, input[type=number]:hover{
      border-color:var(--accent2);
    }

    .muted{
      color:var(--muted);
      font-size:13px;
      line-height:1.5;
    }

    .generate-btn{
      margin-top:20px;
      padding:16px 24px;
      background:linear-gradient(135deg,var(--accent2),var(--accent1));
      border-radius:16px;
      border:0;
      font-weight:800;
      font-size:16px;
      cursor:pointer;
      width:100%;
      color:white;
      transition:transform 0.2s ease, box-shadow 0.2s ease;
      box-shadow:0 6px 24px rgba(6,182,212,0.3);
    }
    
    .generate-btn:hover{
      transform:translateY(-2px);
      box-shadow:0 8px 32px rgba(6,182,212,0.4);
    }
    
    .generate-btn:disabled{
      opacity:0.6;
      cursor:not-allowed;
      transform:none;
    }

    .results{
      margin-top:20px;
      display:grid;
      grid-template-columns:1fr 1fr;
      gap:16px;
    }
    
    .result-card{
      background:linear-gradient(145deg, var(--card2), var(--card));
      padding:16px;
      border-radius:16px;
      border:1px solid var(--border);
      transition:transform 0.2s ease, border-color 0.2s ease;
    }
    
    .result-card:hover{
      transform:translateY(-1px);
      border-color:var(--accent1);
    }
    
    .result-card h4{
      margin:0 0 16px 0;
      color:var(--accent1);
      font-size:18px;
      font-weight:700;
    }
    
    .caption-text{
      font-weight:600;
      font-size:15px;
      line-height:1.5;
      margin-bottom:12px;
    }
    
    .song-text{
      font-weight:600;
      font-size:15px;
      margin-bottom:8px;
    }
    
    .song-text strong{
      color:var(--accent2);
    }
    
    .chip{
      display:inline-block;
      padding:6px 12px;
      border-radius:20px;
      background:linear-gradient(135deg,rgba(139,92,246,0.2),rgba(6,182,212,0.2));
      font-size:12px;
      font-weight:600;
      margin-right:8px;
      margin-bottom:4px;
      border:1px solid var(--border);
    }

    .actions{
      display:flex;
      gap:8px;
      margin-top:12px;
    }
    
    .btn-small{
      padding:8px 16px;
      border-radius:8px;
      border:1px solid var(--border);
      background:var(--card);
      cursor:pointer;
      font-size:12px;
      font-weight:600;
      color:var(--text);
      transition:all 0.2s ease;
    }
    
    .btn-small:hover{
      background:var(--accent1);
      border-color:var(--accent1);
      color:white;
      transform:translateY(-1px);
    }
    
    .btn-small.success{
      background:var(--success);
      border-color:var(--success);
      color:white;
    }

    #status{
      margin-top:16px;
      padding:12px;
      border-radius:12px;
      font-weight:600;
      text-align:center;
    }
    
    .status-loading{
      background:linear-gradient(135deg,rgba(6,182,212,0.1),rgba(139,92,246,0.1));
      border:1px solid var(--accent2);
      color:var(--accent2);
    }

    footer{
      margin-top:40px;
      color:var(--muted);
      text-align:center;
      font-size:14px;
      padding:20px;
      border-top:1px solid var(--border);
    }

    @media(max-width:1024px){
      .grid{grid-template-columns:1fr;}
      .results{grid-template-columns:1fr;}
      .container{padding:16px;}
      h1{font-size:28px;}
    }
    
    /* Loading animation */
    .loading-dots::after {
      content: '...';
      animation: loading 1.5s infinite;
    }
    
    @keyframes loading {
      0%, 20% { content: '.'; }
      40% { content: '..'; }
      60%, 100% { content: '...'; }
    }
  </style>
</head>
<body>
  <div class="container">
    <div class="top">
      <div class="logo">
        <div class="mark">IM</div>
        <div>
          <h1>InstaMuse</h1>
          <p class="lead">Aesthetic captions and song picks for every photo — powered by AI.</p>
        </div>
      </div>
      <div style="margin-left:auto;text-align:right">
        <div class="muted">Pro tip: choose the style + length for tighter results</div>
      </div>
    </div>

    <div class="grid">
      <div class="card">
        <div class="uploader">
          <label class="upload-btn" for="imageInput">Upload photo</label>
          <input id="imageInput" type="file" accept="image/*">
          <div class="preview" id="previewArea" style="display:none">
            <img id="previewImg" src="#" alt="preview">
          </div>
          <div class="muted">Max 8MB. JPG or PNG. No image leaves your browser unless you hit Generate.</div>

          <form id="optionsForm" onsubmit="return false;">
            <div class="form-row" style="margin-top:14px">
              <select id="captionLength">
                <option value="short">Short — 5–10 words</option>
                <option value="medium" selected>Medium — 11–20 words</option>
                <option value="long">Long — 21–35 words</option>
              </select>
              <select id="captionTone">
                <option value="cute">Cute / Playful</option>
                <option value="moody">Moody / Poetic</option>
                <option value="funny">Funny / Witty</option>
                <option value="romantic">Romantic</option>
                <option value="aesthetic" selected>Aesthetic / Minimal</option>
              </select>
            </div>

            <div class="form-row">
              <select id="songRegion">
                <option value="any" selected>Any region</option>
                <option value="bollywood">Bollywood</option>
                <option value="hollywood">Hollywood / English</option>
                <option value="tollywood">Tollywood</option>
                <option value="kpop">K-Pop</option>
              </select>
              <select id="songMood">
                <option value="chill">Chill</option>
                <option value="upbeat">Upbeat</option>
                <option value="romantic">Romantic</option>
                <option value="nostalgic">Nostalgic</option>
                <option value="party">Party</option>
              </select>
            </div>

            <div style="display:flex;gap:8px;margin-top:12px;align-items:center">
              <label class="muted" style="width:140px">How many options?</label>
              <input id="numOptions" type="number" min="1" max="6" value="3" style="width:90px">
            </div>

            <button id="generate" class="generate-btn">Generate captions & songs</button>
          </form>
        </div>

        <div id="status" style="margin-top:12px"></div>
      </div>

      <div class="card">
        <h3 style="margin:0">Results</h3>
        <p class="muted" style="margin:6px 0 12px">Tap copy to paste directly into Instagram, or click preview to audition a suggested song on YouTube.</p>

        <div id="resultsArea">
          <div class="muted">No results yet — upload a photo and choose Generate.</div>
        </div>

      </div>
    </div>

    <footer>
      <div style="margin-bottom:8px;">🎨 Made with care • InstaMuse — AI-powered captions & songs tailored to your photos</div>
      <div class="muted">✨ Try different tones and regions for personalized results • 🎵 Songs matched to your selected region</div>
    </footer>
  </div>

<script>
const imageInput = document.getElementById('imageInput');
const previewArea = document.getElementById('previewArea');
const previewImg = document.getElementById('previewImg');
const generateBtn = document.getElementById('generate');
const status = document.getElementById('status');
const resultsArea = document.getElementById('resultsArea');

let uploadedDataUrl = null;
let uploadedBlob = null;

imageInput.addEventListener('change', async (e) => {
  const file = e.target.files[0];
  if(!file) return;
  const ext = file.name.split('.').pop().toLowerCase();
  if(!['jpg','jpeg','png'].includes(ext)) { alert('Unsupported file type'); return; }

  const reader = new FileReader();
  reader.onload = function(ev) {
    uploadedDataUrl = ev.target.result;
    previewImg.src = uploadedDataUrl;
    previewArea.style.display = 'block';
  }
  reader.readAsDataURL(file);
  uploadedBlob = file;
});

function setStatus(msg, busy=false){
  status.innerHTML = msg;
  if(busy) {
    generateBtn.disabled = true;
    generateBtn.textContent = 'Generating...';
    status.className = 'status-loading loading-dots';
  } else {
    generateBtn.disabled = false;
    generateBtn.textContent = 'Generate captions & songs';
    status.className = '';
  }
}

function el(tag, cls, txt){ const d = document.createElement(tag); if(cls) d.className = cls; if(txt) d.textContent = txt; return d; }

async function handleGenerate(){
  if(!uploadedBlob){ alert('Please upload a photo first'); return; }
  const length = document.getElementById('captionLength').value;
  const tone = document.getElementById('captionTone').value;
  const region = document.getElementById('songRegion').value;
  const mood = document.getElementById('songMood').value;
  const num = parseInt(document.getElementById('numOptions').value)||3;

  setStatus('Generating — hang on a moment...', true);
  resultsArea.innerHTML = '';

  const form = new FormData();
  form.append('image', uploadedBlob);
  form.append('length', length);
  form.append('tone', tone);
  form.append('region', region);
  form.append('mood', mood);
  form.append('num', num);

  try{
    const r = await fetch('/generate', { method: 'POST', body: form });
    const data = await r.json();
    setStatus('');
    if(data.error){ resultsArea.innerHTML = '<div class="muted">Error: '+data.error+'</div>'; return; }

    const captions = data.captions || [];
    const songs = data.songs || [];

    if(captions.length===0 && songs.length===0){ resultsArea.innerHTML = '<div class="muted">No suggestions. Try different tone or length.</div>'; return; }

    const container = document.createElement('div');
    container.className = 'results';

    const capCol = document.createElement('div');
    const songCol = document.createElement('div');

    capCol.innerHTML = '<h4>Captions</h4>';
    songCol.innerHTML = '<h4>Songs</h4>';

    captions.forEach((c,i)=>{
      const card = document.createElement('div'); card.className='result-card';
      const p = document.createElement('div'); p.textContent = c; p.className='caption-text';
      const chips = document.createElement('div'); chips.style.marginTop='12px';
      chips.innerHTML = '<span class="chip">'+document.getElementById('captionLength').value+'</span><span class="chip">'+document.getElementById('captionTone').value+'</span>';
      const actions = document.createElement('div'); actions.className='actions';
      const copy = document.createElement('button'); copy.className='btn-small'; copy.textContent='Copy';
      copy.onclick = ()=>{ 
        navigator.clipboard.writeText(c); 
        copy.textContent='Copied ✓'; 
        copy.className='btn-small success';
        setTimeout(()=>{copy.textContent='Copy'; copy.className='btn-small';},1500); 
      };
      actions.appendChild(copy);
      card.appendChild(p); card.appendChild(chips); card.appendChild(actions);
      capCol.appendChild(card);
    });

    songs.forEach((s,i)=>{
      const card = document.createElement('div'); card.className='result-card';
      const p = document.createElement('div'); p.innerHTML = '<strong>'+s.title+'</strong> — '+s.artist; p.className='song-text';
      const regionChip = document.createElement('div'); regionChip.style.marginTop='8px';
      regionChip.innerHTML = '<span class="chip">'+region+'</span><span class="chip">'+mood+'</span>';
      const actions = document.createElement('div'); actions.className='actions';
      const yt = document.createElement('button'); yt.className='btn-small'; yt.textContent='🎵 Preview';
      yt.onclick = ()=>{ window.open('https://www.youtube.com/results?search_query='+encodeURIComponent(s.title+' '+s.artist), '_blank') };
      const copy = document.createElement('button'); copy.className='btn-small'; copy.textContent='Copy';
      copy.onclick = ()=>{ 
        navigator.clipboard.writeText(s.title+' — '+s.artist); 
        copy.textContent='Copied ✓'; 
        copy.className='btn-small success';
        setTimeout(()=>{copy.textContent='Copy'; copy.className='btn-small';},1500); 
      };
      actions.appendChild(yt); actions.appendChild(copy);
      card.appendChild(p); card.appendChild(regionChip); card.appendChild(actions);
      songCol.appendChild(card);
    });

    container.appendChild(capCol); container.appendChild(songCol);
    resultsArea.appendChild(container);

  }catch(err){
    console.error(err);
    setStatus('Something went wrong — check console', false);
  }finally{ setStatus('', false); }
}

generateBtn.addEventListener('click', handleGenerate);
</script>
</body>
</html>
'''

# -----------------
# Routes
# -----------------

@app.route('/')
def index():
    return render_template_string(INDEX_HTML)


@app.route('/generate', methods=['POST'])
def generate():
    # Validate and load image
    img_file = request.files.get('image')
    if not img_file:
        return jsonify({'error':'No image uploaded'}), 400

    filename = secure_filename(img_file.filename)
    ext = os.path.splitext(filename)[1].lower()
    if ext not in app.config['UPLOAD_EXTENSIONS']:
        return jsonify({'error':'Unsupported file type'}), 400

    img_bytes = img_file.read()

    # Read options
    length = request.form.get('length','medium')
    tone = request.form.get('tone','aesthetic')
    region = request.form.get('region','any')
    mood = request.form.get('mood','chill')
    try:
        num = int(request.form.get('num','3'))
        num = max(1, min(6, num))
    except:
        num = 3

    # Build a clear prompt for the LLM with strong region emphasis
    prompt = f"""You are a social-media assistant. I will provide a photo. Generate {num} caption suggestions and {num} song suggestions.

CRITICAL REQUIREMENTS:
- Caption length: {length}
- Tone: {tone} 
- Song region: {region} (THIS IS MANDATORY - only suggest songs from this region)
- Song mood: {mood}

For song region '{region}':
- bollywood: Only Hindi/Bollywood songs (Arijit Singh, Shreya Ghoshal, A.R. Rahman, etc.)
- hollywood: Only English/Western pop songs
- tollywood: Only Telugu cinema songs
- kpop: Only Korean pop songs
- any: Mix from different regions

Provide captions as single lines and songs with title and artist."""

    print(f"DEBUG: Generating for region: {region}, mood: {mood}, tone: {tone}, length: {length}")

    try:
        response = call_gemini(prompt, image_bytes=img_bytes, max_outputs=num)
        print(f"DEBUG: Generated {len(response.get('songs', []))} songs for region {region}")
    except Exception as e:
        print(f"ERROR: {str(e)}")
        return jsonify({'error':str(e)}), 500

    # For safety, ensure we return simple JSON lists
    captions = response.get('captions', [])[:num]
    songs = response.get('songs', [])[:num]

    return jsonify({'captions':captions,'songs':songs})


if __name__ == '__main__':
    app.run(debug=True)
