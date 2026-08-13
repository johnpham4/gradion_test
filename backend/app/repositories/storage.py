import json
import os
import threading
from pathlib import Path
from typing import Optional, Dict, Any, Tuple, Callable
from datetime import datetime
import secrets


class StorageRepository:
    def __init__(self, base_path: str = "data"):
        self.base_path = Path(base_path)
        self.users_path = self.base_path / "users"
        self.projects_path = self.base_path / "projects"

        # Ensure directories exist
        self.users_path.mkdir(parents=True, exist_ok=True)
        self.projects_path.mkdir(parents=True, exist_ok=True)
    
    def _get_user_path(self, email: str) -> Path:
        # Sanitize email for filename
        safe_email = email.replace("@", "_at_").replace(".", "_dot_")
        return self.users_path / f"{safe_email}.json"
    
    def _get_project_path(self, project_id: str) -> Path:
        return self.projects_path / f"{project_id}.json"
    
    def _with_lock(self, resource_id: str, func):
        """Execute function with a per-resource in-process lock.

        Prevents two concurrent triggers of the same step from both passing the
        RUNNING check (the no-duplicate-calls requirement). One uvicorn process
        is a single worker, so an in-process lock is sufficient here.
        """
        if not hasattr(self, "_locks"):
            self._locks = {}
            self._lock_lock = threading.Lock()

        with self._lock_lock:
            if resource_id not in self._locks:
                self._locks[resource_id] = threading.RLock()

        lock = self._locks[resource_id]
        with lock:
            return func()
    
    def create_user(self, email: str, name: str) -> Dict[str, Any]:
        """Create a new user"""
        user_data = {
            "email": email,
            "name": name,
            "projects": []
        }
        
        user_path = self._get_user_path(email)
        with open(user_path, 'w') as f:
            json.dump(user_data, f, indent=2)
        
        return user_data
    
    def get_user(self, email: str) -> Optional[Dict[str, Any]]:
        """Get user by email"""
        user_path = self._get_user_path(email)
        
        if not user_path.exists():
            return None
        
        with open(user_path, 'r') as f:
            return json.load(f)
    
    def update_user(self, email: str, user_data: Dict[str, Any]) -> Dict[str, Any]:
        """Update user data"""
        def _update():
            user_path = self._get_user_path(email)
            with open(user_path, 'w') as f:
                json.dump(user_data, f, indent=2)
            return user_data

        return self._with_lock(email, _update)
    
    def create_project(self, project_id: str, project_data: Dict[str, Any]) -> Dict[str, Any]:
        """Create a new project"""
        project_path = self._get_project_path(project_id)
        
        # Add timestamps if not present
        if "created_at" not in project_data:
            project_data["created_at"] = datetime.utcnow().isoformat()
        
        with open(project_path, 'w') as f:
            json.dump(project_data, f, indent=2)
        
        return project_data
    
    def get_project(self, project_id: str) -> Optional[Dict[str, Any]]:
        """Get project by ID"""
        project_path = self._get_project_path(project_id)
        
        if not project_path.exists():
            return None
        
        with open(project_path, 'r') as f:
            return json.load(f)
    
    def update_project(self, project_id: str, project_data: Dict[str, Any]) -> Dict[str, Any]:
        """Update project data"""
        def _update():
            project_path = self._get_project_path(project_id)
            with open(project_path, 'w') as f:
                json.dump(project_data, f, indent=2)
            return project_data

        return self._with_lock(project_id, _update)
    
    def get_user_projects(self, email: str) -> list:
        """Get all projects for a user"""
        user = self.get_user(email)
        if not user:
            return []
        
        projects = []
        for project_id in user.get("projects", []):
            project = self.get_project(project_id)
            if project:
                projects.append(project)
        
        return projects
    
    def add_project_to_user(self, email: str, project_id: str) -> Dict[str, Any]:
        """Add project ID to user's project list"""
        user = self.get_user(email)
        if not user:
            raise ValueError(f"User {email} not found")
        
        if project_id not in user.get("projects", []):
            user["projects"].append(project_id)
        
        return self.update_user(email, user)
    
    def save_book_text(self, project_id: str, book_text: str) -> str:
        """Save book text to filesystem"""
        book_texts_path = self.base_path / "files" / "book_texts"
        book_texts_path.mkdir(parents=True, exist_ok=True)
        
        file_path = book_texts_path / f"{project_id}.txt"
        with open(file_path, 'w', encoding='utf-8') as f:
            f.write(book_text)
        
        return str(file_path)
    
    def get_book_text(self, project_id: str) -> Optional[str]:
        """Get book text from filesystem"""
        book_texts_path = self.base_path / "files" / "book_texts"
        file_path = book_texts_path / f"{project_id}.txt"
        
        if not file_path.exists():
            return None
        
        with open(file_path, 'r', encoding='utf-8') as f:
            return f.read()
    
    @staticmethod
    def generate_id() -> str:
        """Generate a unique ID"""
        return secrets.token_urlsafe(16)
    
    def get_step_states(self, project_id: str) -> Dict[str, Any]:
        """Get all step states for a project"""
        project = self.get_project(project_id)
        if not project:
            return {}
        return project.get("step_states", {})

    def atomic_transition_to_running(self, project_id: str, step: str) -> Dict[str, Any]:
        """Atomically check conditions and transition step to RUNNING (single lock)"""
        def _transition():
            project = self.get_project(project_id)
            if not project:
                raise ValueError(f"Project {project_id} not found")

            # Define step order
            steps = ["STYLE", "CHARACTERS", "PORTRAITS", "CHAPTERS", "ILLUSTRATIONS"]
            if step not in steps:
                raise ValueError(f"Invalid step name: {step}")

            step_index = steps.index(step)
            current_step = project.get("current_step", 0)

            # Check ordering
            if step_index > current_step:
                raise ValueError(f"Cannot execute {step} before completing step {steps[current_step]}")

            # Check state
            step_states = project.get("step_states", {})
            step_state = step_states.get(step)
            if step_state:
                current_status = step_state.get("status")
                if current_status == "RUNNING":
                    raise ValueError(f"Step {step} is already running")
                if current_status == "COMPLETED" and step_index == current_step:
                    raise ValueError(f"Step {step} is already completed")

            # Initialize step_states if not present
            if "step_states" not in project:
                project["step_states"] = {}

            # Transition to RUNNING
            from datetime import datetime
            project["step_states"][step] = {
                "status": "RUNNING",
                "started_at": datetime.utcnow().isoformat(),
                "completed_at": None,
                "error_message": None,
                "result": None
            }

            # Write to file directly (no nested lock)
            project_path = self._get_project_path(project_id)
            with open(project_path, 'w') as f:
                json.dump(project, f, indent=2)

            return project

        return self._with_lock(project_id, _transition)
    
    def atomic_mark_completed(self, project_id: str, step: str, result: Any) -> Dict[str, Any]:
        """Atomically mark step as COMPLETED and advance pipeline (single lock)"""
        def _mark_complete():
            project = self.get_project(project_id)
            if not project:
                raise ValueError(f"Project {project_id} not found")

            # Initialize step_states if not present
            if "step_states" not in project:
                project["step_states"] = {}

            # Mark as COMPLETED
            from datetime import datetime
            project["step_states"][step] = {
                "status": "COMPLETED",
                "started_at": project["step_states"].get(step, {}).get("started_at"),
                "completed_at": datetime.utcnow().isoformat(),
                "error_message": None,
                "result": result
            }

            # Advance current_step
            steps = ["STYLE", "CHARACTERS", "PORTRAITS", "CHAPTERS", "ILLUSTRATIONS"]
            step_index = steps.index(step)
            project["current_step"] = step_index + 1

            # Update overall_status
            statuses = ["CREATED", "STYLE_SET", "CHARACTERS_GENERATED", "PORTRAITS_GENERATED", "CHAPTERS_GENERATED", "DONE"]
            if project["current_step"] < len(statuses):
                project["overall_status"] = statuses[project["current_step"]]

            # Write to file directly (no nested lock)
            project_path = self._get_project_path(project_id)
            with open(project_path, 'w') as f:
                json.dump(project, f, indent=2)

            return project

        return self._with_lock(project_id, _mark_complete)
    
    def atomic_mark_failed(self, project_id: str, step: str, error_message: str) -> Dict[str, Any]:
        """Atomically mark step as FAILED (single lock)"""
        def _mark_failed():
            project = self.get_project(project_id)
            if not project:
                raise ValueError(f"Project {project_id} not found")

            # Initialize step_states if not present
            if "step_states" not in project:
                project["step_states"] = {}

            # Mark as FAILED
            from datetime import datetime
            project["step_states"][step] = {
                "status": "FAILED",
                "started_at": project["step_states"].get(step, {}).get("started_at"),
                "completed_at": None,
                "error_message": error_message,
                "result": None
            }

            # Do NOT advance current_step on failure

            # Write to file directly (no nested lock)
            project_path = self._get_project_path(project_id)
            with open(project_path, 'w') as f:
                json.dump(project, f, indent=2)

            return project

        return self._with_lock(project_id, _mark_failed)

    def update_step_result(self, project_id: str, step: str, result: Any) -> Dict[str, Any]:
        """Persist partial step results while a step is RUNNING (for per-item progress)"""
        def _update():
            project = self.get_project(project_id)
            if not project:
                raise ValueError(f"Project {project_id} not found")

            step_states = project.setdefault("step_states", {})
            if step not in step_states:
                raise ValueError(f"No step state found for {step}")

            step_states[step]["result"] = result

            project_path = self._get_project_path(project_id)
            with open(project_path, 'w') as f:
                json.dump(project, f, indent=2)

            return project

        return self._with_lock(project_id, _update)

    def mutate_project(self, project_id: str, mutate: Callable[[Dict[str, Any]], Dict[str, Any]]) -> Dict[str, Any]:
        """Read-modify-write a project atomically (single lock)"""
        def _mutate():
            project = self.get_project(project_id)
            if not project:
                raise ValueError(f"Project {project_id} not found")

            project = mutate(project)

            project_path = self._get_project_path(project_id)
            with open(project_path, 'w') as f:
                json.dump(project, f, indent=2)

            return project

        return self._with_lock(project_id, _mutate)
    
    def can_execute_step(self, project_id: str, step: str) -> Tuple[bool, str]:
        """Check if a step can be executed (ordering + state validation)"""
        project = self.get_project(project_id)
        if not project:
            return False, "Project not found"
        
        # Define step order
        steps = ["STYLE", "CHARACTERS", "PORTRAITS", "CHAPTERS", "ILLUSTRATIONS"]
        if step not in steps:
            return False, "Invalid step name"
        
        step_index = steps.index(step)
        current_step = project.get("current_step", 0)
        
        # Check ordering: can only execute current step or retry previous steps
        if step_index > current_step:
            return False, f"Cannot execute {step} before completing step {steps[current_step]}"
        
        # Check state: can only execute PENDING, FAILED, or STRANDED steps
        step_states = project.get("step_states", {})
        step_state = step_states.get(step)
        if step_state:
            current_status = step_state.get("status")
            if current_status == "RUNNING":
                return False, f"Step {step} is already running"
            if current_status == "COMPLETED" and step_index == current_step:
                return False, f"Step {step} is already completed"
        
        return True, "Can execute"
    
    def detect_stranded_steps(self, project_id: str, timeout_seconds: int = 300) -> list:
        """Detect steps that have been RUNNING for too long"""
        project = self.get_project(project_id)
        if not project:
            return []
        
        step_states = project.get("step_states", {})
        stranded_steps = []
        
        for step_name, step_state in step_states.items():
            if step_state.get("status") != "RUNNING":
                continue
            
            started_at = step_state.get("started_at")
            if not started_at:
                continue
            
            try:
                from datetime import datetime
                start_time = datetime.fromisoformat(started_at)
                elapsed = (datetime.utcnow() - start_time).total_seconds()
                if elapsed > timeout_seconds:
                    # Mark as stranded
                    project = self.get_project(project_id)
                    if project and project.get("step_states", {}).get(step_name):
                        project["step_states"][step_name]["status"] = "STRANDED"
                        project["step_states"][step_name]["error_message"] = f"Step stranded after {int(elapsed)} seconds"
                        self.update_project(project_id, project)
                        stranded_steps.append(step_name)
            except:
                pass
        
        return stranded_steps
    
