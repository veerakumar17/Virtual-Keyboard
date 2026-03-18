from fastapi import FastAPI, Request, Form
from fastapi.responses import HTMLResponse, RedirectResponse
from fastapi.staticfiles import StaticFiles
from fastapi.templating import Jinja2Templates
import subprocess

app = FastAPI()
app.mount("/static", StaticFiles(directory="static"), name="static")
templates = Jinja2Templates(directory="templates")

@app.get("/", response_class=HTMLResponse)
async def home(request: Request):
    return templates.TemplateResponse("index.html", {"request": request})

@app.post("/login")
async def login(request: Request, username: str = Form(...), password: str = Form(...)):
    # Basic input validation
    if not username.strip() or not password.strip():
        return templates.TemplateResponse("index.html", {"request": request, "error": "Invalid credentials"})
    
    try:
        subprocess.Popen(["python", "virtual_keyboard.py"])
    except Exception as e:
        print(f"Error launching virtual keyboard: {e}")
        return templates.TemplateResponse("index.html", {"request": request, "error": "System error"})
    
    return RedirectResponse("/", status_code=302)

@app.post("/register")
async def register(request: Request, username: str = Form(...), email: str = Form(...), password: str = Form(...)):
    # Basic input validation
    if not username.strip() or not email.strip() or not password.strip():
        return templates.TemplateResponse("index.html", {"request": request, "error": "All fields required"})
    
    try:
        subprocess.Popen(["python", "virtual_keyboard.py"])
    except Exception as e:
        print(f"Error launching virtual keyboard: {e}")
        return templates.TemplateResponse("index.html", {"request": request, "error": "System error"})
    
    return RedirectResponse("/", status_code=302)
