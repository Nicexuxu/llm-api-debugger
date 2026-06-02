"""OpenAI Chat API 调试工具入口。"""

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent))

from config.settings import Settings
from tui.app import App


def main():
    try:
        settings = Settings.load()
    except FileNotFoundError as e:
        print(str(e))
        sys.exit(1)
    except (KeyError, json.JSONDecodeError) as e:
        print(f"Invalid config.json: {e}")
        sys.exit(1)

    app = App(settings)
    try:
        app.run()
    except KeyboardInterrupt:
        print()
        sys.exit(0)


if __name__ == "__main__":
    import json
    main()
