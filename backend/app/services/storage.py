import json
import os
import threading
from pathlib import Path
from typing import Optional, Dict, Any
from datetime import datetime
import secrets


class StorageService:
    def __init__(self, base_path: str = "data"):
        self.base_path = Path(base_path)
        self.users_path = self.base_path / "users"
        self.projects_path = self.base_path / "projects"
        self.locks_path = self.base_path / "locks"
        
        # Ensure directories exist
        self.users_path.mkdir(parents=True, exist_ok=True)
        self.projects_path.mkdir(parents=True, exist_ok=True)
        self.locks_path.mkdir(parents=True, exist_ok=True)
    
    def _get_user_path(self, email: str) -> Path:
        # Sanitize email for filename
        safe_email = email.replace("@", "_at_").replace(".", "_dot_")
        return self.users_path / f"{safe_email}.json"
    
    def _get_project_path(self, project_id: str) -> Path:
        return self.projects_path / f"{project_id}.json"
    
    def _get_lock_path(self, resource_id: str) -> Path:
        return self.locks_path / f"{resource_id}.lock"
    
    def _with_lock(self, resource_id: str, func):
        """Execute function with file-based write lock (cross-platform)"""
        import threading
        
        # Use in-memory locks for simplicity in this assessment scope
        # For production, use proper file locking libraries
        if not hasattr(self, '_locks'):
            self._locks = {}
            self._lock_lock = threading.Lock()
        
        with self._lock_lock:
            if resource_id not in self._locks:
                self._locks[resource_id] = threading.Lock()
        
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
        def _add():
            user = self.get_user(email)
            if not user:
                raise ValueError(f"User {email} not found")
            
            if project_id not in user.get("projects", []):
                user["projects"].append(project_id)
            
            return self.update_user(email, user)
        
        return self._with_lock(email, _add)
    
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