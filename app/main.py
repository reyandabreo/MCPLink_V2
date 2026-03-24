from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
import uvicorn
from app.config import settings
from app.api.routes import router as api_router

# Ensure necessary tool imports are executed to register them in the registry
import app.tools.filesystem
import app.tools.execution
import app.tools.git_tools
import app.tools.news_tools
import app.tools.spreadsheet_tools
import app.tools.web_fetch_tools

app = FastAPI(
    title=settings.APP_NAME,
    openapi_url=f"{settings.API_V1_STR}/openapi.json"
)

# Optional CORS middleware
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

app.include_router(api_router, prefix=settings.API_V1_STR)

@app.get("/")
def read_root():
    return {"message": "Welcome to MCPLink v2 Backend - Agent Runtime"}

if __name__ == "__main__":
    uvicorn.run("app.main:app", host="0.0.0.0", port=8000, reload=True)
