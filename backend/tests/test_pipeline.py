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


def test_get_project_detects_stranded_steps(test_project, test_storage):
    """Test that GET /projects/{id} marks long-RUNNING steps as STRANDED"""
    project_id = test_project["project_id"]
    user_email = test_project["data"]["user_email"]
    import secrets
    from app.api.auth import sessions
    session_token = secrets.token_urlsafe(32)
    sessions[session_token] = user_email

    # Set step to RUNNING with an old timestamp (> 5 min timeout)
    import json
    old_time = datetime.utcnow() - timedelta(seconds=400)
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

    response = client.get(
        f"/api/projects/{project_id}",
        cookies={"session_token": session_token}
    )

    assert response.status_code == 200
    data = response.json()
    assert data["step_states"]["STYLE"]["status"] == "STRANDED"


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
    # Mock GeminiClient for testing
    from unittest.mock import Mock
    mock_gemini = Mock()
    mock_gemini.upload_file.return_value = Mock(uri="file://test")
    mock_gemini.generate_text.return_value = ("watercolor style", "interaction_id")
    pipeline = PipelineService(test_storage, mock_gemini)
    
    # Execute STYLE step
    result = pipeline.execute_step(project_id, "STYLE")
    assert result["status"] == "COMPLETED"
    assert "result" in result
    
    # Check state
    project = test_storage.get_project(project_id)
    assert project["step_states"]["STYLE"]["status"] == "COMPLETED"
    assert project["current_step"] == 1


def test_pipeline_service_execute_step_failure(test_project, test_storage):
    """Test PipelineService execute_step with failure"""
    project_id = test_project["project_id"]
    # Mock GeminiClient that raises an exception
    from unittest.mock import Mock
    mock_gemini = Mock()
    mock_gemini.generate_text.side_effect = Exception("Gemini API error")
    pipeline = PipelineService(test_storage, mock_gemini)
    
    # Execute STYLE step - should fail
    with pytest.raises(Exception):
        pipeline.execute_step(project_id, "STYLE")
    
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


# Phase 4.2 Tests with mocked GeminiClient

def test_style_step_with_mocked_gemini(test_project, test_storage):
    """Test STYLE step with mocked GeminiClient"""
    from unittest.mock import Mock
    project_id = test_project["project_id"]
    
    # Mock GeminiClient
    mock_gemini = Mock()
    mock_gemini.upload_file.return_value = Mock(uri="file://test")
    mock_gemini.generate_text.side_effect = [
        ("book response", "interaction_1"),  # Book upload response
        ("watercolor style", "interaction_2")  # Style generation response
    ]
    
    pipeline = PipelineService(test_storage, mock_gemini)
    
    # Execute STYLE step
    result = pipeline.execute_step(project_id, "STYLE")
    
    assert result["status"] == "COMPLETED"
    assert "result" in result
    assert result["result"]["style"] == "watercolor style"
    
    # Verify Gemini calls
    mock_gemini.upload_file.assert_called_once()
    assert mock_gemini.generate_text.call_count == 2
    
    # Check state
    project = test_storage.get_project(project_id)
    assert project["step_states"]["STYLE"]["status"] == "COMPLETED"
    assert project["current_step"] == 1


def test_style_step_with_user_provided_style(test_project, test_storage):
    """Test STYLE step with user-provided style"""
    from unittest.mock import Mock
    project_id = test_project["project_id"]
    
    # Mock GeminiClient
    mock_gemini = Mock()
    mock_gemini.upload_file.return_value = Mock(uri="file://test")
    mock_gemini.generate_text.side_effect = [
        ("book response", "interaction_1"),  # Book upload response
        ("style acknowledged", "interaction_2")  # User style acknowledgment
    ]
    
    pipeline = PipelineService(test_storage, mock_gemini)
    
    # Execute STYLE step with user style
    result = pipeline.execute_step(project_id, "STYLE", user_style="impressionist")
    
    assert result["status"] == "COMPLETED"
    assert result["result"]["style"] == "impressionist"
    
    # Verify Gemini used the user style
    assert mock_gemini.generate_text.call_count == 2
    # Second call should acknowledge user style
    second_call_args = mock_gemini.generate_text.call_args_list[1]
    assert "impressionist" in second_call_args[0][0]


def test_characters_step_max_2_enforcement(test_project, test_storage):
    """Test CHARACTERS step enforces max 2 limit server-side"""
    from unittest.mock import Mock
    project_id = test_project["project_id"]
    
    # Mock GeminiClient to return 5 characters
    mock_gemini = Mock()
    mock_gemini.generate_structured_json.return_value = (
        [
            {"name": "Character1", "prompt": "prompt1"},
            {"name": "Character2", "prompt": "prompt2"},
            {"name": "Character3", "prompt": "prompt3"},
            {"name": "Character4", "prompt": "prompt4"},
            {"name": "Character5", "prompt": "prompt5"},
        ],
        "interaction_id"
    )
    
    pipeline = PipelineService(test_storage, mock_gemini)
    
    # Complete STYLE step first with interaction ID
    test_storage.atomic_transition_to_running(project_id, "STYLE")
    test_storage.atomic_mark_completed(project_id, "STYLE", {"style": "test style"})
    
    # Manually set the interaction ID for context chaining
    project = test_storage.get_project(project_id)
    project["gemini_interactions"] = {
        "book_interaction": "style_interaction_id",
        "last_interaction": "style_interaction_id"
    }
    test_storage.update_project(project_id, project)
    
    # Execute CHARACTERS step
    result = pipeline.execute_step(project_id, "CHARACTERS")
    
    assert result["status"] == "COMPLETED"
    # SERVER-SIDE: Should only return 2 characters despite Gemini returning 5
    assert len(result["result"]["characters"]) == 2
    assert result["result"]["characters"][0]["name"] == "Character1"
    assert result["result"]["characters"][1]["name"] == "Character2"


def test_chapters_step_max_1_enforcement(test_project, test_storage):
    """Test CHAPTERS step enforces max 1 limit server-side"""
    from unittest.mock import Mock
    import base64
    project_id = test_project["project_id"]
    
    # Mock GeminiClient to return 3 chapters
    mock_gemini = Mock()
    mock_gemini.generate_structured_json.return_value = (
        [
            {"name": "Chapter1", "prompt": "prompt1"},
            {"name": "Chapter2", "prompt": "prompt2"},
            {"name": "Chapter3", "prompt": "prompt3"},
        ],
        "interaction_id"
    )
    
    # Mock image generation for PORTRAITS step
    fake_image_bytes = b"fake_image_data" * 10
    fake_image_base64 = base64.b64encode(fake_image_bytes).decode('utf-8')
    mock_image = Mock()
    mock_image.data = fake_image_base64
    mock_gemini.generate_image.return_value = (mock_image, "image_interaction_id")
    
    pipeline = PipelineService(test_storage, mock_gemini)
    
    # Complete prerequisite steps including PORTRAITS
    test_storage.atomic_transition_to_running(project_id, "STYLE")
    test_storage.atomic_mark_completed(project_id, "STYLE", {"style": "test style"})
    test_storage.atomic_transition_to_running(project_id, "CHARACTERS")
    test_storage.atomic_mark_completed(project_id, "CHARACTERS", {"characters": []})
    test_storage.atomic_transition_to_running(project_id, "PORTRAITS")
    test_storage.atomic_mark_completed(project_id, "PORTRAITS", {"portraits": []})
    
    # Manually set the interaction ID for context chaining
    project = test_storage.get_project(project_id)
    project["gemini_interactions"] = {
        "book_interaction": "style_interaction_id",
        "last_interaction": "characters_interaction_id"
    }
    test_storage.update_project(project_id, project)
    
    # Execute CHAPTERS step
    result = pipeline.execute_step(project_id, "CHAPTERS")
    
    assert result["status"] == "COMPLETED"
    # SERVER-SIDE: Should only return 1 chapter despite Gemini returning 3
    assert len(result["result"]["chapters"]) == 1
    assert result["result"]["chapters"][0]["name"] == "Chapter1"


def test_portraits_step_max_2_enforcement(test_project, test_storage):
    """Test PORTRAITS step enforces max 2 limit server-side"""
    from unittest.mock import Mock
    import base64
    project_id = test_project["project_id"]
    
    # Mock GeminiClient with proper base64 encoded data
    fake_image_bytes = b"fake_image_data" * 10  # Make it longer
    fake_image_base64 = base64.b64encode(fake_image_bytes).decode('utf-8')
    
    mock_image = Mock()
    mock_image.data = fake_image_base64
    mock_gemini = Mock()
    mock_gemini.generate_image.return_value = (mock_image, "image_interaction_id")
    
    pipeline = PipelineService(test_storage, mock_gemini)
    
    # Complete prerequisite steps with 3 characters
    test_storage.atomic_transition_to_running(project_id, "STYLE")
    test_storage.atomic_mark_completed(project_id, "STYLE", {"style": "test style"})
    test_storage.atomic_transition_to_running(project_id, "CHARACTERS")
    test_storage.atomic_mark_completed(project_id, "CHARACTERS", {
        "characters": [
            {"name": "Char1", "prompt": "prompt1"},
            {"name": "Char2", "prompt": "prompt2"},
            {"name": "Char3", "prompt": "prompt3"},
        ]
    })
    
    # Execute PORTRAITS step
    result = pipeline.execute_step(project_id, "PORTRAITS")
    
    assert result["status"] == "COMPLETED"
    # SERVER-SIDE: Should only generate 2 portraits despite 3 characters
    assert len(result["result"]["portraits"]) == 2
    assert result["result"]["portraits"][0]["name"] == "Char1"
    assert result["result"]["portraits"][1]["name"] == "Char2"


def test_illustrations_step_max_1_enforcement(test_project, test_storage):
    """Test ILLUSTRATIONS step enforces max 1 limit server-side"""
    from unittest.mock import Mock
    import base64
    project_id = test_project["project_id"]
    
    # Mock GeminiClient with proper base64 encoded data
    fake_image_bytes = b"fake_image_data" * 10  # Make it longer
    fake_image_base64 = base64.b64encode(fake_image_bytes).decode('utf-8')
    
    mock_image = Mock()
    mock_image.data = fake_image_base64
    mock_gemini = Mock()
    mock_gemini.generate_image.return_value = (mock_image, "image_interaction_id")
    
    pipeline = PipelineService(test_storage, mock_gemini)
    
    # Complete prerequisite steps with 2 chapters
    test_storage.atomic_transition_to_running(project_id, "STYLE")
    test_storage.atomic_mark_completed(project_id, "STYLE", {"style": "test style"})
    test_storage.atomic_transition_to_running(project_id, "CHARACTERS")
    test_storage.atomic_mark_completed(project_id, "CHARACTERS", {"characters": []})
    test_storage.atomic_transition_to_running(project_id, "PORTRAITS")
    test_storage.atomic_mark_completed(project_id, "PORTRAITS", {"portraits": []})
    test_storage.atomic_transition_to_running(project_id, "CHAPTERS")
    test_storage.atomic_mark_completed(project_id, "CHAPTERS", {
        "chapters": [
            {"name": "Chapter1", "prompt": "prompt1"},
            {"name": "Chapter2", "prompt": "prompt2"},
        ]
    })
    
    # Execute ILLUSTRATIONS step
    result = pipeline.execute_step(project_id, "ILLUSTRATIONS")
    
    assert result["status"] == "COMPLETED"
    # SERVER-SIDE: Should only generate 1 illustration despite 2 chapters
    assert len(result["result"]["illustrations"]) == 1
    assert result["result"]["illustrations"][0]["name"] == "Chapter1"


def test_gemini_failure_sets_failed_state(test_project, test_storage):
    """Test that Gemini failure sets step to FAILED and doesn't advance current_step"""
    from unittest.mock import Mock
    project_id = test_project["project_id"]
    
    # Mock GeminiClient that raises an exception
    mock_gemini = Mock()
    mock_gemini.upload_file.return_value = Mock(uri="file://test")
    mock_gemini.generate_text.side_effect = Exception("Gemini API error")
    
    pipeline = PipelineService(test_storage, mock_gemini)
    
    # Try to execute STYLE step - should fail
    with pytest.raises(Exception):
        pipeline.execute_step(project_id, "STYLE")
    
    # Check state
    project = test_storage.get_project(project_id)
    assert project["step_states"]["STYLE"]["status"] == "FAILED"
    assert "Gemini API error" in project["step_states"]["STYLE"]["error_message"]
    assert project["current_step"] == 0  # Not advanced on failure


def test_failed_step_does_not_advance_current_step(test_project, test_storage):
    """Test that failed step does not advance current_step"""
    from unittest.mock import Mock
    project_id = test_project["project_id"]
    
    # Mock GeminiClient
    mock_gemini = Mock()
    mock_gemini.upload_file.return_value = Mock(uri="file://test")
    mock_gemini.generate_text.side_effect = [
        ("response", "id1"),  # STYLE succeeds
        ("response", "id2"),  # STYLE user style call succeeds
        Exception("Gemini error")  # CHARACTERS fails
    ]
    
    pipeline = PipelineService(test_storage, mock_gemini)
    
    # Execute STYLE step (succeeds)
    pipeline.execute_step(project_id, "STYLE")
    project = test_storage.get_project(project_id)
    assert project["current_step"] == 1
    
    # Try to execute CHARACTERS step (fails)
    with pytest.raises(Exception):
        pipeline.execute_step(project_id, "CHARACTERS")
    
    # Check that current_step did not advance
    project = test_storage.get_project(project_id)
    assert project["current_step"] == 1  # Still at 1, not advanced to 2


def test_successful_step_advances_current_step(test_project, test_storage):
    """Test that successful step advances current_step"""
    from unittest.mock import Mock
    project_id = test_project["project_id"]
    
    # Mock GeminiClient
    mock_gemini = Mock()
    mock_gemini.upload_file.return_value = Mock(uri="file://test")
    mock_gemini.generate_text.return_value = ("response", "interaction_id")
    mock_gemini.generate_structured_json.return_value = ([], "interaction_id")
    
    pipeline = PipelineService(test_storage, mock_gemini)
    
    # Execute STYLE step
    pipeline.execute_step(project_id, "STYLE")
    project = test_storage.get_project(project_id)
    assert project["current_step"] == 1
    
    # Execute CHARACTERS step
    pipeline.execute_step(project_id, "CHARACTERS")
    project = test_storage.get_project(project_id)
    assert project["current_step"] == 2


def test_previous_step_results_remain_intact(test_project, test_storage):
    """Test that previous step results remain intact after later steps execute"""
    from unittest.mock import Mock
    project_id = test_project["project_id"]
    
    # Mock GeminiClient
    mock_gemini = Mock()
    mock_gemini.upload_file.return_value = Mock(uri="file://test")
    mock_gemini.generate_text.return_value = ("response", "interaction_id")
    mock_gemini.generate_structured_json.return_value = ([], "interaction_id")
    
    pipeline = PipelineService(test_storage, mock_gemini)
    
    # Execute STYLE step
    pipeline.execute_step(project_id, "STYLE")
    
    # Execute CHARACTERS step
    pipeline.execute_step(project_id, "CHARACTERS")
    
    # Verify STYLE result is still intact
    project = test_storage.get_project(project_id)
    assert project["step_states"]["STYLE"]["status"] == "COMPLETED"
    assert project["step_states"]["STYLE"]["result"]["style"] == "response"
    assert project["step_states"]["CHARACTERS"]["status"] == "COMPLETED"


def test_retry_works_after_failure(test_project, test_storage):
    """Test that retry works after a failed step"""
    from unittest.mock import Mock
    project_id = test_project["project_id"]
    
    # Mock GeminiClient - fails first time, succeeds second time
    mock_gemini = Mock()
    mock_gemini.upload_file.return_value = Mock(uri="file://test")
    mock_gemini.generate_text.side_effect = [
        Exception("First failure"),  # First attempt fails on first call
    ]
    
    pipeline = PipelineService(test_storage, mock_gemini)
    
    # First attempt fails
    with pytest.raises(Exception):
        pipeline.execute_step(project_id, "STYLE")
    
    project = test_storage.get_project(project_id)
    assert project["step_states"]["STYLE"]["status"] == "FAILED"
    
    # Reset mock to succeed on retry - STYLE needs 2 calls now
    mock_gemini.generate_text.side_effect = [
        ("response", "interaction_id"),  # Book upload call
        ("response", "interaction_id")   # Style generation call
    ]
    
    # Retry the step
    pipeline.retry_step(project_id, "STYLE")
    
    # Check that step is now COMPLETED
    project = test_storage.get_project(project_id)
    assert project["step_states"]["STYLE"]["status"] == "COMPLETED"
    assert project["current_step"] == 1


def test_full_pipeline_with_mocked_gemini(test_project, test_storage):
    """Test full pipeline execution with mocked GeminiClient"""
    from unittest.mock import Mock
    import base64
    project_id = test_project["project_id"]
    
    # Mock GeminiClient with proper base64 encoded data
    fake_image_bytes = b"fake_image_data" * 10  # Make it longer
    fake_image_base64 = base64.b64encode(fake_image_bytes).decode('utf-8')
    
    mock_image = Mock()
    mock_image.data = fake_image_base64
    mock_gemini = Mock()
    mock_gemini.upload_file.return_value = Mock(uri="file://test")
    
    # Setup return values for each step
    mock_gemini.generate_text.side_effect = [
        ("book response", "book_interaction_id"),  # STYLE: book upload
        ("watercolor style", "style_interaction_id"),  # STYLE: style generation
    ]
    
    mock_gemini.generate_structured_json.side_effect = [
        ([{"name": "Char1", "prompt": "prompt1"}], "characters_interaction_id"),  # CHARACTERS
        ([{"name": "Chapter1", "prompt": "prompt1"}], "chapters_interaction_id"),  # CHAPTERS
    ]
    
    mock_gemini.generate_image.return_value = (mock_image, "image_interaction_id")
    
    pipeline = PipelineService(test_storage, mock_gemini)
    
    # Execute STYLE step
    result = pipeline.execute_step(project_id, "STYLE")
    assert result["status"] == "COMPLETED"
    
    # Reset and setup for CHARACTERS
    mock_gemini.generate_text.reset_mock()
    mock_gemini.generate_text.side_effect = []  # No text calls for CHARACTERS
    
    # Execute CHARACTERS step
    result = pipeline.execute_step(project_id, "CHARACTERS")
    assert result["status"] == "COMPLETED"
    
    # Execute PORTRAITS step
    result = pipeline.execute_step(project_id, "PORTRAITS")
    assert result["status"] == "COMPLETED"
    
    # Execute CHAPTERS step
    result = pipeline.execute_step(project_id, "CHAPTERS")
    assert result["status"] == "COMPLETED"
    
    # Execute ILLUSTRATIONS step
    result = pipeline.execute_step(project_id, "ILLUSTRATIONS")
    assert result["status"] == "COMPLETED"
    
    # Verify final state
    project = test_storage.get_project(project_id)
    assert project["current_step"] == 5
    assert project["overall_status"] == "DONE"
    
    # Verify all steps are COMPLETED
    steps = ["STYLE", "CHARACTERS", "PORTRAITS", "CHAPTERS", "ILLUSTRATIONS"]
    for step in steps:
        assert project["step_states"][step]["status"] == "COMPLETED"
