import os
import json
import traceback
from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles
from fastapi.responses import FileResponse
from pydantic import BaseModel
import requests
from openai import OpenAI

app = FastAPI(title="CineMind AI")

# Enable CORS for frontend communication
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Initialize OpenAI client pointed to Groq's FREE API endpoint
groq_api_key = os.getenv("GROQ_API_KEY")
client = OpenAI(
    base_url="https://api.groq.com/openai/v1",
    api_key=groq_api_key or "dummy_key"
)


class RecommendationRequest(BaseModel):
    favorites: str = ""
    genres: str = ""
    mood: str = ""
    count: int = 4


@app.get("/")
async def serve_index():
    index_path = os.path.join("frontend", "index.html")
    if os.path.exists(index_path):
        return FileResponse(index_path)
    return {"status": "CineMind API is online"}


if os.path.exists("frontend"):
    app.mount("/static", StaticFiles(directory="frontend"), name="static")


def fetch_tvmaze_details(title: str):
    try:
        url = f"https://api.tvmaze.com/singlesearch/shows?q={title}&embed=cast"
        res = requests.get(url, timeout=4)
        if res.status_code == 200:
            data = res.json()
            image = data.get("image", {}).get("medium") if data.get("image") else None
            cast_list = []
            if "_embedded" in data and "cast" in data["_embedded"]:
                cast_list = [member["person"]["name"] for member in data["_embedded"]["cast"][:3]]
            return image, cast_list
    except Exception as e:
        print(f"TVMaze lookup skipped for '{title}': {e}")
    return None, []


@app.post("/api/recommend")
async def get_recommendations(req: RecommendationRequest):
    try:
        if not os.getenv("GROQ_API_KEY"):
            raise ValueError("GROQ_API_KEY is missing in Render environment variables!")

        prompt = f"""
        You are an expert movie and TV show recommendation system.
        User Input:
        - Favorite Shows/Movies: {req.favorites}
        - Preferred Genres: {req.genres}
        - Current Mood: {req.mood}
        - Number of Recommendations: {req.count}

        Respond ONLY with a raw JSON array containing exactly {req.count} objects.
        Do NOT wrap the response in markdown or backticks (no ```json).
        Each object must have these exact keys:
        "title", "type", "year", "genre", "reason"
        """

        # Call Groq using Llama 3.1 model (100% free)
        response = client.chat.completions.create(
            model="llama-3.1-8b-instant",
            messages=[
                {"role": "system", "content": "You are a helpful AI that outputs strictly valid JSON arrays."},
                {"role": "user", "content": prompt}
            ],
            temperature=0.7
        )

        raw_content = response.choices[0].message.content.strip()

        # Clean potential markdown formatting
        if raw_content.startswith("```"):
            raw_content = raw_content.split("\n", 1)[-1]
        if raw_content.endswith("```"):
            raw_content = raw_content.rsplit("\n", 1)[0]
        raw_content = raw_content.strip()

        recommendations = json.loads(raw_content)

        enriched = []
        for item in recommendations:
            title = item.get("title", "")
            poster, cast = fetch_tvmaze_details(title)
            item["poster"] = poster
            item["cast"] = cast
            enriched.append(item)

        return {"recommendations": enriched}

    except Exception as e:
        print("=" * 60)
        print("BACKEND ERROR:")
        traceback.print_exc()
        print("=" * 60)
        raise HTTPException(status_code=500, detail=str(e))