"""FastAPI service for Cloud Run & RapidAPI deployment."""

from __future__ import annotations

from fastapi import FastAPI, HTTPException
from pydantic import BaseModel, Field

from .engine import ComplianceGuardEngine, Finding, normalize_jp_business_text

app = FastAPI(
    title="JP Compliance & LLM PII Guard API",
    version="1.0.0",
    description="Check-digit-verified Japanese PII redaction, normalization, and prompt-injection screening.",
)

_engine = ComplianceGuardEngine()


class RedactRequest(BaseModel):
    text: str | None = None
    texts: list[str] | None = None
    include_vault: bool = True


class RedactItemResponse(BaseModel):
    redacted_text: str
    vault_map: dict[str, str] = Field(default_factory=dict)
    findings: list[Finding] = Field(default_factory=list)
    injection_risk_score: float
    injection_flags: list[str] = Field(default_factory=list)


class RedactBatchResponse(BaseModel):
    count: int
    results: list[RedactItemResponse]


class RestoreRequest(BaseModel):
    text: str
    vault_map: dict[str, str] = Field(default_factory=dict)


class RestoreResponse(BaseModel):
    restored_text: str


class NormalizeRequest(BaseModel):
    text: str | None = None
    texts: list[str] | None = None


class NormalizeResponse(BaseModel):
    normalized_text: str | None = None
    normalized_texts: list[str] | None = None


@app.get("/healthz")
def healthz() -> dict[str, str]:
    return {"status": "ok", "engine": "jp-compliance-guard-v1"}


@app.post("/v1/redact", response_model=RedactItemResponse | RedactBatchResponse)
def redact_endpoint(req: RedactRequest) -> RedactItemResponse | RedactBatchResponse:
    if req.text is not None and req.texts is not None:
        raise HTTPException(status_code=422, detail="Provide either 'text' or 'texts', not both.")
    if req.text is None and req.texts is None:
        raise HTTPException(status_code=422, detail="Either 'text' or 'texts' is required.")

    if req.text is not None:
        res = _engine.redact(req.text)
        return RedactItemResponse(
            redacted_text=res.redacted_text,
            vault_map=res.vault_map if req.include_vault else {},
            findings=res.findings,
            injection_risk_score=res.injection_risk_score,
            injection_flags=res.injection_flags,
        )

    assert req.texts is not None
    items: list[RedactItemResponse] = []
    for item_text in req.texts:
        res = _engine.redact(item_text)
        items.append(
            RedactItemResponse(
                redacted_text=res.redacted_text,
                vault_map=res.vault_map if req.include_vault else {},
                findings=res.findings,
                injection_risk_score=res.injection_risk_score,
                injection_flags=res.injection_flags,
            )
        )
    return RedactBatchResponse(count=len(items), results=items)


@app.post("/v1/restore", response_model=RestoreResponse)
def restore_endpoint(req: RestoreRequest) -> RestoreResponse:
    return RestoreResponse(restored_text=_engine.restore(req.text, req.vault_map))


@app.post("/v1/normalize", response_model=NormalizeResponse)
def normalize_endpoint(req: NormalizeRequest) -> NormalizeResponse:
    if req.text is not None and req.texts is not None:
        raise HTTPException(status_code=422, detail="Provide either 'text' or 'texts', not both.")
    if req.text is None and req.texts is None:
        raise HTTPException(status_code=422, detail="Either 'text' or 'texts' is required.")
    if req.text is not None:
        return NormalizeResponse(normalized_text=normalize_jp_business_text(req.text))
    assert req.texts is not None
    return NormalizeResponse(
        normalized_texts=[normalize_jp_business_text(t) for t in req.texts]
    )
