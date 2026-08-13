"""
Test that step results are properly returned and displayed
"""

import pytest
from app.models.project import StepState, Project
from datetime import datetime


def test_step_state_with_result():
    """Test that StepState can include result data"""
    step_state = StepState(
        step="STYLE",
        status="COMPLETED",
        started_at="2026-08-13T10:00:00",
        completed_at="2026-08-13T10:01:00",
        result={"style": "Watercolor painting style with soft brushstrokes"}
    )
    
    assert step_state.step == "STYLE"
    assert step_state.status == "COMPLETED"
    assert step_state.result is not None
    assert step_state.result["style"] == "Watercolor painting style with soft brushstrokes"


def test_step_state_with_characters_result():
    """Test that StepState can include characters result"""
    step_state = StepState(
        step="CHARACTERS",
        status="COMPLETED",
        result={
            "characters": [
                {
                    "name": "Alice",
                    "prompt": "Young woman with golden hair and blue eyes"
                },
                {
                    "name": "Bob",
                    "prompt": "Tall man with dark hair and green eyes"
                }
            ]
        }
    )
    
    assert step_state.result is not None
    assert len(step_state.result["characters"]) == 2
    assert step_state.result["characters"][0]["name"] == "Alice"


def test_step_state_with_portraits_result():
    """Test that StepState can include portraits result with image paths"""
    step_state = StepState(
        step="PORTRAITS",
        status="COMPLETED",
        result={
            "portraits": [
                {
                    "name": "Alice",
                    "prompt": "Young woman with golden hair and blue eyes",
                    "portrait_path": "data/mock_images/mock_alice_123456.png",
                    "interaction_id": "mock_interaction_1234"
                }
            ]
        }
    )
    
    assert step_state.result is not None
    assert len(step_state.result["portraits"]) == 1
    assert step_state.result["portraits"][0]["portrait_path"] is not None
    assert "mock_images" in step_state.result["portraits"][0]["portrait_path"]


def test_step_state_with_chapters_result():
    """Test that StepState can include chapters result"""
    step_state = StepState(
        step="CHAPTERS",
        status="COMPLETED",
        result={
            "chapters": [
                {
                    "name": "Chapter 1: The Beginning",
                    "prompt": "A peaceful village at sunrise with rolling hills"
                }
            ]
        }
    )
    
    assert step_state.result is not None
    assert len(step_state.result["chapters"]) == 1
    assert step_state.result["chapters"][0]["name"] == "Chapter 1: The Beginning"


def test_step_state_with_illustrations_result():
    """Test that StepState can include illustrations result"""
    step_state = StepState(
        step="ILLUSTRATIONS",
        status="COMPLETED",
        result={
            "illustrations": [
                {
                    "name": "Chapter 1: The Beginning",
                    "prompt": "A peaceful village at sunrise with rolling hills",
                    "illustration_path": "data/mock_images/mock_chapter1_789012.png",
                    "interaction_id": "mock_interaction_5678"
                }
            ]
        }
    )
    
    assert step_state.result is not None
    assert len(step_state.result["illustrations"]) == 1
    assert step_state.result["illustrations"][0]["illustration_path"] is not None


def test_step_state_error_case():
    """Test that StepState can include error information"""
    step_state = StepState(
        step="PORTRAITS",
        status="FAILED",
        error_message="Failed to generate portrait for Alice: API rate limit exceeded",
        result=None
    )
    
    assert step_state.status == "FAILED"
    assert step_state.error_message is not None
    assert "API rate limit exceeded" in step_state.error_message
    assert step_state.result is None


def test_project_with_step_states():
    """Test that Project can include step_states dictionary"""
    project = Project(
        id="test_project",
        user_email="test@example.com",
        title="Test Project",
        created_at=datetime.utcnow(),
        book_text_path="data/files/book_texts/test_project.txt",
        overall_status="STYLE_SET",
        current_step=1,
        step_states={
            "STYLE": StepState(
                step="STYLE",
                status="COMPLETED",
                result={"style": "Watercolor painting style"}
            ),
            "CHARACTERS": StepState(
                step="CHARACTERS",
                status="RUNNING",
                result=None
            )
        }
    )
    
    assert len(project.step_states) == 2
    assert project.step_states["STYLE"].status == "COMPLETED"
    assert project.step_states["STYLE"].result is not None
    assert project.step_states["CHARACTERS"].status == "RUNNING"


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
