# Job Brief

## Purpose

A Job Brief converts one saved job into a compact decision and action snapshot.
It is not another search stage and it does not modify the resume or application
status. The brief combines the saved JD, latest saved analysis, and one owned
resume profile.

The structured output contains:

- a decision summary;
- evidence-grounded fit signals and gaps;
- resume actions;
- interview focus areas;
- immediate next actions.

## Lifecycle

Briefs are immutable, versioned snapshots under a saved job. Regeneration adds a
new version and retains prior versions. The newest version is shown by default in
the saved-job detail view.

Profile selection follows this order:

1. an explicitly requested active profile;
2. the profile linked to the latest saved analysis;
3. the user's active default profile;
4. no profile, with a reduced deterministic brief.

Deleting a saved job deletes only its briefs. Deleting a resume profile clears
the reference from existing briefs but retains their content and the saved job.

## Agent Boundary

The generator calls models only through JobAgent's `JSONChatLLM` interface. It
requires validated JSON, limits action lists, and prohibits invented resume
evidence or JD requirements. Provider failure stores a deterministic fallback
with the failure reason for engineering diagnosis; generation remains usable.

This is a single bounded generation step. LangGraph is not needed until the
brief becomes a multi-turn workflow with user confirmation, branching, or
checkpointed resume-tailoring actions.
