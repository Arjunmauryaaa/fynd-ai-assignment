from fastapi import FastAPI, HTTPException
from database import SessionLocal, Review
from schemas import ReviewCreate
import requests, os, json, re
from dotenv import load_dotenv

# ---------------- LOAD ENV ----------------
load_dotenv()
API_KEY = os.getenv("OPENROUTER_API_KEY")

if not API_KEY:
    raise RuntimeError("OPENROUTER_API_KEY not found in .env")

app = FastAPI(title="Fynd AI Task 2")

# ---------------- JSON EXTRACTOR ----------------
def extract_json(text: str):
    """
    Safely extract JSON object from LLM output
    """
    match = re.search(r"\{[\s\S]*\}", text)
    if match:
        return match.group()
    return None

# ---------------- AI CALL ----------------
def call_llm(prompt: str):
    response = requests.post(
        "https://openrouter.ai/api/v1/chat/completions",
        headers={
            "Authorization": f"Bearer {API_KEY}",
            "HTTP-Referer": "http://localhost",
            "X-Title": "Fynd AI Task 2",
            "Content-Type": "application/json"
        },
        json={
            "model": "mistralai/mistral-7b-instruct",
            "messages": [
                {
                    "role": "system",
                    "content": "You are a helpful assistant. Follow instructions strictly."
                },
                {
                    "role": "user",
                    "content": prompt
                }
            ],
            "temperature": 0
        },
        timeout=30
    )

    response.raise_for_status()
    data = response.json()
    return data["choices"][0]["message"]["content"]

# ---------------- USER SUBMIT REVIEW ----------------
@app.post("/submit-review")
def submit_review(data: ReviewCreate):
    if not data.review.strip():
        raise HTTPException(status_code=400, detail="Review cannot be empty")

    db = SessionLocal()

    # ---- USER RESPONSE PROMPT ----
    user_prompt = f"""
    User gave {data.rating} stars.

    Review:
    {data.review}

    Write a polite and friendly reply to the user.
    """

    # ---- ADMIN JSON PROMPT ----
    admin_prompt = f"""
    You are a JSON API.

    Return ONLY valid JSON.
    No markdown.
    No explanation text.

    Review:
    {data.review}

    Return EXACTLY this format:

    {{
      "summary": "one sentence summary of the review",
      "action": "recommended next action for admin"
    }}
    """

    # ---- AI CALLS ----
    ai_response = call_llm(user_prompt)
    admin_output = call_llm(admin_prompt)

    # ---- PARSE ADMIN JSON ----
    json_text = extract_json(admin_output)

    if json_text:
        try:
            parsed = json.loads(json_text)
        except:
            parsed = {"summary": "N/A", "action": "N/A"}
    else:
        parsed = {"summary": "N/A", "action": "N/A"}

    # ---- SAVE TO DB ----
    review = Review(
        rating=data.rating,
        review=data.review,
        ai_response=ai_response,
        ai_summary=parsed.get("summary", "N/A"),
        ai_action=parsed.get("action", "N/A")
    )

    db.add(review)
    db.commit()
    db.refresh(review)

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
