# Vision

## Abstraction

```
VisionProvider
├── OllamaVisionProvider
├── CloudVisionProvider (interface)
└── MockVisionProvider (tests / pre-model smoke)
```

Text chat still uses separate `ModelProvider` / `OllamaProvider`.

## API

`POST /api/vision/analyze` multipart `file`

Response:

```json
{
  "analysis": {
    "content_type": "math_problem",
    "subject": "mathematics",
    "topic": "matrix",
    "problem_text": "...",
    "detected_formula": [],
    "diagram_description": "...",
    "confidence": 0.0,
    "provider": "ollama",
    "model": "moondream:latest"
  },
  "stored_filename": "<uuid>.png",
  "mime_type": "image/png",
  "size": 1234
}
```

The configured local model remains `moondream:latest`. Vision performs visual
understanding and OCR-like extraction only; it is not a math solver. The user
must confirm/edit extracted problem text before Agent execution. Unit tests use
`MockVisionProvider`; production does not silently fall back to mock.
