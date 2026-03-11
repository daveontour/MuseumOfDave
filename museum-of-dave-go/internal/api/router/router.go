// Package router wires all HTTP routes onto a chi.Mux.
package router

import (
	"encoding/json"
	"net/http"

	"github.com/go-chi/chi/v5"
	chimiddleware "github.com/go-chi/chi/v5/middleware"
	"github.com/jackc/pgx/v5/pgxpool"
	appai "github.com/museum-of-dave/app/internal/ai"
	"github.com/museum-of-dave/app/internal/config"
	"github.com/museum-of-dave/app/internal/handler"
	"github.com/museum-of-dave/app/internal/middleware"
	"github.com/museum-of-dave/app/internal/repository"
	"github.com/museum-of-dave/app/internal/service"
)

// New returns the fully-wired application router.
func New(pool *pgxpool.Pool, cfg *config.Config) http.Handler {
	r := chi.NewRouter()

	// ── Global middleware ───────────────────────────────────────────────────────
	r.Use(middleware.Recoverer)
	r.Use(middleware.Logger)
	r.Use(chimiddleware.RequestID)
	r.Use(chimiddleware.RealIP)

	// ── Health check ───────────────────────────────────────────────────────────
	r.Get("/health", healthHandler)

	// ── Static files ───────────────────────────────────────────────────────────
	// Serve /static/* from PYTHON_STATIC_DIR (../src/api/static by default).
	// This covers css/, images/, js/ and any other assets the frontend requests.
	fs := http.FileServer(http.Dir(cfg.App.PythonStaticDir))
	r.Handle("/static/*", http.StripPrefix("/static/", fs))

	// ── Emails ─────────────────────────────────────────────────────────────────
	emailRepo := repository.NewEmailRepo(pool)
	emailSvc := service.NewEmailService(emailRepo)
	emailHandler := handler.NewEmailHandler(emailSvc)
	emailHandler.RegisterRoutes(r)

	// ── IMAP ──────────────────────────────────────────────────────────────────
	imapHandler := handler.NewIMAPHandler(pool)
	imapHandler.RegisterRoutes(r)

	// ── Images & media ─────────────────────────────────────────────────────────
	imageRepo := repository.NewImageRepo(pool)
	imageSvc := service.NewImageService(imageRepo)
	imageHandler := handler.NewImageHandler(imageSvc)
	imageHandler.RegisterRoutes(r)

	// ── Messages ────────────────────────────────────────────────────────────────
	messageRepo := repository.NewMessageRepo(pool)
	messageSvc := service.NewMessageService(messageRepo)
	messageHandler := handler.NewMessageHandler(messageSvc)
	messageHandler.RegisterRoutes(r)

	// ── Dashboard & subject configuration ────────────────────────────────────
	dashboardRepo := repository.NewDashboardRepo(pool)
	subjectConfigRepo := repository.NewSubjectConfigRepo(pool)
	dashboardSvc := service.NewDashboardService(dashboardRepo, subjectConfigRepo)
	subjectConfigSvc := service.NewSubjectConfigService(subjectConfigRepo)
	dashboardHandler := handler.NewDashboardHandler(dashboardSvc, subjectConfigSvc)
	dashboardHandler.RegisterRoutes(r)

	// ── Templated endpoints (GET /, suggestions, JS files) ───────────────────
	templateHandler := handler.NewTemplateHandler(subjectConfigRepo, cfg)
	templateHandler.RegisterRoutes(r)

	// ── Sensitive data ────────────────────────────────────────────────────────
	sensitiveRepo := repository.NewSensitiveRepo(pool)
	sensitiveSvc := service.NewSensitiveService(sensitiveRepo, pool, cfg.Attachments.RawAllowedTypes)
	sensitiveHandler := handler.NewSensitiveHandler(sensitiveSvc, cfg.App.PythonStaticDir)
	sensitiveHandler.RegisterRoutes(r)

	// ── Artefacts ─────────────────────────────────────────────────────────────
	artefactRepo := repository.NewArtefactRepo(pool)
	artefactSvc := service.NewArtefactService(artefactRepo)
	artefactHandler := handler.NewArtefactHandler(artefactSvc)
	artefactHandler.RegisterRoutes(r)

	// ── Reference documents ───────────────────────────────────────────────────
	documentRepo := repository.NewDocumentRepo(pool)
	documentSvc := service.NewDocumentService(documentRepo)
	documentHandler := handler.NewDocumentHandler(documentSvc)
	documentHandler.RegisterRoutes(r)

	// ── Voices ────────────────────────────────────────────────────────────────
	voiceRepo := repository.NewVoiceRepo(pool)
	voiceSvc := service.NewVoiceService(voiceRepo, subjectConfigRepo, cfg.App.PythonStaticDir)
	voiceHandler := handler.NewVoiceHandler(voiceSvc)
	voiceHandler.RegisterRoutes(r)

	// ── Interests ─────────────────────────────────────────────────────────────
	interestRepo := repository.NewInterestRepo(pool)
	interestSvc := service.NewInterestService(interestRepo)
	interestHandler := handler.NewInterestHandler(interestSvc)
	interestHandler.RegisterRoutes(r)

	// ── Saved responses ───────────────────────────────────────────────────────
	savedResponseRepo := repository.NewSavedResponseRepo(pool)
	savedResponseSvc := service.NewSavedResponseService(savedResponseRepo)
	savedResponseHandler := handler.NewSavedResponseHandler(savedResponseSvc)
	savedResponseHandler.RegisterRoutes(r)

	// ── Configuration ─────────────────────────────────────────────────────────
	configRepo := repository.NewConfigRepo(pool)
	configSvc := service.NewConfigService(configRepo)
	configHandler := handler.NewConfigHandler(configSvc)
	configHandler.RegisterRoutes(r)

	// ── Contacts, email-matches, exclusions, classifications ──────────────────
	contactRepo := repository.NewContactRepo(pool)
	contactSvc := service.NewContactService(contactRepo)
	contactHandler := handler.NewContactHandler(contactSvc)
	contactHandler.RegisterRoutes(r)

	// ── Attachments ───────────────────────────────────────────────────────────
	attachmentRepo := repository.NewAttachmentRepo(pool)
	attachmentSvc := service.NewAttachmentService(attachmentRepo)
	attachmentHandler := handler.NewAttachmentHandler(attachmentSvc, cfg.App.PythonStaticDir)
	attachmentHandler.RegisterRoutes(r)

	// ── Import jobs ───────────────────────────────────────────────────────────
	importerHandler := handler.NewImporterHandler(handler.ImporterHandlerDeps{
		ExcludePatterns:   cfg.Filesystem.ExcludePatterns,
		ImageRepo:         imageRepo,
		Pool:              pool,
		SubjectConfigRepo: subjectConfigRepo,
	})
	importerHandler.RegisterRoutes(r)

	// ── Chat & AI ────────────────────────────────────────────────────────────
	geminiProvider := appai.NewGeminiProvider(cfg.AI.GeminiAPIKey, cfg.AI.GeminiModelName)
	emailSvc.WithGemini(geminiProvider)
	messageSvc.WithGemini(geminiProvider)

	// ── Admin & AI summarization ───────────────────────────────────────────────
	adminHandler := handler.NewAdminHandler(pool, subjectConfigRepo)
	adminHandler.WithGemini(geminiProvider)
	adminHandler.RegisterRoutes(r)
	claudeProvider := appai.NewClaudeProvider(cfg.AI.AnthropicAPIKey, cfg.AI.ClaudeModelName)
	chatRepo := repository.NewChatRepo(pool)
	completeProfileRepo := repository.NewCompleteProfileRepo(pool)
	chatSvc := service.NewChatService(
		chatRepo,
		subjectConfigRepo,
		pool,
		geminiProvider,
		claudeProvider,
		cfg.App.PythonStaticDir,
		cfg.AI.TavilyAPIKey,
	)
	chatHandler := handler.NewChatHandler(chatSvc, completeProfileRepo)
	chatHandler.RegisterRoutes(r)

	return r
}

func healthHandler(w http.ResponseWriter, r *http.Request) {
	w.Header().Set("Content-Type", "application/json")
	_ = json.NewEncoder(w).Encode(map[string]string{"status": "ok"})
}
