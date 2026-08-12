from typing import Optional, Dict, Any
from datetime import datetime
from app.repositories.storage import StorageRepository
from app.clients.gemini import GeminiClient


class PipelineService:
    """Service for managing pipeline execution with Gemini integration"""
    
    # Assessment limits
    MAX_CHARACTERS = 2
    MAX_CHAPTERS = 1
    
    def __init__(self, storage: StorageRepository, gemini_client: Optional[GeminiClient] = None):
        self.storage = storage
        self.gemini_client = gemini_client
        self.timeout_seconds = 300  # 5 minutes default timeout
    
    def execute_step(self, project_id: str, step: str, user_style: Optional[str] = None) -> Dict[str, Any]:
        """Execute a pipeline step with Gemini integration"""
        # Atomically transition to RUNNING (checks ordering, state, persists RUNNING)
        self.storage.atomic_transition_to_running(project_id, step)
        
        try:
            # Execute the step with Gemini
            result = self._execute_gemini_step(project_id, step, user_style)
            
            # Atomically mark as COMPLETED and advance pipeline
            self.storage.atomic_mark_completed(project_id, step, result)
            
            return {"status": "COMPLETED", "result": result}
            
        except Exception as e:
            # Atomically mark as FAILED
            self.storage.atomic_mark_failed(project_id, step, str(e))
            raise
    
    def _execute_gemini_step(self, project_id: str, step: str, user_style: Optional[str] = None) -> Dict[str, Any]:
        """Execute a pipeline step using Gemini"""
        project = self.storage.get_project(project_id)
        if not project:
            raise ValueError("Project not found")
        
        # Map step to executor
        step_executors = {
            "STYLE": self._execute_style_step,
            "CHARACTERS": self._execute_characters_step,
            "PORTRAITS": self._execute_portraits_step,
            "CHAPTERS": self._execute_chapters_step,
            "ILLUSTRATIONS": self._execute_illustrations_step,
        }
        
        executor = step_executors.get(step)
        if not executor:
            raise ValueError(f"Unknown step: {step}")
        
        return executor(project_id, project, user_style)
    
    def _execute_style_step(self, project_id: str, project: Dict[str, Any], user_style: Optional[str]) -> Dict[str, Any]:
        """Execute STYLE step: generate or accept art style"""
        book_text = self._get_book_text(project_id, project)
        if not book_text:
            raise ValueError("Book text not found")
        
        # Upload book to Gemini File API for context
        book_file = self.gemini_client.upload_file(project["book_text_path"], "book.txt")
        
        # Start chat with book (notebook pattern)
        book_response, book_interaction_id = self.gemini_client.generate_text(
            "Here's a book, to illustrate using Gemini. Don't say anything for now, instructions will follow."
        )
        
        if user_style:
            # User provided style - inform Gemini about it
            style_response, style_interaction_id = self.gemini_client.generate_text(
                f'The art style will be: "{user_style}". Keep that in mind when generating future prompts. Keep quiet for now, instructions will follow.',
                previous_interaction_id=book_interaction_id
            )
            style = user_style
            last_interaction_id = style_interaction_id
        else:
            # Generate style from book using notebook prompt
            style_prompt = "Can you define an art style that would fit the story but with a twist? Just give us the prompt for the art style that will be added to future prompts."
            style, style_interaction_id = self.gemini_client.generate_text(style_prompt, previous_interaction_id=book_interaction_id)
            last_interaction_id = style_interaction_id
        
        # Store interaction IDs for context chaining
        self._store_interaction_id(project_id, "book_interaction", book_interaction_id)
        self._store_interaction_id(project_id, "last_interaction", last_interaction_id)
        
        return {"style": style}
    
    def _execute_characters_step(self, project_id: str, project: Dict[str, Any], _user_style: Optional[str]) -> Dict[str, Any]:
        """Execute CHARACTERS step: extract max 2 adult characters with prompts"""
        last_interaction_id = self._get_interaction_id(project_id, "last_interaction")
        if not last_interaction_id:
            raise ValueError("No previous interaction found. Complete STYLE step first.")
        
        # Generate structured character data using notebook schema
        schema = {
            "type": "array",
            "items": {
                "type": "object",
                "properties": {
                    "name": {"type": "string"},
                    "prompt": {"type": "string"}
                },
                "required": ["name", "prompt"]
            }
        }
        
        # Use notebook prompt for character generation
        prompt = (
            "Can you describe the main characters (only the adults) and prepare a prompt describing them "
            "with as much details as possible (use the descriptions from the book) so Gemini can generate "
            "images of them? Each prompt should be at least 50 words."
        )
        
        characters_data, characters_interaction_id = self.gemini_client.generate_structured_json(
            prompt,
            schema,
            previous_interaction_id=last_interaction_id
        )
        
        # SERVER-SIDE: Enforce max 2 characters limit
        characters = characters_data[:self.MAX_CHARACTERS]
        
        # Store interaction ID for context chaining
        self._store_interaction_id(project_id, "characters_interaction", characters_interaction_id)
        self._store_interaction_id(project_id, "last_interaction", characters_interaction_id)
        
        return {"characters": characters}
    
    def _execute_portraits_step(self, project_id: str, project: Dict[str, Any], _user_style: Optional[str]) -> Dict[str, Any]:
        """Execute PORTRAITS step: generate portraits for each character"""
        step_states = project.get("step_states", {})
        characters_step = step_states.get("CHARACTERS", {})
        characters_result = characters_step.get("result", {})
        characters = characters_result.get("characters", [])
        
        if not characters:
            raise ValueError("No characters found. Complete CHARACTERS step first.")
        
        # Get style for consistency
        style_step = step_states.get("STYLE", {})
        style_result = style_step.get("result", {})
        style = style_result.get("style", "")
        
        # SERVER-SIDE: Enforce max 2 portraits limit
        characters = characters[:self.MAX_CHARACTERS]
        
        # System instructions from notebook
        system_instructions = """
        There must be no text on the image, it should not look like a cover page.
        It should be a full illustration with no borders, titles, nor description.
        Unless asked otherwise, stay family-friendly with uplifting colors.
        Each produced should be a simple image, no panels.
        """
        
        # For image generation, we start fresh without previous text context
        # but we include the style in the prompt
        image_context_id = None
        
        portraits = []
        last_image_interaction_id = None
        for character in characters:
            # Generate portrait for each character
            portrait_prompt = f"Create an illustration for {character['name']} following this description: {character['prompt']}"
            
            try:
                # Generate image with style and system instructions
                full_prompt = f"{system_instructions}\n\nFollow this style: \"{style}\"\n\n{portrait_prompt}"
                image, image_interaction_id = self.gemini_client.generate_image(
                    full_prompt,
                    aspect_ratio="9:16"
                )
                
                # Save image to disk
                portrait_path = self._save_image(project_id, f"portrait_{character['name']}.png", image)
                
                portraits.append({
                    "name": character["name"],
                    "prompt": character["prompt"],
                    "portrait_path": portrait_path
                })
                
                # Keep track of the last interaction ID for consistency
                last_image_interaction_id = image_interaction_id
                
            except Exception as e:
                # Image generation requires billing - surface clear error
                raise Exception(f"Portrait generation requires billing. Failed for {character['name']}: {str(e)}")
        
        # Store the image interaction ID for consistency in ILLUSTRATIONS step
        if last_image_interaction_id:
            self._store_interaction_id(project_id, "image_context", last_image_interaction_id)
        
        return {"portraits": portraits}
    
    def _execute_chapters_step(self, project_id: str, project: Dict[str, Any], _user_style: Optional[str]) -> Dict[str, Any]:
        """Execute CHAPTERS step: generate prompts for max 1 chapter"""
        last_interaction_id = self._get_interaction_id(project_id, "last_interaction")
        if not last_interaction_id:
            raise ValueError("No previous interaction found. Complete CHARACTERS step first.")
        
        schema = {
            "type": "array",
            "items": {
                "type": "object",
                "properties": {
                    "name": {"type": "string"},
                    "prompt": {"type": "string"}
                },
                "required": ["name", "prompt"]
            }
        }
        
        # Use notebook prompt for chapter generation
        prompt = (
            "Now, for each chapter of the book, give me a prompt to illustrate what happens in it. "
            "It should be a single image, not a multi-tiled page. Be very descriptive, especially of the characters. "
            "Be very descriptive and remember to tell their name and to reuse the character prompts if they appear in the images."
        )
        
        chapters_data, chapters_interaction_id = self.gemini_client.generate_structured_json(
            prompt,
            schema,
            previous_interaction_id=last_interaction_id
        )
        
        # SERVER-SIDE: Enforce max 1 chapter limit
        chapters = chapters_data[:self.MAX_CHAPTERS]
        
        # Store interaction ID for context chaining
        self._store_interaction_id(project_id, "chapters_interaction", chapters_interaction_id)
        self._store_interaction_id(project_id, "last_interaction", chapters_interaction_id)
        
        return {"chapters": chapters}
    
    def _execute_illustrations_step(self, project_id: str, project: Dict[str, Any], _user_style: Optional[str]) -> Dict[str, Any]:
        """Execute ILLUSTRATIONS step: generate illustrations for each chapter"""
        step_states = project.get("step_states", {})
        chapters_step = step_states.get("CHAPTERS", {})
        chapters_result = chapters_step.get("result", {})
        chapters = chapters_result.get("chapters", [])
        portraits_step = step_states.get("PORTRAITS", {})
        portraits_result = portraits_step.get("result", {})
        portraits = portraits_result.get("portraits", [])
        
        if not chapters:
            raise ValueError("No chapters found. Complete CHAPTERS step first.")
        
        # Get style for consistency
        style_step = step_states.get("STYLE", {})
        style_result = style_step.get("result", {})
        style = style_result.get("style", "")
        
        # Get image context from PORTRAITS step for character consistency
        image_context_id = self._get_interaction_id(project_id, "image_context")
        
        # System instructions from notebook
        system_instructions = """
        There must be no text on the image, it should not look like a cover page.
        It should be a full illustration with no borders, titles, nor description.
        Unless asked otherwise, stay family-friendly with uplifting colors.
        Each produced should be a simple image, no panels.
        """
        
        # SERVER-SIDE: Enforce max 1 illustration limit
        chapters = chapters[:self.MAX_CHAPTERS]
        
        # Set up context for chapter illustrations following notebook pattern
        # We use the image context from PORTRAITS step for character consistency
        chapter_context_id = image_context_id
        
        illustrations = []
        for chapter in chapters:
            # Generate illustration for each chapter
            illustration_prompt = f"Create an illustration for {chapter['name']} using the previously generated characters following this description: {chapter['prompt']}"
            
            try:
                # Generate image with style and system instructions
                full_prompt = f"{system_instructions}\n\nFollow this style: \"{style}\"\n\n{illustration_prompt}"
                image, illustration_interaction_id = self.gemini_client.generate_image(
                    full_prompt,
                    aspect_ratio="16:9",
                    previous_interaction_id=chapter_context_id
                )
                
                # Save image to disk
                illustration_path = self._save_image(project_id, f"illustration_{chapter['name']}.png", image)
                
                illustrations.append({
                    "name": chapter["name"],
                    "prompt": chapter["prompt"],
                    "illustration_path": illustration_path
                })
                
                # Update context for next iteration (if multiple chapters)
                chapter_context_id = illustration_interaction_id
                
            except Exception as e:
                # Image generation requires billing - surface clear error
                raise Exception(f"Illustration generation requires billing. Failed for {chapter['name']}: {str(e)}")
        
        return {"illustrations": illustrations}
    
    def _get_book_text(self, project_id: str, project: Dict[str, Any]) -> Optional[str]:
        """Get book text from project"""
        if project.get("book_text"):
            return project["book_text"]
        
        book_text_path = project.get("book_text_path")
        if book_text_path:
            return self.storage.get_book_text(project_id)
        
        return None
    
    def _store_interaction_id(self, project_id: str, key: str, interaction_id: str):
        """Store Gemini interaction ID for context chaining"""
        project = self.storage.get_project(project_id)
        if not project:
            raise ValueError("Project not found")
        
        if "gemini_interactions" not in project:
            project["gemini_interactions"] = {}
        
        project["gemini_interactions"][key] = interaction_id
        self.storage.update_project(project_id, project)
    
    def _get_interaction_id(self, project_id: str, key: str) -> Optional[str]:
        """Get stored Gemini interaction ID"""
        project = self.storage.get_project(project_id)
        if not project:
            return None
        
        interactions = project.get("gemini_interactions", {})
        return interactions.get(key)
    
    def _save_image(self, project_id: str, filename: str, image: Any) -> str:
        """Save generated image to disk and return path"""
        import base64
        from pathlib import Path
        
        # Create images directory for project
        images_dir = Path("data") / "images" / project_id
        images_dir.mkdir(parents=True, exist_ok=True)
        
        image_path = images_dir / filename
        
        # Handle image data - if it's already bytes, use directly; if base64 string, decode it
        if isinstance(image.data, bytes):
            image_bytes = image.data
        else:
            # Assume it's a base64 string
            image_bytes = base64.b64decode(image.data)
        
        with open(image_path, "wb") as f:
            f.write(image_bytes)
        
        return str(image_path)
    
    def retry_step(self, project_id: str, step: str) -> Dict[str, Any]:
        """Retry a FAILED or STRANDED step"""
        project = self.storage.get_project(project_id)
        if not project:
            raise ValueError("Project not found")
        
        step_states = project.get("step_states", {})
        step_state = step_states.get(step)
        if not step_state:
            raise ValueError(f"No step state found for {step}")
        
        current_status = step_state.get("status")
        if current_status not in ["FAILED", "STRANDED"]:
            raise ValueError(f"Cannot retry step with status {current_status}")
        
        # Execute the step again
        return self.execute_step(project_id, step)
    
    def detect_and_recover_stranded(self, project_id: str) -> Optional[Dict[str, Any]]:
        """Detect stranded steps and return recovery info (user must explicitly retry)"""
        stranded_steps = self.storage.detect_stranded_steps(project_id, self.timeout_seconds)
        if stranded_steps:
            return {
                "stranded_steps": stranded_steps,
                "message": f"Steps {stranded_steps} are stranded and can be retried"
            }
        return None
