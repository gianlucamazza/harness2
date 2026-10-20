"""Install the pinned DeepSeek SDK and peer for cold OpenCode environments."""

from __future__ import annotations

import json
import subprocess

from harness2 import config

SDK_VERSION = "3.0.69"
ZOD_VERSION = "4.3.6"


def main():
    major = int(
        subprocess.check_output(["node", "--version"], text=True).strip().lstrip("v").split(".")[0]
    )
    if major < 22:
        raise SystemExit("The pinned DeepSeek SDK requires Node.js 22 or newer")
    packages = [f"@ai-sdk/deepseek@{SDK_VERSION}", f"zod@{ZOD_VERSION}"]
    for package in packages:
        subprocess.run(
            [
                "npm",
                "view",
                package,
                "version",
                "engines",
                "peerDependencies",
                "dist.integrity",
                "--json",
            ],
            check=True,
        )
    target = config.DEPENDENCIES / "deepseek-sdk"
    target.mkdir(parents=True, exist_ok=True)
    subprocess.run(
        ["npm", "install", "--prefix", str(target), "--ignore-scripts", "--save-exact", *packages],
        check=True,
    )
    entry = target / "node_modules/@ai-sdk/deepseek/dist/index.js"
    if not entry.is_file():
        raise SystemExit("SDK entrypoint is missing")
    # Import through its installed dependency graph; a Bun auto-install cache is insufficient.
    subprocess.run(
        [
            str(config.BUN),
            "-e",
            f"const m=await import({json.dumps(entry.as_uri())}); if(typeof m.createDeepSeek!=='function') process.exit(1)",
        ],
        check=True,
    )
    print("Pinned DeepSeek SDK and zod peer are ready.")


if __name__ == "__main__":
    main()
