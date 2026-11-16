import codecs
import fnmatch
import json
import os
from pathlib import Path
import stat
import tempfile


class ToolError(ValueError):
    pass


def dumps(value):
    return json.dumps(value, ensure_ascii=False, separators=(",", ":"), allow_nan=False)


def schema(name, description, properties, required):
    return {"type": "function", "function": {"name": name, "description": description,
        "parameters": {"type": "object", "properties": properties,
                       "required": required, "additionalProperties": False}}}


S, I, B = {"type": "string"}, {"type": "integer", "minimum": 1}, {"type": "boolean"}
SCHEMAS = {
    "view": schema("view", "Read UTF-8 lines, page losslessly with byte offset, or list one directory level.",
                   {"path": S, "start": I, "end": I, "offset": {"type": "integer", "minimum": 0}}, ["path"]),
    "grep": schema("grep", "Find literal text in UTF-8 files, with bounded matches.",
                   {"pattern": S, "path": S, "file_glob": S, "case_sensitive": B}, ["pattern"]),
    "glob": schema("glob", "Find paths; count matches but return a bounded subset.",
                   {"pattern": S, "path": S, "max_depth": I}, ["pattern"]),
    "edit": schema("edit", "Replace exact UTF-8 text in one existing file; require one match by default.",
                   {"path": S, "old": S, "new": S, "allow_multiple": B, "dry_run": B},
                   ["path", "old", "new"]),
    "task_complete": schema("task_complete", "Finish immediately with a short final summary.",
                            {"summary": S}, ["summary"]),
}
GUIDANCE = {
    "view": "view: list a directory or read lines. For lossless file paging start with offset=0, then use next_offset until eof.",
    "grep": "grep: literal search; narrow the path and file_glob.",
    "glob": "glob: narrow patterns or explore hierarchically when truncated.",
    "edit": "edit: supply exact old/new text; preserve unrelated bytes.",
    "task_complete": "task_complete: provide a short summary; this ends the loop.",
}
DEFAULT_LIMITS = {name: {"max_items": 50, "max_lines": 200, "max_bytes": 8192, "max_tokens": 2048}
                  for name in SCHEMAS}
DEFAULT_LIMITS["glob"]["max_depth"] = 3


def local_path(root, value, must_exist=True):
    if not isinstance(value, str) or "\x00" in value or value.startswith(("\\\\", "//")):
        raise ToolError("Invalid local path; network paths are not allowed.")
    candidate = Path(value)
    if any(":" in part for part in candidate.parts if part != candidate.anchor):
        raise ToolError("Alternate streams and network paths are not allowed.")
    resolved = (root / candidate).resolve(strict=must_exist)
    if str(resolved).startswith(("\\\\", "//")) or not resolved.is_relative_to(root):
        raise ToolError("Path is outside the configured working root.")
    return resolved


def read_text(path, max_bytes):
    if not stat.S_ISREG(path.stat().st_mode):
        raise ToolError("Only regular local text files are supported.")
    with path.open("rb") as stream:
        data = stream.read(max_bytes + 1)
    truncated = len(data) > max_bytes
    data = data[:max_bytes]
    if b"\0" in data:
        raise ToolError("Binary content is not allowed.")
    try:
        text = codecs.getincrementaldecoder("utf-8-sig")().decode(data, final=not truncated)
    except UnicodeDecodeError as error:
        raise ToolError("File is not UTF-8 text; binary/other encodings are not injected.") from error
    return text, truncated


def read_chunk(path, offset, max_bytes):
    if not stat.S_ISREG(path.stat().st_mode):
        raise ToolError("Only regular local text files are supported.")
    with path.open("rb") as stream:
        size = os.fstat(stream.fileno()).st_size
        if offset > size:
            raise ToolError("Byte offset exceeds the file size.")
        stream.seek(offset)
        data = stream.read(max_bytes)
    if b"\0" in data:
        raise ToolError("Binary content is not allowed.")
    decoder = codecs.getincrementaldecoder("utf-8")()
    try:
        text = decoder.decode(data, final=offset + len(data) == size)
    except UnicodeDecodeError as error:
        raise ToolError("File is not UTF-8 text or offset is not a UTF-8 boundary.") from error
    consumed = len(data) - len(decoder.getstate()[0])
    if data and not consumed:
        raise ToolError("Read limit cannot fit one UTF-8 character; raise read_bytes.")
    next_offset = offset + consumed
    return {"text": text, "start_offset": offset, "next_offset": next_offset,
            "total_bytes": size, "eof": next_offset == size, "more_available": next_offset < size,
            "content_clipped": False, "truncated": False}


def walk(root, start, depth, scan_limit, check):
    pending, scanned = [(start, 0)], 0
    while pending:
        directory, level = pending.pop()
        with os.scandir(directory) as entries:
            for entry in entries:
                check()
                scanned += 1
                if scanned > scan_limit:
                    raise ToolError(f"Scan limit ({scan_limit}) reached; narrow the path or raise scan_files.")
                info = entry.stat(follow_symlinks=False)
                if entry.is_symlink() or getattr(info, "st_file_attributes", 0) & 0x400:
                    continue
                path = local_path(root, entry.path)
                yield path
                if stat.S_ISDIR(info.st_mode) and level + 1 < depth:
                    pending.append((path, level + 1))


def matches(path, pattern):
    return fnmatch.fnmatchcase(path, pattern) or (
        pattern.startswith("**/") and fnmatch.fnmatchcase(path, pattern[3:]))


def validate_arguments(name, args):
    definition = SCHEMAS[name]["function"]["parameters"]
    if not isinstance(args, dict) or set(args) - set(definition["properties"]):
        raise ToolError("Tool arguments must be an object with only declared properties.")
    if set(definition["required"]) - set(args):
        raise ToolError("Missing required tool arguments.")
    for key, value in args.items():
        expected = definition["properties"][key]["type"]
        if expected == "string" and not isinstance(value, str):
            raise ToolError(f"{key} must be a string.")
        if expected == "integer" and (type(value) is not int or value < definition["properties"][key].get("minimum", 1)):
            raise ToolError(f"{key} is below its declared integer minimum.")
        if expected == "boolean" and type(value) is not bool:
            raise ToolError(f"{key} must be boolean.")


def execute(name, args, config, check):
    validate_arguments(name, args)
    root = Path(config["working_root"]).resolve(strict=True)
    limit = config["limits"][name]
    check()
    if name == "task_complete":
        if not args["summary"].strip() or len(args["summary"].encode("utf-8")) > limit["max_bytes"]:
            raise ToolError("Completion summary is empty or exceeds its byte limit.")
        return {"summary": args["summary"], "complete": True}
    path = local_path(root, args.get("path", "."))
    if name == "view":
        if "offset" in args and (path.is_dir() or "start" in args or "end" in args):
            raise ToolError("offset is for files and cannot be combined with line ranges.")
        if path.is_dir():
            total, items = 0, []
            with os.scandir(path) as entries:
                for entry in entries:
                    check()
                    total += 1
                    if total > config["scan_files"]:
                        raise ToolError("Directory scan limit reached; narrow the working root.")
                    if len(items) < limit["max_items"]:
                        items.append({"name": entry.name, "directory": entry.is_dir(follow_symlinks=False)})
            return {"items": items, "total": total, "returned": len(items), "truncated": total > len(items)}
        if "offset" in args:
            return read_chunk(path, args["offset"], config["read_bytes"])
        text, partial = read_text(path, config["read_bytes"])
        lines, start = text.splitlines(), args.get("start", 1)
        end = args.get("end", start + limit["max_lines"] - 1)
        if end < start:
            raise ToolError("end must be at least start.")
        if partial and start > len(lines):
            raise ToolError("Requested lines exceed the bounded file read; raise read_bytes.")
        end = min(end, start + limit["max_lines"] - 1)
        items = [{"line": n + 1, "text": lines[n]} for n in range(start - 1, min(end, len(lines)))]
        return {"items": items, "total": None if partial else len(lines), "returned": len(items),
                "file_bytes": path.stat().st_size, "truncated": partial or end < len(lines),
                "more_available": partial or end < len(lines), "content_clipped": False,
                "read_prefix_limited": partial}
    if name in {"glob", "grep"}:
        if not path.is_dir():
            candidates = [path]
        else:
            depth = min(args.get("max_depth", config["scan_depth"]), config["scan_depth"])
            if name == "glob":
                depth = min(depth, limit["max_depth"])
            candidates = walk(root, path, depth, config["scan_files"], check)
        items, total, skipped_binary, partial_files = [], 0, 0, 0
        pattern = args["pattern"]
        if not pattern:
            raise ToolError("Search pattern must not be empty.")
        for candidate in candidates:
            check()
            relative = candidate.relative_to(root).as_posix()
            if name == "glob":
                if matches(candidate.relative_to(path).as_posix() if path.is_dir() else candidate.name, pattern):
                    total += 1
                    if len(items) < limit["max_items"]:
                        items.append(relative)
            elif candidate.is_file() and matches(relative, args.get("file_glob", "**/*")):
                try:
                    text, partial = read_text(candidate, config["read_bytes"])
                except ToolError:
                    skipped_binary += 1
                    continue
                partial_files += int(partial)
                needle = pattern if args.get("case_sensitive", True) else pattern.casefold()
                for number, line in enumerate(text.splitlines(), 1):
                    check()
                    if needle in (line if args.get("case_sensitive", True) else line.casefold()):
                        total += 1
                        if len(items) < limit["max_items"]:
                            items.append({"path": relative, "line": number, "text": line})
        return {"items": items, "total": total, "returned": len(items),
                "total_exact_within_scan": partial_files == 0,
                "skipped_binary_files": skipped_binary, "partial_files": partial_files,
                "truncated": total > len(items) or partial_files > 0,
                "note": "Narrow the pattern or explore hierarchically." if total > len(items) else ""}
    if name == "edit":
        if not args["old"]:
            raise ToolError("old must not be empty.")
        read_text(path, config["read_bytes"])
        if path.stat().st_size > config["read_bytes"]:
            raise ToolError("Edit exceeds read_bytes; no partial edits are performed.")
        original = path.read_bytes()
        old, new = args["old"].encode("utf-8"), args["new"].encode("utf-8")
        count = original.count(old)
        if count == 0 or (count != 1 and not args.get("allow_multiple", False)):
            raise ToolError(f"Exact old text occurs {count} times; expected exactly once.")
        changed = original.replace(old, new)
        check()
        if not args.get("dry_run", False):
            with tempfile.NamedTemporaryFile(dir=path.parent, delete=False) as temporary:
                temporary.write(changed)
                temporary_name = Path(temporary.name)
            try:
                os.chmod(temporary_name, stat.S_IMODE(path.stat().st_mode))
                if path.read_bytes() != original:
                    raise ToolError("File changed during the edit; refusing to overwrite it.")
                os.replace(temporary_name, path)
            finally:
                temporary_name.unlink(missing_ok=True)
        return {"path": path.relative_to(root).as_posix(), "replacements": count,
                "first_changed_line": original[:original.index(old)].count(b"\n") + 1,
                "old_bytes": len(original), "new_bytes": len(changed), "dry_run": args.get("dry_run", False)}
    raise ToolError("Unknown tool.")


def bound_result(result, limit, count):
    bounded = json.loads(dumps(result))
    for _ in range(40):
        text = dumps(bounded)
        if len(text.encode("utf-8")) <= limit["max_bytes"] and count(text) <= limit["max_tokens"]:
            return bounded, text
        bounded["truncated"] = True
        bounded["content_clipped"] = True
        if "next_offset" in bounded and isinstance(bounded.get("text"), str):
            value = bounded["text"]
            if len(value) <= 1:
                raise ToolError("Tool limits cannot fit one character and its cursor metadata.")
            bounded["text"] = value[:max(1, len(value) // 2)]
            bounded["next_offset"] = bounded["start_offset"] + len(bounded["text"].encode("utf-8"))
            bounded["eof"] = False
            bounded["more_available"] = True
        elif bounded.get("items"):
            if len(bounded["items"]) > 1:
                bounded["items"] = bounded["items"][:max(1, len(bounded["items"]) // 2)]
                bounded["returned"] = len(bounded["items"])
            elif isinstance(bounded["items"][0], dict) and len(bounded["items"][0].get("text", "")) > 8:
                value = bounded["items"][0]["text"]
                bounded["items"][0]["text"] = value[:len(value) // 2]
            else:
                bounded["items"], bounded["returned"] = [], 0
        elif isinstance(bounded.get("summary"), str):
            raise ToolError("Completion summary exceeds its token limit; shorten it.")
        elif isinstance(bounded.get("error"), str) and len(bounded["error"]) > 8:
            bounded["error"] = bounded["error"][:len(bounded["error"]) // 2]
        else:
            raise ToolError("Tool metadata cannot fit the configured result limits.")
    raise ToolError("Tool result could not be bounded.")
