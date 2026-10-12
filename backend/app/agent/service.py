"""Bounded Agent executor and closed-loop learning trace persistence."""

from __future__ import annotations

import json
import time
import uuid
from typing import Any

from sqlalchemy.orm import Session

from app.agent.context import ContextBuilder
from app.agent.orchestrator import AgentOrchestrator
from app.agent.planner import Planner
from app.agent.schemas import (
    AgentRunRequest,
    AgentRunResponse,
    AgentTraceResponse,
    TeachingMode,
    ToolCallTrace,
    SourceReference,
    VerificationStatus,
)
from app.agent.verifier import Verifier
from app.application.adaptive import AdaptiveTutor
from app.application.learning_loop import LearningLoopService, LearningOutcomeRequest
from app.application.outcome_automation import decide_from_verification
from app.application.student_learning_state import StudentLearningStateService
from app.application.student_model import StudentModelService
from app.application.subject_aliases import (
    canonicalize_subject,
    normalize_learning_label,
)
from app.config import settings
from app.models import AgentTrace, Conversation, Material, Message, Question, utcnow
from app.providers.base import ModelProvider
from app.tools.base import ToolResult
from app.tools.router import ToolRouter


class AgentService:
    def __init__(
        self,
        db: Session,
        model_provider: ModelProvider,
        tool_router: ToolRouter,
        *,
        planner: Planner | None = None,
        context_builder: ContextBuilder | None = None,
        verifier: Verifier | None = None,
        adaptive_tutor: AdaptiveTutor | None = None,
        orchestrator: AgentOrchestrator | None = None,
        student_model: StudentModelService | None = None,
        learning_loop: LearningLoopService | None = None,
        learning_state: StudentLearningStateService | None = None,
    ) -> None:
        self.db = db
        self.model_provider = model_provider
        self.tool_router = tool_router
        self.orchestrator = orchestrator or AgentOrchestrator()
        self.planner = planner or Planner(settings.max_agent_steps, self.orchestrator)
        self.context_builder = context_builder or ContextBuilder()
        self.verifier = verifier or Verifier()
        self.adaptive_tutor = adaptive_tutor or AdaptiveTutor(db)
        self.student_model = student_model or StudentModelService(db)
        self.learning_loop = learning_loop or LearningLoopService(db)
        self.learning_state = learning_state or StudentLearningStateService(db)

    async def run(self, request: AgentRunRequest) -> AgentRunResponse:
        started = time.perf_counter()
        trace_id = uuid.uuid4().hex
        requested_mode = request.mode
        # Avoid polluting mastery / learning-state with placeholder topics.
        subject = canonicalize_subject(normalize_learning_label(request.subject))
        topic = normalize_learning_label(request.topic)
        # Resolve focus from material / lean learning state when chat omitted it.
        if request.material_id and not subject:
            material = self.db.get(Material, request.material_id)
            if material is not None:
                subject = canonicalize_subject(material.subject)
        if subject and not topic:
            lean = self.learning_state.get(subject=subject).model_dump()
            topic = normalize_learning_label(
                lean.get("current_topic")
                or (
                    (lean.get("recent_errors") or [{}])[0].get("topic")
                    if lean.get("recent_errors")
                    else None
                )
            )
        request = request.model_copy(update={"subject": subject, "topic": topic})

        conversation = (
            self.db.get(Conversation, request.conversation_id)
            if request.conversation_id is not None
            else None
        )
        if conversation is None or conversation.user_id != settings.default_user_id:
            conversation = Conversation(
                user_id=settings.default_user_id,
                title=(request.confirmed_problem or request.message)[:120],
            )
            self.db.add(conversation)
            self.db.flush()

        session = self.learning_loop.get_or_create_session(
            subject=request.subject,
            topic=request.topic,
            conversation_id=conversation.id,
            session_id=request.session_id,
        )
        student_state = self.learning_loop.snapshot_mastery(request.subject, request.topic)
        adapted_mode, mode_reason = self.learning_loop.adapt_teaching_mode(
            requested_mode,
            subject=request.subject,
            topic=request.topic,
        )
        effective_request = request.model_copy(update={"mode": adapted_mode})

        question = Question(
            user_id=settings.default_user_id,
            material_id=request.material_id,
            content=request.confirmed_problem or request.message,
            subject=request.subject,
            topic=request.topic,
        )
        self.db.add(question)
        self.db.flush()

        self.db.add(
            Message(
                conversation_id=conversation.id,
                role="user",
                content=request.confirmed_problem or request.message,
                trace_id=trace_id,
            )
        )
        trace = AgentTrace(
            trace_id=trace_id,
            user_id=settings.default_user_id,
            status="running",
            input_type=request.input_type,
            mode=adapted_mode.value,
            conversation_id=conversation.id,
            session_id=session.id,
            question_id=question.id,
            provider=self.model_provider.name,
            model=self.model_provider.model,
        )
        self.db.add(trace)
        self.db.commit()

        decision = self.orchestrator.decide(effective_request, self.tool_router.names)
        if request.subject and request.topic:
            decision.consult_student_model = True
        if (
            adapted_mode == TeachingMode.ERROR_DIAGNOSIS
            or int(student_state.get("consecutive_errors") or 0) >= 1
            or student_state.get("last_mistake_pattern")
        ):
            decision.consult_memory = True

        plan = self.planner.plan(effective_request, self.tool_router.names, decision)
        tool_results: dict[str, ToolResult] = {}
        call_traces: list[ToolCallTrace] = []
        try:
            for step in plan.steps:
                if not step.tool:
                    continue
                payload = self._tool_payload(step.tool, effective_request)
                result = await self.tool_router.execute(step.tool, payload)
                tool_results[step.tool] = result
                call_traces.append(
                    ToolCallTrace(
                        tool=step.tool,
                        ok=result.ok,
                        execution_time_ms=result.execution_time_ms,
                        summary=_safe_tool_summary(step.tool, result),
                    )
                )

            verification = self.verifier.verify(tool_results)
            adaptive = self.adaptive_tutor.decide(
                subject=request.subject,
                topic=request.topic,
                mode=adapted_mode,
            )
            student_snapshot = None
            memory_snapshot = None
            learning_state_snapshot = None
            if decision.consult_student_model:
                student = self.student_model.student()
                mastery_rows = [
                    {
                        "subject": item.subject,
                        "topic": item.topic,
                        "mastery": item.mastery,
                        "consecutive_errors": item.consecutive_errors,
                    }
                    for item in student.mastery
                    if not request.subject or item.subject == request.subject
                ][:8]
                student_snapshot = {
                    "weak_concepts": student.weak_concepts[:6],
                    "strong_concepts": student.strong_concepts[:4],
                    "topic_state": student_state if request.topic else None,
                    "mastery": mastery_rows,
                }
                # Lean StudentLearningState (+ Error DNA slice) for personalization
                learning_state_snapshot = self.learning_state.get(
                    subject=request.subject,
                    topic=request.topic,
                ).model_dump()
            if decision.consult_memory:
                memory = self.student_model.memory()
                mistakes = memory.repeated_mistakes[:8]
                if request.subject:
                    mistakes = [
                        m
                        for m in mistakes
                        if not m.get("subject") or m.get("subject") == request.subject
                    ][:8]
                memory_snapshot = {
                    "repeated_mistakes": mistakes,
                    "last_mistake_pattern": student_state.get("last_mistake_pattern"),
                }
            # Always attach topic_state when we have subject/topic even if consult
            # flags were off — cheap and already computed.
            if student_snapshot is None and request.subject and request.topic:
                student_snapshot = {"topic_state": student_state, "mastery": []}
                learning_state_snapshot = self.learning_state.get(
                    subject=request.subject,
                    topic=request.topic,
                ).model_dump()
            context = self.context_builder.build(
                tool_outputs={name: result.output for name, result in tool_results.items()},
                mode=adapted_mode.value,
                adaptive_policy={
                    **adaptive.model_dump(),
                    "mode_adaptation": mode_reason,
                    "requested_mode": requested_mode.value,
                    "adapted_mode": adapted_mode.value,
                },
                student_model=student_snapshot,
                memory=memory_snapshot,
                learning_state=learning_state_snapshot,
                intent=f"{decision.intent.value} / {decision.route}: {decision.reason}",
            )
            answer = await self.model_provider.chat(
                _mode_instruction(adapted_mode, request.confirmed_problem or request.message),
                context=context,
            )
            if verification in {
                VerificationStatus.NOT_VERIFIABLE,
                VerificationStatus.PARTIALLY_VERIFIED,
            }:
                answer = (
                    f"{answer}\n\n驗證狀態：{verification.value}。"
                    "以上內容未獲完整工具驗證，請勿視為絕對確定。"
                )
            latency = round((time.perf_counter() - started) * 1000, 2)
            sources = _source_references(tool_results)
            selected_tools = [call.tool for call in call_traces]

            weakness = None
            if int(student_state.get("consecutive_errors") or 0) >= 2:
                weakness = (
                    f"{request.subject}/{request.topic}: "
                    f"{student_state['consecutive_errors']} consecutive errors"
                )
                if student_state.get("last_mistake_pattern"):
                    weakness += f" ({student_state['last_mistake_pattern']})"
            elif student_state.get("last_mistake_pattern"):
                weakness = str(student_state["last_mistake_pattern"])

            mastery_update = None
            recommendation = None
            learning_result: dict[str, Any] = {
                "route": decision.route,
                "intent": decision.intent.value,
                "answer_preview": answer[:240],
            }
            selected_tool_names = [call.tool for call in call_traces]
            outcome_decision = decide_from_verification(
                verification=verification,
                route=decision.route,
                tool_names=selected_tool_names,
                record_attempt=request.record_attempt,
            )
            should_record = outcome_decision.should_record_attempt
            learning_trace_obj = None
            if should_record and request.subject and request.topic:
                outcome = self.learning_loop.record_outcome(
                    LearningOutcomeRequest(
                        subject=request.subject,
                        topic=request.topic,
                        correct=bool(outcome_decision.correct),
                        mistake_pattern=(
                            None
                            if outcome_decision.correct
                            else "verification_failed"
                        ),
                        answer=answer[:2000],
                        ai_explanation=answer[:4000],
                        mode=adapted_mode.value,
                        difficulty=adaptive.question_difficulty,
                        session_id=session.id,
                        conversation_id=conversation.id,
                        question_id=question.id,
                        problem_id=request.problem_id,
                        trace_id=trace_id,
                        verified=outcome_decision.status.value == "VERIFIED",
                        outcome_source="tool_verifier",
                    )
                )
                learning_result = outcome.learning_trace.learning_result
                mastery_update = outcome.learning_trace.mastery_update
                recommendation = outcome.recommendation
                learning_trace_obj = outcome.learning_trace
                # Preserve automation decision (student-mark path overwrites these).
                learning_trace_obj.outcome_status = outcome_decision.status.value
                learning_trace_obj.outcome_reason = outcome_decision.reason
                learning_trace_obj.outcome_evidence = [
                    item.value for item in outcome_decision.evidence
                ]
                learning_trace_obj.outcome_student_message = (
                    outcome_decision.student_message
                )
                learning_trace_obj.mastery_updated = (
                    outcome_decision.should_update_mastery
                    and not outcome.idempotent_replay
                )
            else:
                self.learning_loop.bump_session(session, 2)
                if request.subject and request.topic:
                    recommendation = self.adaptive_tutor.recommend_for_topic(
                        request.subject,
                        request.topic,
                        session_id=session.id,
                    )

            if learning_trace_obj is not None:
                learning_trace_obj.selected_tools = selected_tools
                learning_trace_obj.tools = selected_tools
                learning_trace_obj.verification = verification.value
                learning_trace_obj.agent_decision = {
                    **learning_trace_obj.agent_decision,
                    "requested_mode": requested_mode.value,
                    "adapted_mode": adapted_mode.value,
                    "mode_reason": mode_reason,
                    "intent": decision.intent.value,
                    "route": decision.route,
                    "reason": decision.reason,
                    "adaptive": adaptive.model_dump(),
                    "outcome_status": outcome_decision.status.value,
                    "outcome_reason": outcome_decision.reason,
                }
                learning_trace = learning_trace_obj
            else:
                learning_trace = self.learning_loop.build_agent_trace(
                    session_id=session.id,
                    trace_id=trace_id,
                    student_state=student_state,
                    detected_weakness=weakness,
                    agent_decision={
                        "requested_mode": requested_mode.value,
                        "adapted_mode": adapted_mode.value,
                        "mode_reason": mode_reason,
                        "intent": decision.intent.value,
                        "route": decision.route,
                        "reason": decision.reason,
                        "adaptive": adaptive.model_dump(),
                        "outcome_status": outcome_decision.status.value,
                        "outcome_reason": outcome_decision.reason,
                    },
                    selected_tools=selected_tools,
                    verification=verification.value,
                    learning_result=learning_result,
                    mastery_update=mastery_update,
                    recommendation=recommendation,
                    outcome_status=outcome_decision.status.value,
                    outcome_reason=outcome_decision.reason,
                    outcome_evidence=[
                        item.value for item in outcome_decision.evidence
                    ],
                    outcome_student_message=outcome_decision.student_message,
                    mastery_updated=False,
                )

            response = AgentRunResponse(
                trace_id=trace_id,
                conversation_id=conversation.id,
                session_id=session.id,
                question_id=question.id,
                steps=plan.steps,
                tool_calls=call_traces,
                sources=sources,
                adaptive_decision={
                    **adaptive.model_dump(),
                    "mode_adaptation": mode_reason,
                    "requested_mode": requested_mode.value,
                    "adapted_mode": adapted_mode.value,
                },
                final_answer=answer,
                verification_status=verification,
                requested_mode=requested_mode,
                mode=adapted_mode,
                intent=decision.intent.value,
                route=decision.route,
                provider=self.model_provider.name,
                model=self.model_provider.model,
                latency_ms=latency,
                learning_trace=learning_trace.model_dump(),
                recommendation=recommendation.model_dump() if recommendation else None,
            )
            self._complete_trace(trace, response)
            return response
        except Exception as exc:
            trace.status = "failed"
            trace.steps_json = json.dumps(
                [step.model_dump() for step in plan.steps], ensure_ascii=False
            )
            trace.tool_calls_json = json.dumps(
                [call.model_dump() for call in call_traces], ensure_ascii=False
            )
            trace.error_code = getattr(exc, "code", exc.__class__.__name__)
            trace.error_message = str(exc)[:500]
            trace.latency_ms = round((time.perf_counter() - started) * 1000, 2)
            trace.completed_at = utcnow()
            self.db.commit()
            raise

    def get_trace(self, trace_id: str) -> AgentTraceResponse | None:
        trace = (
            self.db.query(AgentTrace).filter(AgentTrace.trace_id == trace_id).first()
        )
        if not trace:
            return None
        adaptive = json.loads(trace.adaptive_json or "{}")
        return AgentTraceResponse(
            trace_id=trace.trace_id,
            status=trace.status,
            steps=json.loads(trace.steps_json or "[]"),
            tool_calls=json.loads(trace.tool_calls_json or "[]"),
            sources=json.loads(trace.sources_json or "[]"),
            adaptive_decision=adaptive,
            final_answer=trace.final_answer or "",
            conversation_id=trace.conversation_id or 0,
            session_id=trace.session_id,
            question_id=trace.question_id,
            verification_status=VerificationStatus(trace.verification_status),
            requested_mode=TeachingMode(
                adaptive.get("requested_mode", trace.mode)
            ),
            mode=TeachingMode(trace.mode),
            intent=adaptive.get("intent", "tutor"),
            route=adaptive.get("route", "tutor"),
            provider=trace.provider or "unknown",
            model=trace.model or "unknown",
            latency_ms=trace.latency_ms,
            learning_trace=json.loads(trace.learning_trace_json or "{}"),
            recommendation=(json.loads(trace.learning_trace_json or "{}") or {}).get(
                "next_recommendation"
            ),
            error_code=trace.error_code,
            error_message=trace.error_message,
        )

    def get_learning_trace(self, trace_id: str) -> dict[str, Any] | None:
        trace = (
            self.db.query(AgentTrace).filter(AgentTrace.trace_id == trace_id).first()
        )
        if not trace:
            return None
        payload = json.loads(trace.learning_trace_json or "{}")
        if payload:
            return payload
        return {
            "session_id": trace.session_id,
            "trace_id": trace.trace_id,
            "agent_decision": json.loads(trace.adaptive_json or "{}"),
            "selected_tools": [
                item.get("tool")
                for item in json.loads(trace.tool_calls_json or "[]")
                if isinstance(item, dict)
            ],
            "verification": trace.verification_status,
        }

    def _tool_payload(self, tool: str, request: AgentRunRequest) -> dict[str, object]:
        message = request.confirmed_problem or request.message
        if tool == "knowledge_search":
            return {
                "query": message,
                "subject": request.subject,
                "topic": request.topic,
                "document_id": request.material_id,
                "limit": 5,
            }
        return {
            "problem": message,
            "expression": message,
            "code": message,
            "subject": request.subject,
        }

    def _complete_trace(self, trace: AgentTrace, response: AgentRunResponse) -> None:
        trace.status = "completed"
        trace.steps_json = json.dumps(
            [step.model_dump() for step in response.steps], ensure_ascii=False
        )
        trace.tool_calls_json = json.dumps(
            [call.model_dump() for call in response.tool_calls], ensure_ascii=False
        )
        trace.sources_json = json.dumps(
            [source.model_dump() for source in response.sources], ensure_ascii=False
        )
        trace.adaptive_json = json.dumps(
            {
                **response.adaptive_decision,
                "intent": response.intent,
                "route": response.route,
            },
            ensure_ascii=False,
        )
        trace.learning_trace_json = json.dumps(
            response.learning_trace, ensure_ascii=False
        )
        trace.final_answer = response.final_answer
        self.db.add(
            Message(
                conversation_id=response.conversation_id,
                role="assistant",
                content=response.final_answer,
                trace_id=response.trace_id,
            )
        )
        trace.verification_status = response.verification_status.value
        trace.latency_ms = response.latency_ms
        trace.completed_at = utcnow()
        self.db.commit()


def _should_auto_record(
    request: AgentRunRequest,
    route: str,
    verification: VerificationStatus,
    tool_names: list[str] | None = None,
) -> bool:
    """Backward-compatible helper; prefers outcome_automation decision."""
    return decide_from_verification(
        verification=verification,
        route=route,
        tool_names=tool_names,
        record_attempt=request.record_attempt,
    ).should_record_attempt


def _mode_instruction(mode: TeachingMode, message: str) -> str:
    brevity = "回覆控制在 120–220 字以內，除非學生明確要求詳解。"
    if mode == TeachingMode.HINT:
        return f"只提供下一步提示，不要揭露最終答案。{brevity}學生問題：{message}"
    if mode in {TeachingMode.TUTOR, TeachingMode.SOCRATIC}:
        return f"逐步引導學生思考，每次只講一個關鍵點。{brevity}學生問題：{message}"
    if mode == TeachingMode.CONCEPT:
        return f"先解釋適用概念、已知條件與目標，不直接解完整題目。{brevity}學生問題：{message}"
    if mode == TeachingMode.ERROR_DIAGNOSIS:
        return f"診斷學生可能的錯誤與 misconception，再提供修正提示。{brevity}學生問題：{message}"
    if mode == TeachingMode.STEP_BY_STEP:
        return f"提供逐步解釋，清楚標示每一步理由；最多 4 步。{brevity}學生問題：{message}"
    return f"提供清楚解題流程，重點優先。{brevity}學生問題：{message}"


def _safe_tool_summary(name: str, result: ToolResult) -> str:
    if not result.ok:
        return f"{name} failed: {(result.error or '')[:160]}"
    if name == "knowledge_search":
        count = len(result.output.get("results", []))
        return f"{count} passages retrieved"
    return f"{name} completed; output keys={sorted(result.output.keys())}"


def _source_references(tool_results: dict[str, ToolResult]) -> list[SourceReference]:
    knowledge = tool_results.get("knowledge_search")
    if not knowledge or not knowledge.ok:
        return []
    return [
        SourceReference(
            document_id=int(item["document_id"]),
            document_title=str(item["document_title"]),
            page=int(item["page"]),
            chunk_id=int(item["chunk_id"]),
            score=float(item["score"]),
        )
        for item in knowledge.output.get("results", [])
        if all(
            key in item
            for key in ("document_id", "document_title", "page", "chunk_id", "score")
        )
    ]
