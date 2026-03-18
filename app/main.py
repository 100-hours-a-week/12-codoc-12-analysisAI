from fastapi import FastAPI

from app.common.exceptions.exception_handler import register_exception_handlers
from app.core.config import settings
from app.database.vector_db import vector_db
from app.domain.recommend import recommend_router
from app.domain.report import report_router
from app.domain.workbook import workbook_router

app = FastAPI(title="Codoc AI Server", version="2.0.0")
register_exception_handlers(app)

app.include_router(
    recommend_router.router,
    prefix=f"{settings.API_PREFIX}/recommend",
    tags=["Recommendation"],
)
app.include_router(
    report_router.router,
    prefix=f"{settings.API_PREFIX}/reports",
    tags=["Report"],
)
app.include_router(
    router=workbook_router.router,
    prefix=f"{settings.API_PREFIX}/ocr",
    tags=["Workbook"],
)


@app.get("/")
async def health_check():
    return {"status": "healthy", "message": "Codoc AI Server is running"}


@app.get("/health/db")
async def check_db_connection():
    try:
        collections = vector_db.client.get_collections()
        return {
            "status": "connected",
            "details": "Successfully reached Qdrant DB",
            "collections": collections,
        }
    except Exception as e:
        return {"status": "error", "details": f"Failed to connect to Qdrant: {str(e)}"}
