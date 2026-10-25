"""Deterministic Temporal workflow: the backbone of WATTSON's closed loop."""

from __future__ import annotations

from datetime import timedelta
from typing import Any

from temporalio import workflow
from temporalio.common import RetryPolicy

SAFETY_ERROR_TYPES = [
    "InvalidConfig",
    "ApprovalRequired",
    "KillSwitchActive",
    "BudgetExceeded",
    "CapabilityMissing",
    "ProviderNotConnected",
    "MissingBaseline",
    "ProviderFailure",
]


def _safe(text: str) -> str:
    return text[:1000]


def _cause_type(exc: BaseException) -> str:
    cause = getattr(exc, "cause", None)
    if cause is not None:
        return str(getattr(cause, "type", None) or type(cause).__name__)
    return type(exc).__name__


def _cause_message(exc: BaseException) -> str:
    cause = getattr(exc, "cause", None)
    return _safe(str(cause or exc))


@workflow.defn
class OptimizationWorkflow:
    def __init__(self) -> None:
        self._proposal_id = ""
        self.stage = "created"
        self.decision: dict[str, Any] | None = None
        self.cancelled = False
        self.cancel_reason = ""
        self.run_id: str | None = None
        self.report_id: str | None = None
        self.verdict: str | None = None
        self.last_error: str | None = None
        self.executed = False

    def _retry(self, maximum_attempts: int = 3) -> RetryPolicy:
        return RetryPolicy(
            initial_interval=timedelta(seconds=0.2),
            backoff_coefficient=2.0,
            maximum_interval=timedelta(seconds=2),
            maximum_attempts=maximum_attempts,
            non_retryable_error_types=SAFETY_ERROR_TYPES,
        )

    async def _record(self, stage: str, status: str, note: str = "", error: str = "") -> None:
        self.stage = stage
        try:
            await workflow.execute_activity(
                "record_stage",
                {
                    "workflow_id": workflow.info().workflow_id,
                    "proposal_id": self._proposal_id,
                    "stage": stage,
                    "status": status,
                    "note": note,
                    "error": error,
                },
                start_to_close_timeout=timedelta(seconds=15),
                retry_policy=self._retry(2),
            )
        except Exception as exc:  # monitoring must not abort the safety-critical loop
            workflow.logger.warning(f"stage recording failed: {type(exc).__name__}")

    async def _stage(
        self,
        name: str,
        activity: str,
        arg: Any,
        *,
        timeout_seconds: int = 30,
        attempts: int = 3,
        note: str = "",
    ) -> Any:
        await self._record(name, "running", note)
        try:
            result = await workflow.execute_activity(
                activity,
                arg,
                start_to_close_timeout=timedelta(seconds=timeout_seconds),
                retry_policy=self._retry(attempts),
            )
        except Exception as exc:
            self.last_error = _cause_message(exc)
            await self._record(name, "failed", error=self.last_error)
            raise
        await self._record(name, "completed", note)
        return result

    async def _cleanup(self) -> None:
        if not self.run_id:
            return
        try:
            await self._stage(
                "cleanup",
                "cleanup",
                {
                    "proposal_id": self._proposal_id,
                    "workflow_id": workflow.info().workflow_id,
                    "run_id": self.run_id,
                },
                attempts=3,
            )
        except Exception as exc:
            self.last_error = _cause_message(exc)

    async def _finish(self, status: str, error: str = "") -> dict[str, Any]:
        result = await workflow.execute_activity(
            "finalize",
            {
                "proposal_id": self._proposal_id,
                "workflow_id": workflow.info().workflow_id,
                "status": status,
                "error": error or self.last_error or "",
                "verdict": self.verdict,
            },
            start_to_close_timeout=timedelta(seconds=30),
            retry_policy=self._retry(3),
        )
        return result

    @workflow.signal
    def approve(self, approval_id: str) -> None:
        self.decision = {"decision": "approved", "approval_id": approval_id}

    @workflow.signal
    def reject(self, payload: dict[str, Any]) -> None:
        self.decision = {
            "decision": "rejected",
            "approval_id": payload.get("approval_id", ""),
            "reason": payload.get("reason", ""),
        }

    @workflow.signal
    def cancel(self, reason: str = "") -> None:
        self.cancelled = True
        self.cancel_reason = reason

    @workflow.query
    def status(self) -> dict[str, Any]:
        return {
            "stage": self.stage,
            "decision": self.decision,
            "cancelled": self.cancelled,
            "cancel_reason": self.cancel_reason,
            "run_id": self.run_id,
            "report_id": self.report_id,
            "verdict": self.verdict,
            "executed": self.executed,
            "last_error": self.last_error,
        }

    @workflow.run
    async def run(self, input: dict[str, Any]) -> dict[str, Any]:
        self._proposal_id = input["proposal_id"]
        workflow_id = workflow.info().workflow_id
        approval_timeout = int(input["approval_timeout_seconds"])

        try:
            await self._stage(
                "validate",
                "validate_plan",
                self._proposal_id,
                note="validating workload and constraints",
            )
            await self._stage(
                "load_baseline",
                "load_baseline",
                self._proposal_id,
                note="loading baseline measurements",
            )
            await self._stage(
                "generate_candidates",
                "generate_candidates",
                self._proposal_id,
                note="deterministic candidate generation",
            )
            await self._stage(
                "gemma_analysis",
                "analyze_plan",
                self._proposal_id,
                timeout_seconds=90,
                note="optional Gemma analysis with deterministic fallback",
            )
            await self._stage(
                "validate_proposal",
                "validate_proposal",
                self._proposal_id,
                note="validating selected candidate against policy",
            )
            await self._stage(
                "simulate_candidates",
                "simulate_candidates",
                self._proposal_id,
                note="simulating eligible candidates",
            )
            request = await self._stage(
                "approval_request",
                "request_approval",
                {
                    "proposal_id": self._proposal_id,
                    "workflow_id": workflow_id,
                    "approval_timeout_seconds": approval_timeout,
                },
                note="creating recorded approval request",
            )
            if request.get("already_final"):
                status = str(request.get("status") or "needs_intervention")
                if status not in {"cancelled", "rejected", "completed"}:
                    status = "needs_intervention"
                return await self._finish(status, "proposal was already final")

            await self._record(
                "awaiting_approval", "running", "BLOCKED: waiting for a human signal"
            )
            try:
                await workflow.wait_condition(
                    lambda: self.decision is not None or self.cancelled,
                    timeout=timedelta(seconds=approval_timeout),
                )
            except TimeoutError:
                self.last_error = f"approval timed out after {approval_timeout}s"
                await self._record("awaiting_approval", "failed", error=self.last_error)
                return await self._finish("needs_intervention", self.last_error)

            if self.cancelled:
                await self._record(
                    "cancelled", "completed", self.cancel_reason or "cancelled before execution"
                )
                return await self._finish("cancelled", self.cancel_reason)
            assert self.decision is not None
            if self.decision["decision"] == "rejected":
                await self._record("rejected", "completed", self.decision.get("reason", ""))
                return await self._finish("rejected", self.decision.get("reason", ""))
            approval_id = self.decision["approval_id"]

            revalidation = await self._stage(
                "revalidate",
                "revalidate",
                {"proposal_id": self._proposal_id, "approval_id": approval_id},
                note="revalidating approval, budget, kill switch, provider capability",
            )
            if not revalidation.get("ok"):
                self.last_error = (
                    f"{revalidation.get('code')}: {revalidation.get('message')}"
                )
                await self._record("revalidate", "failed", error=self.last_error)
                return await self._finish("needs_intervention", self.last_error)
            if self.cancelled:
                return await self._finish("cancelled", self.cancel_reason)

            idempotency_key = f"{workflow_id}:execute:launch"
            execution = await self._stage(
                "execute",
                "execute_candidate",
                {
                    "proposal_id": self._proposal_id,
                    "workflow_id": workflow_id,
                    "approval_id": approval_id,
                    "idempotency_key": idempotency_key,
                },
                timeout_seconds=120,
                attempts=5,
                note="executing on provider (idempotent launch)",
            )
            self.run_id = execution["run_id"]
            self.executed = True

            await self._stage(
                "collect",
                "collect_results",
                {
                    "proposal_id": self._proposal_id,
                    "workflow_id": workflow_id,
                    "run_id": self.run_id,
                    "idempotency_key": f"{workflow_id}:execute:collect",
                },
                timeout_seconds=120,
                attempts=4,
                note="collecting post-run metrics",
            )
            if self.cancelled:
                await self._cleanup()
                return await self._finish(
                    "cancelled", self.cancel_reason or "cancelled during execution"
                )

            comparison = await self._stage(
                "compare",
                "compare_results",
                {
                    "proposal_id": self._proposal_id,
                    "workflow_id": workflow_id,
                    "run_id": self.run_id,
                },
                note="comparing result to baseline",
            )
            self.verdict = str(comparison.get("verdict"))
            report = await self._stage(
                "persist_report",
                "build_report",
                {
                    "proposal_id": self._proposal_id,
                    "workflow_id": workflow_id,
                    "run_id": self.run_id,
                },
                timeout_seconds=120,
                note="persisting evidence-based report and audit trail",
            )
            self.report_id = report.get("report_id")
            self.verdict = report.get("verdict", self.verdict)
            await self._cleanup()
            return await self._finish("completed")

        except Exception as exc:
            self.last_error = _cause_message(exc)
            error_type = _cause_type(exc)
            if self.run_id and not self.verdict:
                await self._cleanup()
            status = "needs_intervention" if error_type in SAFETY_ERROR_TYPES else "failed"
            try:
                return await self._finish(status, f"{error_type}: {self.last_error}")
            except Exception as finish_exc:
                workflow.logger.error(f"finalize failed: {type(finish_exc).__name__}")
                return {
                    "proposal_id": input["proposal_id"],
                    "status": status,
                    "verdict": self.verdict,
                    "error": self.last_error,
                }
