"use server";

import { revalidatePath } from "next/cache";
import { redirect } from "next/navigation";

import { api } from "@/lib/api";

function errorText(error: unknown): string {
  if (error instanceof Error) return error.message.slice(0, 300);
  return "Unknown error";
}

function withMessage(path: string, key: "notice" | "error", message: string): string {
  return `${path}?${key}=${encodeURIComponent(message.slice(0, 300))}`;
}

function refreshAll(): void {
  revalidatePath("/", "layout");
}

export async function createProposalAction(formData: FormData): Promise<void> {
  const workloadId = String(formData.get("workloadId") ?? "");
  let target: string;
  try {
    const proposal = await api.createProposal(workloadId);
    target = withMessage(
      "/optimizations",
      "notice",
      `Proposal ${proposal.id.slice(0, 8)} created from the deterministic optimizer.`,
    );
  } catch (error) {
    target = withMessage("/workloads", "error", errorText(error));
  }
  refreshAll();
  redirect(target);
}

export async function startWorkflowAction(formData: FormData): Promise<void> {
  const proposalId = String(formData.get("proposalId") ?? "");
  let target: string;
  try {
    const workflow = await api.startWorkflow(proposalId);
    target = withMessage(
      "/workflows",
      "notice",
      `Workflow ${workflow.workflow_id} started and is waiting for approval.`,
    );
  } catch (error) {
    target = withMessage("/optimizations", "error", errorText(error));
  }
  refreshAll();
  redirect(target);
}

export async function approveAction(formData: FormData): Promise<void> {
  const proposalId = String(formData.get("proposalId") ?? "");
  const reason = String(formData.get("reason") ?? "Approved from the WATTSON dashboard.");
  let target: string;
  try {
    await api.approve(proposalId, reason);
    target = withMessage("/optimizations", "notice", "Approval recorded and signalled to Temporal.");
  } catch (error) {
    target = withMessage("/optimizations", "error", errorText(error));
  }
  refreshAll();
  redirect(target);
}

export async function rejectAction(formData: FormData): Promise<void> {
  const proposalId = String(formData.get("proposalId") ?? "");
  const reason = String(formData.get("reason") ?? "Rejected from the WATTSON dashboard.");
  let target: string;
  try {
    await api.reject(proposalId, reason);
    target = withMessage("/optimizations", "notice", "Rejection recorded; nothing will execute.");
  } catch (error) {
    target = withMessage("/optimizations", "error", errorText(error));
  }
  refreshAll();
  redirect(target);
}

export async function cancelWorkflowAction(formData: FormData): Promise<void> {
  const workflowId = String(formData.get("workflowId") ?? "");
  const reason = String(formData.get("reason") ?? "Cancelled from the WATTSON dashboard.");
  let target: string;
  try {
    await api.cancel(workflowId, reason);
    target = withMessage("/workflows", "notice", "Cancellation requested.");
  } catch (error) {
    target = withMessage("/workflows", "error", errorText(error));
  }
  refreshAll();
  redirect(target);
}

export async function toggleKillSwitchAction(formData: FormData): Promise<void> {
  const enabled = String(formData.get("enabled") ?? "true") === "true";
  let target: string;
  try {
    const settings = await api.setKillSwitch(enabled);
    target = withMessage(
      "/settings",
      "notice",
      `Kill switch is now ${settings.kill_switch_active ? "ACTIVE" : "off"}.`,
    );
  } catch (error) {
    target = withMessage("/settings", "error", errorText(error));
  }
  refreshAll();
  redirect(target);
}
