from fastapi import APIRouter, HTTPException, status, Request, UploadFile, File, Form
from pydantic import BaseModel
from typing import Optional, List
from app.models.project import ProjectCreate, ProjectResponse, Project
from app.repositories.storage import StorageRepository
from app.services.pipeline import PipelineService
from app.clients.gemini import GeminiClient
from app.api.auth import get_current_user_email

router = APIRouter()
storage = StorageRepository()
gemini_client = GeminiClient()
pipeline = PipelineService(storage, gemini_client)


class ProjectListResponse(BaseModel):
    projects: List[ProjectResponse]


def get_session_token(request: Request) -> Optional[str]:
    """Extract session token from request"""
    return request.cookies.get("session_token")


@router.get("/projects", response_model=ProjectListResponse)
async def list_projects(request: Request):
    """List all projects for the current user"""
    session_token = get_session_token(request)
    user_email = get_current_user_email(session_token)
    
    if not user_email:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Not authenticated"
        )
    
    projects = storage.get_user_projects(user_email)
    
    # Convert to response format
    project_responses = [
        ProjectResponse(
            id=p["id"],
            user_email=p["user_email"],
            title=p["title"],
            created_at=p["created_at"],
            overall_status=p.get("overall_status", "CREATED"),
            current_step=p.get("current_step", 0)
        )
        for p in projects
    ]
    
    return ProjectListResponse(projects=project_responses)


@router.post("/projects", response_model=ProjectResponse, status_code=status.HTTP_201_CREATED)
async def create_project(
    request: Request,
    title: str = Form(...),
    book_text: Optional[str] = Form(None),
    file: Optional[UploadFile] = File(None)
):
    """Create a new project with either pasted text or file upload"""
    session_token = get_session_token(request)
    user_email = get_current_user_email(session_token)
    
    if not user_email:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Not authenticated"
        )
    
    # Validate title
    if not title or not title.strip():
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Project title is required"
        )
    
    # Validate that either text or file is provided
    if not book_text and not file:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Either book text or file upload is required"
        )
    
    # Process book text
    final_book_text = ""
    if file:
        # Validate file is .txt
        if not file.filename or not file.filename.endswith('.txt'):
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Only .txt files are supported"
            )
        
        # Read file content
        content = await file.read()
        final_book_text = content.decode('utf-8')
    elif book_text:
        final_book_text = book_text
    
    # Validate book text length
    if not final_book_text or not final_book_text.strip():
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Book text is required"
        )
    
    if len(final_book_text.strip()) < 10:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Book text must be at least 10 characters"
        )
    
    # Generate project ID
    project_id = storage.generate_id()
    
    # Save book text to filesystem
    book_text_path = storage.save_book_text(project_id, final_book_text)
    
    # Create project data
    from datetime import datetime
    new_project = {
        "id": project_id,
        "user_email": user_email,
        "title": title.strip(),
        "created_at": datetime.utcnow().isoformat(),
        "book_text_path": book_text_path,
        "overall_status": "CREATED",
        "current_step": 0,
        "step_states": {},
        "style": None,
        "characters": [],
        "chapters": []
    }
    
    # Save project
    storage.create_project(project_id, new_project)
    
    # Add project to user's project list
    storage.add_project_to_user(user_email, project_id)
    
    return ProjectResponse(
        id=new_project["id"],
        user_email=new_project["user_email"],
        title=new_project["title"],
        created_at=new_project["created_at"],
        overall_status=new_project["overall_status"],
        current_step=new_project["current_step"]
    )


@router.get("/projects/{project_id}", response_model=Project)
async def get_project(project_id: str, request: Request):
    """Get project details"""
    session_token = get_session_token(request)
    user_email = get_current_user_email(session_token)
    
    if not user_email:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Not authenticated"
        )
    
    project = storage.get_project(project_id)
    
    if not project:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Project not found"
        )
    
    # Check if user owns this project
    if project.get("user_email") != user_email:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Access denied"
        )
    
    # Add book text content to response
    book_text = storage.get_book_text(project_id)
    if book_text:
        project["book_text"] = book_text
    
    return Project(**project)


@router.post("/projects/{project_id}/steps/{step}")
async def trigger_step(project_id: str, step: str, request: Request):
    """Trigger execution of a pipeline step"""
    session_token = get_session_token(request)
    user_email = get_current_user_email(session_token)
    
    if not user_email:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Not authenticated"
        )
    
    project = storage.get_project(project_id)
    if not project:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Project not found"
        )
    
    # Check ownership
    if project.get("user_email") != user_email:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Access denied"
        )
    
    # Validate step name
    valid_steps = ["STYLE", "CHARACTERS", "PORTRAITS", "CHAPTERS", "ILLUSTRATIONS"]
    if step not in valid_steps:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Invalid step. Must be one of: {', '.join(valid_steps)}"
        )
    
    try:
        result = pipeline.execute_step(project_id, step)
        return result
    except ValueError as e:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail=str(e)
        )
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Step execution failed: {str(e)}"
        )


@router.get("/projects/{project_id}/status")
async def get_pipeline_status(project_id: str, request: Request):
    """Get current pipeline status for a project"""
    session_token = get_session_token(request)
    user_email = get_current_user_email(session_token)
    
    if not user_email:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Not authenticated"
        )
    
    project = storage.get_project(project_id)
    if not project:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Project not found"
        )
    
    # Check ownership
    if project.get("user_email") != user_email:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Access denied"
        )
    
    # Detect stranded steps
    stranded_info = pipeline.detect_and_recover_stranded(project_id)
    
    return {
        "project_id": project_id,
        "current_step": project.get("current_step", 0),
        "overall_status": project.get("overall_status", "CREATED"),
        "step_state": project.get("step_state"),
        "stranded_info": stranded_info
    }


@router.post("/projects/{project_id}/steps/{step}/retry")
async def retry_step(project_id: str, step: str, request: Request):
    """Retry a FAILED or STRANDED step"""
    session_token = get_session_token(request)
    user_email = get_current_user_email(session_token)
    
    if not user_email:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Not authenticated"
        )
    
    project = storage.get_project(project_id)
    if not project:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Project not found"
        )
    
    # Check ownership
    if project.get("user_email") != user_email:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Access denied"
        )
    
    # Validate step name
    valid_steps = ["STYLE", "CHARACTERS", "PORTRAITS", "CHAPTERS", "ILLUSTRATIONS"]
    if step not in valid_steps:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Invalid step. Must be one of: {', '.join(valid_steps)}"
        )
    
    try:
        result = pipeline.retry_step(project_id, step)
        return result
    except ValueError as e:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail=str(e)
        )
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Step retry failed: {str(e)}"
        )