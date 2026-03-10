# Museum of Dave — Python → Go Migration Plan

> **Status:** Draft — awaiting review before implementation begins
> **API contract:** HTTP routes and JSON shapes are frozen; the frontend will not change
> **Go version target:** 1.23+
> **Existing Go assets:** `import-processor/` and `datahandler/` are absorbed as internal packages — their logic is ported directly, not rewritten

---

## Table of Contents

1. [Go Project Structure](#1-go-project-structure)
2. [Dependency Mapping](#2-dependency-mapping)
3. [Endpoint Inventory](#3-endpoint-inventory)
4. [Data Model Structs](#4-data-model-structs)
5. [Auth & Middleware](#5-auth--middleware)
6. [Background Jobs & SSE](#6-background-jobs--sse)
7. [AI Service Layer](#7-ai-service-layer)
8. [Existing Go Code Integration](#8-existing-go-code-integration)
9. [Testing Strategy](#9-testing-strategy)
10. [Migration Sequence](#10-migration-sequence)
11. [Risk Areas & Python Patterns](#11-risk-areas--python-patterns)

---

## 1. Go Project Structure

```
museum-of-you-go/
│
├── cmd/
│   └── server/
│       └── main.go             # Entry point: load config, init DB, wire deps, start server
│
├── internal/
│   │
│   ├── config/
│   │   └── config.go           # Typed config struct; loads .env + DB override
│   │
│   ├── database/
│   │   ├── db.go               # pgx/v5 pool setup, graceful close
│   │   ├── migrate.go          # Schema creation/migration (raw SQL, no ORM)
│   │   └── queries/            # sqlc-generated code (DO NOT edit by hand)
│   │       ├── *.sql.go
│   │       └── db.go
│   │
│   ├── handler/                # HTTP layer only — parse request, call service, write response
│   │   ├── admin.go
│   │   ├── artefacts.go
│   │   ├── attachments.go
│   │   ├── chat.go
│   │   ├── configuration.go
│   │   ├── documents.go
│   │   ├── emails.go
│   │   ├── imap.go
│   │   ├── interests.go
│   │   ├── messages.go
│   │   ├── relationships.go
│   │   ├── responses.go        # saved_responses
│   │   ├── sensitive.go
│   │   ├── voices.go
│   │   └── media/
│   │       ├── images.go
│   │       ├── facebook.go     # albums, posts, places, all
│   │       ├── filesystem.go
│   │       └── thumbnails.go
│   │
│   ├── service/                # Business logic; no HTTP types; takes/returns domain types
│   │   ├── artefact_service.go
│   │   ├── chat_service.go
│   │   ├── configuration_service.go
│   │   ├── document_service.go
│   │   ├── email_service.go
│   │   ├── image_service.go
│   │   ├── message_service.go
│   │   ├── relationship_service.go
│   │   ├── subject_service.go
│   │   └── saved_response_service.go
│   │
│   ├── repository/             # DB access only; thin wrappers around sqlc queries
│   │   ├── artefact_repo.go
│   │   ├── chat_repo.go
│   │   ├── configuration_repo.go
│   │   ├── contact_repo.go
│   │   ├── document_repo.go
│   │   ├── email_repo.go
│   │   ├── media_repo.go
│   │   ├── message_repo.go
│   │   └── subject_repo.go
│   │
│   ├── importer/               # Long-running background import jobs
│   │   ├── job.go              # JobManager: goroutine lifecycle, cancel, SSE broadcast
│   │   ├── email.go            # Gmail import worker (new — Python only)
│   │   ├── imap.go             # IMAP import worker (new — Python only)
│   │   ├── thumbnail.go        # Thumbnail generation worker (new — Python only)
│   │   └── workers/            # Ported directly from import-processor/internal/import/
│   │       ├── whatsapp/       # ← import-processor/internal/import/whatsapp/
│   │       ├── imessage/       # ← import-processor/internal/import/imessage/
│   │       ├── facebook/       # ← import-processor/internal/import/facebook/
│   │       ├── facebookalbums/ # ← import-processor/internal/import/facebookalbums/
│   │       ├── facebookposts/  # ← import-processor/internal/import/facebookposts/
│   │       ├── facebookplaces/ # ← import-processor/internal/import/facebookplaces/
│   │       ├── instagram/      # ← import-processor/internal/import/instagram/
│   │       ├── filesystem/     # ← import-processor/internal/import/filesystem/
│   │       └── contacts/       # ← import-processor/internal/import/contacts/
│   │
│   ├── crypto/                 # Ported directly from datahandler/cmd/main.go
│   │   ├── keys.go             # Master key generation, trusted key derivation
│   │   ├── encrypt.go          # AES-256-GCM + RSA-OAEP hybrid encryption/decryption
│   │   ├── argon2.go           # Argon2id key derivation
│   │   └── seed.go             # Embeds seed.txt via go:embed
│   │
│   ├── ai/
│   │   ├── provider.go         # ChatProvider interface
│   │   ├── gemini.go           # Google Gemini implementation
│   │   └── claude.go           # Anthropic Claude implementation
│   │
│   ├── emailclient/
│   │   ├── gmail.go            # Gmail API OAuth2 client
│   │   └── imap.go             # IMAP client
│   │
│   ├── middleware/
│   │   ├── logging.go          # slog request/response logging
│   │   └── recover.go          # panic recovery → 500
│   │
│   └── model/                  # Pure domain types (no DB tags, no JSON tags)
│       ├── chat.go
│       ├── contact.go
│       ├── email.go
│       ├── media.go
│       └── ...
│
├── sqlc/
│   ├── sqlc.yaml               # sqlc configuration
│   ├── schema.sql              # Canonical schema (matches Python migration)
│   └── queries/                # Hand-written SQL queries
│       ├── emails.sql
│       ├── media.sql
│       ├── messages.sql
│       ├── chat.sql
│       └── ...
│
├── static/                     # Served unchanged from Python version
│   └── (copy of src/api/static)
│
├── .env                        # Same variables as Python .env
├── go.mod
├── go.sum
└── Makefile                    # build, test, generate (sqlc), lint
```

### Package responsibility summary

| Package | Responsibility |
|---|---|
| `cmd/server` | Wire all dependencies; start HTTP server; handle OS signals for graceful shutdown |
| `internal/config` | Load typed `Config` struct from environment + DB override; no business logic |
| `internal/database` | pgx pool creation; schema migration; sqlc query wrappers |
| `internal/handler` | Decode HTTP request → call service → encode HTTP response. No SQL, no business logic |
| `internal/service` | Business logic, orchestration, validation. No HTTP types, no direct DB calls |
| `internal/repository` | Thin typed wrappers around sqlc queries. Transactions managed here |
| `internal/importer` | Goroutine-based long-running workers. `job.go` manages lifecycle; `workers/` contains ported import-processor logic |
| `internal/crypto` | AES-256-GCM + RSA-OAEP hybrid encryption, Argon2id key derivation. Ported from `datahandler/` |
| `internal/ai` | `ChatProvider` interface + Gemini/Claude implementations |
| `internal/emailclient` | Gmail OAuth2 and IMAP clients; pure I/O, no DB |
| `internal/middleware` | Chi middleware: logging, panic recovery |
| `internal/model` | Shared domain types passed between layers |
| `sqlc/` | Source of truth for schema + queries; `go generate` runs sqlc |

---

## 2. Dependency Mapping

### Web Framework & Server

| Python | Go | Notes |
|---|---|---|
| `fastapi` | `github.com/go-chi/chi/v5` | Chi is lightweight, idiomatic, no magic. Alternatively `net/http` stdlib if even simpler is preferred |
| `uvicorn` | `net/http` stdlib | Built into Go; no separate ASGI server needed |
| `pydantic` (request validation) | Struct field tags + `github.com/go-playground/validator/v10` | Validation at handler boundary |
| `pydantic` (response serialization) | `encoding/json` stdlib | No extra library needed for marshalling |
| `jinja2` | `html/template` stdlib | Templating for the two JS files served with dynamic values |
| `python-multipart` | `net/http` stdlib `r.FormFile` / `r.MultipartForm` | Built into Go |

### Database

| Python | Go | Notes |
|---|---|---|
| `sqlalchemy>=2.0` | `github.com/jackc/pgx/v5` + `github.com/sqlc-dev/sqlc` | sqlc generates type-safe Go from SQL. pgx/v5 is the recommended PostgreSQL driver |
| `psycopg2-binary` | `pgx/v5/pgxpool` | pgx replaces psycopg2 |
| SQLAlchemy ORM | sqlc (generated code) | No ORM; queries are explicit SQL in `sqlc/queries/*.sql` |
| SQLAlchemy connection pool | `pgxpool.Pool` | Pool size/overflow/recycle configured on `pgxpool.Config` |

### Configuration

| Python | Go | Notes |
|---|---|---|
| `python-dotenv` | `github.com/joho/godotenv` | Same `.env` file format |
| Pydantic `BaseSettings` | Plain Go struct + `os.Getenv` | Typed struct with defaults; no reflection magic needed |

### AI / LLM

| Python | Go | Notes |
|---|---|---|
| `google-genai` | `github.com/google/generative-ai-go` | Official Go SDK for Gemini |
| `anthropic` | `github.com/anthropics/anthropic-sdk-go` | Official Go SDK for Claude |
| `tavily-python` | HTTP client to Tavily REST API | No official Go SDK; call the REST API directly with `net/http` |

### Email

| Python | Go | Notes |
|---|---|---|
| `google-api-python-client` + `google-auth-oauthlib` | `google.golang.org/api/gmail/v1` + `golang.org/x/oauth2` | Official Go Gmail API client |
| Custom IMAP client | `github.com/emersion/go-imap/v2` | Mature Go IMAP library |

### Image Processing

| Python | Go | Notes |
|---|---|---|
| `Pillow` | `github.com/disintegration/imaging` + `image/jpeg`, `image/png` stdlib | Thumbnail generation, format conversion |
| `pillow-heif` | `github.com/strukturag/libheif` (CGo) or skip HEIC on first pass | HEIC support requires CGo binding; note as optional feature |

### Logging

| Python | Go | Notes |
|---|---|---|
| `print` / no structured logging | `log/slog` stdlib (Go 1.21+) | Structured JSON logging; zero extra dependency |

### Memory / Profiling

| Python | Go | Notes |
|---|---|---|
| `pympler` (memory profiling) | `net/http/pprof` stdlib | pprof endpoint for profiling; register under `/debug/pprof` in dev |

### Cryptography (from datahandler)

| Python | Go | Notes |
|---|---|---|
| No Python equivalent (external Go process) | `golang.org/x/crypto/argon2` | Argon2id key derivation (already used in datahandler) |
| No Python equivalent | `crypto/aes`, `crypto/cipher` stdlib | AES-256-GCM symmetric encryption (already used in datahandler) |
| No Python equivalent | `crypto/rsa`, `crypto/rand` stdlib | RSA-OAEP asymmetric encryption (already used in datahandler) |
| No Python equivalent | `embed` stdlib (`//go:embed seed.txt`) | Compile-time seed embedding (already used in datahandler) |

### Handled Natively in Go

| Python pattern | Go equivalent |
|---|---|
| `threading.Lock` | `sync.Mutex` |
| `threading.Event` (cancel) | `context.WithCancel` |
| `asyncio.Queue` (SSE clients) | `chan []byte` per client, registered in a slice guarded by `sync.RWMutex` |
| `BackgroundTasks` (FastAPI) | `go func()` goroutine launched from handler |
| SSE (`EventSourceResponse`) | `http.Flusher` + chunked write loop |
| `BytesIO` | `bytes.Buffer` / `io.Reader` |
| Python exceptions | `error` return values |
| `Optional[X]` | pointer types or `sql.NullXxx` / `pgtype.Xxx` |

---

## 3. Endpoint Inventory

Each endpoint maps to: `handler func` → `service method` → `repo method(s)`.

### Admin & System

| Method | Path | Handler | Service | Repo |
|---|---|---|---|---|
| GET | `/` | `AdminHandler.ServeIndex` | `SubjectService.Get` + `ConfigService.Get("PAGE_TITLE")` | `SubjectRepo.Get` |
| GET | `/health` | `AdminHandler.Health` | — | — |
| GET | `/api/dashboard` | `AdminHandler.Dashboard` | `AdminService.GetStats` | multiple repos |
| GET | `/api/suggestions` | `AdminHandler.Suggestions` | `SubjectService.Get` | `SubjectRepo.Get` |
| GET | `/api/import-control-last-run` | `AdminHandler.LastRun` | `ImportService.GetLastRuns` | `ImportRepo.GetAll` |
| GET | `/api/control-defaults` | `AdminHandler.ControlDefaults` | — | — |
| GET | `/static/js/museum/foundation.js` | `AdminHandler.FoundationJS` | `SubjectService.Get` | `SubjectRepo.Get` |
| GET | `/static/js/museum/modals-people.js` | `AdminHandler.ModalsJS` | — | — |
| DELETE | `/admin/empty-media-tables` | `AdminHandler.EmptyMediaTables` | `MediaService.EmptyTables` | `MediaRepo.DeleteAll` |

### Emails

| Method | Path | Handler | Service | Repo |
|---|---|---|---|---|
| POST | `/emails/process` | `EmailHandler.StartProcess` | `ImportJobManager.Start("email", ...)` | — |
| POST | `/emails/process/cancel` | `EmailHandler.CancelProcess` | `ImportJobManager.Cancel("email")` | — |
| GET | `/emails/process/status` | `EmailHandler.ProcessStatus` | `ImportJobManager.Status("email")` | — |
| GET | `/emails/process/stream` | `EmailHandler.ProcessStream` | `ImportJobManager.Subscribe("email")` | — |
| GET | `/emails/folders` | `EmailHandler.ListFolders` | `EmailService.ListFolders` | Gmail client |
| GET | `/emails/label` | `EmailHandler.ByLabel` | `EmailService.GetByLabels` | `EmailRepo.GetByLabels` |
| GET | `/emails/search` | `EmailHandler.Search` | `EmailService.Search` | `EmailRepo.Search` |
| GET | `/emails/{id}/html` | `EmailHandler.GetHTML` | `EmailService.GetHTML` | `EmailRepo.GetByID` |
| GET | `/emails/{id}/text` | `EmailHandler.GetText` | `EmailService.GetText` | `EmailRepo.GetByID` |
| GET | `/emails/{id}/snippet` | `EmailHandler.GetSnippet` | `EmailService.GetSnippet` | `EmailRepo.GetByID` |
| GET | `/emails/{id}/metadata` | `EmailHandler.GetMetadata` | `EmailService.GetMetadata` | `EmailRepo.GetByID` |
| PUT | `/emails/{id}` | `EmailHandler.Update` | `EmailService.Update` | `EmailRepo.Update` |
| DELETE | `/emails/{id}` | `EmailHandler.Delete` | `EmailService.SoftDelete` | `EmailRepo.SoftDelete` |
| DELETE | `/emails/bulk-delete` | `EmailHandler.BulkDelete` | `EmailService.BulkDelete` | `EmailRepo.BulkDelete` |
| POST | `/emails/thread/{participant}/summarize` | `EmailHandler.SummarizeThread` | `EmailService.Summarize` + `ai.ChatProvider` | `EmailRepo.GetThread` |

### IMAP

| Method | Path | Handler | Service | Repo |
|---|---|---|---|---|
| POST | `/imap/process` | `IMAPHandler.Start` | `ImportJobManager.Start("imap", ...)` | — |
| POST | `/imap/process/cancel` | `IMAPHandler.Cancel` | `ImportJobManager.Cancel("imap")` | — |
| GET | `/imap/process/status` | `IMAPHandler.Status` | `ImportJobManager.Status("imap")` | — |
| GET | `/imap/process/stream` | `IMAPHandler.Stream` | `ImportJobManager.Subscribe("imap")` | — |
| POST | `/imap/folders` | `IMAPHandler.TestAndListFolders` | `IMAPService.Connect` | IMAP client |

### Messages (iMessage / WhatsApp / Facebook / Instagram)

Each platform follows the exact same pattern. Shown for iMessage; others identical with their prefix.

| Method | Path | Handler | Service | Repo |
|---|---|---|---|---|
| POST | `/{platform}/import` | `MessageHandler.StartImport` | `ImportJobManager.Start(platform, ...)` | — |
| POST | `/{platform}/import/cancel` | `MessageHandler.CancelImport` | `ImportJobManager.Cancel(platform)` | — |
| GET | `/{platform}/import/status` | `MessageHandler.ImportStatus` | `ImportJobManager.Status(platform)` | — |
| GET | `/{platform}/import/stream` | `MessageHandler.ImportStream` | `ImportJobManager.Subscribe(platform)` | — |
| GET | `/imessages/chat-sessions` | `MessageHandler.ChatSessions` | `MessageService.GetSessions` | `MessageRepo.GetSessions` |
| GET | `/imessages/conversation/{session}` | `MessageHandler.GetConversation` | `MessageService.GetConversation` | `MessageRepo.GetBySession` |
| DELETE | `/imessages/conversation/{session}` | `MessageHandler.DeleteConversation` | `MessageService.DeleteSession` | `MessageRepo.DeleteBySession` |
| GET | `/imessages/{id}/attachment` | `MessageHandler.GetAttachment` | `MessageService.GetAttachment` | `MediaRepo.GetBlob` |
| POST | `/writing-style/summarize` | `MessageHandler.SummarizeStyle` | `ImportJobManager.Start("writing-style", ...)` | — |
| GET | `/writing-style/summarize/stream` | `MessageHandler.SummarizeStream` | `ImportJobManager.Subscribe("writing-style")` | — |

### Chat & AI

| Method | Path | Handler | Service | Repo |
|---|---|---|---|---|
| GET | `/chat/availability` | `ChatHandler.Availability` | `ChatService.CheckProviders` | — |
| POST | `/chat/generate` | `ChatHandler.Generate` | `ChatService.Generate` | `ChatRepo.SaveTurn` |
| POST | `/chat/conversations` | `ChatHandler.CreateConversation` | `ChatService.CreateConversation` | `ChatRepo.CreateConversation` |
| GET | `/chat/conversations` | `ChatHandler.ListConversations` | `ChatService.ListConversations` | `ChatRepo.ListConversations` |
| GET | `/chat/conversations/{id}` | `ChatHandler.GetConversation` | `ChatService.GetConversation` | `ChatRepo.GetConversation` |
| PUT | `/chat/conversations/{id}` | `ChatHandler.UpdateConversation` | `ChatService.UpdateConversation` | `ChatRepo.UpdateConversation` |
| DELETE | `/chat/conversations/{id}` | `ChatHandler.DeleteConversation` | `ChatService.DeleteConversation` | `ChatRepo.DeleteConversation` |
| GET | `/chat/conversations/{id}/turns` | `ChatHandler.GetTurns` | `ChatService.GetTurns` | `ChatRepo.GetTurns` |
| GET | `/chat/complete-profile/names` | `ChatHandler.ProfileNames` | `ChatService.ListProfileNames` | `ChatRepo.ListProfileNames` |
| GET | `/chat/complete-profile` | `ChatHandler.GetProfile` | `ChatService.GetProfile` | `ChatRepo.GetProfile` |
| PUT | `/chat/complete-profile` | `ChatHandler.UpdateProfile` | `ChatService.UpdateProfile` | `ChatRepo.UpdateProfile` |
| POST | `/chat/complete-profile` | `ChatHandler.CreateProfile` | `ChatService.CreateProfile` | `ChatRepo.CreateProfile` |
| DELETE | `/chat/complete-profile` | `ChatHandler.DeleteProfile` | `ChatService.DeleteProfile` | `ChatRepo.DeleteProfile` |
| GET | `/api/subject-configuration` | `ChatHandler.GetSubjectConfig` | `SubjectService.Get` | `SubjectRepo.Get` |
| POST | `/api/subject-configuration` | `ChatHandler.SetSubjectConfig` | `SubjectService.Set` | `SubjectRepo.Upsert` |

### Configuration

| Method | Path | Handler | Service | Repo |
|---|---|---|---|---|
| GET | `/api/configuration` | `ConfigHandler.List` | `ConfigService.List` | `ConfigRepo.GetAll` |
| POST | `/api/configuration` | `ConfigHandler.Upsert` | `ConfigService.Upsert` | `ConfigRepo.Upsert` |
| DELETE | `/api/configuration/{key}` | `ConfigHandler.Delete` | `ConfigService.Delete` | `ConfigRepo.Delete` |
| POST | `/api/configuration/seed` | `ConfigHandler.Seed` | `ConfigService.SeedFromEnv` | `ConfigRepo.BulkUpsert` |

### Attachments

| Method | Path | Handler | Service | Repo |
|---|---|---|---|---|
| GET | `/attachments/random` | `AttachmentHandler.Random` | `AttachmentService.GetRandom` | `AttachmentRepo.Random` |
| GET | `/attachments/by-id` | `AttachmentHandler.ByID` | `AttachmentService.GetByIDOrder` | `AttachmentRepo.ByID` |
| GET | `/attachments/by-size` | `AttachmentHandler.BySize` | `AttachmentService.GetBySizeOrder` | `AttachmentRepo.BySize` |
| GET | `/attachments/count` | `AttachmentHandler.Count` | `AttachmentService.Count` | `AttachmentRepo.Count` |
| GET | `/attachments/images` | `AttachmentHandler.Images` | `AttachmentService.GetImages` | `AttachmentRepo.GetImages` |
| GET | `/attachments/{id}` | `AttachmentHandler.Download` | `AttachmentService.GetContent` | `AttachmentRepo.GetData` |
| GET | `/attachments/{id}/info` | `AttachmentHandler.Info` | `AttachmentService.GetInfo` | `AttachmentRepo.GetInfo` |
| DELETE | `/attachments/{id}` | `AttachmentHandler.Delete` | `AttachmentService.Delete` | `AttachmentRepo.Delete` |
| GET | `/attachments-viewer` | `AttachmentHandler.ViewerPage` | — | — |
| GET | `/attachments-images-grid` | `AttachmentHandler.GridPage` | — | — |

### Reference Documents

| Method | Path | Handler | Service | Repo |
|---|---|---|---|---|
| GET | `/reference-documents` | `DocumentHandler.List` | `DocumentService.List` | `DocumentRepo.List` |
| GET | `/reference-documents/{id}` | `DocumentHandler.Get` | `DocumentService.Get` | `DocumentRepo.GetByID` |
| GET | `/reference-documents/{id}/download` | `DocumentHandler.Download` | `DocumentService.GetContent` | `DocumentRepo.GetData` |
| POST | `/reference-documents` | `DocumentHandler.Upload` | `DocumentService.Upload` | `DocumentRepo.Create` |
| PUT | `/reference-documents/{id}` | `DocumentHandler.Update` | `DocumentService.Update` | `DocumentRepo.Update` |
| DELETE | `/reference-documents/{id}` | `DocumentHandler.Delete` | `DocumentService.Delete` | `DocumentRepo.Delete` |

### Media / Images

| Method | Path | Handler | Service | Repo |
|---|---|---|---|---|
| GET | `/images` | `ImageHandler.List` | `ImageService.Search` | `MediaRepo.Search` |
| GET | `/images/{id}` | `ImageHandler.GetMetadata` | `ImageService.GetMetadata` | `MediaRepo.GetByID` |
| GET | `/images/{blob_id}/thumbnail` | `ImageHandler.GetThumbnail` | `ImageService.GetThumbnail` | `MediaRepo.GetBlob` |
| GET | `/images/{blob_id}` | `ImageHandler.GetFull` | `ImageService.GetFull` | `MediaRepo.GetBlob` |
| PUT | `/images/{id}` | `ImageHandler.Update` | `ImageService.Update` | `MediaRepo.Update` |
| DELETE | `/images/{id}` | `ImageHandler.Delete` | `ImageService.Delete` | `MediaRepo.Delete` |
| POST | `/facebook/albums/import` | `FacebookHandler.StartAlbumImport` | `ImportJobManager.Start("fb-albums", ...)` | — |
| ... (cancel/status/stream same pattern) | | | | |
| GET | `/facebook/albums` | `FacebookHandler.ListAlbums` | `FacebookService.ListAlbums` | `MediaRepo.ListAlbums` |
| GET | `/facebook/albums/{id}/images` | `FacebookHandler.AlbumImages` | `FacebookService.AlbumImages` | `MediaRepo.AlbumImages` |
| POST | `/facebook/posts/import` | `FacebookHandler.StartPostImport` | `ImportJobManager.Start("fb-posts", ...)` | — |
| GET | `/facebook/posts` | `FacebookHandler.ListPosts` | `FacebookService.ListPosts` | `MediaRepo.ListPosts` |
| POST | `/facebook/import-places` | `FacebookHandler.StartPlacesImport` | `ImportJobManager.Start("fb-places", ...)` | — |
| GET | `/facebook/places` | `FacebookHandler.ListPlaces` | `FacebookService.ListPlaces` | `MediaRepo.ListPlaces` |
| POST | `/filesystem/import` | `FilesystemHandler.StartImport` | `ImportJobManager.Start("filesystem", ...)` | — |
| POST | `/thumbnails/generate` | `ThumbnailHandler.Generate` | `ImportJobManager.Start("thumbnails", ...)` | — |
| POST | `/images/export` | `ImageHandler.Export` | `ImportJobManager.Start("img-export", ...)` | — |

### Artefacts

| Method | Path | Handler | Service | Repo |
|---|---|---|---|---|
| GET | `/artefacts` | `ArtefactHandler.List` | `ArtefactService.List` | `ArtefactRepo.List` |
| GET | `/artefacts/{id}` | `ArtefactHandler.Get` | `ArtefactService.Get` | `ArtefactRepo.GetByID` |
| POST | `/artefacts` | `ArtefactHandler.Create` | `ArtefactService.Create` | `ArtefactRepo.Create` |
| PUT | `/artefacts/{id}` | `ArtefactHandler.Update` | `ArtefactService.Update` | `ArtefactRepo.Update` |
| DELETE | `/artefacts/{id}` | `ArtefactHandler.Delete` | `ArtefactService.Delete` | `ArtefactRepo.Delete` |
| GET | `/artefacts/{id}/thumbnail` | `ArtefactHandler.Thumbnail` | `ArtefactService.GetThumbnail` | `ArtefactRepo.GetFirstMedia` |
| POST | `/artefacts/{id}/media/upload` | `ArtefactHandler.UploadMedia` | `ArtefactService.UploadMedia` | `ArtefactRepo.LinkMedia` |
| POST | `/artefacts/{id}/media/{media_id}` | `ArtefactHandler.LinkMedia` | `ArtefactService.LinkMedia` | `ArtefactRepo.LinkMedia` |
| DELETE | `/artefacts/{id}/media/{media_id}` | `ArtefactHandler.UnlinkMedia` | `ArtefactService.UnlinkMedia` | `ArtefactRepo.UnlinkMedia` |
| GET | `/artefacts/export` | `ArtefactHandler.Export` | `ArtefactService.Export` | `ArtefactRepo.ExportAll` |
| POST | `/artefacts/import` | `ArtefactHandler.Import` | `ArtefactService.Import` | `ArtefactRepo.BulkCreate` |

### Relationships & Contacts

| Method | Path | Handler | Service | Repo |
|---|---|---|---|---|
| GET | `/contacts` | `RelationshipHandler.ListContacts` | `RelationshipService.ListContacts` | `ContactRepo.List` |
| GET | `/relationship/strength` | `RelationshipHandler.StrengthGraph` | `RelationshipService.BuildGraph` | `ContactRepo.GetGraph` |
| GET | `/relationship/{id}` | `RelationshipHandler.GetContact` | `RelationshipService.GetContact` | `ContactRepo.GetByID` |
| POST | `/relationship/contact` | `RelationshipHandler.CreateContact` | `RelationshipService.CreateContact` | `ContactRepo.Create` |
| PUT | `/relationship/{id}` | `RelationshipHandler.UpdateContact` | `RelationshipService.UpdateContact` | `ContactRepo.Update` |
| DELETE | `/relationship/{id}` | `RelationshipHandler.DeleteContact` | `RelationshipService.DeleteContact` | `ContactRepo.Delete` |
| GET | `/email-matches` | `RelationshipHandler.ListMatches` | `RelationshipService.ListMatches` | `ContactRepo.ListMatches` |
| POST | `/email-matches` | `RelationshipHandler.CreateMatch` | `RelationshipService.CreateMatch` | `ContactRepo.CreateMatch` |
| DELETE | `/email-matches/{id}` | `RelationshipHandler.DeleteMatch` | `RelationshipService.DeleteMatch` | `ContactRepo.DeleteMatch` |
| GET | `/email-exclusions` | `RelationshipHandler.ListExclusions` | `RelationshipService.ListExclusions` | `ContactRepo.ListExclusions` |
| POST | `/email-exclusions` | `RelationshipHandler.CreateExclusion` | `RelationshipService.CreateExclusion` | `ContactRepo.CreateExclusion` |
| DELETE | `/email-exclusions/{id}` | `RelationshipHandler.DeleteExclusion` | `RelationshipService.DeleteExclusion` | `ContactRepo.DeleteExclusion` |

### Interests / Voices / Saved Responses / Sensitive Data

All four follow identical CRUD patterns:

| Resource | Handler | Service | Repo |
|---|---|---|---|
| `/api/interests` | `InterestHandler` | `InterestService` | `InterestRepo` |
| `/api/voices` | `VoiceHandler` | `VoiceService` | `VoiceRepo` |
| `/api/saved-responses` | `ResponseHandler` | `ResponseService` | `ResponseRepo` |
| `/sensitive` | `SensitiveHandler` | `SensitiveService` | `SensitiveRepo` |

---

## 4. Data Model Structs

### Approach

- **sqlc generates Go structs** from `schema.sql` — these are the canonical DB types
- **Domain model types** in `internal/model/` may be thinner or richer than DB types, used between service↔handler
- **JSON response types** are the handler-level types (can be same as domain or separate DTOs)
- **Validation** via `go-playground/validator` tags on request structs (only at handler boundary)

### Key struct patterns (representative samples)

```go
// internal/database/queries/emails.sql.go (sqlc-generated, DO NOT hand-edit)
type Email struct {
    ID             int64
    UID            string
    Folder         string
    Subject        pgtype.Text        // nullable
    FromAddress    pgtype.Text
    ToAddresses    pgtype.Text        // comma-separated or JSON array
    Date           pgtype.Timestamptz
    RawMessage     pgtype.Text
    PlainText      pgtype.Text
    Snippet        pgtype.Text
    HasAttachments bool
    UserDeleted    bool
    IsPersonal     bool
    IsImportant    bool
    UseByAI        bool
    CreatedAt      pgtype.Timestamptz
    UpdatedAt      pgtype.Timestamptz
}

// internal/model/email.go (domain type — service layer)
type Email struct {
    ID             int64
    UID            string
    Folder         string
    Subject        string
    FromAddress    string
    ToAddresses    []string   // parsed from CSV
    Date           time.Time
    PlainText      string
    Snippet        string
    HasAttachments bool
    IsPersonal     bool
    IsImportant    bool
    UseByAI        bool
}

// handler request/response (inline in handler package, or separate dto package)
type UpdateEmailRequest struct {
    IsPersonal  *bool `json:"is_personal"`
    IsImportant *bool `json:"is_important"`
    UseByAI     *bool `json:"use_by_ai"`
}

type EmailMetadataResponse struct {
    ID          int64    `json:"id"`
    UID         string   `json:"uid"`
    Folder      string   `json:"folder"`
    Subject     string   `json:"subject"`
    From        string   `json:"from_address"`
    To          []string `json:"to_addresses"`
    Date        string   `json:"date"`   // ISO8601 string to match Python
    Snippet     string   `json:"snippet"`
    IsPersonal  bool     `json:"is_personal"`
    IsImportant bool     `json:"is_important"`
    UseByAI     bool     `json:"use_by_ai"`
}
```

### Nullable fields

Python's `Optional[str]` maps to `*string` (pointer) in Go request types and `pgtype.Text` in DB types. The `pgtype` package from pgx/v5 handles PostgreSQL nulls correctly without needing `database/sql.NullString`.

### Validation approach

```go
type CreateVoiceRequest struct {
    Key          string  `json:"key"          validate:"required,slug"`
    Name         string  `json:"name"         validate:"required,max=255"`
    Description  string  `json:"description"`
    Instructions string  `json:"instructions"`
    Creativity   float64 `json:"creativity"   validate:"min=0,max=2"`
}
```

A `validateRequest(v any) error` helper in the handler package runs validation and maps errors to a structured 400 response. This replaces Pydantic's automatic validation.

---

## 5. Auth & Middleware

### Current state: No auth

The Python app has no authentication. Go will preserve this — **no auth middleware** in the initial migration. This is an explicit carry-over decision, not an oversight.

### Middleware stack (Chi)

```go
r := chi.NewRouter()
r.Use(middleware.RequestID)
r.Use(middleware.RealIP)
r.Use(LoggingMiddleware)   // slog structured logging
r.Use(RecoverMiddleware)   // panic → 500 JSON
r.Use(middleware.Timeout(60 * time.Second))
```

### Gmail OAuth2

The existing `credentials.json` + `token.json` flow is replicated in `internal/emailclient/gmail.go`:
- Load credentials from file
- Load/refresh token from file
- Standard `golang.org/x/oauth2` flow
- Token auto-refresh using `oauth2.TokenSource`

### Static files

```go
r.Handle("/static/*", http.StripPrefix("/static/", http.FileServer(http.Dir("static"))))
```

### Templated endpoints — four, not two

Four endpoints render responses through `html/template` at request time (not static file serving):

| Endpoint | Template / file | Template variables |
|---|---|---|
| `GET /` | `index.template.html` **or** `non_user_init.template.html` | `page_title` + full subject context (see below) |
| `GET /api/suggestions` | `static/data/suggestions.json` (Jinja2 template, not a static file) | Full subject context |
| `GET /static/js/museum/foundation.js` | `foundation.js` | Full subject context + `gemini_configured`, `claude_configured` |
| `GET /static/js/museum/modals-people.js` | `modals-people.js` | Full subject context |

**`GET /` template selection logic** — this is not a simple file serve:
```go
func (h *AdminHandler) ServeIndex(w http.ResponseWriter, r *http.Request) {
    cfg, _ := h.subjectSvc.Get(r.Context())
    pageTitle := strings.ReplaceAll(
        h.configSvc.Get("PAGE_TITLE", "Digital Museum of SUBJECT_NAME"),
        "SUBJECT_NAME", cfg.SubjectName,
    )

    // Serve onboarding page if subject has never been configured
    templateName := "index.template.html"
    if cfg.SubjectName == "" && cfg.FamilyName == "" {
        templateName = "non_user_init.template.html"
    }

    h.templates.ExecuteTemplate(w, templateName, map[string]any{
        "page_title": pageTitle,
        // ... full subject context
    })
}
```

**Subject template context helper** — a single `buildSubjectContext(cfg SubjectConfiguration) map[string]any` function produces the 12 variables used by all four templated endpoints:

| Variable | Derived from |
|---|---|
| `owner` | `subject_name` |
| `owners` | `subject_name + "'s"` |
| `full_name` | `subject_name + " " + family_name` |
| `he` / `him` / `his` / `himself` | gender — "he/him/his/himself" or "she/her/her/herself" |
| `owner_image` / `owner_image_small` | gender — "male.png"/"female.png" |
| `admirer_image` / `admirer_image_small` | opposite of owner_image |

This helper lives in `internal/handler/admin.go` and is called by all four template handlers.

**`foundation.js` additional context** — beyond the subject context, this endpoint also injects two booleans derived from whether Gemini/Claude API keys are present and valid at startup:
```go
ctx["gemini_configured"] = h.ai.GeminiAvailable()   // "True" / "False" string to match Python
ctx["claude_configured"] = h.ai.ClaudeAvailable()
```

Note: Python serialises these as the strings `"True"` and `"False"` (not JSON `true`/`false`). The frontend JS reads them as strings. **Match this exactly.**

---

## 6. Background Jobs & SSE

This is the most architecturally significant change from Python.

### Python pattern (problematic for Go)

```python
processing_lock = threading.Lock()
processing_cancelled = threading.Event()
processing_in_progress = bool
# ... 15+ sets of these globals, one per import type
sse_clients: List[asyncio.Queue] = []
```

Problems: global mutable state, no type safety, difficult to test, doesn't scale.

### Go design: `ImportJobManager`

```go
// internal/importer/job.go

type JobType string

const (
    JobEmail       JobType = "email"
    JobIMAP        JobType = "imap"
    JobIMessage    JobType = "imessage"
    JobWhatsApp    JobType = "whatsapp"
    JobFacebook    JobType = "facebook"
    JobInstagram   JobType = "instagram"
    JobFBAlbums    JobType = "fb-albums"
    JobFBPosts     JobType = "fb-posts"
    JobFBPlaces    JobType = "fb-places"
    JobFilesystem  JobType = "filesystem"
    JobThumbnails  JobType = "thumbnails"
    JobImgExport   JobType = "img-export"
    JobWritingStyle JobType = "writing-style"
)

type Progress struct {
    Status    string `json:"status"`
    Message   string `json:"message"`
    Current   int    `json:"current"`
    Total     int    `json:"total"`
    Error     string `json:"error,omitempty"`
}

type jobState struct {
    cancel   context.CancelFunc
    progress atomic.Value // stores Progress
    clients  []chan []byte // SSE subscriber channels
    mu       sync.RWMutex
}

type ImportJobManager struct {
    jobs map[JobType]*jobState
    mu   sync.RWMutex
    db   *pgxpool.Pool
    log  *slog.Logger
}

func (m *ImportJobManager) Start(ctx context.Context, jobType JobType, worker WorkerFunc) error
func (m *ImportJobManager) Cancel(jobType JobType) bool
func (m *ImportJobManager) Status(jobType JobType) (Progress, bool)
func (m *ImportJobManager) Subscribe(jobType JobType) (<-chan []byte, func())
func (m *ImportJobManager) Broadcast(jobType JobType, p Progress)
```

### SSE handler pattern

```go
func (h *EmailHandler) ProcessStream(w http.ResponseWriter, r *http.Request) {
    flusher, ok := w.(http.Flusher)
    if !ok {
        http.Error(w, "streaming not supported", 500)
        return
    }
    w.Header().Set("Content-Type", "text/event-stream")
    w.Header().Set("Cache-Control", "no-cache")
    w.Header().Set("Connection", "keep-alive")

    ch, unsub := h.jobs.Subscribe(importer.JobEmail)
    defer unsub()

    ticker := time.NewTicker(30 * time.Second)
    defer ticker.Stop()

    for {
        select {
        case data := <-ch:
            fmt.Fprintf(w, "data: %s\n\n", data)
            flusher.Flush()
        case <-ticker.C:
            fmt.Fprintf(w, ": heartbeat\n\n")
            flusher.Flush()
        case <-r.Context().Done():
            return
        }
    }
}
```

### Worker interface

```go
type WorkerFunc func(ctx context.Context, broadcast func(Progress)) error
```

Each importer (`internal/importer/email.go`, etc.) implements `WorkerFunc`. The `ImportJobManager.Start` runs it in a goroutine, passes a `broadcast` closure, and records the result in `import_control_last_run` when done.

---

## 7. AI Service Layer

### Interface

```go
// internal/ai/provider.go

type GenerateRequest struct {
    Prompt        string
    Voice         string
    Temperature   float64
    ConversationID *int64
    SystemPrompt  string
    Documents     []DocumentRef   // reference documents for context
    Mood          string
    CompanionMode bool
    WhosAsking    string
}

type GenerateResponse struct {
    Text         string
    EmbeddedJSON map[string]any
}

type ChatProvider interface {
    Generate(ctx context.Context, req GenerateRequest) (GenerateResponse, error)
    Available() bool
    ProviderName() string
}
```

### Implementations

- `internal/ai/gemini.go` — wraps `google-genai-go`; handles file upload for reference documents
- `internal/ai/claude.go` — wraps `anthropic-sdk-go`

### Service layer

`internal/service/chat_service.go` selects provider (Gemini or Claude), builds system prompt from subject config + voice, calls `ChatProvider.Generate`, parses embedded JSON from response, persists turn to DB.

### Gemini file tracking

The `gemini_files` table maps `reference_document_id` → Gemini uploaded file URI. The Gemini service checks this table before re-uploading; marks entries as EXPIRED when Gemini returns 404. This logic lives in `internal/ai/gemini.go` with a repo call.

---

## 8. Existing Go Code Integration

The Python app currently calls `import-processor` and `datahandler` as external subprocess invocations. Both are already written in Go and target the same PostgreSQL database. Rather than rewriting this logic, it is ported directly into the new monolith as internal packages.

### 8.1 import-processor → `internal/importer/workers/`

**Current Python invocation pattern:**
```python
# Python calls the Go binary as a subprocess
subprocess.run(["import-processor", "whatsapp", "/path/to/exports"])
```

**New Go invocation pattern (direct function call):**
```go
// Handler starts a goroutine via ImportJobManager; worker is called directly
func (m *ImportJobManager) Start(ctx context.Context, job JobType, params any) error {
    go func() {
        err := workers.ImportWhatsApp(ctx, m.db, params.(WhatsAppParams), m.broadcast)
        m.recordResult(job, err)
    }()
}
```

**Porting approach for each worker package:**

| Source (import-processor) | Destination | Changes required |
|---|---|---|
| `internal/import/whatsapp/` | `internal/importer/workers/whatsapp/` | Replace `pgxpool.New` call with injected pool; add `broadcast func(Progress)` parameter |
| `internal/import/imessage/` | `internal/importer/workers/imessage/` | Same as above |
| `internal/import/facebook/` | `internal/importer/workers/facebook/` | Same as above |
| `internal/import/facebookalbums/` | `internal/importer/workers/facebookalbums/` | Same as above |
| `internal/import/facebookposts/` | `internal/importer/workers/facebookposts/` | Same as above |
| `internal/import/facebookplaces/` | `internal/importer/workers/facebookplaces/` | Same as above |
| `internal/import/instagram/` | `internal/importer/workers/instagram/` | Same as above |
| `internal/import/filesystem/` | `internal/importer/workers/filesystem/` | Same as above |
| `internal/import/contacts/` | `internal/importer/workers/contacts/` | Same as above; expose as API endpoint (see §8.3) |
| `internal/database/storage.go` | `internal/repository/message_import_repo.go` | Rename; accept injected pool rather than creating own |
| `internal/database/image_storage.go` | `internal/repository/media_import_repo.go` | Same |
| `internal/database/facebook_*.go` | `internal/repository/facebook_import_repo.go` | Same |
| `internal/database/location_storage.go` | `internal/repository/location_repo.go` | Same |
| `internal/services/thumbnail-and-exif.go` | `internal/importer/workers/thumbnail.go` | Merge with Python's thumbnail logic |
| `pkg/utils/mime.go`, `file.go` | `internal/importer/workers/utils/` | No changes needed |

**Changes are minimal** — the only edits to each worker are:
1. Remove the `pgxpool.New(...)` call at the top of each `Import*` function
2. Accept a `*pgxpool.Pool` as an injected parameter
3. Accept a `func(Progress)` callback for SSE progress broadcasting (replacing `fmt.Println` progress output)
4. Change the module path from `import-processor` to the new module name

**Keep intact:**
- All parsing logic (CSV, JSON, MIME detection)
- All batch insert/deduplication logic
- Worker pool patterns (`sync.WaitGroup` + goroutines)
- The `SetIsGroupChat` post-import SQL
- Orphan conversation cleanup

### 8.2 datahandler → `internal/crypto/`

**Current Python invocation pattern:**
```python
# Python calls the Go binary as a subprocess
result = subprocess.run(["datahandler", "getrecord", record_id, password], capture_output=True)
data = json.loads(result.stdout)
```

**New Go invocation pattern:**
```go
// Service layer calls crypto package directly
record, err := crypto.GetRecord(ctx, db, recordID, password)
```

**Porting approach:**

| Source (datahandler) | Destination | Notes |
|---|---|---|
| Crypto functions (Argon2id, AES-GCM, RSA-OAEP) | `internal/crypto/encrypt.go` | Pure functions, no DB access — port unchanged |
| Key derivation helpers | `internal/crypto/argon2.go` | Port unchanged |
| Seed loading | `internal/crypto/seed.go` | Use `//go:embed seed.txt`; `seed.txt` file kept at project root or `internal/crypto/` |
| `generateMasterKey` command | `internal/crypto/keys.go` | Exported as `GenerateMasterKey(ctx, db, password)` |
| `generateTrustedKeys` command | `internal/crypto/keys.go` | Exported as `GenerateTrustedKey(ctx, db, userPass, masterPass)` |
| `getRecord` / `getRecords` | `internal/service/sensitive_service.go` | Service calls `crypto.Decrypt(...)` + repo |
| `createRecord` / `updateRecord` | `internal/service/sensitive_service.go` | Service calls `crypto.Encrypt(...)` + repo |
| `deleteRecord` | `internal/service/sensitive_service.go` | Service calls repo directly |
| `test` command | `internal/service/sensitive_service.go` | `SensitiveService.TestMasterPassword(ctx, password)` |
| `getkeycount` / `getrecordcount` | `internal/service/sensitive_service.go` | Simple repo count queries |

**The sensitive data HTTP endpoints** (already in the endpoint inventory at §3) now have their full implementation path:
- `GET /sensitive` → `SensitiveHandler` → `SensitiveService.ListRecords(ctx, password)` → `crypto.Decrypt` + `SensitiveRepo.GetAll`
- `POST /sensitive` → `SensitiveHandler` → `SensitiveService.CreateRecord(ctx, req)` → `crypto.EncryptHybrid` + `SensitiveRepo.Create`

**Important:** The `seed.txt` file embedded in the datahandler binary is the cryptographic seed for all existing encrypted records. This file **must** be preserved exactly as-is and embedded in the new binary. Loss or modification of this file makes all existing encrypted records permanently unrecoverable.

### 8.3 Contacts Normalization — New API Endpoint

The `contacts-normalise` command in import-processor has no equivalent HTTP endpoint in the Python app — it was a standalone CLI operation. In the Go monolith, expose it as:

```
POST /contacts/normalise
```

| Method | Path | Handler | Service | Worker |
|---|---|---|---|---|
| POST | `/contacts/normalise` | `RelationshipHandler.Normalise` | `RelationshipService.Normalise` | `workers/contacts.RunContactsNormalise` |

This is a background job managed by `ImportJobManager` (job type `"contacts-normalise"`), following the same start/cancel/status/stream pattern as all other import jobs.

### 8.4 Summary of what is NOT being rewritten

| Component | Already exists in Go | Action |
|---|---|---|
| WhatsApp CSV parser + batch importer | `import-processor` | Port (change module path + inject pool) |
| iMessage CSV parser + batch importer | `import-processor` | Port |
| Facebook JSON parser + batch importer | `import-processor` | Port |
| Facebook albums/posts/places importers | `import-processor` | Port |
| Instagram JSON parser + batch importer | `import-processor` | Port |
| Filesystem image importer | `import-processor` | Port |
| Contact normalization + deduplication pipeline | `import-processor` | Port + expose as HTTP |
| AES-256-GCM encryption/decryption | `datahandler` | Port (pure functions) |
| RSA-OAEP hybrid encryption | `datahandler` | Port (pure functions) |
| Argon2id key derivation | `datahandler` | Port (pure functions) |
| Master key + trusted key management | `datahandler` | Port |
| Batch insert + dedup logic (messages, media) | `import-processor` | Port |

---

## 9. Testing Strategy

### Unit tests (handler + service + repo layers)

- Each handler tested with `httptest.NewRecorder` + `httptest.NewServer`
- Services tested with mock interfaces (no real DB)
- Repos tested against a real test DB (see integration tests)
- Use `github.com/stretchr/testify` for assertions

### Interface-driven mocks

Every service dependency is an interface. Mocks are hand-written or generated with `github.com/vektra/mockery`.

```go
// internal/service/interfaces.go
type EmailRepository interface {
    GetByID(ctx context.Context, id int64) (model.Email, error)
    Search(ctx context.Context, params SearchParams) ([]model.Email, error)
    SoftDelete(ctx context.Context, id int64) error
    // ...
}
```

### Integration tests (repo layer)

- Spin up a real PostgreSQL instance (Docker or `testcontainers-go`)
- Run schema migrations before tests
- Each test gets a transaction that is rolled back at the end
- Test file: `internal/repository/*_test.go`

### E2E / API tests

- Start the full server with a test DB
- Use `net/http/httptest` or a real server on a random port
- Test the complete request/response cycle for critical paths
- Priority: chat generate, email search, image list, import start/cancel/status

### What Python had: nothing

There are zero existing tests. The Go rewrite is the opportunity to build a proper test suite. Start testing from phase 1 of implementation so bugs are caught early.

### Test file layout

```
internal/handler/emails_test.go
internal/service/chat_service_test.go
internal/repository/email_repo_test.go
internal/importer/job_test.go
internal/ai/gemini_test.go          # uses recorded HTTP fixtures
```

---

## 10. Migration Sequence

The goal is to have a continuously deployable Go binary at each phase. Each phase ends with a working server that can run alongside or replace the Python server for that phase's covered routes.

### Phase 1 — Foundation (build before anything else)

**Why first:** Everything else depends on these.

1. `go.mod`, `Makefile`, CI skeleton
2. `internal/config/config.go` — load all env vars into typed struct
3. `internal/database/db.go` — pgx/v5 pool setup
4. `internal/database/migrate.go` — schema DDL (copy from Python `connection.py`)
5. `sqlc/schema.sql` — canonical schema file
6. `cmd/server/main.go` — minimal server, `/health` only
7. Middleware stack (logging, recovery)
8. Static file serving

### Phase 2 — Core Read APIs (most frontend usage)

**Why second:** These are read-only, low-risk, high-value endpoints.

1. `sqlc/queries/` — write SQL for emails, media, messages, chat, contacts
2. Run `sqlc generate`
3. Implement repositories for emails, media, messages, contacts, chat
4. Implement services: `EmailService.Search/Get`, `ImageService.Search/Get`, `MessageService.GetSessions/GetConversation`
5. Implement handlers: `GET /emails/*`, `GET /images/*`, `GET /imessages/*`
6. `GET /api/dashboard` and `GET /api/subject-configuration`
7. Write unit + integration tests for all of the above

### Phase 2.5 — Crypto Layer

**Why before Phase 3:** The sensitive data CRUD endpoints (Phase 4) depend on the crypto package. Port this early while it's a clean, self-contained task.

1. Copy `seed.txt` from `datahandler/` to `internal/crypto/seed.txt`
2. Port pure crypto functions into `internal/crypto/encrypt.go` and `internal/crypto/argon2.go` (no DB dependency — port unchanged)
3. Port key management functions into `internal/crypto/keys.go` (inject DB pool)
4. Write unit tests for all crypto functions (they are pure and highly testable)

### Phase 3 — Chat & AI

**Why third:** Core product feature; depends on config and subject service.

1. `internal/ai/provider.go` interface
2. `internal/ai/gemini.go`
3. `internal/ai/claude.go`
4. `internal/service/chat_service.go`
5. All `/chat/*` handlers
6. `/api/subject-configuration` POST
7. Gemini file tracking (reference document → file URI mapping)

### Phase 4 — CRUD endpoints (lower risk, repetitive)

1. Artefacts CRUD + media linking
2. Reference documents (upload, download, metadata)
3. Voices, Interests, Saved Responses (simple CRUD)
4. Configuration CRUD + seed
5. Sensitive data
6. Contacts / Relationships / Email matches / Exclusions
7. Attachments viewer

### Phase 5 — Background Import Jobs

**Why here:** The import logic already exists in Go (`import-processor`). This phase is primarily a port + wiring job, not a write-from-scratch effort. The `ImportJobManager` infrastructure is new; the worker logic is largely transplanted.

1. `internal/importer/job.go` — `ImportJobManager` (new)
2. SSE handler infrastructure (new)
3. Port `import-processor` workers into `internal/importer/workers/` (see §8.1):
   - Change module path
   - Inject `*pgxpool.Pool` instead of creating own connection
   - Add `broadcast func(Progress)` callback parameter
   - Workers to port: WhatsApp, iMessage, Facebook, Facebook Albums/Posts/Places, Instagram, Filesystem
4. Port `import-processor` storage/repo layer into `internal/repository/` (see §8.1)
5. Email import worker (Gmail) — new, no existing equivalent
6. IMAP import worker — new, no existing equivalent
7. Thumbnail generation worker — new (Python-only logic)
8. Writing style analysis — new (Python-only logic, calls AI provider)
9. Contacts normalisation job + `POST /contacts/normalise` endpoint (see §8.3)
10. Wire all workers into `ImportJobManager` with correct job type constants

### Phase 6 — Email Mutation + Delete

1. `PUT /emails/{id}`, `DELETE /emails/{id}`, `DELETE /emails/bulk-delete`
2. Thread summarize
3. IMAP folder listing

### Phase 7 — Hardening

1. Full E2E test pass against test DB
2. JSON shape verification (compare Python vs Go responses for every endpoint)
3. Memory profiling (`pprof`) under import load
4. Graceful shutdown: drain in-progress imports, close DB pool
5. Remove `DELETE /admin/empty-media-tables` from production build (or put behind env flag)

---

## 11. Risk Areas & Python Patterns

### 10.1 Global mutable state for import jobs

**Python pattern:**
```python
processing_lock = threading.Lock()
processing_in_progress = False
processing_progress = {}
```

**Risk:** 15+ sets of these globals; difficult to test or reason about.
**Go solution:** `ImportJobManager` struct (see §6) — all state encapsulated, injected via constructor, testable with mocks.

---

### 10.2 Python exceptions as control flow

**Python pattern:**
```python
raise ServiceException("not found", status_code=404)
```
FastAPI catches these and maps to HTTP responses automatically.

**Go equivalent:**
```go
// Define sentinel errors in the service layer
var ErrNotFound = errors.New("not found")
var ErrConflict  = errors.New("conflict")

// Handler maps errors to status codes
func writeError(w http.ResponseWriter, err error) {
    switch {
    case errors.Is(err, service.ErrNotFound):
        http.Error(w, err.Error(), 404)
    case errors.Is(err, service.ErrConflict):
        http.Error(w, err.Error(), 409)
    default:
        http.Error(w, "internal server error", 500)
    }
}
```

**Behavioral difference:** None from the frontend's perspective — same HTTP status codes and error JSON shapes.

---

### 10.3 Pydantic automatic request validation

**Python pattern:** Pydantic models validate automatically; FastAPI raises 422 with detailed field errors.

**Go equivalent:** Manual validation at handler boundary using `go-playground/validator`. Return 400 (not 422) with a JSON body matching the existing error shape. Audit the frontend to confirm it checks for 400 vs 422 — if it expects 422, that status code can be returned.

**Action:** Check the frontend JS for `.status === 422` checks before finalising the error code.

---

### 10.4 Dependency injection via FastAPI `Depends()`

**Python pattern:**
```python
def get_db() -> Session: ...
def get_email_service(db = Depends(get_db)) -> EmailService: ...

@router.get("/emails")
async def list_emails(svc = Depends(get_email_service)):
    ...
```

**Go equivalent:** Constructor injection — each handler struct receives its dependencies at startup:
```go
type EmailHandler struct {
    svc EmailService
    log *slog.Logger
}
func NewEmailHandler(svc EmailService, log *slog.Logger) *EmailHandler
```

No reflection, no magic. Dependencies are wired explicitly in `cmd/server/main.go`.

---

### 10.5 SQLAlchemy ORM lazy loading

**Python pattern:**
```python
email.attachments  # lazy-loaded relationship; triggers a SELECT on access
```

**Risk:** In Go with raw SQL, there are no lazy-loaded relationships. Every join or sub-query must be explicit.

**Go equivalent:** Service layer makes explicit calls:
```go
email, _ := repo.GetByID(ctx, id)
attachments, _ := repo.GetAttachmentsByEmailID(ctx, id)
```

This is actually better — N+1 queries become obvious and can be optimised with a single JOIN query in sqlc.

---

### 10.6 Python `Optional` and `None` vs Go nil/zero values

**Risk:** Python's `None` is unambiguous; Go's zero values (`""`, `0`, `false`) can be confused with intentional values.

**Pattern:** Use pointer types (`*string`, `*bool`, `*int`) for nullable request fields. Use `pgtype.Text`, `pgtype.Int4` etc. from pgx/v5 for nullable DB columns — they serialise to/from JSON correctly and map to/from PostgreSQL NULL.

---

### 10.7 CSV-encoded array fields

**Python pattern:** `to_addresses` stored as a CSV string in a `TEXT` column; decoded to `List[str]` at the Python layer.

**Go equivalent:** Decoded in the repository layer using `strings.Split`. The DB schema is unchanged — this is a migration, not a refactor of the data model. A `pgtype.Array` type could be used if the column is ever altered to a proper PostgreSQL array, but that is out of scope for this migration.

---

### 10.8 Embedded JSON in AI responses

**Python pattern:** Chat responses sometimes contain embedded JSON blobs that the service parses out with regex:
```python
import re
match = re.search(r'\{.*\}', response_text, re.DOTALL)
```

**Go equivalent:**
```go
re := regexp.MustCompile(`\{[\s\S]*\}`)
match := re.FindString(responseText)
if match != "" {
    var embedded map[string]any
    json.Unmarshal([]byte(match), &embedded)
}
```

Same logic, no behavioural difference. Compile the regex once at package init (not inside the function).

---

### 10.9 Binary blob storage in PostgreSQL

**Pattern:** Images and documents stored as `BYTEA` (LargeBinary) columns in the DB.

**Risk:** Large binary reads can be slow; pgx/v5 reads them as `[]byte` in Go. No special handling needed, but be aware that fetching a row with a large blob will load it fully into memory. The Python code already does this, so behaviour is identical — no regression.

**Future consideration (out of scope):** Move blobs to S3/object storage and store only references. Flag this as a known debt item.

---

### 10.10 Jinja2 templated responses — four endpoints, not two

**Python pattern:** Four endpoints render Jinja2 templates at request time — the root HTML page, `suggestions.json`, and two JS files. The plan's §5 documents all four in detail.

**Go equivalent:** `html/template` loaded from disk. Re-render on each request (no caching needed — these are low-frequency, and subject config changes must reflect immediately on page reload).

**`GET /` branch:** The root route serves one of two HTML templates depending on whether the subject has been initialised. If `subject_name == ""` and `family_name == ""`, serve `non_user_init.template.html` (onboarding). Otherwise serve `index.template.html`. **This conditional must be preserved exactly** — it is the app's onboarding flow.

**`"True"`/`"False"` string quirk:** `foundation.js` receives `gemini_configured` and `claude_configured` as the Python string literals `"True"` and `"False"`, not JSON booleans. The frontend JS compares against these strings. Emit the same strings from the Go template:
```go
// Wrong:  true / false
// Correct: "True" / "False"
ctx["gemini_configured"] = "False"
if h.ai.GeminiAvailable() {
    ctx["gemini_configured"] = "True"
}
```

**`suggestions.json` is not a static file:** It is stored on disk with Jinja2 template syntax and rendered at request time with the subject context. In Go, load it with `template.ParseFiles` and execute it with `json.NewEncoder` — or render to a `bytes.Buffer` then `json.Unmarshal` to verify it is still valid JSON before sending.

**Security note:** All template values come from the DB/config (not user input), so no XSS risk for any of the four endpoints.

---

### 10.11 HEIC/HEIF image support

**Python:** `pillow-heif` registers with Pillow transparently.

**Go risk:** The Go equivalent requires CGo binding to libheif. This adds a C dependency to the build, complicates cross-compilation, and may not be available in all deployment environments.

**Recommendation:** Implement Phase 1–6 without HEIC support. Add a clear feature flag `ENABLE_HEIC=true` that only activates the CGo code path. Document that HEIC images will return an error without this flag.

---

### 10.12 Docker path translation

**Python:** `src/utils/docker_utils.py` translates host filesystem paths to container paths for import operations.

**Go:** Replicate this as a simple string replacement utility in `internal/importer/paths.go`. Read `DOCKER_HOST_PATH` / `DOCKER_CONTAINER_PATH` from config; if unset, paths are used as-is.

---

### 10.13 No authentication

The Python app has no auth. This is carried over intentionally. The Go version will also have no auth. If auth is added in the future, Chi middleware makes it straightforward to insert at the router level without touching handlers.

---

### 10.14 Singleton subject configuration

**Python pattern:** `subject_configuration` table has exactly one row; code queries `first()` always.

**Go equivalent:**
```go
func (r *SubjectRepo) Get(ctx context.Context) (model.SubjectConfiguration, error) {
    // LIMIT 1, return ErrNotFound if no rows
}
func (r *SubjectRepo) Upsert(ctx context.Context, cfg model.SubjectConfiguration) error {
    // INSERT ... ON CONFLICT DO UPDATE
}
```

No special singleton framework needed — the data model enforces it.

---

### 11.16 Cryptographic seed preservation

**Risk:** `datahandler` embeds `seed.txt` at compile time using `go:embed`. This seed is used as the Argon2id salt and AES nonce for all existing encrypted records in `sensitive_data`. If the seed changes — or the file is not ported correctly — all existing records become permanently unrecoverable.

**Go action:**
- Copy `seed.txt` byte-for-byte from `datahandler/` to `internal/crypto/seed.txt`
- Use `//go:embed seed.txt` in `internal/crypto/seed.go`
- Add a test that verifies the embedded seed matches a known SHA-256 checksum before any crypto function is callable
- Treat `seed.txt` like a production secret — do not regenerate it

---

### 11.17 import-processor subprocess → direct function call

**Python pattern:** Python calls the Go binary as a subprocess and blocks until it exits:
```python
result = subprocess.run(["./import-processor", "whatsapp", path], capture_output=True)
```

**Risk areas in the port:**
1. **Progress reporting:** The subprocess wrote progress to stdout, which Python ignored. In the monolith, the same progress must be broadcast via SSE. The port must add a `broadcast func(Progress)` callback everywhere that `fmt.Println` or `log.Println` is currently called.
2. **Context cancellation:** The Python cancel flow sent `SIGTERM` to the subprocess. In the monolith, cancellation uses `context.WithCancel`. Every worker loop must check `ctx.Err()` and return promptly.
3. **Error propagation:** Subprocess exit codes are replaced by `error` return values. The `ImportJobManager` captures the returned error and stores it in `import_control_last_run`.
4. **Concurrency:** import-processor uses its own worker pool internally. This is preserved — the outer `ImportJobManager` goroutine simply runs the worker function, which manages its own internal concurrency.

---

### 11.18 datahandler subprocess → direct function call

**Python pattern:**
```python
result = subprocess.run(["./datahandler", "getrecord", str(record_id), password], capture_output=True)
data = json.loads(result.stdout)
```

**Risk areas:**
1. **Password handling:** Passwords currently flow as CLI arguments (visible in `ps aux`). As direct function calls, passwords are Go strings in memory — significantly more secure, no process list exposure.
2. **stdin for record creation:** `createrecord` reads base64 JSON from stdin. In the monolith, this becomes a direct struct parameter — no stdin/stdout I/O.
3. **Deterministic nonce:** `datahandler` uses a fixed 12-byte nonce from the seed file for AES-GCM rather than a random nonce per encryption. This is an unusual (non-standard) choice — it means encrypting the same plaintext twice with the same key produces the same ciphertext. This is intentional in the existing design (supports deterministic re-encryption). **Do not change this behaviour** during the port, as changing it would invalidate all existing records.
4. **`ATTACHMENT_ALLOWED_TYPES` as crypto pepper:** `datahandler` reads the `ATTACHMENT_ALLOWED_TYPES` environment variable as a cryptographic pepper — a surprising reuse of a name intended for attachment filtering. In the new config struct, expose this as a dedicated `CRYPTO_PEPPER` field while keeping backward compatibility via the old env var name.

---

### 11.15 Graceful shutdown

**Python:** Uvicorn handles SIGTERM; in-progress requests may be interrupted.

**Go explicit approach:**
```go
// cmd/server/main.go
srv := &http.Server{Addr: addr, Handler: router}

go srv.ListenAndServe()

stop := make(chan os.Signal, 1)
signal.Notify(stop, syscall.SIGTERM, syscall.SIGINT)
<-stop

ctx, cancel := context.WithTimeout(context.Background(), 30*time.Second)
defer cancel()
srv.Shutdown(ctx)     // drains in-flight HTTP requests
jobManager.Shutdown() // cancels all running import jobs
pool.Close()          // closes DB connections
```

This is a significant improvement over Python — import jobs can be cleanly cancelled on shutdown rather than being killed mid-write.

---

## Appendix: Key Go Packages (go.mod)

```
github.com/go-chi/chi/v5
github.com/jackc/pgx/v5
github.com/sqlc-dev/sqlc              (dev/codegen tool, not a runtime dep)
github.com/joho/godotenv
github.com/go-playground/validator/v10
github.com/google/generative-ai-go/genai
github.com/anthropics/anthropic-sdk-go
google.golang.org/api/gmail/v1
golang.org/x/oauth2
golang.org/x/oauth2/google
golang.org/x/crypto                   # Argon2id (ported from datahandler)
github.com/emersion/go-imap/v2
github.com/disintegration/imaging
github.com/stretchr/testify
github.com/vektra/mockery/v2           (dev/codegen tool)
```

Standard library packages used heavily:
- `log/slog` — structured logging
- `net/http` — server and client
- `html/template` — JS template rendering
- `encoding/json` — JSON marshalling
- `context` — cancellation and deadlines
- `sync` — mutexes and wait groups
- `regexp` — embedded JSON extraction
- `image/jpeg`, `image/png` — image encoding
- `bytes`, `io` — binary data handling
- `crypto/aes`, `crypto/cipher` — AES-256-GCM (ported from datahandler)
- `crypto/rsa`, `crypto/rand` — RSA-OAEP (ported from datahandler)
- `embed` — compile-time seed embedding (ported from datahandler)
- `net/http/pprof` — profiling (dev only)
