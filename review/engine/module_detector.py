import re
from pathlib import Path


def detect_modules(repo_path: str = ".") -> list[dict]:
    """Parse settings.gradle[.kts] and extract module definitions.

    Returns list of {name, path, type} where:
      - name: Gradle-style ":app" or ":lib-common"
      - path: directory relative to repo root (e.g. "app", "lib-common")
      - type: guessed from directory contents ("application", "library", "unknown")
    """
    repo = Path(repo_path).resolve()

    for filename in ("settings.gradle", "settings.gradle.kts"):
        settings_file = repo / filename
        if settings_file.exists():
            modules = _parse_settings(settings_file.read_text(encoding="utf-8"))
            return [_enrich_module(repo, m) for m in modules]

    return []


_MODULE_TYPES = {"application", "com.android.application", "library", "com.android.library"}


def _enrich_module(repo: Path, module: dict) -> dict:
    """Guess module type by scanning for build.gradle plugin declarations."""
    module_path = repo / module["path"]
    for gradle_file in (module_path / "build.gradle", module_path / "build.gradle.kts"):
        if gradle_file.exists():
            text = gradle_file.read_text(encoding="utf-8")
            for plugin_id in _MODULE_TYPES:
                if plugin_id in text:
                    type_label = "application" if "application" in plugin_id else "library"
                    return {**module, "type": type_label}
    return {**module, "type": "unknown"}


def _parse_settings(content: str) -> list[dict]:
    """Extract module includes from settings.gradle content.

    Handles:
      - include ':module-name'
      - include ':module-name', ':another-module'
      - include ':nested:module'
      - Single-line comments // and block comments /* */
    """
    # Strip block comments
    content = re.sub(r"/\*.*?\*/", "", content, flags=re.DOTALL)
    # Strip line comments
    content = re.sub(r"//.*$", "", content, flags=re.MULTILINE)

    modules = []
    for line in content.splitlines():
        stripped = line.strip()
        if not stripped.startswith("include"):
            continue
        # Extract all quoted strings after 'include'
        names = re.findall(r"'([^']+)'", stripped)
        for name in names:
            name = name.strip()
            if not name:
                continue
            # Convert ":app" → path "app", ":lib:common" → path "lib/common"
            path = name.replace(":", "/").lstrip("/")
            modules.append({"name": name, "path": path})

    return modules


def file_to_module(file_path: str, modules: list[dict]) -> str:
    """Map a file path to its containing Gradle module using longest prefix match.

    Returns module name (e.g. ":app") or empty string if not matched.
    """
    best = ""
    for m in modules:
        prefix = m["path"] + "/"
        if file_path.startswith(prefix) and len(prefix) > len(best):
            best = prefix
    if best:
        # Find the module whose path matches
        for m in modules:
            if m["path"] + "/" == best:
                return m["name"]
    return ""
