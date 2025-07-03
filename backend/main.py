from fastapi import FastAPI, Request, Form, Depends
from fastapi.responses import HTMLResponse
from fastapi.templating import Jinja2Templates
from sqlalchemy.orm import Session
from backend import models, database, crud, schemas, utils, auth
from backend.api import router as api_router  
from fastapi import WebSocket, WebSocketDisconnect
from typing import List
from datetime import datetime

# Initialize the app
app = FastAPI()
connected_users: List[WebSocket] = []
active_connections = {}
# Create DB tables
models.Base.metadata.create_all(bind=database.engine)

# Load templates
templates = Jinja2Templates(directory="backend/templates")

# Include API routes
app.include_router(api_router)

# Dependency to get DB session
def get_db():
    db = database.SessionLocal()
    try:
        yield db
    finally:
        db.close()

# Root route
@app.get("/")
def root():
    print("🔥 Root route hit!")
    return {"message": "Welcome to Task Managers"}

# HTML - Login Page
@app.get("/login", response_class=HTMLResponse)
def login_form(request: Request):
    return templates.TemplateResponse("login.html", {"request": request})

# HTML - Register Page
@app.get("/register", response_class=HTMLResponse)
def register_form(request: Request):
    return templates.TemplateResponse("register.html", {"request": request})

# HTML - Register POST handler
@app.post("/register", response_class=HTMLResponse)
def register_from_form(
    request: Request,
    email: str = Form(...),
    password: str = Form(...),
    phone_number: str = Form(""),
    first_name: str = Form(""),
    last_name: str = Form(""),
    db: Session = Depends(get_db)
):
    user = schemas.UserCreate(
        email=email,
        password=password,
        phone_number=phone_number,
        first_name=first_name,
        last_name=last_name
    )

    existing_user = crud.get_user_by_email(db, email=email)
    if existing_user:
        return templates.TemplateResponse("register.html", {"request": request, "message": "Email already exists!"})

    hashed_password = utils.hash_password(password)
    user.password = hashed_password
    crud.create_user(db, user)

    return templates.TemplateResponse("login.html", {"request": request, "message": "Registration successful!"})

# HTML - Login POST handler
from fastapi.responses import RedirectResponse

@app.post("/login", response_class=HTMLResponse)
def login_from_form(
    request: Request,
    email: str = Form(...),
    password: str = Form(...),
    db: Session = Depends(get_db)
):
    user = crud.get_user_by_email(db, email)
    if not user or not utils.verify_password(password, user.hashed_password):
        return templates.TemplateResponse("login.html", {"request": request, "message": "Invalid credentials"})

    # ✅ Redirect to dashboard after successful login
    return RedirectResponse(url="/dashboard", status_code=303)

@app.get("/dashboard", response_class=HTMLResponse)
def dashboard(request: Request):
    return templates.TemplateResponse("dashboard.html", {"request": request})
@app.websocket("/ws/chat/{receiver_id}")
async def chat_websocket(websocket: WebSocket, receiver_id: int):
    await websocket.accept()

    # ✅ Extract token from cookies and decode current user
    token = websocket.cookies.get("access_token")
    user = auth.decode_token(token) if token else None

    if not user:
        await websocket.close()
        return

    user_id = user.id  # Assuming decode_token returns user object

    active_connections[str(user_id)] = websocket

    try:
        while True:
            data = await websocket.receive_text()

            # ✅ Save message to DB
            with database.SessionLocal() as db:
                new_message = models.Message(
                    sender_id=user_id,
                    receiver_id=receiver_id,
                    message=data,
                    timestamp=datetime.utcnow()
                )
                db.add(new_message)
                db.commit()
                db.refresh(new_message)

            # ✅ Prepare payload with timestamp
            message_payload = {
                "sender_id": user_id,
                "message": data,
                "timestamp": new_message.timestamp.strftime("%H:%M")
            }

            # ✅ Send to receiver if online
            receiver_ws = active_connections.get(str(receiver_id))
            if receiver_ws:
                await receiver_ws.send_json(message_payload)

            # ✅ Echo back to sender for instant display
            await websocket.send_json(message_payload)

    except WebSocketDisconnect:
        print(f"❌ User {user_id} disconnected")
        active_connections.pop(str(user_id), None)
    

@app.websocket("/ws/call/{receiver_id}")
async def call_signaling(websocket: WebSocket, receiver_id: int):
    await websocket.accept()

    # Get current user from token
    token = websocket.cookies.get("access_token")
    user = auth.decode_token(token) if token else None
    if not user:
        await websocket.close()
        return

    user_id = user.id
    active_connections[str(user_id)] = websocket

    try:
        while True:
            data = await websocket.receive_text()
            receiver_ws = active_connections.get(str(receiver_id))
            if receiver_ws:
                await receiver_ws.send_text(data)
    except WebSocketDisconnect:
        print(f"❌ User {user_id} disconnected from call")
        active_connections.pop(str(user_id), None)
@app.websocket("/ws/group_chat/{group_id}")
async def websocket_group_chat(websocket: WebSocket, group_id: int):
    await websocket.accept()

    # Authenticate user from cookie
    token = websocket.cookies.get("access_token")
    user = auth.decode_token(token) if token else None
    if not user:
        await websocket.close()
        return

    user_id = user.id
    key = f"group_{group_id}"
    if key not in active_connections:
        active_connections[key] = []
    active_connections[key].append(websocket)

    try:
        while True:
            message_text = await websocket.receive_text()

            # Save message to DB
            with database.SessionLocal() as db:
                msg = models.GroupMessage(
                    group_id=group_id,
                    sender_id=user_id,
                    message=message_text,
                    timestamp=datetime.utcnow()
                )
                db.add(msg)
                db.commit()
                db.refresh(msg)

                payload = {
                    "sender_id": user_id,
                    "sender_name": msg.sender.first_name,
                    "message": msg.message,
                    "timestamp": msg.timestamp.strftime("%H:%M")
                }

                for ws in active_connections[key]:
                    await ws.send_json(payload)

    except WebSocketDisconnect:
        print(f"User {user_id} left group {group_id}")
        active_connections[key].remove(websocket)
