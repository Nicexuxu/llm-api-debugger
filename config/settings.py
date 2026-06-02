import json
from dataclasses import dataclass, field, asdict
from pathlib import Path


@dataclass
class Settings:
    api_key: str
    base_url: str
    model: str

    @classmethod
    def load(cls, config_path: str | None = None) -> "Settings":
        if config_path is None:
            config_path = Path(__file__).parent.parent / "config.json"
        path = Path(config_path)

        if not path.exists():
            raise FileNotFoundError(
                f"Config file not found: {path}\n"
                "Create a config.json with: api_key, base_url, model"
            )

        with open(path, encoding="utf-8") as f:
            data = json.load(f)

        for key in ("api_key", "base_url", "model"):
            if key not in data:
                raise KeyError(f"Missing required key in config.json: {key}")

        return cls(
            api_key=data["api_key"],
            base_url=data["base_url"].rstrip("/"),
            model=data["model"],
        )

    def save(self, config_path: str | None = None) -> None:
        if config_path is None:
            config_path = Path(__file__).parent.parent / "config.json"
        with open(Path(config_path), "w", encoding="utf-8") as f:
            json.dump(asdict(self), f, indent=2, ensure_ascii=False)
