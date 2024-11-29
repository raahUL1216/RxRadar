import uvicorn
from fastapi import FastAPI
from server.router import knowledge, agent
from server.utils.embedding import create_index

app = FastAPI()

@app.get("/")
def read_root():
    return {"message": "RxRadar service is up"}

app.include_router(knowledge.router)
app.include_router(agent.router)


def main():
    create_index()
    uvicorn.run("server.app:app", host="0.0.0.0", port=8000, reload=True)