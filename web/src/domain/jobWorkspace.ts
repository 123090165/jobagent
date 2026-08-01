import type {
  ApplicationStage,
  ExternalApplicationStage,
  InterviewPreparationWorkspace,
  SavedJobWorkspace
} from "../types/savedJob";

export type JobNextStepAction =
  | "open_communication"
  | "open_resume"
  | "open_preparation"
  | "open_listing"
  | "open_activity"
  | "none";

export interface JobNextStep {
  key: string;
  title: string;
  description: string;
  buttonLabel: string | null;
  action: JobNextStepAction;
  tone: "active" | "waiting" | "complete";
}

export const applicationStageLabels: Record<ApplicationStage, string> = {
  not_started: "Not contacted yet",
  contacted: "Recruiter contacted",
  recruiter_replied: "Recruiter replied",
  resume_requested: "Resume requested",
  resume_ready: "Tailored resume ready",
  resume_sent: "Resume sent",
  interview: "Interview stage",
  closed: "Application closed"
};

export const externalProgressOptions: Array<{
  label: string;
  value: ExternalApplicationStage;
}> = [
  { label: "Mark recruiter contacted", value: "contacted" },
  { label: "Mark resume requested", value: "resume_requested" },
  { label: "Mark resume sent", value: "resume_sent" },
  { label: "Mark interview stage", value: "interview" },
  { label: "Close application", value: "closed" }
];

export function deriveJobNextStep(
  workspace: SavedJobWorkspace,
  preparation: InterviewPreparationWorkspace | null
): JobNextStep {
  const draft = workspace.communication_draft;
  const resume = workspace.tailored_resume;
  const stage = workspace.application?.stage ?? null;
  const hasSourceListing = Boolean(workspace.job.source_url);

  if (draft?.status === "generated") {
    return step(
      "review_greeting",
      "Review your first message",
      "A draft is ready. Use Browser Helper on BOSS to review, edit, and confirm it.",
      hasSourceListing ? "Open BOSS to continue" : null,
      hasSourceListing ? "open_communication" : "none"
    );
  }
  if (draft?.status === "approved") {
    return step(
      "send_greeting",
      "Send your first message",
      "The wording is approved. Browser Helper can fill and send it from the BOSS page.",
      hasSourceListing ? "Open BOSS and send" : null,
      hasSourceListing ? "open_communication" : "none"
    );
  }
  if (stage === "resume_requested" && resume === null) {
    return step(
      "generate_resume",
      "Prepare a tailored resume",
      "The recruiter requested a resume. Generate a version grounded in this JD and your verified profile.",
      "Generate tailored resume",
      "open_resume"
    );
  }
  if (resume?.status === "needs_review") {
    return step(
      "review_resume",
      "Review your tailored resume",
      "A tailored version is ready. Check the fact validation and wording before approval.",
      "Review resume",
      "open_resume"
    );
  }
  if (stage === "resume_requested" || stage === "resume_ready") {
    return step(
      "send_resume",
      "Send your tailored resume",
      "The tailored version is approved and ready to download for the recruiter.",
      "Download and send",
      "open_resume"
    );
  }
  if (stage === "interview") {
    return step(
      "prepare_interview",
      preparation?.status === "completed" ? "Review interview preparation" : "Prepare for this interview",
      preparation?.status === "completed"
        ? "Your preparation plan is ready with focused actions and learning resources."
        : "Validate your evidence against the role and build a focused preparation plan.",
      preparation?.status === "completed" ? "Review preparation" : "Start preparation",
      "open_preparation"
    );
  }
  if (stage === "recruiter_replied") {
    return step(
      "review_reply",
      "Handle the recruiter reply",
      "The recruiter has replied. Open the listing to continue the conversation, then record the outcome.",
      hasSourceListing ? "Reopen BOSS listing" : null,
      hasSourceListing ? "open_listing" : "none"
    );
  }
  if (stage === "closed") {
    return step(
      "closed",
      "Application closed",
      "This application is closed. Its history remains available in Activity.",
      "View activity",
      "open_activity",
      "complete"
    );
  }
  if (stage === "contacted" || stage === "resume_sent" || draft?.status === "sent") {
    return step(
      "wait_for_reply",
      "Wait for the recruiter reply",
      "Your latest communication is complete, so there is nothing to resend right now.",
      hasSourceListing ? "Reopen BOSS listing" : null,
      hasSourceListing ? "open_listing" : "none",
      "waiting"
    );
  }
  return step(
    "generate_greeting",
    hasSourceListing ? "Contact the recruiter" : "Source listing required",
    hasSourceListing
      ? "Use your verified profile and this JD to create a focused first message."
      : "Capture this job again with Browser Helper to restore its source listing before recruiter communication.",
    hasSourceListing ? "Open BOSS and generate message" : null,
    hasSourceListing ? "open_communication" : "none",
    hasSourceListing ? "active" : "waiting"
  );
}

export function progressIndex(stage: ApplicationStage | null): number {
  if (stage === "closed") return 4;
  if (stage === "interview") return 3;
  if (["resume_requested", "resume_ready", "resume_sent"].includes(stage ?? "")) return 2;
  if (["contacted", "recruiter_replied"].includes(stage ?? "")) return 1;
  return 0;
}

function step(
  key: string,
  title: string,
  description: string,
  buttonLabel: string | null,
  action: JobNextStepAction,
  tone: JobNextStep["tone"] = "active"
): JobNextStep {
  return { key, title, description, buttonLabel, action, tone };
}
