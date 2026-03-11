"""Orchestration engine for the novel generation workflow."""

from typing import Callable, Optional

from rich.console import Console
from rich.panel import Panel
from rich.prompt import Prompt, Confirm
from rich.markdown import Markdown

from .project import Project, ProjectStage
from ..engines.author import AuthorEngine
from ..engines.narrative import NarrativeEngine
from ..engines.prose import ProseEngine
from ..engines.memory import MemoryEngine
from ..llm.client import LLMClient


class Orchestrator:
    """Manages the novel generation workflow."""

    def __init__(
        self,
        project: Project,
        author_engine: AuthorEngine,
        llm_client: LLMClient,
        console: Console,
    ):
        self.project = project
        self.author_engine = author_engine
        self.llm_client = llm_client
        self.console = console

        self.narrative_engine = NarrativeEngine(llm_client, author_engine)
        self.prose_engine = ProseEngine(llm_client, author_engine)
        self.memory_engine = MemoryEngine(project)

    def run(self, start_stage: Optional[ProjectStage] = None) -> None:
        """Run the workflow from the current or specified stage."""
        stage = start_stage or self.project.config.current_stage

        stage_handlers = {
            ProjectStage.ESSENCE: self._run_essence,
            ProjectStage.ARCHITECTURE: self._run_architecture,
            ProjectStage.BLUEPRINT: self._run_blueprint,
            ProjectStage.PROSE: self._run_prose,
            ProjectStage.POLISH: self._run_polish,
        }

        while stage != ProjectStage.COMPLETE:
            handler = stage_handlers.get(stage)
            if not handler:
                break

            self.console.print(f"\n[bold cyan]Stage: {stage.value.upper()}[/bold cyan]\n")

            success = handler()
            if not success:
                self.console.print("[yellow]Workflow paused. Use 'litai work' to continue.[/yellow]")
                return

            # Advance to next stage
            stages = list(ProjectStage)
            current_idx = stages.index(stage)
            if current_idx < len(stages) - 1:
                stage = stages[current_idx + 1]
                self.project.config.current_stage = stage
                self.project.save_config()
            else:
                break

        self.console.print("\n[bold green]Novel generation complete![/bold green]")

    def _approval_gate(
        self,
        content: str,
        regenerate_fn: Callable[[], str],
        title: str = "Generated Content",
    ) -> tuple[bool, str]:
        """Show content and get user approval."""
        while True:
            # Show preview
            preview = content[:1000] + "..." if len(content) > 1000 else content
            self.console.print(Panel(Markdown(preview), title=title))

            self.console.print("\n[a]pprove  [r]egenerate  [e]dit with guidance  [v]iew full  [q]uit\n")
            choice = Prompt.ask("Choice", choices=["a", "r", "e", "v", "q"], default="a")

            if choice == "a":
                return True, content
            elif choice == "r":
                self.console.print("[dim]Regenerating...[/dim]")
                content = regenerate_fn()
            elif choice == "e":
                guidance = Prompt.ask("Enter revision guidance")
                self.console.print("[dim]Regenerating with guidance...[/dim]")
                content = regenerate_fn(guidance)
            elif choice == "v":
                self.console.print(Panel(Markdown(content), title=title))
            elif choice == "q":
                return False, content

    def _run_essence(self) -> bool:
        """Run the essence generation stage."""
        # Get seed from user if not set
        if not self.project.config.seed:
            self.console.print("[bold]What is the seed idea for your novel?[/bold]")
            self.console.print("[dim]Examples: 'A story about AI consciousness', 'A man returns to his hometown'[/dim]\n")
            seed = Prompt.ask("Seed idea")
            self.project.config.seed = seed
            self.project.save_config()

        author_profile = self.author_engine.get_profile()

        def generate(guidance: Optional[str] = None) -> str:
            return self.narrative_engine.generate_essence(
                seed=self.project.config.seed,
                author_profile=author_profile,
                guidance=guidance,
            )

        self.console.print("[dim]Generating essence document...[/dim]")
        content = generate()

        approved, final_content = self._approval_gate(
            content,
            generate,
            title="Essence Document",
        )

        if approved:
            self.project.save_essence(final_content)
            self.console.print("[green]Essence saved.[/green]")

        return approved

    def _run_architecture(self) -> bool:
        """Run the architecture generation stage."""
        essence = self.project.get_essence()
        if not essence:
            self.console.print("[red]No essence document found. Run essence stage first.[/red]")
            return False

        author_profile = self.author_engine.get_profile()
        target_words = self.project.config.target_words

        def generate(guidance: Optional[str] = None) -> str:
            return self.narrative_engine.generate_architecture(
                essence=essence,
                author_profile=author_profile,
                target_words=target_words,
                guidance=guidance,
            )

        self.console.print("[dim]Generating narrative architecture...[/dim]")
        content = generate()

        approved, final_content = self._approval_gate(
            content,
            generate,
            title="Narrative Architecture",
        )

        if approved:
            self.project.save_architecture(final_content)
            # Parse chapter count from architecture
            self._parse_chapter_count(final_content)
            self.console.print("[green]Architecture saved.[/green]")

        return approved

    def _parse_chapter_count(self, architecture: str) -> None:
        """Extract chapter count from architecture document."""
        import re

        # Look for patterns like "18 chapters" or "Chapters 1-18"
        match = re.search(r"(\d+)\s*chapters", architecture, re.IGNORECASE)
        if match:
            self.project.config.total_chapters = int(match.group(1))
            self.project.save_config()

    def _run_blueprint(self) -> bool:
        """Run the blueprint generation stage."""
        architecture = self.project.get_architecture()
        if not architecture:
            self.console.print("[red]No architecture document found. Run architecture stage first.[/red]")
            return False

        author_profile = self.author_engine.get_profile()
        total_chapters = self.project.config.total_chapters or 18

        self.console.print(f"[dim]Generating blueprints for {total_chapters} chapters...[/dim]\n")

        for chapter_num in range(1, total_chapters + 1):
            # Check if blueprint already exists
            existing = self.project.get_blueprint(chapter_num)
            if existing:
                self.console.print(f"[dim]Chapter {chapter_num} blueprint exists, skipping...[/dim]")
                continue

            self.console.print(f"[bold]Chapter {chapter_num}/{total_chapters}[/bold]")

            # Get previous blueprints for context
            previous_blueprints = self.project.get_all_blueprints()

            def generate(guidance: Optional[str] = None) -> str:
                return self.narrative_engine.generate_blueprint(
                    chapter_num=chapter_num,
                    architecture=architecture,
                    author_profile=author_profile,
                    previous_blueprints=previous_blueprints,
                    guidance=guidance,
                )

            content = generate()

            approved, final_content = self._approval_gate(
                content,
                generate,
                title=f"Chapter {chapter_num} Blueprint",
            )

            if not approved:
                return False

            self.project.save_blueprint(chapter_num, final_content)
            self.console.print(f"[green]Chapter {chapter_num} blueprint saved.[/green]\n")

        return True

    def _run_prose(self) -> bool:
        """Run the prose generation stage."""
        author_profile = self.author_engine.get_profile()
        blueprints = self.project.get_all_blueprints()

        if not blueprints:
            self.console.print("[red]No blueprints found. Run blueprint stage first.[/red]")
            return False

        total_chapters = len(blueprints)
        start_chapter = self.project.config.current_chapter + 1

        self.console.print(f"[dim]Writing chapters {start_chapter}-{total_chapters}...[/dim]\n")

        for chapter_num in range(start_chapter, total_chapters + 1):
            blueprint = blueprints.get(chapter_num)
            if not blueprint:
                self.console.print(f"[red]No blueprint for chapter {chapter_num}.[/red]")
                continue

            # Check if chapter already exists
            existing = self.project.get_chapter(chapter_num)
            if existing:
                self.console.print(f"[dim]Chapter {chapter_num} exists, skipping...[/dim]")
                continue

            self.console.print(f"[bold]Writing Chapter {chapter_num}/{total_chapters}[/bold]")

            # Get context from story bible and previous chapters
            story_bible = self.project.get_story_bible()
            previous_chapters = self.project.get_all_chapters()

            def generate(guidance: Optional[str] = None) -> str:
                return self.prose_engine.generate_chapter(
                    chapter_num=chapter_num,
                    blueprint=blueprint,
                    author_profile=author_profile,
                    story_bible=story_bible,
                    previous_chapters=previous_chapters,
                    guidance=guidance,
                )

            content = generate()

            # Count words
            word_count = len(content.split())
            self.console.print(f"[dim]Generated {word_count} words[/dim]")

            approved, final_content = self._approval_gate(
                content,
                generate,
                title=f"Chapter {chapter_num}",
            )

            if not approved:
                return False

            self.project.save_chapter(chapter_num, final_content)

            # Update story bible
            self.console.print("[dim]Updating story bible...[/dim]")
            updated_bible = self.memory_engine.update_story_bible(
                chapter_num=chapter_num,
                chapter_content=final_content,
                blueprint=blueprint,
                current_bible=story_bible,
                llm_client=self.llm_client,
                author_profile=author_profile,
            )
            self.project.save_story_bible(updated_bible)

            self.project.config.current_chapter = chapter_num
            self.project.save_config()

            self.console.print(f"[green]Chapter {chapter_num} saved.[/green]\n")

        return True

    def _run_polish(self) -> bool:
        """Run the polish/revision stage."""
        chapters = self.project.get_all_chapters()
        if not chapters:
            self.console.print("[red]No chapters found. Run prose stage first.[/red]")
            return False

        self.console.print("[dim]Running consistency check...[/dim]")

        story_bible = self.project.get_story_bible()
        author_profile = self.author_engine.get_profile()

        # Generate consistency report
        issues = self.prose_engine.check_consistency(
            chapters=chapters,
            story_bible=story_bible,
            author_profile=author_profile,
        )

        if issues:
            self.console.print(Panel(issues, title="Consistency Issues"))
            if not Confirm.ask("Continue with compilation?"):
                return False

        # Compile final novel
        self.console.print("[dim]Compiling final novel...[/dim]")
        final_path = self.project.save_final()

        self.console.print(f"[green]Final novel saved to: {final_path}[/green]")

        self.project.config.current_stage = ProjectStage.COMPLETE
        self.project.save_config()

        return True
