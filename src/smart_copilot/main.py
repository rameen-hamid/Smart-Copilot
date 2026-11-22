from fastapi import FastAPI

app = FastAPI(title="Smart Customer Support Copilot")


@app.get("/health")
def health() -> dict[str, str]:
    return {"status": "ok"}
