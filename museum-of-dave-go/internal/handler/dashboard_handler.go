package handler

import (
	"fmt"
	"net/http"

	"github.com/go-chi/chi/v5"
	"github.com/museum-of-dave/app/internal/service"
)

// DashboardHandler handles GET /api/dashboard and GET /api/subject-configuration.
type DashboardHandler struct {
	dashSvc    *service.DashboardService
	subjectSvc *service.SubjectConfigService
}

// NewDashboardHandler creates a DashboardHandler.
func NewDashboardHandler(dashSvc *service.DashboardService, subjectSvc *service.SubjectConfigService) *DashboardHandler {
	return &DashboardHandler{dashSvc: dashSvc, subjectSvc: subjectSvc}
}

// RegisterRoutes mounts the dashboard and subject-configuration read routes.
func (h *DashboardHandler) RegisterRoutes(r chi.Router) {
	r.Get("/api/dashboard", h.GetDashboard)
	r.Get("/api/subject-configuration", h.GetSubjectConfiguration)
}

// GetDashboard handles GET /api/dashboard.
func (h *DashboardHandler) GetDashboard(w http.ResponseWriter, r *http.Request) {
	resp, err := h.dashSvc.GetDashboard(r.Context())
	if err != nil {
		writeError(w, http.StatusInternalServerError, fmt.Sprintf("error retrieving dashboard: %s", err))
		return
	}
	writeJSON(w, resp)
}

// GetSubjectConfiguration handles GET /api/subject-configuration.
func (h *DashboardHandler) GetSubjectConfiguration(w http.ResponseWriter, r *http.Request) {
	resp, err := h.subjectSvc.GetConfiguration(r.Context())
	if err != nil {
		writeError(w, http.StatusInternalServerError, fmt.Sprintf("error retrieving subject configuration: %s", err))
		return
	}
	if resp == nil {
		writeError(w, http.StatusNotFound, "subject configuration not found")
		return
	}
	writeJSON(w, resp)
}
