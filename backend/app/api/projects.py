from fastapi import APIRouter, HTTPException, status, Request, UploadFile, File, Form
from fastapi.responses import FileResponse
from pydantic import BaseModel
from typing import Optional, List, Dict
from pathlib import Path
from loguru import logger
from app.models.project import ProjectCreate, ProjectResponse, Project, StepState
from app.repositories.storage import StorageRepository
from app.services.pipeline import PipelineService
from app.clients.gemini import GeminiClient
from app.api.auth import get_current_user_email

router = APIRouter()
storage = StorageRepository()
gemini_client = None  # Lazy initialization
pipeline = None  # Lazy initialization

def get_gemini_client():
    global gemini_client, pipeline
    if gemini_client is None:
        try:
            gemini_client = GeminiClient()
            pipeline = PipelineService(storage, gemini_client)
        except Exception as e:
            logger.error(f"Failed to initialize Gemini client: {e}")
            raise
    return gemini_client, pipeline


class ProjectListResponse(BaseModel):
    projects: List[ProjectResponse]


def get_session_token(request: Request) -> Optional[str]:
    """Extract session token from request"""
    return request.cookies.get("session_token")


def convert_step_states(step_states: Dict[str, Dict]) -> Dict[str, StepState]:
    """Convert raw step_states dicts to StepState models (tolerates legacy shapes)"""
    result = {}
    for step_name, step_data in step_states.items():
        try:
            result[step_name] = StepState(**step_data)
        except Exception:
            result[step_name] = StepState(
                step=step_name,
                status=step_data.get("status", "UNKNOWN"),
                started_at=step_data.get("started_at"),
                completed_at=step_data.get("completed_at"),
                error_message=step_data.get("error_message"),
                result=step_data.get("result"),
            )
    return result


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
    """Get project details with step results"""
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
    
    # Ensure step_states is included
    if "step_states" not in project:
        project["step_states"] = {}
    
    # Convert step_states dict to proper format
    project["step_states"] = convert_step_states(project.get("step_states", {}))
    
    return Project(**project)


@router.post("/projects/{project_id}/steps/{step}")
def trigger_step(
    project_id: str,
    step: str,
    request: Request,
    user_style: Optional[str] = None
):
    """Trigger execution of a pipeline step.

    Sync (non-async) on purpose: FastAPI runs sync handlers in a threadpool,
    so the event loop stays free and /status polling keeps responding while a
    step is running (Gemini calls can take tens of seconds).
    """
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
        # Initialize pipeline if not already done
        _, pipeline_instance = get_gemini_client()
        result = pipeline_instance.execute_step(project_id, step, user_style=user_style)
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
    """Get current pipeline status for a project with step results"""
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
    
    # Detect stranded steps (storage-only; does not require Gemini initialization)
    stranded_info = storage.detect_stranded_steps(project_id, timeout_seconds=300)
    stranded_payload = None
    if stranded_info:
        stranded_payload = {
            "stranded_steps": stranded_info,
            "message": f"Steps {stranded_info} are stranded and can be retried"
        }
    
    # Convert step_states to proper format
    step_states_dict = convert_step_states(project.get("step_states", {}))
    
    return {
        "project_id": project_id,
        "current_step": project.get("current_step", 0),
        "overall_status": project.get("overall_status", "CREATED"),
        "step_states": step_states_dict,
        "stranded_info": stranded_payload
    }


@router.post("/projects/{project_id}/steps/{step}/retry")
def retry_step(project_id: str, step: str, request: Request):
    """Retry a FAILED or STRANDED step (sync for threadpool, see trigger_step)."""
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
        _, pipeline_instance = get_gemini_client()
        result = pipeline_instance.retry_step(project_id, step)
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


@router.get("/images/{image_path:path}")
async def get_image(image_path: str, request: Request):
    """Serve generated images from the data directory"""
    session_token = get_session_token(request)
    user_email = get_current_user_email(session_token)
    
    if not user_email:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Not authenticated"
        )
    
    # Security: Only allow images from data directory
    base_path = Path("data")
    full_path = base_path / image_path
    
    # Resolve to prevent directory traversal
    try:
        full_path = full_path.resolve()
        base_path = base_path.resolve()
    except:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Invalid path"
        )
    
    # Check if the path is within base directory
    try:
        full_path.relative_to(base_path)
    except ValueError:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Access denied to this file"
        )
    
    if not full_path.exists():
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Image not found"
        )
    
    return FileResponse(full_path)