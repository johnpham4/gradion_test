from typing import Optional, Dict, Any
from loguru import logger
from app.repositories.storage import StorageRepository
from app.clients.gemini import GeminiClient
from app.clients.mock_image import MockImageClient
from app.config import settings


class PipelineService:
    """Service for managing pipeline execution with Gemini integration"""

    # Assessment limits (hard caps, enforced server-side)
    MAX_CHARACTERS = 2
    MAX_CHAPTERS = 1

    def __init__(self, storage: StorageRepository, gemini_client: Optional[GeminiClient] = None):
        self.storage = storage
        self.gemini_client = gemini_client
        self.timeout_seconds = 300  # 5 minutes default timeout

        # Image provider selection: "gemini" (default) or "mock" (dev/test fallback)
        self.image_provider = settings.IMAGE_PROVIDER.lower()
        self.image_client = self._initialize_image_client()

    def _initialize_image_client(self):
        """Initialize image client based on provider configuration"""
        provider = settings.IMAGE_PROVIDER.lower()

        if provider == "mock":
            logger.info("Using MockImageClient for image generation (dev/test fallback)")
            return MockImageClient(output_dir=settings.MOCK_IMAGE_OUTPUT_DIR)

        elif provider == "gemini":
            if not self.gemini_client:
                logger.warning("Gemini client not available, falling back to mock")
                return MockImageClient(output_dir=settings.MOCK_IMAGE_OUTPUT_DIR)
            logger.info("Using Gemini client for image generation")
            return self.gemini_client

        else:
            logger.warning(f"Unknown image provider: {provider}, falling back to mock")
            return MockImageClient(output_dir=settings.MOCK_IMAGE_OUTPUT_DIR)

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
        """Execute STYLE step: upload the book once and generate (or accept) an art style"""
        book_text = self._get_book_text(project_id, project)
        if not book_text:
            raise ValueError("Book text not found")

        # Upload the book to the File API once and reference it via URI from now on
        book_file = self.gemini_client.upload_file(project["book_text_path"], "book.txt")

        # Start the chat with the book attached (notebook pattern)
        _, book_interaction_id = self.gemini_client.generate_text(
            "Here's a book, to illustrate using Gemini. Don't say anything for now, instructions will follow.",
            file_uri=book_file.uri,
        )

        if user_style:
            # User provided style - inform Gemini so it adapts future prompts
            _, style_interaction_id = self.gemini_client.generate_text(
                f'The art style will be: "{user_style}". Keep that in mind when generating future prompts. Keep quiet for now, instructions will follow.',
                previous_interaction_id=book_interaction_id,
            )
            style = user_style
        else:
            # Let Gemini choose a fitting style (notebook prompt)
            style, style_interaction_id = self.gemini_client.generate_text(
                "Can you define an art style that would fit the story but with a twist? Just give us the prompt for the art style that will be added to future prompts.",
                previous_interaction_id=book_interaction_id,
            )

        # Store interaction IDs for context chaining in later steps
        self._store_interaction_id(project_id, "book_interaction", book_interaction_id)
        self._store_interaction_id(project_id, "last_interaction", style_interaction_id)

        return {"style": style}

    def _execute_characters_step(self, project_id: str, project: Dict[str, Any], _user_style: Optional[str]) -> Dict[str, Any]:
        """Execute CHARACTERS step: extract max 2 adult characters with prompts (structured JSON)"""
        last_interaction_id = self._get_interaction_id(project_id, "last_interaction")
        if not last_interaction_id:
            raise ValueError("No previous interaction found. Complete STYLE step first.")

        # Notebook schema: a flat array of {name, prompt}
        schema = {
            "type": "array",
            "items": {
                "type": "object",
                "properties": {
                    "name": {"type": "string"},
                    "prompt": {"type": "string"},
                },
                "required": ["name", "prompt"],
            },
        }

        # Notebook prompt (adults only, image-ready prompts)
        prompt = (
            "Can you describe the main characters (only the adults) and prepare a prompt describing them "
            "with as much details as possible (use the descriptions from the book) so Gemini can generate "
            "images of them? Each prompt should be at least 50 words."
        )

        characters_data, characters_interaction_id = self.gemini_client.generate_structured_json(
            prompt,
            schema,
            previous_interaction_id=last_interaction_id,
        )

        # SERVER-SIDE: Enforce max 2 characters limit
        characters = characters_data[: self.MAX_CHARACTERS]

        self._store_interaction_id(project_id, "characters_interaction", characters_interaction_id)
        self._store_interaction_id(project_id, "last_interaction", characters_interaction_id)

        return {"characters": characters}

    def _execute_portraits_step(self, project_id: str, project: Dict[str, Any], _user_style: Optional[str]) -> Dict[str, Any]:
        """Execute PORTRAITS step: one portrait per character, chained on the image model"""
        step_states = project.get("step_states", {})
        characters_result = step_states.get("CHARACTERS", {}).get("result", {})
        characters = characters_result.get("characters", [])

        if not characters:
            raise ValueError("No characters found. Complete CHARACTERS step first.")

        style_result = step_states.get("STYLE", {}).get("result", {})
        style = style_result.get("style", "")

        # SERVER-SIDE: Enforce max 2 portraits limit
        characters = characters[: self.MAX_CHARACTERS]

        # Notebook system instructions (negative prompt)
        system_instructions = """
        There must be no text on the image, it should not look like a cover page.
        It should be a full illustration with no borders, titles, nor description.
        Unless asked otherwise, stay family-friendly with uplifting colors.
        Each produced should be a simple image, no panels.
        """

        # Seed the image model with style + rules, then chain every portrait (notebook pattern)
        context_prompt = (
            "You are going to generate portrait images to illustrate this book.\n"
            f'The style we want you to follow is: "{style}"\n'
            f"Also follow those rules: {system_instructions}"
        )
        last_image_interaction_id = self.image_client.generate_image_context(context_prompt)

        portraits = []
        for character in characters:
            portrait_prompt = (
                f"Create an illustration for {character['name']} following this description: {character['prompt']}"
            )

            image_data, image_interaction_id = self.image_client.generate_image(
                portrait_prompt,
                aspect_ratio="9:16",
                previous_interaction_id=last_image_interaction_id,
            )

            if self._image_provider_is_gemini():
                portrait_path = self._save_image(project_id, f"portrait_{character['name']}.png", image_data)
            else:
                portrait_path = image_data

            portraits.append({
                "name": character["name"],
                "prompt": character["prompt"],
                "portrait_path": portrait_path,
            })

            last_image_interaction_id = image_interaction_id

            # Persist partial results so the UI shows each portrait landing
            self.storage.update_step_result(project_id, "PORTRAITS", {"portraits": portraits})

        self._store_interaction_id(project_id, "image_context", last_image_interaction_id)

        return {"portraits": portraits}

    def _execute_chapters_step(self, project_id: str, project: Dict[str, Any], _user_style: Optional[str]) -> Dict[str, Any]:
        """Execute CHAPTERS step: generate prompts for max 1 chapter (structured JSON)"""
        last_interaction_id = self._get_interaction_id(project_id, "last_interaction")
        if not last_interaction_id:
            raise ValueError("No previous interaction found. Complete CHARACTERS step first.")

        schema = {
            "type": "array",
            "items": {
                "type": "object",
                "properties": {
                    "name": {"type": "string"},
                    "prompt": {"type": "string"},
                },
                "required": ["name", "prompt"],
            },
        }

        # Notebook prompt (single image, descriptive, references characters)
        prompt = (
            "Now, for each chapter of the book, give me a prompt to illustrate what happens in it. "
            "It should be a single image, not a multi-tiled page. Be very descriptive, especially of the characters. "
            "Be very descriptive and remember to tell their name and to reuse the character prompts if they appear in the images."
        )

        chapters_data, chapters_interaction_id = self.gemini_client.generate_structured_json(
            prompt,
            schema,
            previous_interaction_id=last_interaction_id,
        )

        # SERVER-SIDE: Enforce max 1 chapter limit
        chapters = chapters_data[: self.MAX_CHAPTERS]

        self._store_interaction_id(project_id, "chapters_interaction", chapters_interaction_id)
        self._store_interaction_id(project_id, "last_interaction", chapters_interaction_id)

        return {"chapters": chapters}

    def _execute_illustrations_step(self, project_id: str, project: Dict[str, Any], _user_style: Optional[str]) -> Dict[str, Any]:
        """Execute ILLUSTRATIONS step: one scene illustration per chapter, chained from the portraits"""
        step_states = project.get("step_states", {})
        chapters_result = step_states.get("CHAPTERS", {}).get("result", {})
        chapters = chapters_result.get("chapters", [])

        if not chapters:
            raise ValueError("No chapters found. Complete CHAPTERS step first.")

        style_result = step_states.get("STYLE", {}).get("result", {})
        style = style_result.get("style", "")

        # SERVER-SIDE: Enforce max 1 illustration limit
        chapters = chapters[: self.MAX_CHAPTERS]

        # Notebook system instructions (negative prompt)
        system_instructions = """
        There must be no text on the image, it should not look like a cover page.
        It should be a full illustration with no borders, titles, nor description.
        Unless asked otherwise, stay family-friendly with uplifting colors.
        Each produced should be a simple image, no panels.
        """

        # Continue the image-model conversation from the last portrait so characters stay consistent
        image_context_id = self._get_interaction_id(project_id, "image_context")
        if self._image_provider_is_gemini() and image_context_id:
            # Notebook: tell the image model we're switching to chapter illustrations
            last_image_interaction_id = self.image_client.generate_image_context(
                "Starting from now, we're going to illustrate the book's chapters. "
                "Don't forget to refer to your previous illustrations of the characters to keep the characters consistency, but feel free to change their position.",
                previous_interaction_id=image_context_id,
            )
        else:
            last_image_interaction_id = self.image_client.generate_image_context(
                "Starting from now, we're going to illustrate the book's chapters."
            )

        illustrations = []
        for chapter in chapters:
            illustration_prompt = (
                f"Create an illustration for {chapter['name']} using the previously generated characters following this description: {chapter['prompt']}"
            )

            image_data, image_interaction_id = self.image_client.generate_image(
                illustration_prompt,
                aspect_ratio="16:9",
                previous_interaction_id=last_image_interaction_id,
            )

            if self._image_provider_is_gemini():
                illustration_path = self._save_image(project_id, f"illustration_{chapter['name']}.png", image_data)
            else:
                illustration_path = image_data

            illustrations.append({
                "name": chapter["name"],
                "prompt": chapter["prompt"],
                "illustration_path": illustration_path,
            })

            last_image_interaction_id = image_interaction_id

            # Persist partial results so the UI shows each illustration landing
            self.storage.update_step_result(project_id, "ILLUSTRATIONS", {"illustrations": illustrations})

        return {"illustrations": illustrations}

    def _image_provider_is_gemini(self) -> bool:
        """Whether image generation goes through the real Gemini client"""
        return self.image_provider == "gemini" and isinstance(self.image_client, GeminiClient)

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
        def _update(project):
            if "gemini_interactions" not in project:
                project["gemini_interactions"] = {}
            project["gemini_interactions"][key] = interaction_id
            return project

        self.storage.mutate_project(project_id, _update)

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
            image_bytes = base64.b64decode(image.data)

        with open(image_path, "wb") as f:
            f.write(image_bytes)

        # Normalize to forward slashes so the path works as a URL segment
        return str(image_path).replace("\\", "/")

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
                "message": f"Steps {stranded_steps} are stranded and can be retried",
            }
        return None