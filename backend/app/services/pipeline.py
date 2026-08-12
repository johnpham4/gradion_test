from typing import Optional, Dict, Any
from datetime import datetime
from app.services.storage import StorageService


class PipelineService:
    """Service for managing pipeline execution with deterministic mock executors"""
    
    def __init__(self, storage: StorageService):
        self.storage = storage
        self.timeout_seconds = 300  # 5 minutes default timeout
    
    def execute_step(self, project_id: str, step: str, force_fail: bool = False) -> Dict[str, Any]:
        """Execute a pipeline step with deterministic mock behavior"""
        # Atomically transition to RUNNING (checks ordering, state, persists RUNNING)
        self.storage.atomic_transition_to_running(project_id, step)
        
        try:
            # Execute the step with deterministic mock behavior
            result = self._mock_execute_step(project_id, step, force_fail)
            
            # Atomically mark as COMPLETED and advance pipeline
            self.storage.atomic_mark_completed(project_id, step, result)
            
            return {"status": "COMPLETED", "result": result}
            
        except Exception as e:
            # Atomically mark as FAILED
            self.storage.atomic_mark_failed(project_id, step, str(e))
            raise
    
    def _mock_execute_step(self, project_id: str, step: str, force_fail: bool = False) -> Dict[str, Any]:
        """Deterministic mock executor for testing (no Gemini calls)"""
        if force_fail:
            raise Exception(f"Mock failure for step {step}")
        
        # Return deterministic mock results based on step
        mock_results = {
            "STYLE": {"style": "watercolor illustration style"},
            "CHARACTERS": {
                "characters": [
                    {"name": "Alice", "prompt": "Alice as a young girl with blonde hair"},
                    {"name": "Bob", "prompt": "Bob as a curious boy with brown hair"}
                ]
            },
            "PORTRAITS": {
                "portraits": [
                    {"name": "Alice", "portrait_path": "/mock/alice_portrait.png"},
                    {"name": "Bob", "portrait_path": "/mock/bob_portrait.png"}
                ]
            },
            "CHAPTERS": {
                "chapters": [
                    {"name": "Chapter 1", "prompt": "Alice falls down the rabbit hole"},
                    {"name": "Chapter 2", "prompt": "Alice meets the Cheshire Cat"}
                ]
            },
            "ILLUSTRATIONS": {
                "illustrations": [
                    {"chapter": "Chapter 1", "illustration_path": "/mock/chapter1.png"},
                    {"chapter": "Chapter 2", "illustration_path": "/mock/chapter2.png"}
                ]
            }
        }
        
        return mock_results.get(step, {})
    
    def retry_step(self, project_id: str, step: str) -> Dict[str, Any]:
        """Retry a FAILED or STRANDED step"""
        project = self.storage.get_project(project_id)
        if not project:
            raise ValueError("Project not found")
        
        step_state = project.get("step_state")
        if not step_state:
            raise ValueError("No step state found")
        
        current_status = step_state.get("status")
        if current_status not in ["FAILED", "STRANDED"]:
            raise ValueError(f"Cannot retry step with status {current_status}")
        
        if step_state.get("step") != step:
            raise ValueError(f"Current step is {step_state.get('step')}, cannot retry {step}")
        
        # Execute the step again
        return self.execute_step(project_id, step, force_fail=False)
    
    def detect_and_recover_stranded(self, project_id: str) -> Optional[Dict[str, Any]]:
        """Detect stranded steps and return recovery info (user must explicitly retry)"""
        stranded_steps = self.storage.detect_stranded_steps(project_id, self.timeout_seconds)
        if stranded_steps:
            return {
                "stranded_steps": stranded_steps,
                "message": f"Steps {stranded_steps} are stranded and can be retried"
            }
        return None
