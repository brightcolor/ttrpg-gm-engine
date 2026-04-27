import json
import re
import yaml

PROMPT_INJECTION_RE = re.compile(r"(ignore previous|system prompt|developer message|follow these instructions|jailbreak)", re.I)


def detect_prompt_injection(text: str) -> list[str]:
    return [match.group(0) for match in PROMPT_INJECTION_RE.finditer(text)]


def chunk_text(text: str, max_chars: int = 1200) -> list[str]:
    paragraphs = [p.strip() for p in re.split(r"\n\s*\n", text) if p.strip()]
    chunks: list[str] = []
    current = ""
    for paragraph in paragraphs:
        if len(current) + len(paragraph) > max_chars and current:
            chunks.append(current.strip())
            current = ""
        current += paragraph + "\n\n"
    if current.strip():
        chunks.append(current.strip())
    return chunks or ([text[:max_chars]] if text else [])


def parse_import_payload(filename: str, content: str) -> dict:
    suffix = filename.rsplit(".", 1)[-1].lower()
    if suffix == "json":
        data = json.loads(content)
    elif suffix in ("yaml", "yml"):
        data = yaml.safe_load(content)
    else:
        data = {"title": filename, "content": content}
    raw_text = content if isinstance(content, str) else json.dumps(data)
    return {
        "data": data,
        "injection_warnings": detect_prompt_injection(raw_text),
        "chunks": chunk_text(raw_text),
    }

