import os
import shutil
from typing import List, Optional
from django import apps
from fastapi import APIRouter, Depends, File, Form, HTTPException, Query, Request, UploadFile, WebSocket
from fastapi.responses import RedirectResponse, HTMLResponse
from fastapi.staticfiles import StaticFiles
from fastapi.templating import Jinja2Templates
from sqlalchemy.orm import Session


from backend.signaling import connect_user, disconnect_user, forward_signal
from . import crud, schemas, database, utils , models
from . import auth
from jose import jwt
from datetime import datetime,timedelta
from fastapi import status
from fastapi import APIRouter, Response
from fastapi.responses import RedirectResponse
from .auth import get_current_user  # ✅ make sure this path is correct based on your project
from .models import User



router = APIRouter()
templates = Jinja2Templates(directory="backend/templates")


# Dependency
def get_db():
    db = database.SessionLocal()
    try:
        yield db
    finally:
        db.close()

@router.post("/register", response_model=schemas.StandardResponse)
def register_user(
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

    existing_user = crud.get_user_by_email(db, email=user.email)
    if existing_user:
        return {
            "isSuccess": False,
            "data": None,
            "errorCode": 1001,
            "errorMessage": "Email already registered"
        }

    hashed_password = utils.hash_password(user.password)
    user.password = hashed_password
    created_user = crud.create_user(db, user)

    return {
        "isSuccess": True,
        "data": schemas.UserResponse(**created_user.__dict__),
        "errorCode": 0,
        "errorMessage": ""
    }

# ✅ Updated Login Route: redirect to /dashboard
@router.post("/login", response_class=HTMLResponse)
def login_form(
    request: Request,
    email: str = Form(...),
    password: str = Form(...),
    db: Session = Depends(get_db)
):
    user = crud.get_user_by_email(db, email)
    if not user or not utils.verify_password(password, user.hashed_password):
        return templates.TemplateResponse("login.html", {"request": request, "message": "Invalid credentials"})

    # Create token
    token_data = {
        "sub": str(user.id),
        "exp": datetime.utcnow() + timedelta(minutes=60)
    }
    token = jwt.encode(token_data, auth.SECRET_KEY, algorithm=auth.ALGORITHM)

    # Set token in cookie
    response = RedirectResponse(url="/dashboard", status_code=status.HTTP_303_SEE_OTHER)
    response.set_cookie(key="access_token", value=token, httponly=True, path="/")
    return response


@router.get("/dashboard", response_class=HTMLResponse)
async def dashboard(
    request: Request,
    db: Session = Depends(database.get_db),
    current_user=Depends(auth.get_current_user)
):
    try:
        users = db.query(models.User).all()
        groups = db.query(models.Group).filter(models.Group.members.any(id=current_user.id)).all()  # ✅ Get user's groups
        return templates.TemplateResponse("dashboard.html", {
            "request": request,
            "users": users,
            "groups": groups,
            "current_user": current_user
        })
    except Exception as e:
        return HTMLResponse(f"<h2>Error: {e}</h2>", status_code=500)


@router.get("/chat/{receiver_id}", response_class=HTMLResponse)
def chat_page(
    receiver_id: int,
    request: Request,
    db: Session = Depends(get_db),
    current_user: models.User = Depends(auth.get_current_user)
):
    receiver = db.query(models.User).filter(models.User.id == receiver_id).first()
    if not receiver:
        raise HTTPException(status_code=404, detail="User not found")

    messages = db.query(models.Message).filter(
        ((models.Message.sender_id == current_user.id) & (models.Message.receiver_id == receiver_id)) |
        ((models.Message.sender_id == receiver_id) & (models.Message.receiver_id == current_user.id))
    ).order_by(models.Message.timestamp).all()

    return templates.TemplateResponse("chat_page.html", {
        "request": request,
        "receiver": receiver,
        "messages": messages,
        "current_user": current_user,
        "current_user_id": current_user.id   # ✅ pass user id for JS
    })


# --- Chat Send Message ---
@router.post("/chat/{receiver_id}", response_class=HTMLResponse)
def send_message(
    receiver_id: int,
    request: Request,
    message: str = Form(...),
    db: Session = Depends(get_db),
    current_user: models.User = Depends(auth.get_current_user)
):
    try:
        print("✅ SEND MESSAGE")
        print("Receiver ID:", receiver_id)
        print("Sender ID:", current_user.id)
        print("Message:", message)

        receiver = db.query(models.User).filter(models.User.id == receiver_id).first()
        if not receiver:
            return HTMLResponse("<h2>Receiver not found</h2>", status_code=404)

        new_message = models.Message(
            sender_id=current_user.id,
            receiver_id=receiver.id,
            message=message,
            timestamp=datetime.utcnow()
        )
        db.add(new_message)
        db.commit()

        # ✅ Redirect back to chat page
        return RedirectResponse(url=f"/chat/{receiver_id}", status_code=303)

    except Exception as e:
        print("❌ Error in send_message:", str(e))
        return HTMLResponse(f"<h2>❌ Error: {e}</h2>", status_code=500)
    


@router.post("/create_group", response_class=HTMLResponse)
def create_group(
    request: Request,
    group_name: str = Form(...),
    members: Optional[List[int]] = Form(None),
    db: Session = Depends(get_db),
    current_user: models.User = Depends(auth.get_current_user)
):
    if not members:
        users = db.query(models.User).all()
        return templates.TemplateResponse("create_group.html", {
            "request": request,
            "users": users,
            "current_user": current_user,
            "error": "❗ Please choose at least one member to create a group."
        })

    group = models.Group(name=group_name, created_by=current_user.id)
    db.add(group)
    db.commit()
    db.refresh(group)

    for member_id in members:
        member = db.query(models.User).get(member_id)
        if member:
            group.members.append(member)

    current_user_merged = db.merge(current_user)
    group.members.append(current_user_merged)

    db.commit()

    # 👇 Redirect to dashboard instead of group chat
    return RedirectResponse(url="/dashboard", status_code=303)

@router.get("/group_chat/{group_id}", response_class=HTMLResponse)
def group_chat(group_id: int, request: Request, db: Session = Depends(get_db), current_user=Depends(auth.get_current_user)):
    group = db.query(models.Group).filter(models.Group.id == group_id).first()
    messages = db.query(models.GroupMessage).filter(models.GroupMessage.group_id == group_id).order_by(models.GroupMessage.timestamp).all()

    return templates.TemplateResponse("group_chat.html", {
        "request": request,
        "group": group,
        "messages": messages,
        "current_user": current_user
    })


@router.get("/start_create_group", response_class=HTMLResponse)
def show_group_user_selector(
    request: Request,
    db: Session = Depends(get_db),
    current_user: models.User = Depends(auth.get_current_user)
):
    users = db.query(models.User).all()
    return templates.TemplateResponse("create_group.html", {
        "request": request,
        "users": users,
        "current_user": current_user
    })


@router.get("/group/{group_id}/add_members", response_class=HTMLResponse)
def show_add_members(group_id: int, request: Request, db: Session = Depends(get_db), current_user=Depends(auth.get_current_user)):
    group = db.query(models.Group).filter(models.Group.id == group_id).first()
    users = db.query(models.User).all()
    current_member_ids = [member.id for member in group.members]
    
    return templates.TemplateResponse("add_members.html", {
        "request": request,
        "group": group,
        "users": users,
        "current_user": current_user,
        "current_member_ids": current_member_ids
    })


@router.post("/group/{group_id}/add_members")
def update_group_members(
    group_id: int,
    members: List[int] = Form(...),
    db: Session = Depends(get_db),
    current_user: models.User = Depends(auth.get_current_user)
):
    group = db.query(models.Group).filter(models.Group.id == group_id).first()
    group.members.clear()  # Remove all current members

    # Add selected members back
    for user_id in members:
        user = db.query(models.User).filter(models.User.id == user_id).first()
        if user:
            group.members.append(user)

    # Always re-add current user (group creator or participant)
    group.members.append(db.merge(current_user))

    db.commit()
    return RedirectResponse(url=f"/group_chat/{group_id}", status_code=303)


@router.get("/logout")
def logout(response: Response):
    response = RedirectResponse(url="/login", status_code=302)
    response.delete_cookie(key="access_token", path="/", httponly=True)
    return response


@router.post("/upload_profile_photo")
async def upload_profile_photo(
    file: UploadFile = File(...),
    db: Session = Depends(get_db),
    current_user: models.User = Depends(auth.get_current_user)
):
    contents = await file.read()
    mime_type = file.content_type

    existing = db.query(models.UserPhoto).filter_by(user_id=current_user.id).first()
    if existing:
        existing.photo = contents
        existing.mime_type = mime_type
    else:
        photo = models.UserPhoto(user_id=current_user.id, photo=contents, mime_type=mime_type)
        db.add(photo)

    db.commit()
    return {"detail": "Photo uploaded"}

@router.get("/user/photo/{user_id}")
def get_user_photo(user_id: int, db: Session = Depends(get_db)):
    photo = db.query(models.UserPhoto).filter_by(user_id=user_id).first()
    if photo:
        return Response(content=photo.photo, media_type=photo.mime_type)
    raise HTTPException(status_code=404, detail="User photo not found")

# Upload route
@router.post("/upload_group_photo/{group_id}")
async def upload_group_photo(group_id: int, file: UploadFile = File(...), db: Session = Depends(get_db)):
    group = db.query(models.Group).filter(models.Group.id == group_id).first()
    if not group:
        raise HTTPException(status_code=404, detail="Group not found")

    contents = await file.read()
    mime_type = file.content_type

    existing = db.query(models.GroupPhoto).filter_by(group_id=group_id).first()
    if existing:
        existing.photo = contents
        existing.mime_type = mime_type
    else:
        new_photo = models.GroupPhoto(group_id=group_id, photo=contents, mime_type=mime_type)
        db.add(new_photo)

    db.commit()
    return {"message": "Group photo uploaded"}

# Serve image
@router.get("/group/photo/{group_id}")
def get_group_photo(group_id: int, db: Session = Depends(get_db)):
    photo = db.query(models.GroupPhoto).filter_by(group_id=group_id).first()
    if not photo:
        raise HTTPException(status_code=404, detail="Photo not found")
    return Response(content=photo.photo, media_type=photo.mime_type)

@router.get("/audio_call/{receiver_id}", response_class=HTMLResponse)
def audio_call(
    receiver_id: int,
    caller: bool = Query(False),
    request: Request = None,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    receiver = db.query(User).filter(User.id == receiver_id).first()
    if not receiver:
        return HTMLResponse(content="Receiver not found", status_code=404)

    return templates.TemplateResponse("audio_call.html", {
        "request": request,
        "receiver": receiver,
        "caller": caller,
        "current_user": current_user
    })
@router.get("/audio_call/{user_id}", response_class=HTMLResponse)
def audio_call(
    user_id: int,
    caller: bool = Query(False),  # /audio_call/2?caller=true
    request: Request = None,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    receiver = db.query(models.User).filter(models.User.id == user_id).first()
    if not receiver:
        return HTMLResponse(content="Receiver not found", status_code=404)

    return templates.TemplateResponse("audio_call.html", {
        "request": request,
        "receiver": receiver,
        "caller": caller,
        "current_user": current_user
    })
