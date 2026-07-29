# Modular RAG MCP Integration

## Purpose

JobAgent can connect to a separately running Modular RAG service through MCP
Streamable HTTP. The RAG implementation, model dependencies, Chroma, BM25, and
document ingestion remain outside the JobAgent process.

The current boundary is:

~~~text
JobAgent backend
  -> configured Streamable HTTP MCP client
  -> initialize and tools/list contract validation
  -> allowlisted tools/call
Modular RAG MCP service
  -> hybrid retrieval and local knowledge storage
~~~

This integration is independent from the Search V2 job-provider pipeline.
Career Assistant exposes only the bounded `search_personal_knowledge` capability
to its tool-selection policy. It never exposes the MCP server's arbitrary tool
surface or lets the model supply an authenticated user identity.

## Configuration

~~~text
JOBAGENT_RAG_MCP_URL=http://127.0.0.1:8002/mcp
JOBAGENT_RAG_MCP_TIMEOUT_SECONDS=10
JOBAGENT_RAG_MCP_MAX_RESPONSE_CHARS=500000
JOBAGENT_RAG_SERVICE_TOKEN=<same value as RAG_SERVICE_TOKEN>
~~~

An empty URL disables the integration. The URL must be an absolute HTTP(S) URL
without embedded credentials or a fragment. The local service should bind to
`127.0.0.1` unless authentication and a trusted network boundary have been
added.

JobAgent currently requires these tools:

- `query_knowledge_hub`;
- `list_collections`;
- `get_document_summary`.
- `search_authorized_knowledge`.

Calls outside this allowlist are rejected by the JobAgent client.

## Typed Adapter

`app/services/mcp/client.py` owns MCP transport, timeout handling, result-size
limits, service inspection, and allowlisted tool calls.

`app/services/mcp/modular_rag.py` maps the external tools into typed
JobAgent operations:

- list knowledge collections;
- execute a bounded knowledge query with `top_k <= 20`;
- load one document summary.
- execute a user-scoped private query with a short-lived signed scope.

Pydantic schemas validate every structured response before application code can
consume it. MCP failures and contract drift produce integration errors rather
than unvalidated dictionaries.

The legacy query adapter permits only an optional collection filter and cannot
return managed private resources. Private retrieval uses
`search_authorized_knowledge`: JobAgent creates a short-lived HMAC scope from
the authenticated backend `user_id`, and RAG verifies it before building
mandatory dense and sparse filters. An LLM-created `user_id` or metadata filter
does not grant access.

## Private Resource Synchronization

The managed-indexing foundation exists behind an explicit feature flag.
JobAgent persists `rag_index_outbox` and `rag_resource_status` records in
the same transaction as supported Resume Profile and Saved Job writes.

When `JOBAGENT_RAG_SYNC_ENABLED=true`, a bounded worker formats confirmed
profiles and saved jobs into deterministic searchable text and sends them to
the RAG service's authenticated internal management routes. Raw resume text,
authentication data, and arbitrary database rows are not included.

~~~powershell
$env:JOBAGENT_RAG_SYNC_ENABLED = "true"
$env:JOBAGENT_RAG_MANAGEMENT_URL = "http://127.0.0.1:8002"
$env:JOBAGENT_RAG_SERVICE_TOKEN = "<same value as RAG_SERVICE_TOKEN>"
.\.venv\Scripts\python.exe -m scripts.run_rag_sync --limit 10
~~~

The command above processes one bounded batch. A deployment should supervise the
continuous mode as a process separate from the web API:

~~~powershell
.\.venv\Scripts\python.exe -m scripts.run_rag_sync `
  --watch `
  --limit 10 `
  --poll-interval 2 `
  --max-idle-interval 30
~~~

The outbox survives JobAgent restarts. Claimed rows receive a processing lease;
if a worker exits after claiming but before completing an event, another worker
can reclaim it after the lease expires. Empty polling backs off to the configured
maximum, while new work resets polling to the active interval.

Authenticated users can inspect their own synchronization coverage and MCP
availability at `GET /api/v1/rag/status` or from the **Knowledge Status** page.
The endpoint never exposes another user's resource counts or failure records.

### Backfill, rebuild, and repair

New writes enter the outbox automatically when synchronization is enabled.
Historical resources and explicit repairs use the administrative CLI; these
commands enqueue durable events and do not write Chroma or BM25 directly.

~~~powershell
.\.venv\Scripts\python.exe -m scripts.rag_admin backfill

.\.venv\Scripts\python.exe -m scripts.rag_admin reindex `
  --user-id "<user-id>" `
  --resource-type saved_job `
  --resource-id "<saved-job-id>"

.\.venv\Scripts\python.exe -m scripts.rag_admin status
.\.venv\Scripts\python.exe -m scripts.rag_admin retry-failed --limit 100
.\.venv\Scripts\python.exe -m scripts.rag_admin reconcile
~~~

`backfill --force` creates a new version even for ready resources. Use it after
an index schema, chunking, or embedding-model migration. `reconcile` compares
managed sync state with current JobAgent ownership and archival state; it does
not trust the RAG index as the business source of truth.

## Career Assistant Product Flow

Career Assistant keeps exact reads and semantic discovery separate:

- explicit attachments, exact resource reads, lists, mutations, and counts use
  JobAgent repositories;
- broad questions such as "which saved jobs mention Kubernetes?" may select
  `search_personal_knowledge`;
- JobAgent derives allowed resource types from the conversation data scope and
  signs the current backend user into a short-lived token;
- RAG performs authorized hybrid retrieval and returns evidence candidates;
- JobAgent rejects foreign, malformed, deleted, or stale-version results, then
  reloads the current Resume Profile or Saved Job from its repository;
- the final prompt receives current JobAgent business fields plus a bounded RAG
  recall excerpt, applies the existing evidence budget, and requires citations;
- an unavailable service or no usable match falls back to bounded JobAgent
  repository retrieval and records a quality warning.

RAG text remains a derived retrieval copy. JobAgent repositories remain the
business source of truth.

## Verification

Start the Modular RAG service from its own repository:

~~~powershell
.\.venv\Scripts\python.exe -m mcp_server.server `
  --transport streamable-http `
  --host 127.0.0.1 `
  --port 8002 `
  --http-path /mcp `
  --settings config/settings.yaml
~~~

Then inspect it from the JobAgent repository:

~~~powershell
$env:JOBAGENT_RAG_MCP_URL = "http://127.0.0.1:8002/mcp"
.\.venv\Scripts\python.exe -m scripts.inspect_rag_mcp `
  --query "Simple plain text" `
  --top-k 3
~~~

The command verifies service identity, protocol negotiation, required tools,
collection listing, knowledge retrieval, and—when a result contains a document
identifier—document-summary retrieval.

Default tests use fake MCP sessions and remain deterministic and network-free.
The diagnostic command is the explicit live integration check.

## Current Non-Goals

- exposing arbitrary MCP tools directly to an LLM;
- trusting a Tool argument as authenticated user identity;
- changing Search V2 retrieval, ranking, or trace stages;
- managing the Modular RAG process from JobAgent;
- treating the RAG index as a JobAgent business-data source of truth.

Production readiness still requires real-data relevance evaluation, supervised
process configuration, secret rotation, monitoring, backup, and index rebuild
operations.

## Retrieval quality evaluation

The committed `career-private-v1` fixture covers saved-job semantic discovery,
resume evidence discovery, and a same-query resource owned by another user that
must never be returned.

The default mode is deterministic and network-free:

~~~powershell
.\.venv\Scripts\python.exe -m scripts.evaluate_rag_quality --mode lexical
~~~

Live mode creates isolated temporary JobAgent users and resources, synchronizes
them through the real management API, queries through authorized MCP, reports
Hit Rate, Recall@K, Precision@K, MRR, forbidden hits, and latency, then deletes
the fixture resources:

~~~powershell
.\.venv\Scripts\python.exe -m scripts.evaluate_rag_quality --mode live
~~~

The local-hash embedding provider is suitable only for transport and lifecycle
verification. Semantic-quality acceptance must be rerun with the intended
embedding model, currently `bge-m3`, and recorded as a separate baseline.

Chinese career queries receive a bounded bilingual alias expansion before MCP
retrieval so English JDs remain available to BM25 as well as dense retrieval.
The first local `bge-m3` baseline is recorded under
`experiments/rag_quality/baselines/`.

Personal-knowledge retrieval logs content-free stage timings for query expansion,
the MCP query, JobAgent validation/business-record hydration, and total latency.
User identifiers and query text are intentionally excluded from these records.
