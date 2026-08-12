import pytest
from fastapi.testclient import TestClient
from main import app
from app.api.auth import sessions, storage
from app.repositories.storage import StorageRepository
from app.services.pipeline import PipelineService
import secrets
from datetime import datetime, timedelta


client = TestClient(app)


@pytest.fixture(autouse=True)
def clear_sessions():
    """Clear sessions before each test"""
    sessions.clear()
    yield
    sessions.clear()


@pytest.fixture
def test_storage():
    """Create test storage instance"""
    storage_instance = StorageRepository()
    # Clear existing test data
    if storage_instance.get_user("pipeline@example.com"):
        import os
        user_path = storage_instance._get_user_path("pipeline@example.com")
        if user_path.exists():
            os.remove(user_path)
    return storage_instance


@pytest.fixture
def authenticated_user(test_storage):
    """Create and authenticate a test user"""
    email = "pipeline@example.com"
    test_storage.create_user(email, "Pipeline Test User")
    session_token = secrets.token_urlsafe(32)
    sessions[session_token] = email
    return {"email": email, "session_token": session_token}


@pytest.fixture
def test_project(authenticated_user, test_storage):
    """Create a test project"""
    project_id = test_storage.generate_id()
    book_text = "This is a test book text for pipeline testing."
    book_text_path = test_storage.save_book_text(project_id, book_text)
    
    new_project = {
        "id": project_id,
        "user_email": authenticated_user["email"],
        "title": "Pipeline Test Project",
        "created_at": datetime.utcnow().isoformat(),
        "book_text_path": book_text_path,
        "overall_status": "CREATED",
        "current_step": 0,
        "step_states": {},
        "style": None,
        "characters": [],
        "chapters": []
    }
    
    test_storage.create_project(project_id, new_project)
    
    # Add project to user directly (avoid locking in tests)
    user = test_storage.get_user(authenticated_user["email"])
    if project_id not in user.get("projects", []):
        user["projects"].append(project_id)
    user_path = test_storage._get_user_path(authenticated_user["email"])
    import json
    with open(user_path, 'w') as f:
        json.dump(user, f, indent=2)
    
    return {"project_id": project_id, "data": new_project}


def test_initial_pipeline_state(test_project, test_storage):
    """Test that a new project has correct initial pipeline state"""
    project = test_storage.get_project(test_project["project_id"])
    assert project["current_step"] == 0
    assert project["overall_status"] == "CREATED"
    assert project["step_states"] == {}
    assert project.get("step_state") is None  # Old field should not exist


def test_multi_step_state_persistence(test_project, test_storage):
    """Test that all five step states are persisted independently"""
    project_id = test_project["project_id"]
    
    # Manually set multiple step states
    import json
    project = test_storage.get_project(project_id)
    project["step_states"] = {
        "STYLE": {
            "status": "COMPLETED",
            "started_at": datetime.utcnow().isoformat(),
            "completed_at": datetime.utcnow().isoformat(),
            "error_message": None,
            "result": {"style": "watercolor"}
        },
        "CHARACTERS": {
            "status": "COMPLETED",
            "started_at": datetime.utcnow().isoformat(),
            "completed_at": datetime.utcnow().isoformat(),
            "error_message": None,
            "result": {"characters": []}
        }
    }
    project["current_step"] = 2
    project["overall_status"] = "CHARACTERS_GENERATED"
    project_path = test_storage._get_project_path(project_id)
    with open(project_path, 'w') as f:
        json.dump(project, f, indent=2)
    
    # Reload and verify both steps persisted
    new_storage = StorageRepository()
    reloaded_project = new_storage.get_project(project_id)
    assert reloaded_project["step_states"]["STYLE"]["status"] == "COMPLETED"
    assert reloaded_project["step_states"]["CHARACTERS"]["status"] == "COMPLETED"
    assert reloaded_project["step_states"]["STYLE"]["result"]["style"] == "watercolor"


def test_step_ordering_enforcement(test_project, test_storage):
    """Test that steps must execute in correct order"""
    project_id = test_project["project_id"]
    
    # Cannot execute CHARACTERS before STYLE
    can_execute, reason = test_storage.can_execute_step(project_id, "CHARACTERS")
    assert not can_execute
    assert "STYLE" in reason
    
    # Can execute STYLE (current step)
    can_execute, reason = test_storage.can_execute_step(project_id, "STYLE")
    assert can_execute


def test_atomic_transition_to_running(test_project, test_storage):
    """Test atomic transition to RUNNING state"""
    project_id = test_project["project_id"]
    
    # Transition to RUNNING
    test_storage.atomic_transition_to_running(project_id, "STYLE")
    
    # Verify state persisted
    project = test_storage.get_project(project_id)
    assert project["step_states"]["STYLE"]["status"] == "RUNNING"
    assert project["step_states"]["STYLE"]["started_at"] is not None
    assert project["step_states"]["STYLE"]["completed_at"] is None


def test_atomic_mark_completed(test_project, test_storage):
    """Test atomic mark as COMPLETED and advance pipeline"""
    project_id = test_project["project_id"]
    
    # First transition to RUNNING
    test_storage.atomic_transition_to_running(project_id, "STYLE")
    
    # Mark as COMPLETED
    result = {"style": "watercolor"}
    test_storage.atomic_mark_completed(project_id, "STYLE", result)
    
    # Verify state
    project = test_storage.get_project(project_id)
    assert project["step_states"]["STYLE"]["status"] == "COMPLETED"
    assert project["step_states"]["STYLE"]["result"]["style"] == "watercolor"
    assert project["current_step"] == 1
    assert project["overall_status"] == "STYLE_SET"


def test_atomic_mark_failed(test_project, test_storage):
    """Test atomic mark as FAILED without advancing pipeline"""
    project_id = test_project["project_id"]
    
    # First transition to RUNNING
    test_storage.atomic_transition_to_running(project_id, "STYLE")
    
    # Mark as FAILED
    test_storage.atomic_mark_failed(project_id, "STYLE", "Mock failure")
    
    # Verify state
    project = test_storage.get_project(project_id)
    assert project["step_states"]["STYLE"]["status"] == "FAILED"
    assert project["step_states"]["STYLE"]["error_message"] == "Mock failure"
    assert project["current_step"] == 0  # Not advanced
    assert project["overall_status"] == "CREATED"


def test_previous_results_preserved_after_later_step(test_project, test_storage):
    """Test that STYLE result remains after CHARACTERS completes"""
    project_id = test_project["project_id"]
    
    # Complete STYLE
    test_storage.atomic_transition_to_running(project_id, "STYLE")
    test_storage.atomic_mark_completed(project_id, "STYLE", {"style": "watercolor"})
    
    # Complete CHARACTERS
    test_storage.atomic_transition_to_running(project_id, "CHARACTERS")
    test_storage.atomic_mark_completed(project_id, "CHARACTERS", {"characters": []})
    
    # Verify STYLE result still preserved
    project = test_storage.get_project(project_id)
    assert project["step_states"]["STYLE"]["status"] == "COMPLETED"
    assert project["step_states"]["STYLE"]["result"]["style"] == "watercolor"
    assert project["step_states"]["CHARACTERS"]["status"] == "COMPLETED"


def test_retry_preserves_previous_results(test_project, test_storage):
    """Test that retrying CHARACTERS does not erase STYLE results"""
    project_id = test_project["project_id"]
    
    # Complete STYLE
    test_storage.atomic_transition_to_running(project_id, "STYLE")
    test_storage.atomic_mark_completed(project_id, "STYLE", {"style": "watercolor"})
    
    # Fail CHARACTERS
    test_storage.atomic_transition_to_running(project_id, "CHARACTERS")
    test_storage.atomic_mark_failed(project_id, "CHARACTERS", "First failure")
    
    # Retry CHARACTERS
    test_storage.atomic_transition_to_running(project_id, "CHARACTERS")
    test_storage.atomic_mark_completed(project_id, "CHARACTERS", {"characters": []})
    
    # Verify STYLE result still preserved
    project = test_storage.get_project(project_id)
    assert project["step_states"]["STYLE"]["status"] == "COMPLETED"
    assert project["step_states"]["STYLE"]["result"]["style"] == "watercolor"
    assert project["step_states"]["CHARACTERS"]["status"] == "COMPLETED"


def test_concurrent_execution_prevention(test_project, test_storage):
    """Test that concurrent execution of the same step is prevented"""
    project_id = test_project["project_id"]
    
    # Transition to RUNNING
    test_storage.atomic_transition_to_running(project_id, "STYLE")
    
    # Try to transition again - should fail
    with pytest.raises(ValueError) as exc_info:
        test_storage.atomic_transition_to_running(project_id, "STYLE")
    
    assert "already running" in str(exc_info.value).lower()


def test_stranded_step_detection(test_project, test_storage):
    """Test detection of stranded steps (RUNNING too long)"""
    project_id = test_project["project_id"]
    
    # Set step to RUNNING with old timestamp
    old_time = datetime.utcnow() - timedelta(seconds=400)  # > 5 minutes
    import json
    
    project = test_storage.get_project(project_id)
    project["step_states"] = {
        "STYLE": {
            "status": "RUNNING",
            "started_at": old_time.isoformat(),
            "completed_at": None,
            "error_message": None,
            "result": None
        }
    }
    project_path = test_storage._get_project_path(project_id)
    with open(project_path, 'w') as f:
        json.dump(project, f, indent=2)
    
    # Detect stranded steps
    stranded_steps = test_storage.detect_stranded_steps(project_id, timeout_seconds=300)
    
    assert stranded_steps is not None
    assert "STYLE" in stranded_steps
    
    # Check step was marked as STRANDED
    project = test_storage.get_project(project_id)
    assert project["step_states"]["STYLE"]["status"] == "STRANDED"


def test_stranded_step_recovery(test_project, test_storage):
    """Test recovery of a stranded step"""
    project_id = test_project["project_id"]
    
    # Mark step as STRANDED
    import json
    project = test_storage.get_project(project_id)
    project["step_states"] = {
        "STYLE": {
            "status": "STRANDED",
            "started_at": datetime.utcnow().isoformat(),
            "completed_at": None,
            "error_message": "Stranded during execution",
            "result": None
        }
    }
    project_path = test_storage._get_project_path(project_id)
    with open(project_path, 'w') as f:
        json.dump(project, f, indent=2)
    
    # Simulate recovery by transitioning to RUNNING then COMPLETED
    test_storage.atomic_transition_to_running(project_id, "STYLE")
    test_storage.atomic_mark_completed(project_id, "STYLE", {"style": "watercolor"})
    
    # Check state was updated
    project = test_storage.get_project(project_id)
    assert project["step_states"]["STYLE"]["status"] == "COMPLETED"


def test_state_persistence_after_reload(test_project, test_storage):
    """Test that pipeline state persists after reloading from storage"""
    project_id = test_project["project_id"]
    
    # Execute STYLE step
    test_storage.atomic_transition_to_running(project_id, "STYLE")
    test_storage.atomic_mark_completed(project_id, "STYLE", {"style": "watercolor"})
    
    # Create new storage instance (simulating reload)
    new_storage = StorageRepository()
    
    # Check state persisted
    project = new_storage.get_project(project_id)
    assert project["step_states"]["STYLE"]["status"] == "COMPLETED"
    assert project["current_step"] == 1
    assert project["overall_status"] == "STYLE_SET"
    assert project["step_states"]["STYLE"]["result"]["style"] == "watercolor"


def test_full_pipeline_sequence(test_project, test_storage):
    """Test that all five steps can execute in sequence"""
    project_id = test_project["project_id"]
    
    steps = ["STYLE", "CHARACTERS", "PORTRAITS", "CHAPTERS", "ILLUSTRATIONS"]
    results = [
        {"style": "watercolor"},
        {"characters": []},
        {"portraits": []},
        {"chapters": []},
        {"illustrations": []}
    ]
    
    for i, (step, result) in enumerate(zip(steps, results)):
        test_storage.atomic_transition_to_running(project_id, step)
        test_storage.atomic_mark_completed(project_id, step, result)
        
        project = test_storage.get_project(project_id)
        assert project["current_step"] == i + 1
        assert project["step_states"][step]["status"] == "COMPLETED"
        assert project["step_states"][step]["result"] == result
    
    # Verify final state
    project = test_storage.get_project(project_id)
    assert project["current_step"] == 5
    assert project["overall_status"] == "DONE"
    assert len(project["step_states"]) == 5
    for step in steps:
        assert project["step_states"][step]["status"] == "COMPLETED"


def test_pipeline_service_execute_step(test_project, test_storage):
    """Test PipelineService execute_step with atomic operations"""
    project_id = test_project["project_id"]
    pipeline = PipelineService(test_storage)
    
    # Execute STYLE step
    result = pipeline.execute_step(project_id, "STYLE", force_fail=False)
    assert result["status"] == "COMPLETED"
    assert "result" in result
    
    # Check state
    project = test_storage.get_project(project_id)
    assert project["step_states"]["STYLE"]["status"] == "COMPLETED"
    assert project["current_step"] == 1


def test_pipeline_service_execute_step_failure(test_project, test_storage):
    """Test PipelineService execute_step with failure"""
    project_id = test_project["project_id"]
    pipeline = PipelineService(test_storage)
    
    # Execute STYLE step with failure
    with pytest.raises(Exception):
        pipeline.execute_step(project_id, "STYLE", force_fail=True)
    
    # Check state
    project = test_storage.get_project(project_id)
    assert project["step_states"]["STYLE"]["status"] == "FAILED"
    assert project["current_step"] == 0  # Not advanced


def test_get_step_states(test_project, test_storage):
    """Test get_step_states returns all step states"""
    project_id = test_project["project_id"]
    
    # Set multiple step states
    import json
    project = test_storage.get_project(project_id)
    project["step_states"] = {
        "STYLE": {"status": "COMPLETED", "result": {"style": "watercolor"}},
        "CHARACTERS": {"status": "RUNNING", "result": None}
    }
    project_path = test_storage._get_project_path(project_id)
    with open(project_path, 'w') as f:
        json.dump(project, f, indent=2)
    
    # Get all step states
    step_states = test_storage.get_step_states(project_id)
    assert len(step_states) == 2
    assert step_states["STYLE"]["status"] == "COMPLETED"
    assert step_states["CHARACTERS"]["status"] == "RUNNING"
