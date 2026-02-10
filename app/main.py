from fastapi import FastAPI
from app.api import recommend
from app.core.config import settings

app = FastAPI(
    title = "Codoc AI Server",
    version = "2.0.0"
)

app.include_router(recommend.router, prefix=f"{settings.API_PREFIX}/recommend", tags=["Recommendation"])

@app.get("/")
async def health_check():
    return {"status": "healthy", "message": "Codoc AI Server is running"}

