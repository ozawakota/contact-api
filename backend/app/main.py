from fastapi import FastAPI

app = FastAPI()

@app.get("/")
def read_root():
    return {"Hello v2": "GCP CI/CD!"}