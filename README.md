# LyricLens - AI Caption & Song Generator

![LyricLens](https://img.shields.io/badge/LyricLens-AI%20Powered-8b5cf6?style=for-the-badge&logo=music)

**LyricLens** is a smart web app that analyzes your photos and generates personalized Instagram captions and song recommendations using Google's Gemini AI.

## 🚀 What It Does

- **📸 Upload your photo** → AI analyzes the image
- **🎨 Choose your style** → Caption tone, length, song region  
- **✨ Get suggestions** → Perfect captions + matching songs
- **📋 Copy & use** → One-click copy to clipboard

## ✨ Features

- **Smart Image Analysis** - AI understands your photo's mood and content
- **Custom Captions** - Short/Medium/Long with different tones (Cute, Moody, Funny, Romantic, Aesthetic)
- **Regional Songs** - Bollywood, Hollywood, Tollywood, K-Pop, or Global mix
- **Beautiful UI** - Modern dark theme with smooth animations
- **Mobile Friendly** - Works on all devices

## �️ Quick Setup

1. **Clone or Download the Project**
   ```bash
   git clone https://github.com/Vidhi-bhutia/LyricLens.git
   cd LyricLens
   ```

2. **Create Virtual Environment** (Recommended)
   ```bash
   # Windows
   python -m venv venv
   venv\Scripts\activate
   
   # macOS/Linux
   python3 -m venv venv
   source venv/bin/activate
   ```

3. **Install Dependencies**
   ```bash
   pip install -r requirements.txt
   ```

4. **Set Up Environment Variables**
   Create a `.env` file in the project root:
   ```env
   GEMINI_API_KEY=your_actual_gemini_api_key_here
   ```

### 🔑 Get Gemini API Key

1. Visit [Google AI Studio](https://makersuite.google.com/app/apikey)
2. Click "Create API Key"
3. Copy the key
4. Paste it in your `.env` file

## 🛠️ Tech Stack

- **Backend**: Flask (Python)
- **AI**: Google Gemini 1.5 Flash
- **Frontend**: HTML/CSS/JavaScript
- **Image Processing**: Pillow (PIL)

**Made with ❤️ for Instagram creators**

🌟 Star this repo if you found it helpful!
