from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from routers import upload, analyze, session, download
import uvicorn

app = FastAPI(title="Soochi 3.0")

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

app.include_router(upload.router)
app.include_router(analyze.router)
app.include_router(session.router)
app.include_router(download.router)

@app.get("/health")
async def health():
    return {"status": "ok", "version": "3.0"}

if __name__ == "__main__":
    uvicorn.run("main:app", host="0.0.0.0", port=8000, reload=True)
