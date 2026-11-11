#!/usr/bin/env python3
"""Prepare a version-checked private OpenMausBot UI overlay; never deploy/restart.

Copied CLI finds this runtime's dist and passes OMB_STATIC_DIR to the unchanged
server. Native assets, auth and endpoints are reused without patching npm files.
"""
import argparse
import hashlib
import json
import os
from pathlib import Path
import shutil
import sys
import tempfile

OVERLAY = Path(__file__).resolve().parents[1] / "integrations/openmausbot/workbench"
MARKER = ".workflour-workbench.json"


def sha(path):
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def verify_source(source, lock):
    source = Path(source).resolve(strict=True)
    package = json.loads((source / "package.json").read_text())
    if package.get("name") != lock["package"] or package.get("version") != lock["version"]:
        raise ValueError("Expected the pinned OpenMausBot package version")
    for name, expected in lock["sha256"].items():
        if sha(source / name) != expected:
            raise ValueError("Pinned source hash differs: " + name)
    return source


def injected_index(original, css_hash, js_hash):
    if original.count("</head>") != 1 or "workflour-workbench" in original:
        raise ValueError("Unexpected upstream index structure")
    tags = (f'    <link rel="stylesheet" href="/workflour-workbench.css?v={css_hash[:16]}" />\n'
            f'    <script defer src="/workflour-workbench.js?v={js_hash[:16]}"></script>\n')
    return original.replace("</head>", tags + "  </head>")


def verify_runtime(output, source, lock):
    output = Path(output).resolve(strict=True)
    info = json.loads((output / MARKER).read_text())
    if info.get("kind") != "workflour-workbench" or Path(info["source"]).resolve() != source:
        raise ValueError("Not the expected managed private runtime")
    verify_source(source, lock)
    for name, expected in info["copied_sha256"].items():
        path = output / name
        if path.is_symlink() or sha(path) != expected:
            raise ValueError("Private copied file differs: " + name)
    for name, expected in info["symlinks"].items():
        path = output / name
        if not path.is_symlink() or path.resolve(strict=True) != Path(expected).resolve(strict=True):
            raise ValueError("Private runtime symlink differs: " + name)
    for name, expected in info["overlay_sha256"].items():
        if sha(OVERLAY / name) != expected:
            raise ValueError("Project overlay changed; prepare a new runtime")
    return info


def prepare(source, output, lock):
    source = verify_source(source, lock)
    output = Path(output).expanduser()
    if output.is_symlink():
        raise ValueError("Runtime destination cannot be a symlink")
    output = output.resolve()
    if output == source or source in output.parents:
        raise ValueError("Runtime must be outside the installed package")
    if output.exists():
        return verify_runtime(output, source, lock)
    output.parent.mkdir(parents=True, exist_ok=True)
    stage = Path(tempfile.mkdtemp(prefix=".workbench-", dir=output.parent))
    copied, links = {}, {}
    def copy(name, from_path=None):
        target = stage / name
        target.parent.mkdir(parents=True, exist_ok=True)
        shutil.copy2(from_path or source / name, target)
        copied[str(name)] = sha(target)
    def link(name, from_path=None):
        target = stage / name
        target.parent.mkdir(parents=True, exist_ok=True)
        origin = from_path or source / name
        target.symlink_to(origin, target_is_directory=origin.is_dir())
        links[str(name)] = str(origin)
    try:
        for path in source.iterdir():
            if path.name in {"dist", "dist-server"}:
                continue
            if path.name in {"cli.js", "package.json"}:
                copy(path.name)
            else:
                link(path.name)
        for path in (source / "dist-server").iterdir():
            name = Path("dist-server") / path.name
            if path.name == "openmausbot.js":
                copy(name)
            else:
                link(name)
        for path in (source / "dist").iterdir():
            if path.name != "index.html":
                link(Path("dist") / path.name)
        overlay_hashes = {name: sha(OVERLAY / name) for name in ("workbench.css", "workbench.js")}
        copy("dist/workflour-workbench.css", OVERLAY / "workbench.css")
        copy("dist/workflour-workbench.js", OVERLAY / "workbench.js")
        original = (source / "dist/index.html").read_text()
        index = injected_index(original, overlay_hashes["workbench.css"], overlay_hashes["workbench.js"])
        (stage / "dist/index.html").write_text(index)
        copied["dist/index.html"] = sha(stage / "dist/index.html")
        info = {"kind": "workflour-workbench", "version": lock["version"], "source": str(source),
                "copied_sha256": copied, "symlinks": links, "overlay_sha256": overlay_hashes,
                "cli": str(output / "cli.js"), "static_dir": str(output / "dist"),
                "deployed": False, "note": "Prepared only; no launchd/config/server/data mutation"}
        (stage / MARKER).write_text(json.dumps(info, ensure_ascii=False, indent=2) + "\n")
        # Recheck after staging to catch a package update during preparation.
        verify_source(source, lock)
        stage.rename(output)
        return verify_runtime(output, source, lock)
    finally:
        if stage.exists():
            shutil.rmtree(stage)


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--source", default="/opt/homebrew/lib/node_modules/openmausbot")
    parser.add_argument("--out", default=str(Path.home() / ".workflour/runtime/openmausbot-0.1.143-workbench"))
    parser.add_argument("--verify", action="store_true", help="Verify an existing private runtime, without writing")
    args = parser.parse_args()
    try:
        lock = json.loads((OVERLAY / "source-lock.json").read_text())
        source = verify_source(args.source, lock)
        info = verify_runtime(args.out, source, lock) if args.verify else prepare(source, args.out, lock)
        print(json.dumps({key: info[key] for key in ("version", "cli", "static_dir", "deployed")}, ensure_ascii=False))
        return 0
    except (ValueError, OSError, KeyError) as error:
        print("Workbench preparation failed: " + str(error), file=sys.stderr)
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
