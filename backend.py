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

# Initialize OpenAI client using the environment key
openai_api_key = os.getenv("OPENAI_API_KEY")
client = OpenAI(api_key=openai_api_key) if openai_api_key else None


class RecommendationRequest(BaseModel):
    favorites: str = ""
    genres: str = ""
    mood: str = ""
    count: int = 4


@app.get("/")
async def serve_index():
    """Serves index.html at root route"""
    index_path = os.path.join("frontend", "index.html")
    if os.path.exists(index_path):
        return FileResponse(index_path)
    return {"status": "CineMind API is online"}


# Mount frontend static directory if present
if os.path.exists("frontend"):
    app.mount("/static", StaticFiles(directory="frontend"), name="static")


def fetch_tvmaze_details(title: str):
    """Fetch movie/show poster and cast list from free TVMaze API"""
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
        print(f"TVMaze search skipped for '{title}': {e}")
    return None, []


@app.post("/api/recommend")
async def get_recommendations(req: RecommendationRequest):
    try:
        # Check if API Key is available on Render
        if not os.getenv("OPENAI_API_KEY"):
            raise ValueError("OPENAI_API_KEY is not set in Render environment variables!")

        prompt = f"""
        You are an expert movie and TV show recommendation system.
        User Input:
        - Favorite Shows/Movies: {req.favorites}
        - Preferred Genres: {req.genres}
        - Current Mood: {req.mood}
        - Number of Recommendations: {req.count}

        Respond ONLY with a raw JSON array containing exactly {req.count} objects.
        Do NOT wrap the response in markdown or backticks (e.g. no ```json).
        Each object must have these exact keys:
        "title", "type", "year", "genre", "reason"
        """

        # Call OpenAI API (using modern gpt-4o-mini or gpt-3.5-turbo)
        response = client.chat.completions.create(
            model="gpt-4o-mini",
            messages=[
                {"role": "system", "content": "You are a helpful AI that outputs strictly valid JSON arrays."},
                {"role": "user", "content": prompt}
            ],
            temperature=0.7
        )

        raw_content = response.choices[0].message.content.strip()

        # Sanitize potential markdown block formatting from GPT
        if raw_content.startswith("```"):
            raw_content = raw_content.split("\n", 1)[-1]
        if raw_content.endswith("```"):
            raw_content = raw_content.rsplit("\n", 1)[0]
        raw_content = raw_content.strip()

        # Parse JSON output
        recommendations = json.loads(raw_content)

        # Enrich recommendations with TVMaze posters & cast
        enriched = []
        for item in recommendations:
            title = item.get("title", "")
            poster, cast = fetch_tvmaze_details(title)
            item["poster"] = poster
            item["cast"] = cast
            enriched.append(item)

        return {"recommendations": enriched}

    except Exception as e:
        # Print full stack trace to Render terminal logs
        print("=" * 60)
        print("EXACT BACKEND ERROR ENCOUNTERED:")
        traceback.print_exc()
        print("=" * 60)
        
        # Return the actual error message to the browser popup
        raise HTTPException(status_code=500, detail=str(e))