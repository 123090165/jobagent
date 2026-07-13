# Persona-Centered Preparation Evaluation

This experiment reads an existing resume profile and saved job, creates a
private imperfect-candidate persona, completes the guided Preparation workflow,
and asks the same evaluation model to reflect on whether the result helped that
candidate.

The experiment never writes to the source JobAgent database. It uses SQLite's
backup API to create a temporary shadow database and runs Preparation there.
Reports are written to the gitignored `experiments/output` directory and may
contain profile data, hidden persona memory, private answer reasons, and model
reflections. Treat them as sensitive local files.

## Memory Model

- Profile memory is loaded from `resume_profiles` and remains immutable.
- Persona memory contains private capability calibration, confidence,
  communication style, disclosure behavior, concerns, and goals.
- Episodic memory records every selected answer, optional detail, private
  reason, and candidate reaction.

The Candidate and reflection phases use the same evaluation model but separate
prompts. The reflection call receives all three memory layers explicitly. This
preserves identity without relying on hidden provider conversation state.

## Model Configuration

The evaluation model is independent from the JobAgent generation model and uses
an OpenAI-compatible chat-completions endpoint:

```env
JOBAGENT_EVAL_API_KEY=...
JOBAGENT_EVAL_BASE_URL=https://your-provider.example/v1
JOBAGENT_EVAL_MODEL=your-evaluation-model
JOBAGENT_EVAL_TIMEOUT=180
JOBAGENT_EVAL_TEMPERATURE=0.2
```

DeepSeek, Ollama, or mock remains separately selectable for the Preparation
generation itself.

## Run

List available profile and saved-job IDs:

```powershell
.venv\Scripts\python.exe -m experiments.preparation_eval.runner `
  --env-file .env.deepseek.local `
  --list-context
```

Run an evaluation:

```powershell
.venv\Scripts\python.exe -m experiments.preparation_eval.runner `
  --env-file .env.deepseek.local `
  --saved-job-id SAVED_JOB_ID `
  --persona-archetype "underconfident and guarded" `
  --preparation-provider deepseek `
  --pause-after 2
```

The runner resolves the most recent non-archived Profile associated with the
Saved Job's durable context. Use `--profile-id PROFILE_ID` only to select a
specific associated Profile when a job has multiple contexts. Legacy databases
fall back to the Profile reference in saved-job analyses.

Use `--stop-without-summary` to evaluate voluntary early termination. Raw resume
text is excluded from the evaluation model context unless
`--include-raw-resume` is explicitly provided.

## Prompt Responsibilities

- `persona_system.md` converts resume evidence into a stable, bounded hidden
  persona without creating new history.
- `candidate_system.md` answers one Preparation question at a time using
  explicit Profile, Persona, and Episodic memory.
- `reflection_system.md` switches the same model into a critical first-person
  usefulness assessment after the workflow ends.

Deterministic checks remain separate from self-reflection. They validate terminal
status, stopped-session behavior, resource/question bounds, and whether learning
resources align with answers indicating a learning gap.
