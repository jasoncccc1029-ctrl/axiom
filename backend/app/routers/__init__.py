"""API routers."""

from fastapi import APIRouter, Depends, File, Form, HTTPException, UploadFile
from sqlalchemy.orm import Session

from app.config import settings
from app.agent.schemas import AgentRunRequest, AgentRunResponse, AgentTraceResponse
from app.agent.service import AgentService
from app.application.problem_solver import (
    ProblemSolveRequest,
    ProblemSolveResponse,
    ProblemSolverService,
)
from app.application.memory import (
    LearningRecordRequest,
    LearningRecordResponse,
    MemoryService,
)
from app.application.adaptive import (
    AdaptiveTutor,
    RecommendationsResponse,
)
from app.application.learning_loop import (
    LearningLoopService,
    LearningOutcomeRequest,
    LearningOutcomeResponse,
    LearningTrace,
)
from app.application.evaluation import (
    EvaluationItemInput,
    EvaluationMetrics,
    EvaluationService,
    EvaluationSessionOut,
    LearningReport,
    StartEvaluationRequest,
)
from app.application.problem_repository import (
    ProblemCreate,
    ProblemOut,
    ProblemRepository,
    ProblemUpdate,
)
from app.application.error_dna import ErrorDNAProfile, ErrorDNAService
from app.application.student_learning_state import (
    StudentLearningState,
    StudentLearningStateService,
)
from app.application.adaptive_question_engine import (
    AdaptiveQuestionEngine,
    NextProblemResponse,
)
from app.application.student_model import (
    MasteryItem,
    MemoryResponse,
    StudentModelResponse,
    StudentModelService,
    TopicItem,
)
from app.database import get_db
from app.dependencies import (
    provide_agent_service,
    provide_adaptive_tutor,
    provide_adaptive_question_engine,
    provide_error_dna,
    provide_evaluation_service,
    provide_learning_loop,
    provide_model_provider,
    provide_memory_service,
    provide_problem_repository,
    provide_problem_solver,
    provide_student_learning_state,
    provide_student_model,
    provide_vision_provider,
    provide_vision_service,
)
from app.core.errors import AxiomError
from app.knowledge.ingestion import DocumentIngestionService
from app.models import AgentTrace, LearningRecord, Material, Question
from app.providers import ModelProvider, ProviderError
from app.providers.health import check_text_brain_health
from app.schemas import (
    ChatRequest,
    ChatResponse,
    HealthResponse,
    MaterialCreate,
    MaterialOut,
    OllamaHealthResponse,
    ProgressResponse,
    SolveRequest,
    SolveResponse,
    SolveStep,
    SystemHealthResponse,
    SystemComponentHealth,
    VisionAnalysisOut,
    VisionAnalyzeResponse,
    VisionHealthResponse,
    VisionTiming,
)
from app.services import materials as material_service
from app.services.ollama_health import check_ollama_health
from app.services.progress import get_progress
from app.services.vision import VisionService
from app.vision.exceptions import InvalidImageError, VisionError
from app.vision.base import VisionProvider
import time

router = APIRouter()


@router.get("/health", response_model=HealthResponse)
def health() -> HealthResponse:
    return HealthResponse(status="ok", app=settings.app_name, version=settings.app_version)


@router.get("/api/system/health", response_model=SystemHealthResponse)
async def api_system_health() -> SystemHealthResponse:
    """System health: text Brain follows AI_PROVIDER; vision stays independent.

    ``text_brain`` is canonical. ``ollama`` mirrors it for older clients.
    Vision is checked separately (VisionProvider / Ollama VLM).
    """

    text_brain = await check_text_brain_health()

    vision_provider = settings.vision_provider
    if vision_provider == "mock":
        vision_ok = True
        vision_reachable = True
        vision_model = "mock-vision"
        vision_msg = "Vision mock provider active"
    else:
        # Vision pipeline still depends on Ollama VLM when not mock.
        vision = await check_ollama_health(model=settings.ollama_vision_model)
        vision_ok = vision.ok
        vision_reachable = vision.reachable
        vision_model = settings.ollama_vision_model
        vision_msg = vision.message

    backend = SystemComponentHealth(
        ok=True,
        detail=f"{settings.app_name} {settings.app_version} running",
        provider="fastapi",
        reachable=True,
    )
    vision_component = SystemComponentHealth(
        ok=vision_ok,
        detail=vision_msg,
        provider=vision_provider,
        model=vision_model,
        reachable=vision_reachable,
    )
    text_ok = bool(text_brain.ok)
    return SystemHealthResponse(
        ok=backend.ok and text_ok and bool(vision_component.reachable),
        backend=backend,
        text_brain=text_brain,
        ollama=text_brain,
        vision=vision_component,
        version=settings.app_version,
    )


@router.get("/api/ollama/health", response_model=OllamaHealthResponse)
async def api_ollama_health() -> OllamaHealthResponse:
    result = await check_ollama_health()
    return OllamaHealthResponse(
        ok=result.ok,
        reachable=result.reachable,
        model=result.model,
        model_available=result.model_available,
        models=result.models,
        message=result.message,
    )


@router.post("/api/vision/analyze", response_model=VisionAnalyzeResponse)
async def api_vision_analyze(
    file: UploadFile = File(...),
    service: VisionService = Depends(provide_vision_service),
) -> VisionAnalyzeResponse:
    content = await file.read()
    started = time.perf_counter()
    try:
        result = await service.analyze_upload(
            content=content,
            declared_mime=file.content_type,
            original_filename=file.filename,
        )
    except InvalidImageError as exc:
        raise HTTPException(status_code=400, detail=exc.message) from exc
    except VisionError as exc:
        raise HTTPException(status_code=503, detail=exc.message) from exc

    elapsed_ms = (time.perf_counter() - started) * 1000.0
    analysis = result.analysis
    if analysis.provider == "mock":
        # Hard guard: when VISION_PROVIDER=ollama, mock must never appear
        if settings.vision_provider == "ollama":
            raise HTTPException(
                status_code=500,
                detail="Vision provider misconfigured: unexpected mock response.",
            )

    return VisionAnalyzeResponse(
        analysis=VisionAnalysisOut(
            content_type=analysis.content_type,
            subject=analysis.subject,
            topic=analysis.topic,
            problem_text=analysis.problem_text,
            detected_formula=analysis.detected_formula,
            diagram_description=analysis.diagram_description,
            detected_tables=analysis.detected_tables,
            question_type=analysis.question_type,
            confidence=analysis.confidence,
            provider=analysis.provider,
            model=analysis.model,
        ),
        stored_filename=result.stored_filename,
        mime_type=result.mime_type,
        size=result.size,
        timing=VisionTiming(
            response_time_ms=round(elapsed_ms, 1),
            image_size_bytes=result.size,
            total_duration_ns=analysis.total_duration_ns,
            load_duration_ns=analysis.load_duration_ns,
            prompt_eval_duration_ns=analysis.prompt_eval_duration_ns,
            eval_duration_ns=analysis.eval_duration_ns,
        ),
    )


@router.get("/api/vision/health", response_model=VisionHealthResponse)
async def api_vision_health() -> VisionHealthResponse:
    provider_name = settings.vision_provider
    if provider_name == "mock":
        return VisionHealthResponse(
            ok=True,
            provider="mock",
            reachable=True,
            model="mock-vision",
            model_available=True,
            models=["mock-vision"],
            message="Vision mock provider active",
        )

    result = await check_ollama_health(model=settings.ollama_vision_model)
    return VisionHealthResponse(
        ok=result.ok,
        provider="ollama",
        reachable=result.reachable,
        model=settings.ollama_vision_model,
        model_available=result.model_available,
        models=result.models,
        message=result.message if result.ok else result.message,
    )


@router.post("/api/agent/run", response_model=AgentRunResponse)
async def api_agent_run(
    payload: AgentRunRequest,
    service: AgentService = Depends(provide_agent_service),
) -> AgentRunResponse:
    try:
        return await service.run(payload)
    except (ProviderError, AxiomError) as exc:
        raise HTTPException(
            status_code=getattr(exc, "status_code", 503),
            detail=getattr(exc, "message", str(exc)),
        ) from exc


@router.get("/api/agent/{trace_id}", response_model=AgentTraceResponse)
def api_agent_trace(
    trace_id: str,
    service: AgentService = Depends(provide_agent_service),
) -> AgentTraceResponse:
    result = service.get_trace(trace_id)
    if result is None:
        raise HTTPException(status_code=404, detail="Agent trace not found")
    return result


@router.get("/api/learning/trace/{trace_id}", response_model=LearningTrace)
def api_learning_trace(
    trace_id: str,
    service: AgentService = Depends(provide_agent_service),
) -> LearningTrace:
    payload = service.get_learning_trace(trace_id)
    if payload is None:
        raise HTTPException(status_code=404, detail="Learning trace not found")
    return LearningTrace.model_validate(payload)


@router.post("/api/learning/outcome", response_model=LearningOutcomeResponse)
def api_learning_outcome(
    payload: LearningOutcomeRequest,
    service: LearningLoopService = Depends(provide_learning_loop),
    db: Session = Depends(get_db),
) -> LearningOutcomeResponse:
    import json

    try:
        result = service.record_outcome(payload)
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    if payload.trace_id:
        trace = (
            db.query(AgentTrace).filter(AgentTrace.trace_id == payload.trace_id).first()
        )
        if trace is not None:
            existing = json.loads(trace.learning_trace_json or "{}")
            merged = {
                **existing,
                **result.learning_trace.model_dump(),
                "agent_decision": existing.get(
                    "agent_decision", result.learning_trace.agent_decision
                ),
                "selected_tools": existing.get(
                    "selected_tools", result.learning_trace.selected_tools
                ),
                "verification": existing.get(
                    "verification", result.learning_trace.verification
                ),
            }
            trace.learning_trace_json = json.dumps(merged, ensure_ascii=False)
            db.commit()
            result.learning_trace = LearningTrace.model_validate(merged)
    return result


@router.post("/api/learning/session/{session_id}/end")
def api_learning_session_end(
    session_id: int,
    service: LearningLoopService = Depends(provide_learning_loop),
) -> dict:
    session = service.end_session(session_id)
    if session is None:
        raise HTTPException(status_code=404, detail="Learning session not found")
    return {
        "session_id": session.id,
        "status": session.status,
        "ended_at": session.ended_at.isoformat() if session.ended_at else None,
        "activity_count": session.activity_count,
        "duration_minutes": session.duration_minutes,
    }


# --- v1.3 Learning Efficacy Pilot (evaluation data isolated from mastery writes) ---


from pydantic import BaseModel


class EvaluationPhaseRequest(BaseModel):
    evaluation_id: str
    items: list[EvaluationItemInput] | None = None
    score: float | None = None


@router.post("/api/evaluation/start", response_model=EvaluationSessionOut)
def api_evaluation_start(
    payload: StartEvaluationRequest,
    service: EvaluationService = Depends(provide_evaluation_service),
) -> EvaluationSessionOut:
    return service.start(payload)


@router.post("/api/evaluation/pretest", response_model=EvaluationSessionOut)
def api_evaluation_pretest(
    payload: EvaluationPhaseRequest,
    service: EvaluationService = Depends(provide_evaluation_service),
) -> EvaluationSessionOut:
    try:
        return service.record_pretest(
            payload.evaluation_id, items=payload.items, score=payload.score
        )
    except KeyError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc


@router.post("/api/evaluation/posttest", response_model=EvaluationSessionOut)
def api_evaluation_posttest(
    payload: EvaluationPhaseRequest,
    service: EvaluationService = Depends(provide_evaluation_service),
) -> EvaluationSessionOut:
    try:
        return service.record_posttest(
            payload.evaluation_id, items=payload.items, score=payload.score
        )
    except KeyError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc


@router.post("/api/evaluation/{evaluation_id}/begin-learning", response_model=EvaluationSessionOut)
def api_evaluation_begin_learning(
    evaluation_id: str,
    service: EvaluationService = Depends(provide_evaluation_service),
) -> EvaluationSessionOut:
    try:
        return service.begin_learning(evaluation_id)
    except KeyError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc


@router.get("/api/evaluation/{evaluation_id}", response_model=EvaluationSessionOut)
def api_evaluation_get(
    evaluation_id: str,
    service: EvaluationService = Depends(provide_evaluation_service),
) -> EvaluationSessionOut:
    result = service.get(evaluation_id)
    if result is None:
        raise HTTPException(status_code=404, detail="Evaluation not found")
    return result


@router.get("/api/evaluation/{evaluation_id}/metrics", response_model=EvaluationMetrics)
def api_evaluation_metrics(
    evaluation_id: str,
    service: EvaluationService = Depends(provide_evaluation_service),
) -> EvaluationMetrics:
    try:
        return service.compute_metrics(evaluation_id)
    except KeyError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc


@router.get("/api/evaluation/{evaluation_id}/report", response_model=LearningReport)
def api_evaluation_report(
    evaluation_id: str,
    service: EvaluationService = Depends(provide_evaluation_service),
) -> LearningReport:
    try:
        return service.build_report(evaluation_id)
    except KeyError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc


@router.post("/api/problems/solve", response_model=ProblemSolveResponse)
async def api_problems_solve(
    payload: ProblemSolveRequest,
    service: ProblemSolverService = Depends(provide_problem_solver),
) -> ProblemSolveResponse:
    try:
        return await service.solve(payload)
    except ProviderError as exc:
        raise HTTPException(status_code=503, detail=exc.message) from exc


@router.post("/api/learning/record", response_model=LearningRecordResponse)
def api_learning_record(
    payload: LearningRecordRequest,
    service: MemoryService = Depends(provide_memory_service),
) -> LearningRecordResponse:
    return service.record(payload)


@router.get("/api/recommendations", response_model=RecommendationsResponse)
def api_recommendations(
    tutor: AdaptiveTutor = Depends(provide_adaptive_tutor),
) -> RecommendationsResponse:
    return tutor.recommendations()


@router.get("/api/student", response_model=StudentModelResponse)
def api_student(
    service: StudentModelService = Depends(provide_student_model),
) -> StudentModelResponse:
    return service.student()


@router.get("/api/topics", response_model=list[TopicItem])
def api_topics(
    service: StudentModelService = Depends(provide_student_model),
) -> list[TopicItem]:
    return service.topics()


@router.get("/api/mastery", response_model=list[MasteryItem])
def api_mastery(
    service: StudentModelService = Depends(provide_student_model),
) -> list[MasteryItem]:
    return service.mastery()


@router.get("/api/memory", response_model=MemoryResponse)
def api_memory(
    service: StudentModelService = Depends(provide_student_model),
) -> MemoryResponse:
    return service.memory()


@router.get("/api/student/learning-state", response_model=StudentLearningState)
def api_student_learning_state(
    subject: str | None = None,
    topic: str | None = None,
    concept: str | None = None,
    service: StudentLearningStateService = Depends(provide_student_learning_state),
) -> StudentLearningState:
    return service.get(subject=subject, topic=topic, concept=concept)


@router.get("/api/student/next-problem", response_model=NextProblemResponse)
def api_student_next_problem(
    subject: str | None = None,
    topic: str | None = None,
    concept: str | None = None,
    session_id: int | None = None,
    engine: AdaptiveQuestionEngine = Depends(provide_adaptive_question_engine),
) -> NextProblemResponse:
    return engine.select_next_problem(
        subject=subject,
        topic=topic,
        concept=concept,
        session_id=session_id,
    )


@router.get("/api/student/error-dna", response_model=ErrorDNAProfile)
def api_student_error_dna(
    subject: str | None = None,
    topic: str | None = None,
    service: ErrorDNAService = Depends(provide_error_dna),
) -> ErrorDNAProfile:
    return service.profile(subject=subject, topic=topic)


@router.post("/api/problem-bank", response_model=ProblemOut)
def api_problem_bank_create(
    payload: ProblemCreate,
    repo: ProblemRepository = Depends(provide_problem_repository),
) -> ProblemOut:
    return repo.create(payload)


@router.get("/api/problem-bank", response_model=list[ProblemOut])
def api_problem_bank_list(
    subject: str | None = None,
    topic: str | None = None,
    concept: str | None = None,
    limit: int = 50,
    offset: int = 0,
    repo: ProblemRepository = Depends(provide_problem_repository),
) -> list[ProblemOut]:
    return repo.list(
        subject=subject, topic=topic, concept=concept, limit=limit, offset=offset
    )


@router.get("/api/problem-bank/{problem_id}", response_model=ProblemOut)
def api_problem_bank_get(
    problem_id: int,
    repo: ProblemRepository = Depends(provide_problem_repository),
) -> ProblemOut:
    result = repo.get(problem_id)
    if result is None:
        raise HTTPException(status_code=404, detail="Problem not found")
    return result


@router.patch("/api/problem-bank/{problem_id}", response_model=ProblemOut)
def api_problem_bank_update(
    problem_id: int,
    payload: ProblemUpdate,
    repo: ProblemRepository = Depends(provide_problem_repository),
) -> ProblemOut:
    result = repo.update(problem_id, payload)
    if result is None:
        raise HTTPException(status_code=404, detail="Problem not found")
    return result


@router.get("/api/materials", response_model=list[MaterialOut])
def api_list_materials(db: Session = Depends(get_db)) -> list[Material]:
    return material_service.list_materials(db)


@router.post("/api/materials", response_model=MaterialOut)
async def api_create_material(payload: MaterialCreate, db: Session = Depends(get_db)) -> Material:
    material = material_service.create_note_material(
        db,
        title=payload.title,
        subject=payload.subject,
        description=payload.description,
    )
    ingestion = DocumentIngestionService(db)
    await ingestion.ingest_text(
        material,
        "\n".join(value for value in (payload.title, payload.description) if value),
        source="note",
    )
    db.refresh(material)
    return material


@router.post("/api/materials/upload", response_model=MaterialOut)
async def api_upload_material(
    file: UploadFile = File(...),
    title: str = Form(...),
    subject: str = Form(...),
    description: str | None = Form(None),
    db: Session = Depends(get_db),
    vision_provider: VisionProvider = Depends(provide_vision_provider),
) -> Material:
    ingestion = DocumentIngestionService(db, vision_provider=vision_provider)
    return await material_service.save_upload(
        db,
        file=file,
        title=title,
        subject=subject,
        description=description,
        ingestion_service=ingestion,
    )


@router.delete("/api/materials/{material_id}")
def api_delete_material(material_id: int, db: Session = Depends(get_db)) -> dict[str, str]:
    material_service.delete_material(db, material_id)
    return {"status": "deleted"}


@router.post("/api/chat", response_model=ChatResponse)
async def api_chat(
    payload: ChatRequest,
    db: Session = Depends(get_db),
    provider: ModelProvider = Depends(provide_model_provider),
) -> ChatResponse:
    context = None
    if payload.material_id is not None:
        material = db.get(Material, payload.material_id)
        if material:
            context = f"{material.title} / {material.subject}: {material.description or ''}"

    try:
        reply = await provider.chat(payload.message, context=context)
    except ProviderError as exc:
        raise HTTPException(status_code=503, detail=exc.message) from exc

    db.add(
        LearningRecord(
            user_id=settings.default_user_id,
            activity_type="chat",
            subject=(context.split("/")[1].split(":")[0].strip() if context else None),
            duration_minutes=2,
            notes=payload.message[:200],
        )
    )
    db.commit()

    return ChatResponse(
        reply=reply,
        provider=provider.name,
        model=provider.model,
        material_id=payload.material_id,
    )


@router.post("/api/solve", response_model=SolveResponse)
async def api_solve(
    payload: SolveRequest,
    db: Session = Depends(get_db),
    provider: ModelProvider = Depends(provide_model_provider),
) -> SolveResponse:
    try:
        result = await provider.solve(payload.problem, subject=payload.subject)
    except ProviderError as exc:
        raise HTTPException(status_code=503, detail=exc.message) from exc

    verification = result.get("verification", {})
    is_correct = verification.get("status") == "correct"

    question = Question(
        user_id=settings.default_user_id,
        material_id=payload.material_id,
        content=payload.problem,
        subject=payload.subject,
        solution=result.get("answer"),
        is_correct=is_correct,
    )
    db.add(question)
    db.add(
        LearningRecord(
            user_id=settings.default_user_id,
            activity_type="solve",
            subject=payload.subject,
            duration_minutes=5,
            questions_attempted=1,
            questions_correct=1 if is_correct else 0,
            notes=payload.problem[:200],
        )
    )
    db.commit()

    steps = [SolveStep(**step) for step in result.get("steps", [])]
    model_name = str(result.get("model") or provider.model)
    return SolveResponse(
        problem=payload.problem,
        steps=steps,
        answer=str(result.get("answer", "")),
        verification=verification,
        provider=provider.name,
        model=model_name,
    )


@router.get("/api/progress", response_model=ProgressResponse)
def api_progress(db: Session = Depends(get_db)) -> ProgressResponse:
    return get_progress(db)
