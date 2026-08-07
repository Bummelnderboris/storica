"""
Jinja2-based prompt template engine.
"""

import os
from pathlib import Path
from typing import Any, Dict, Optional

import yaml
from jinja2 import Environment, FileSystemLoader, select_autoescape


class PromptTemplate:
    """A loaded prompt template with metadata."""

    def __init__(
        self,
        name: str,
        system: str,
        user: str,
        description: Optional[str] = None,
        required_vars: Optional[list[str]] = None,
        examples: Optional[list[dict]] = None
    ):
        self.name = name
        self.system = system
        self.user = user
        self.description = description
        self.required_vars = required_vars or []
        self.examples = examples or []

    def format(self, **kwargs) -> tuple[str, str]:
        """
        Format the template with variables.

        Returns:
            Tuple of (system_prompt, user_prompt)
        """
        # Check required variables
        missing = [v for v in self.required_vars if v not in kwargs]
        if missing:
            raise ValueError(f"Missing required variables: {missing}")

        return (
            self.system.format(**kwargs) if self.system else "",
            self.user.format(**kwargs)
        )


class PromptEngine:
    """
    Engine for loading and rendering prompt templates.

    Templates are stored as YAML files with Jinja2 templating support.
    """

    def __init__(self, templates_dir: Optional[str] = None):
        """
        Initialize the prompt engine.

        Args:
            templates_dir: Path to templates directory. Defaults to ./templates
        """
        if templates_dir is None:
            templates_dir = os.path.join(os.path.dirname(__file__), "templates")

        self.templates_dir = Path(templates_dir)
        self._cache: Dict[str, PromptTemplate] = {}

        # Initialize Jinja2 environment
        self.env = Environment(
            loader=FileSystemLoader(str(self.templates_dir)),
            autoescape=select_autoescape(enabled_extensions=()),
            trim_blocks=True,
            lstrip_blocks=True
        )

    def load(self, name: str) -> PromptTemplate:
        """
        Load a prompt template by name.

        Args:
            name: Template name (without .yaml extension)

        Returns:
            PromptTemplate instance
        """
        if name in self._cache:
            return self._cache[name]

        template_path = self.templates_dir / f"{name}.yaml"
        if not template_path.exists():
            raise FileNotFoundError(f"Template not found: {name}")

        with open(template_path, "r", encoding="utf-8") as f:
            data = yaml.safe_load(f)

        template = PromptTemplate(
            name=name,
            system=data.get("system", ""),
            user=data.get("user", ""),
            description=data.get("description"),
            required_vars=data.get("required_vars", []),
            examples=data.get("examples", [])
        )

        self._cache[name] = template
        return template

    def render(self, name: str, **kwargs) -> tuple[str, str]:
        """
        Load and render a template with variables.

        Args:
            name: Template name
            **kwargs: Template variables

        Returns:
            Tuple of (system_prompt, user_prompt)
        """
        template = self.load(name)
        return template.format(**kwargs)

    def render_jinja(self, name: str, context: Dict[str, Any]) -> tuple[str, str]:
        """
        Load and render a Jinja2 template.

        For complex templates that need Jinja2 features like loops and conditionals.

        Args:
            name: Template name (a .yaml file that contains Jinja2 syntax)
            context: Template context variables

        Returns:
            Tuple of (system_prompt, user_prompt)
        """
        template_path = f"{name}.yaml"
        jinja_template = self.env.get_template(template_path)

        # Render the YAML content with Jinja2
        rendered_yaml = jinja_template.render(**context)

        # Parse the rendered YAML
        data = yaml.safe_load(rendered_yaml)

        return (
            data.get("system", ""),
            data.get("user", "")
        )

    def list_templates(self) -> list[str]:
        """List all available template names."""
        return [
            f.stem for f in self.templates_dir.glob("*.yaml")
        ]

    def clear_cache(self) -> None:
        """Clear the template cache."""
        self._cache.clear()

    def validate_template(self, name: str) -> tuple[bool, Optional[str]]:
        """
        Validate a template file.

        Returns:
            Tuple of (is_valid, error_message)
        """
        try:
            template = self.load(name)
            if not template.user:
                return False, "Template must have a 'user' prompt"
            return True, None
        except Exception as e:
            return False, str(e)
