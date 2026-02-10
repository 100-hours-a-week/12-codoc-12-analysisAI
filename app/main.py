from fastapi import FastAPI

from app.core.config import settings
from app.domain.recommend import recommend_router

app = FastAPI(title="Codoc AI Server", version="2.0.0", root_path="/ai")

app.include_router(
    recommend_router.router,
    prefix=f"{settings.API_PREFIX}/recommend",
    tags=["Recommendation"],
)


@app.get("/")
async def health_check():
    return {"status": "healthy", "message": "Codoc AI Server is running"}
