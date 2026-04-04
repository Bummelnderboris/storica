"""Author Mind Loader Agent - loads and prepares author profile for pipeline."""

import time
from typing import Any

from ..base import BaseAgent, AgentContext, AgentResult, AgentPhase
from ..registry import AgentRegistry
from .schema import AuthorMindInput, AuthorMindOutput


@AgentRegistry.register(AgentPhase.AUTHOR_LOADING)
class AuthorMindLoaderAgent(BaseAgent[AuthorMindInput, AuthorMindOutput]):
    """
    Phase 0: Load and prepare an author's creative profile.

    This agent loads the author profile from YAML and prepares
    condensed versions for use by subsequent agents.
    """

    phase = AgentPhase.AUTHOR_LOADING
    name = "Author Mind Loader"
    description = "Load and prepare author profile for creative emulation"
    requires_approval = False

    def __init__(self, llm_service: Any, prompt_engine: Any):
        super().__init__(llm_service, prompt_engine)
        # Import here to avoid circular imports
        from ...authors import AuthorLoader
        self.author_loader = AuthorLoader()

    async def execute(
        self,
        input_data: AuthorMindInput,
        context: AgentContext
    ) -> AgentResult[AuthorMindOutput]:
        """Load the author profile and prepare condensed guides."""
        start_time = time.time()

        try:
            # Load the full profile
            profile = self.author_loader.load(input_data.author_id)

            # Prepare condensed versions for prompts
            output = AuthorMindOutput(
                author_id=input_data.author_id,
                author_name=profile.metadata.name,
                primary_language=profile.metadata.primary_language,
                philosophy_summary=profile.get_philosophy_summary(),
                style_guide=profile.get_style_guide(),
                character_patterns=profile.get_character_patterns_summary(),
                critique_rubric=profile.critique_rubric.model_dump(),
                loaded=True
            )

            # Update context with loaded profile
            context.author_profile = {
                "id": input_data.author_id,
                "name": profile.metadata.name,
                "language": profile.metadata.primary_language,
                "philosophy": output.philosophy_summary,
                "style_guide": output.style_guide,
                "character_patterns": output.character_patterns,
                "critique_rubric": output.critique_rubric
            }

            execution_time_ms = int((time.time() - start_time) * 1000)

            return AgentResult.success_result(
                output=output,
                reasoning=f"Successfully loaded profile for {profile.metadata.name}",
                execution_time_ms=execution_time_ms
            )

        except FileNotFoundError as e:
            execution_time_ms = int((time.time() - start_time) * 1000)
            return AgentResult.failure_result(
                error=f"Author profile not found: {input_data.author_id}",
                execution_time_ms=execution_time_ms
            )
        except Exception as e:
            execution_time_ms = int((time.time() - start_time) * 1000)
            return AgentResult.failure_result(
                error=f"Failed to load author profile: {str(e)}",
                execution_time_ms=execution_time_ms
            )

    async def reason(
        self,
        input_data: AuthorMindInput,
        context: AgentContext
    ) -> str:
        """No LLM reasoning needed for profile loading."""
        return f"Loading author profile for: {input_data.author_id}"
