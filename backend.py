import os
import json
from fastapi import FastAPI, HTTPException
from fastapi.responses import FileResponse
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel
from dotenv import load_dotenv
from openai import AsyncOpenAI

load_dotenv()

app = FastAPI()
client = AsyncOpenAI(api_key=os.getenv("OPENAI_API_KEY"))

class PreferenceRequest(BaseModel):
    favorite_movies: str
    genres: str
    mood: str
    count: int = 4

@app.post("/api/recommend")
async def get_recommendations(pref: PreferenceRequest):
    system_prompt = (
        f"Recommend exactly {pref.count} movies or TV shows in strict JSON format. "
        "Return ONLY a JSON array of objects with keys: "
        '"title", "year" (YYYY), "genre", "matchScore" (integer 80-99), "reason" (2 concise sentences).'
    )
    user_prompt = f"Favorites: {pref.favorite_movies}, Genres: {pref.genres}, Mood: {pref.mood}"

    try:
        response = await client.chat.completions.create(
            model="gpt-4o-mini",
            messages=[
                {"role": "system", "content": system_prompt},
                {"role": "user", "content": user_prompt}
            ],
            response_format={"type": "json_object"} if hasattr(client, 'chat') else None,
            temperature=0.7
        )
        
        content = response.choices[0].message.content
        data = json.loads(content)
        
        # Handle cases where LLM wraps array in a root key
        if isinstance(data, dict):
            for key in data:
                if isinstance(data[key], list):
                    return data[key]
        return data
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

app.mount("/static", StaticFiles(directory="frontend"), name="static")

@app.get("/")
async def serve_index():
    return FileResponse("frontend/index.html")