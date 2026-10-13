"""Run a real Qwen review using only the encrypted administrator configuration."""

import argparse
import json

from scripts.deepseek_smoke import run


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--user-id", type=int)
    parser.add_argument("--upload-id")
    parser.add_argument("--scene-id", type=int)
    args = parser.parse_args()
    result = run(
        args.user_id,
        args.upload_id,
        args.scene_id,
        refresh_key_from_env=False,
        provider="qwen",
    )
    print(json.dumps(result, ensure_ascii=False))


if __name__ == "__main__":
    main()
