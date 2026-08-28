# HTTP API

```shell
pip install -e ".[api]"
ba-downloader server start
```

BAAD prints the local base URL and `/docs` URL at startup. The default host is
`0.0.0.0`; without `--port`, the first available port from `9230` through
`9239` is used.

## Security

The server has no authentication, uses plaintext HTTP, permits every CORS
origin, and supports Private Network Access preflight. It can download,
extract, browse, and clean BAAD data. Run it only on a trusted network.

Proxy credentials and SQLCipher keys stay in process memory. Responses expose
presence flags, never secret values. Jobs and contexts do not survive restart.

## Contexts

Create an immutable context before starting work:

```http
POST /api/v1/contexts
Content-Type: application/json

{
  "region": "jp",
  "platform": "android",
  "workspace": ".",
  "proxy": "",
  "retries": 5,
  "sqlcipher_key": ""
}
```

The server keeps at most 16 contexts for 24 idle hours. Identical unresolved
configuration is deduplicated. The first catalog or runtime use freezes the
resolved resource version. `POST /api/v1/contexts/{context_id}/refresh` derives
a new unresolved context; it never mutates the source context.

## Jobs

All work uses one strict endpoint:

```http
POST /api/v1/jobs
Content-Type: application/json

{
  "operation": "assets.sync",
  "context_id": "<context-id>",
  "concurrency": 30,
  "resources": ["table", "media"],
  "filters": ["name~Ibuki,イプキ", "school=Gehenna"]
}
```

Operations are `assets.sync`, `assets.download`, `assets.extract`,
`index.build`, and `storage.cleanup`. Jobs return `202 Accepted`; one spawned
worker runs at a time and at most 16 jobs wait in FIFO order. The latest 50
terminal summaries are retained.

`GET /api/v1/jobs/{job_id}/events` sends one current snapshot, then live SSE
events and a 15-second heartbeat. Missed events are not replayed. Cancel with
`POST /api/v1/jobs/{job_id}/cancel`.

## Context Resources

Catalog, CharacterIndex, operation preview, storage usage, cleanup preview, and
files are under `/api/v1/contexts/{context_id}`. File browsing is limited to
`raw`, `extracted`, and `indexes`; content responses support HTTP Range.

Cleanup requires a five-minute, single-use preview token. Categories are
`raw`, `extracted`, `indexes`, `cache`, `temp`, `old-snapshots`,
`failed-staging`, and `logs`. Current runtime and schema snapshots are protected.

## Reference

- OpenAPI: `/openapi.json`
- Swagger UI: `/docs`
- ReDoc: `/redoc`
- Health: `GET /api/v1/health`
- Discovery: `GET /api/v1/discovery`
- Shutdown: `POST /api/v1/system/shutdown`

Errors use `application/problem+json` with a stable BAAD `code` field.
