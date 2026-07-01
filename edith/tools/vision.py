import os
import io
import google.generativeai as genai
from PIL import ImageGrab
from edith.config import GEMINI_API_KEY

def capture_and_analyze_screen(prompt="Describe what you see on my screen in a concise, tactical manner. Focus on what I might be looking at or working on."):
    if not GEMINI_API_KEY:
        return "Sir, my Gemini vision optics are offline. Please check your API key."
        
    try:
        # Take a screenshot of the primary monitor
        image = ImageGrab.grab()
        
        # Convert image to bytes
        img_byte_arr = io.BytesIO()
        image = image.convert("RGB") # Drop alpha channel for JPEG
        image.save(img_byte_arr, format='JPEG', quality=85)
        img_byte_arr = img_byte_arr.getvalue()
        
        # Configure Gemini
        genai.configure(api_key=GEMINI_API_KEY)
        
        # gemini-1.5-flash is extremely fast and capable for vision
        model = genai.GenerativeModel("gemini-1.5-flash")
        
        contents = [
            {"role": "user", "parts": [
                prompt,
                {
                    "mime_type": "image/jpeg",
                    "data": img_byte_arr
                }
            ]}
        ]
        
        response = model.generate_content(contents)
        return response.text
        
    except Exception as e:
        print(f"[VISION ERROR] {e}")
        return "I encountered an error trying to capture and analyze the screen, sir."
