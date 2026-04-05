"""Configuration loader with environment variable support.

Priority (highest to lowest):
1. Environment variables (including ~/.openclaw/.env style file loaded into process env)
2. Local config files (config/local.yaml, not in git)
3. Topic-specific config files
4. Template defaults
"""

import os
import re
import yaml
from pathlib import Path
from typing import Dict, Any, Optional
from loguru import logger


_ENV_FILE_LOADED = False


def _find_openclaw_home() -> Optional[Path]:
    """Find the current machine's OpenClaw home directory.

    Resolution order:
    1. OPENCLAW_HOME environment variable
    2. Walk upward from this file looking for an OpenClaw root marker
    """
    env_home = os.getenv("OPENCLAW_HOME")
    if env_home:
        candidate = Path(env_home).expanduser()
        if (candidate / "openclaw.json").exists():
            return candidate

    current = Path(__file__).resolve()
    for parent in current.parents:
        if (parent / "openclaw.json").exists() and (parent / "workspace").exists():
            return parent
    return None


def _load_openclaw_env_file() -> None:
    """Load key=value pairs from the machine-local OpenClaw .env file into os.environ."""
    global _ENV_FILE_LOADED
    if _ENV_FILE_LOADED:
        return

    openclaw_home = _find_openclaw_home()
    if not openclaw_home:
        return

    env_path = openclaw_home / ".env"
    if not env_path.exists():
        _ENV_FILE_LOADED = True
        return

    for raw_line in env_path.read_text(encoding="utf-8").splitlines():
        line = raw_line.strip()
        if not line or line.startswith("#"):
            continue
        if line.startswith("export "):
            line = line[len("export "):].strip()
        if "=" not in line:
            continue
        key, value = line.split("=", 1)
        key = key.strip()
        value = value.strip()
        if not key:
            continue
        if len(value) >= 2 and value[0] == value[-1] and value[0] in {'"', "'"}:
            value = value[1:-1]
        os.environ.setdefault(key, value)

    logger.debug(f"Loaded OpenClaw env file: {env_path}")
    _ENV_FILE_LOADED = True


def _expand_env_vars(value: Any) -> Any:
    """Expand ${VAR} or ${VAR:-default} syntax in config values."""
    if isinstance(value, str):
        # Pattern: ${VAR} or ${VAR:-default}
        pattern = r'\$\{([^}:-]+)(?::-([^}]*))?\}'
        
        def replace_var(match):
            var_name = match.group(1)
            default_val = match.group(2) or ''
            return os.getenv(var_name, default_val)
        
        return re.sub(pattern, replace_var, value)
    elif isinstance(value, dict):
        return {k: _expand_env_vars(v) for k, v in value.items()}
    elif isinstance(value, list):
        return [_expand_env_vars(item) for item in value]
    return value


def load_config(config_path: str) -> Dict[str, Any]:
    """
    Load configuration with environment variable overrides.
    
    Args:
        config_path: Path to topic-specific config YAML
        
    Returns:
        Merged configuration dict
    """
    _load_openclaw_env_file()

    # Load base config from file
    config = _load_yaml(config_path)
    
    # Expand ${VAR} placeholders
    config = _expand_env_vars(config)
    
    # Load local overrides (if exists)
    local_config = _load_local_config()
    if local_config:
        logger.debug("Loaded local config overrides")
        config = _merge_dicts(config, local_config)
    
    # Apply environment variable overrides (highest priority)
    env_overrides = _get_env_overrides()
    if env_overrides:
        logger.debug("Applied environment variable overrides")
        config = _merge_dicts(config, env_overrides)
    
    return config


def _load_yaml(path: str) -> Dict[str, Any]:
    """Load YAML file."""
    with open(path, "r", encoding="utf-8") as f:
        return yaml.safe_load(f) or {}


def _load_local_config() -> Optional[Dict[str, Any]]:
    """Load local config overrides if exists."""
    local_paths = [
        "config/local.yaml",
        "config/local.yml",
    ]
    
    # Check relative to project root
    project_root = Path(__file__).parent.parent
    
    for local_path in local_paths:
        full_path = project_root / local_path
        if full_path.exists():
            return _load_yaml(str(full_path))
    
    return None


def _get_env_overrides() -> Optional[Dict[str, Any]]:
    """Build config overrides from environment variables."""
    overrides = {}
    
    # Semantic Scholar API Key
    ss_key = os.getenv("SEMANTIC_SCHOLAR_API_KEY")
    if ss_key:
        overrides.setdefault("api_keys", {})["semantic_scholar"] = ss_key
    
    # Zotero credentials
    zotero_lib_id = os.getenv("ZOTERO_LIBRARY_ID")
    zotero_api_key = os.getenv("ZOTERO_API_KEY")
    zotero_lib_type = os.getenv("ZOTERO_LIBRARY_TYPE")
    
    if any([zotero_lib_id, zotero_api_key, zotero_lib_type]):
        api_zotero_cfg = overrides.setdefault("api_keys", {}).setdefault("zotero", {})
        top_level_zotero_cfg = overrides.setdefault("zotero", {})
        if zotero_lib_id:
            api_zotero_cfg["library_id"] = zotero_lib_id
            top_level_zotero_cfg["library_id"] = zotero_lib_id
        if zotero_api_key:
            api_zotero_cfg["api_key"] = zotero_api_key
            top_level_zotero_cfg["api_key"] = zotero_api_key
        if zotero_lib_type:
            api_zotero_cfg["library_type"] = zotero_lib_type
            top_level_zotero_cfg["library_type"] = zotero_lib_type
    
    # Bark notification
    bark_key = os.getenv("BARK_KEY")
    bark_url = os.getenv("BARK_URL")
    
    if any([bark_key, bark_url]):
        notif_cfg = overrides.setdefault("notification", {})
        if bark_key:
            notif_cfg["bark_key"] = bark_key
        if bark_url:
            notif_cfg["bark_url"] = bark_url
    
    return overrides if overrides else None


def _merge_dicts(base: Dict[str, Any], override: Dict[str, Any]) -> Dict[str, Any]:
    """Deep merge two dictionaries."""
    result = base.copy()
    
    for key, value in override.items():
        if key in result and isinstance(result[key], dict) and isinstance(value, dict):
            result[key] = _merge_dicts(result[key], value)
        else:
            result[key] = value
    
    return result


def get_api_key(config: Dict[str, Any], key_path: str) -> Optional[str]:
    """
    Get API key from config with fallback to environment.
    
    Args:
        config: Configuration dict
        key_path: Dot-separated path like "api_keys.semantic_scholar"
        
    Returns:
        API key string or None
    """
    _load_openclaw_env_file()

    # Try config first
    parts = key_path.split(".")
    value = config
    for part in parts:
        if isinstance(value, dict):
            value = value.get(part)
        else:
            value = None
            break
    
    if value:
        return value
    
    # Fallback to environment
    env_map = {
        "api_keys.semantic_scholar": "SEMANTIC_SCHOLAR_API_KEY",
        "api_keys.zotero.api_key": "ZOTERO_API_KEY",
        "api_keys.zotero.library_id": "ZOTERO_LIBRARY_ID",
        "notification.bark_key": "BARK_KEY",
    }
    
    env_var = env_map.get(key_path)
    if env_var:
        return os.getenv(env_var)
    
    return None
