You are generating one interview challenge question for one job requirement.

Rules:
- Only generate one question.
- Use only the provided requirement and resume evidence.
- Do not invent projects, companies, metrics, tools, or achievements.
- The question should be specific and interview-realistic.
- If evidence is weak, ask a verification-style question.
- If evidence is strong, ask a deeper implementation or tradeoff question.
- Return only one JSON object.
- No Markdown.

Return this JSON shape:
{
  "question": "string",
  "why_asked": "string",
  "expected_answer_points": ["string"],
  "risk_level": "low | medium | high",
  "question_type": "basic | technical | architecture | tradeoff"
}
