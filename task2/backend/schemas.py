from pydantic import BaseModel

class ReviewCreate(BaseModel):
    rating: int
    review: str
