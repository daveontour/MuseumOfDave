// Package router wires all HTTP routes onto a chi.Mux.
package router

import (
	"encoding/json"
	"net/http"

	"github.com/go-chi/chi/v5"
	chimiddleware "github.com/go-chi/chi/v5/middleware"
	"github.com/jackc/pgx/v5/pgxpool"
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
	fs := http.FileServer(http.Dir("static"))
	r.Handle("/static/*", http.StripPrefix("/static/", fs))

	// ── Emails ─────────────────────────────────────────────────────────────────
	emailRepo := repository.NewEmailRepo(pool)
	emailSvc := service.NewEmailService(emailRepo)
	emailHandler := handler.NewEmailHandler(emailSvc)
	emailHandler.RegisterRoutes(r)

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

	return r
}

func healthHandler(w http.ResponseWriter, r *http.Request) {
	w.Header().Set("Content-Type", "application/json")
	_ = json.NewEncoder(w).Encode(map[string]string{"status": "ok"})
}
