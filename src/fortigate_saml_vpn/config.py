import tomllib
from pathlib import Path

CONFIG_TOML_FILE = "config.toml"


class ConfigError(Exception):
    """Raised when the application configuration is invalid."""


def get_config_path() -> Path:
    # src/fortigate_saml_vpn/config.py -> project root
    return Path(__file__).resolve().parents[2] / CONFIG_TOML_FILE


def load_config(path: str | Path | None = None):
    if path is None:
        path = get_config_path()

    path = Path(path)

    if not path.is_file():
        raise ConfigError(f"Configuration file not found: {path}")

    try:
        with path.open("rb") as file:
            config = tomllib.load(file)
    except tomllib.TOMLDecodeError as exc:
        raise ConfigError(f"Invalid TOML configuration: {exc}") from exc

    required = {
        "fortigate": ["gateway", "saml_port"],
        "strongswan": ["connection"],
    }

    for section, keys in required.items():
        if section not in config:
            raise ConfigError(
                f"Missing configuration section: [{section}]"
            )

        for key in keys:
            if key not in config[section]:
                raise ConfigError(
                    f"Missing configuration value: {section}.{key}"
                )

    return config