import uvicorn

if __name__ == "__main__":
    import os
    uvicorn.run("harness.app:app", host="0.0.0.0", port=int(os.environ.get("PORT", "8080")))
