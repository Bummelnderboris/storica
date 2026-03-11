"""Export functionality for completed novels."""

from pathlib import Path
from typing import Optional

from ..core.project import Project


class Exporter:
    """Export novels to various formats."""

    def __init__(self, project: Project):
        self.project = project

    def export_markdown(self, output_path: Optional[Path] = None) -> Path:
        """Export as a single markdown file."""
        content = self.project.compile_novel()

        if output_path is None:
            output_path = self.project.path / "final" / "novel.md"

        output_path.parent.mkdir(parents=True, exist_ok=True)
        output_path.write_text(content)

        return output_path

    def export_chapters(self, output_dir: Optional[Path] = None) -> Path:
        """Export chapters as separate files."""
        if output_dir is None:
            output_dir = self.project.path / "final" / "chapters"

        output_dir.mkdir(parents=True, exist_ok=True)

        chapters = self.project.get_all_chapters()
        for num, content in chapters.items():
            path = output_dir / f"chapter_{num:02d}.md"
            path.write_text(content)

        return output_dir

    def get_statistics(self) -> dict:
        """Get novel statistics."""
        chapters = self.project.get_all_chapters()

        total_words = 0
        chapter_stats = []

        for num in sorted(chapters.keys()):
            content = chapters[num]
            words = len(content.split())
            total_words += words
            chapter_stats.append({
                "chapter": num,
                "words": words,
            })

        return {
            "total_chapters": len(chapters),
            "total_words": total_words,
            "average_chapter_length": total_words // len(chapters) if chapters else 0,
            "chapters": chapter_stats,
        }
