from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from database import SessionLocal, Review
from schemas import ReviewCreate
import requests, os, json, re
from dotenv import load_dotenv


# ---------------- LOAD ENV ----------------
OPENROUTER_API_KEY = os.getenv("OPENROUTER_API_KEY")

app = FastAPI(title="Fynd AI Task 2")

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)
# ---------------- JSON EXTRACTOR ----------------
def extract_json(text: str):
    match = re.search(r"\{[\s\S]*\}", text)
    if match:
        return match.group()
    return None

# ---------------- AI CALL ----------------
def call_llm(prompt: str):
    if not OPENROUTER_API_KEY:
        raise HTTPException(status_code=500, detail="OpenRouter API key missing")

    headers = {
        "Authorization": f"Bearer {OPENROUTER_API_KEY}",
        "Content-Type": "application/json",
        # 👇 MUST be your deployed backend URL
        "HTTP-Referer": "https://fynd-ai-assignment.onrender.com",
        "X-Title": "Fynd AI Internship Task"
    }

    payload = {
        "model": "mistralai/mistral-7b-instruct",
        "messages": [
            {"role": "user", "content": prompt}
        ],
        "temperature": 0
    }

    response = requests.post(
        "https://openrouter.ai/api/v1/chat/completions",
        headers=headers,
        json=payload,
        timeout=30
    )

    if response.status_code != 200:
        print("OpenRouter Error:", response.text)
        raise HTTPException(status_code=500, detail="LLM request failed")

    data = response.json()
    return data["choices"][0]["message"]["content"]

# ---------------- USER SUBMIT REVIEW ----------------
@app.post("/submit-review")
def submit_review(data: ReviewCreate):

    if not data.review.strip():
        raise HTTPException(status_code=400, detail="Review cannot be empty")

    db = SessionLocal()

    user_prompt = f"""
    User gave {data.rating} stars.

    Review:
    {data.review}

    Write a polite and friendly reply to the user.
    """

    admin_prompt = f"""
    Return ONLY valid JSON.

    Review:
    {data.review}

    {{
      "summary": "one sentence summary",
      "action": "recommended admin action"
    }}
    """

    ai_response = call_llm(user_prompt)
    admin_response = call_llm(admin_prompt)

    json_text = extract_json(admin_response)

    try:
        parsed = json.loads(json_text) if json_text else {}
    except:
        parsed = {}

    review = Review(
        rating=data.rating,
        review=data.review,
        ai_response=ai_response,
        ai_summary=parsed.get("summary", "N/A"),
        ai_action=parsed.get("action", "N/A")
    )

    db.add(review)
    db.commit()

    return {
        "message": "Review submitted successfully",
        "ai_response": ai_response
    }

# ---------------- ADMIN FETCH ----------------
@app.get("/admin/reviews")
def get_reviews():
    db = SessionLocal()
    reviews = db.query(Review).all()

    return [
        {
            "rating": r.rating,
            "review": r.review,
            "summary": r.ai_summary,
            "action": r.ai_action
        }
        for r in reviews
    ]
