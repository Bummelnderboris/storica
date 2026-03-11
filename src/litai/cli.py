"""CLI interface for LitAI."""

import click
from pathlib import Path
from rich.console import Console
from rich.table import Table
from rich.panel import Panel

from .core.config import Config
from .core.project import Project, ProjectStage
from .core.orchestrator import Orchestrator
from .engines.author import AuthorEngine
from .llm.client import LLMClient
from .output.export import Exporter


console = Console()


def get_config() -> Config:
    """Load configuration."""
    return Config.load()


@click.group()
@click.version_option(version="0.1.0")
def cli():
    """LitAI - Generate novels in the voice of literary masters."""
    pass


@cli.command()
@click.argument("name")
@click.option("--author", "-a", required=True, help="Author style to use")
@click.option("--target-words", "-w", default=45000, help="Target word count")
def new(name: str, author: str, target_words: int):
    """Create a new novel project."""
    config = get_config()

    # Verify author exists
    available = AuthorEngine.list_authors(config.authors_dir)
    if author not in available:
        console.print(f"[red]Author '{author}' not found.[/red]")
        console.print(f"Available authors: {', '.join(available)}")
        return

    try:
        project = Project.create(
            projects_dir=config.projects_dir,
            name=name,
            author=author,
            target_words=target_words,
        )
        console.print(f"[green]Created project: {project.path}[/green]")
        console.print(f"Author: {author}")
        console.print(f"Target: {target_words:,} words")
        console.print("\nRun 'litai work {name}' to start generating.")
    except ValueError as e:
        console.print(f"[red]Error: {e}[/red]")


@cli.command()
@click.argument("name")
@click.option("--stage", "-s", type=click.Choice([s.value for s in ProjectStage]), help="Start from specific stage")
def work(name: str, stage: str = None):
    """Work on a novel project."""
    config = get_config()

    if not config.gemini_api_key:
        console.print("[red]Error: GEMINI_API_KEY not set.[/red]")
        console.print("Set it in your environment or .env file.")
        return

    try:
        project = Project.load(config.projects_dir, name)
    except ValueError as e:
        console.print(f"[red]Error: {e}[/red]")
        return

    console.print(Panel(
        f"[bold]{project.config.name}[/bold]\n"
        f"Author: {project.config.author}\n"
        f"Stage: {project.config.current_stage.value}\n"
        f"Target: {project.config.target_words:,} words",
        title="Project"
    ))

    # Initialize components
    author_engine = AuthorEngine(config.authors_dir, project.config.author)
    llm_client = LLMClient(
        api_key=config.gemini_api_key,
        model=config.default_model,
        project_name=name,
    )

    orchestrator = Orchestrator(
        project=project,
        author_engine=author_engine,
        llm_client=llm_client,
        console=console,
    )

    # Run workflow
    start_stage = ProjectStage(stage) if stage else None
    orchestrator.run(start_stage)

    # Show cost summary
    costs = llm_client.get_costs()
    console.print(f"\n[dim]Session tokens: {costs['total_tokens']:,} | Cost: ${costs['total_cost_usd']:.4f}[/dim]")


@cli.command("list")
def list_projects():
    """List all projects."""
    config = get_config()
    projects = Project.list_all(config.projects_dir)

    if not projects:
        console.print("[dim]No projects found.[/dim]")
        return

    table = Table(title="Projects")
    table.add_column("Name")
    table.add_column("Author")
    table.add_column("Stage")
    table.add_column("Progress")

    for name in projects:
        project = Project.load(config.projects_dir, name)
        progress = ""
        if project.config.total_chapters:
            progress = f"{project.config.current_chapter}/{project.config.total_chapters} chapters"

        table.add_row(
            name,
            project.config.author,
            project.config.current_stage.value,
            progress,
        )

    console.print(table)


@cli.command()
@click.argument("name")
@click.option("--format", "-f", type=click.Choice(["markdown", "chapters"]), default="markdown")
@click.option("--output", "-o", type=click.Path(), help="Output path")
def export(name: str, format: str, output: str = None):
    """Export a completed novel."""
    config = get_config()

    try:
        project = Project.load(config.projects_dir, name)
    except ValueError as e:
        console.print(f"[red]Error: {e}[/red]")
        return

    exporter = Exporter(project)

    output_path = Path(output) if output else None

    if format == "markdown":
        path = exporter.export_markdown(output_path)
        console.print(f"[green]Exported to: {path}[/green]")
    elif format == "chapters":
        path = exporter.export_chapters(output_path)
        console.print(f"[green]Exported chapters to: {path}[/green]")

    # Show statistics
    stats = exporter.get_statistics()
    console.print(f"\nTotal: {stats['total_words']:,} words across {stats['total_chapters']} chapters")


@cli.group()
def authors():
    """Manage author profiles."""
    pass


@authors.command("list")
def authors_list():
    """List available authors."""
    config = get_config()
    available = AuthorEngine.list_authors(config.authors_dir)

    if not available:
        console.print("[dim]No author profiles found.[/dim]")
        return

    table = Table(title="Available Authors")
    table.add_column("ID")
    table.add_column("Name")
    table.add_column("Period")
    table.add_column("Central Obsession")

    for author_id in available:
        try:
            summary = AuthorEngine.get_author_summary(config.authors_dir, author_id)
            table.add_row(
                author_id,
                summary["name"],
                summary["lived"],
                summary["central_obsession"][:50] + "..." if len(summary["central_obsession"]) > 50 else summary["central_obsession"],
            )
        except Exception:
            table.add_row(author_id, "Error loading", "", "")

    console.print(table)


@authors.command("show")
@click.argument("author_id")
def authors_show(author_id: str):
    """Show author profile details."""
    config = get_config()

    try:
        engine = AuthorEngine(config.authors_dir, author_id)
        profile = engine.get_profile()
    except ValueError as e:
        console.print(f"[red]Error: {e}[/red]")
        return

    console.print(Panel(
        f"[bold]{profile.name}[/bold] ({profile.lived})\n"
        f"{profile.nationality}\n\n"
        f"[bold]Central Obsession:[/bold]\n{profile.philosophy.central_obsession}\n\n"
        f"[bold]Worldview:[/bold]\n{profile.philosophy.worldview}\n\n"
        f"[bold]Structural Pattern:[/bold] {profile.structure.signature_pattern}\n"
        f"{profile.structure.description}\n\n"
        f"[bold]Prose Style:[/bold]\n{profile.prose.tone}\n\n"
        f"[bold]Primary Themes:[/bold]\n" + "\n".join(f"- {t}" for t in profile.themes.get("primary", [])),
        title=f"Author Profile: {author_id}"
    ))


@cli.command()
@click.argument("name", required=False)
def costs(name: str = None):
    """Show cost tracking information."""
    config = get_config()

    if name:
        try:
            project = Project.load(config.projects_dir, name)
            cost_file = project.path / "costs.json"

            from .llm.costs import CostTracker
            tracker = CostTracker.load(cost_file, name)
            summary = tracker.get_summary()

            console.print(Panel(
                f"Total Calls: {summary['total_calls']}\n"
                f"Input Tokens: {summary['total_input_tokens']:,}\n"
                f"Output Tokens: {summary['total_output_tokens']:,}\n"
                f"Total Tokens: {summary['total_tokens']:,}\n"
                f"Estimated Cost: ${summary['total_cost_usd']:.4f}",
                title=f"Costs: {name}"
            ))
        except ValueError as e:
            console.print(f"[red]Error: {e}[/red]")
    else:
        # Show all projects
        projects = Project.list_all(config.projects_dir)
        if not projects:
            console.print("[dim]No projects found.[/dim]")
            return

        table = Table(title="Project Costs")
        table.add_column("Project")
        table.add_column("Tokens")
        table.add_column("Cost")

        total_cost = 0.0

        for proj_name in projects:
            project = Project.load(config.projects_dir, proj_name)
            cost_file = project.path / "costs.json"

            from .llm.costs import CostTracker
            tracker = CostTracker.load(cost_file, proj_name)
            summary = tracker.get_summary()

            table.add_row(
                proj_name,
                f"{summary['total_tokens']:,}",
                f"${summary['total_cost_usd']:.4f}",
            )
            total_cost += summary['total_cost_usd']

        console.print(table)
        console.print(f"\n[bold]Total: ${total_cost:.4f}[/bold]")


if __name__ == "__main__":
    cli()
