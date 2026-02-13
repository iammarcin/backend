"""Claude Code character configuration.

DEPRECATED: The static CLAUDE_CODE_CHARACTERS list has been removed.

Character routing is now determined by the frontend, which sets
`settings.general.is_claude_code_character = true` for Claude Code characters.
This makes the frontend the single source of truth for character metadata,
eliminating the need to maintain synchronized lists across backend and frontends.

See: DocumentationApp/sherlock-technical-handbook.md for full documentation.
"""

from __future__ import annotations

# Legacy exports removed - functionality moved to frontend settings
# Frontend now passes is_claude_code_character in settings.general
