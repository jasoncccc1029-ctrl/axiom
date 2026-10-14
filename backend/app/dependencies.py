"""Application dependency container and FastAPI dependency providers."""

from __future__ import annotations

import httpx
from fastapi import Depends, Request
from sqlalchemy.orm import Session

from app.agent.service import AgentService
from app.application.problem_solver import ProblemSolverService
from app.application.memory import MemoryService
from app.application.adaptive import AdaptiveTutor
from app.application.learning_loop import LearningLoopService
from app.application.evaluation import EvaluationService
from app.application.problem_repository import ProblemRepository
from app.application.error_dna import ErrorDNAService
from app.application.student_learning_state import StudentLearningStateService
from app.application.adaptive_question_engine import AdaptiveQuestionEngine
from app.application.student_model import StudentModelService
from app.config import settings
from app.database import get_db
from app.guest import provide_user_id
from app.knowledge.embedding import LocalHashEmbeddingProvider
from app.knowledge.retriever import KnowledgeRetriever
from app.knowledge.vector_store import SQLiteVectorStore
from app.providers import ModelProvider
from app.providers.factory import get_provider
from app.services.vision import VisionService
from app.tools.knowledge import KnowledgeSearchTool
from app.tools.math import CalculatorTool, MathTool
from app.tools.python import PythonTool
from app.tools.router import ToolRouter
from app.vision import VisionProvider
from app.vision.factory import get_vision_provider


class AppContainer:
    """Long-lived dependencies initialized once per application lifecycle."""

    def __init__(self) -> None:
        timeout = max(settings.model_timeout_seconds, settings.vision_timeout_seconds)
        self.http_client = httpx.AsyncClient(timeout=timeout)
        self.model_provider = get_provider(client=self.http_client)
        self.vision_provider = get_vision_provider(client=self.http_client)
        self.vision_service = VisionService(provider=self.vision_provider)
        self.embedding_provider = LocalHashEmbeddingProvider(settings.embedding_dimensions)

    async def close(self) -> None:
        await self.http_client.aclose()


def get_container(request: Request) -> AppContainer:
    return request.app.state.container


def provide_model_provider(request: Request) -> ModelProvider:
    return get_container(request).model_provider


def provide_vision_provider(request: Request) -> VisionProvider:
    return get_container(request).vision_provider


def provide_vision_service(request: Request) -> VisionService:
    return get_container(request).vision_service


def provide_agent_service(
    request: Request,
    db: Session = Depends(get_db),
    user_id: int = Depends(provide_user_id),
) -> AgentService:
    container = get_container(request)
    store = SQLiteVectorStore(db)
    retriever = KnowledgeRetriever(container.embedding_provider, store)
    tools = ToolRouter(
        [KnowledgeSearchTool(retriever), CalculatorTool(), MathTool(), PythonTool()]
    )
    return AgentService(
        db,
        container.model_provider,
        tools,
        user_id=user_id,
        adaptive_tutor=AdaptiveTutor(db, user_id),
        student_model=StudentModelService(db, user_id),
        learning_loop=LearningLoopService(db, user_id),
        learning_state=StudentLearningStateService(db, user_id),
    )


def provide_problem_solver(
    request: Request,
    db: Session = Depends(get_db),
    user_id: int = Depends(provide_user_id),
) -> ProblemSolverService:
    return ProblemSolverService(
        get_container(request).model_provider,
        db=db,
        learning_state=StudentLearningStateService(db, user_id),
        student_model=StudentModelService(db, user_id),
    )


def provide_memory_service(
    db: Session = Depends(get_db),
    user_id: int = Depends(provide_user_id),
) -> MemoryService:
    return MemoryService(db, user_id)


def provide_adaptive_tutor(
    db: Session = Depends(get_db),
    user_id: int = Depends(provide_user_id),
) -> AdaptiveTutor:
    return AdaptiveTutor(db, user_id)


def provide_student_model(
    db: Session = Depends(get_db),
    user_id: int = Depends(provide_user_id),
) -> StudentModelService:
    return StudentModelService(db, user_id)


def provide_learning_loop(
    db: Session = Depends(get_db),
    user_id: int = Depends(provide_user_id),
) -> LearningLoopService:
    return LearningLoopService(db, user_id)


def provide_evaluation_service(
    db: Session = Depends(get_db),
    user_id: int = Depends(provide_user_id),
) -> EvaluationService:
    return EvaluationService(db, user_id)


def provide_problem_repository(db: Session = Depends(get_db)) -> ProblemRepository:
    return ProblemRepository(db)


def provide_error_dna(
    db: Session = Depends(get_db),
    user_id: int = Depends(provide_user_id),
) -> ErrorDNAService:
    return ErrorDNAService(db, user_id)


def provide_student_learning_state(
    db: Session = Depends(get_db),
    user_id: int = Depends(provide_user_id),
) -> StudentLearningStateService:
    return StudentLearningStateService(db, user_id)


def provide_adaptive_question_engine(
    db: Session = Depends(get_db),
    user_id: int = Depends(provide_user_id),
) -> AdaptiveQuestionEngine:
    return AdaptiveQuestionEngine(db, user_id)
