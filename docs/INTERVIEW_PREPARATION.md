# Evidence-Based Interview Preparation

## Purpose

Preparation is a saved-job sub-resource. It does not predict an interview or
generate complete model answers. It identifies high-value JD evidence gaps,
retrieves a small number of learning resources for knowledge gaps, asks concrete
questions, and turns user-reported answers into preparation actions.

The flow is:

~~~text
Saved Job + Profile + latest analysis
-> classify skill evidence
-> retrieve resources for at most three knowledge gaps
-> ask at most five evidence questions
-> user answers in JobAgent or an external chat
-> generate bounded preparation actions
~~~

Evidence is marked as `supported`, `partial`, `unknown`, or `missing`. Answers
submitted by the user remain user-reported evidence and do not silently alter
the resume profile.

## MCP Resource Search

The business use case depends on a `LearningResourceSearch` interface. Set
`JOBAGENT_LEARNING_MCP_URL` to use a Streamable HTTP MCP server. Optional
configuration:

- `JOBAGENT_LEARNING_MCP_TOOL`, default `search`;
- `JOBAGENT_LEARNING_MCP_QUERY_ARGUMENT`, default `query`.

The client uses the stable MCP Python SDK v1, a 15-second HTTP timeout, bounded
results, and HTTP(S)-only URLs. MCP errors do not block question generation. A
small official catalog currently covers Linux and Microsoft Office; other topics
remain without a link when search is unavailable rather than receiving a
fabricated URL.

The repository includes a Tavily-backed server at
`mcp_servers/learning_search`. It loads `TAVILY_API_KEY` from the same local
`.env.deepseek.local` file as JobAgent and listens on
`http://127.0.0.1:8001/mcp` by default. Run it separately with:

~~~powershell
python -m mcp_servers.learning_search.server
~~~

The MCP boundary keeps the preparation use case independent from Tavily. Search
results are references only: they do not modify the profile and are not treated
as evidence of candidate ability.

## External Model Exchange

The prompt TXT contains bounded job/profile context, current gaps, question IDs,
and instructions that prohibit invented experience. An external chat returns:

~~~json
{"answers": [{"question_id": "...", "answer": "..."}]}
~~~

The frontend imports only IDs present in the current workspace. The user reviews
the text before submission. Browser-side automatic login probing, message
sending, and background chat capture are outside this version's privacy boundary.
