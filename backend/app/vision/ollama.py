"""Ollama-backed vision provider."""

from __future__ import annotations

import base64
import json
import re
from typing import Any

import httpx

from app.vision.base import VisionProvider
from app.vision.exceptions import VisionModelMissingError, VisionUnavailableError, VisionError
from app.vision.schemas import VisionAnalysis


_ANALYSIS_PROMPT = """Look at this student homework image.
Write a detailed description first: quote readable text, formulas, and say what kind of problem it is.
Do NOT use placeholder dots like "...".
If you can, end with a real JSON object using concrete values:
{"content_type":"math_problem","subject":"mathematics","topic":"determinant","question_type":"calculation","problem_text":"actual quoted text","detected_formula":["actual formula"],"detected_tables":[],"diagram_description":"short visual summary","confidence":0.6}
"""


class OllamaVisionProvider(VisionProvider):
    name = "ollama"

    def __init__(
        self,
        base_url: str,
        model: str,
        *,
        timeout: float = 180.0,
        client: httpx.AsyncClient | None = None,
        use_json_format: bool | None = None,
    ) -> None:
        self.base_url = base_url.rstrip("/")
        self.model = model
        self.timeout = timeout
        self._client = client
        # moondream often misbehaves with forced JSON mode; default off for moondream
        if use_json_format is None:
            self.use_json_format = "moondream" not in model.lower()
        else:
            self.use_json_format = use_json_format

    async def analyze(
        self,
        image_bytes: bytes,
        *,
        mime_type: str,
        filename: str | None = None,
    ) -> VisionAnalysis:
        b64 = base64.b64encode(image_bytes).decode("ascii")
        payload: dict[str, Any] = {
            "model": self.model,
            "messages": [
                {
                    "role": "user",
                    "content": _ANALYSIS_PROMPT,
                    "images": [b64],
                }
            ],
            "stream": False,
            "options": {
                "temperature": 0.2,
                "num_predict": 256,
            },
        }
        if self.use_json_format:
            payload["format"] = "json"

        data = await self._post_chat(payload)
        message = data.get("message") or {}
        content = str(message.get("content", "")).strip()
        if not content:
            raise VisionError("Vision 模型回傳空內容。")

        parsed = _parse_analysis_json(content)
        parsed.provider = self.name
        parsed.model = self.model
        parsed.raw_text = content
        parsed.total_duration_ns = _as_int(data.get("total_duration"))
        parsed.load_duration_ns = _as_int(data.get("load_duration"))
        parsed.prompt_eval_duration_ns = _as_int(data.get("prompt_eval_duration"))
        parsed.eval_duration_ns = _as_int(data.get("eval_duration"))
        return parsed

    async def _post_chat(self, payload: dict[str, Any]) -> dict[str, Any]:
        url = f"{self.base_url}/api/chat"
        try:
            if self._client is not None:
                response = await self._client.post(url, json=payload)
            else:
                async with httpx.AsyncClient(timeout=self.timeout) as client:
                    response = await client.post(url, json=payload)
        except httpx.ConnectError as exc:
            raise VisionUnavailableError() from exc
        except httpx.TimeoutException as exc:
            raise VisionError("Vision 模型回應逾時，請稍後再試。") from exc
        except httpx.HTTPError as exc:
            raise VisionError(f"無法連線 Ollama Vision：{exc}") from exc

        if response.status_code == 404:
            raise VisionModelMissingError(self.model)

        if response.status_code >= 400:
            detail = (response.text or "")[:300]
            lower = detail.lower()
            if "not found" in lower or "pull" in lower:
                raise VisionModelMissingError(self.model)
            raise VisionError(f"Ollama Vision 請求失敗（{response.status_code}）：{detail}")

        try:
            data = response.json()
        except ValueError as exc:
            raise VisionError("Ollama Vision 回傳非 JSON。") from exc
        if not isinstance(data, dict):
            raise VisionError("Ollama Vision 回傳格式不正確。")
        return data


def _parse_analysis_json(content: str) -> VisionAnalysis:
    text = content.strip()
    if text.startswith("```"):
        text = re.sub(r"^```(?:json)?\s*", "", text)
        text = re.sub(r"\s*```$", "", text)

    raw: dict[str, Any] | None = None
    try:
        parsed = json.loads(text)
        if isinstance(parsed, dict):
            raw = parsed
    except json.JSONDecodeError:
        match = re.search(r"\{[\s\S]*\}", text)
        if match:
            try:
                parsed = json.loads(match.group(0))
                if isinstance(parsed, dict):
                    raw = parsed
            except json.JSONDecodeError:
                raw = None

    # Reject nonsense JSON like {"a":1,"b":2,...} from broken JSON-mode models
    if raw is not None and not _looks_like_analysis(raw):
        raw = None
    if raw is not None and _is_placeholder_analysis(raw):
        raw = None

    if raw is None:
        return VisionAnalysis(
            content_type=_guess_content_type(text),
            subject="mathematics" if _looks_like_math(text) else "unknown",
            topic=_guess_topic(text),
            problem_text=text[:2000],
            detected_formula=_extract_formulas(text),
            diagram_description="Free-form vision caption (structured JSON unavailable).",
            question_type=_guess_topic(text),
            confidence=0.35,
        )

    content_type = str(raw.get("content_type", "unknown"))
    allowed = {"math_problem", "lecture", "note", "diagram", "text", "unknown"}
    if content_type not in allowed:
        content_type = "unknown"

    formulas = raw.get("detected_formula") or []
    if not isinstance(formulas, list):
        formulas = [str(formulas)]

    try:
        confidence = float(raw.get("confidence", 0.0))
    except (TypeError, ValueError):
        confidence = 0.0
    confidence = max(0.0, min(1.0, confidence))

    return VisionAnalysis(
        content_type=content_type,  # type: ignore[arg-type]
        subject=str(raw.get("subject") or "unknown"),
        topic=str(raw.get("topic") or "unknown"),
        problem_text=str(raw.get("problem_text") or ""),
        detected_formula=[str(x) for x in formulas],
        diagram_description=str(raw.get("diagram_description") or ""),
        detected_tables=raw.get("detected_tables")
        if isinstance(raw.get("detected_tables"), list)
        else [],
        question_type=str(raw.get("question_type") or "unknown"),
        confidence=confidence,
    )


def _looks_like_analysis(raw: dict[str, Any]) -> bool:
    keys = set(raw.keys())
    expected = {
        "content_type",
        "subject",
        "topic",
        "problem_text",
        "detected_formula",
        "diagram_description",
        "confidence",
    }
    return len(keys & expected) >= 3


def _is_placeholder_analysis(raw: dict[str, Any]) -> bool:
    text_fields = [
        str(raw.get("problem_text") or ""),
        str(raw.get("diagram_description") or ""),
        str(raw.get("topic") or ""),
    ]
    formulas = raw.get("detected_formula") or []
    if isinstance(formulas, list):
        text_fields.extend(str(x) for x in formulas)
    joined = " ".join(text_fields).strip()
    if not joined or joined.replace(".", "").strip() == "":
        return True
    if joined in {"...", "…", "actual quoted text", "actual formula", "short visual summary"}:
        return True
    if all(part.strip() in {"", "...", "…"} for part in text_fields):
        return True
    return False


def _looks_like_math(text: str) -> bool:
    lower = text.lower()
    return any(
        token in lower
        for token in ("matrix", "determinant", "det(", "equation", "algebra", "矩陣", "行列式")
    )


def _guess_content_type(text: str) -> str:
    if _looks_like_math(text):
        return "math_problem"
    if len(text.strip()) < 8:
        return "unknown"
    return "text"


def _guess_topic(text: str) -> str:
    lower = text.lower()
    if "det" in lower or "determinant" in lower:
        return "determinant"
    if "matrix" in lower or "矩陣" in text:
        return "matrix"
    return "unknown"


def _extract_formulas(text: str) -> list[str]:
    found: list[str] = []
    for match in re.findall(r"det\([^)]+\)|[A-Z]\s*=\s*\[[^\]]+\]", text):
        found.append(match.strip())
    return found[:8]


def _as_int(value: Any) -> int | None:
    try:
        if value is None:
            return None
        return int(value)
    except (TypeError, ValueError):
        return None
