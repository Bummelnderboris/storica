"""Markdown formatting utilities."""

from typing import Optional


class MarkdownFormatter:
    """Utilities for markdown formatting."""

    @staticmethod
    def format_chapter(
        chapter_num: int,
        title: str,
        content: str,
        word_count: Optional[int] = None,
    ) -> str:
        """Format a chapter with consistent styling."""
        lines = [
            f"# Chapter {chapter_num}: {title}",
            "",
        ]

        if word_count:
            lines.append(f"*({word_count:,} words)*")
            lines.append("")

        lines.append(content)
        lines.append("")

        return "\n".join(lines)

    @staticmethod
    def format_novel(
        title: str,
        author_style: str,
        chapters: dict[int, str],
    ) -> str:
        """Format a complete novel."""
        lines = [
            f"# {title}",
            "",
            f"*Written in the style of {author_style}*",
            "",
            "---",
            "",
        ]

        for num in sorted(chapters.keys()):
            lines.append(chapters[num])
            lines.append("")
            lines.append("---")
            lines.append("")

        return "\n".join(lines)

    @staticmethod
    def extract_title(chapter_content: str) -> str:
        """Extract chapter title from content."""
        lines = chapter_content.strip().split("\n")

        for line in lines:
            if line.startswith("# Chapter"):
                # Parse "# Chapter N: Title" format
                if ":" in line:
                    return line.split(":", 1)[1].strip()
                return line.replace("# ", "").strip()

        return "Untitled"

    @staticmethod
    def word_count(text: str) -> int:
        """Count words in text."""
        return len(text.split())
