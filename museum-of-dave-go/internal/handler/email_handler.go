// Package handler contains HTTP request handlers.
package handler

import (
	"encoding/json"
	"fmt"
	"net/http"
	"strconv"
	"strings"

	"github.com/go-chi/chi/v5"
	"github.com/museum-of-dave/app/internal/model"
	"github.com/museum-of-dave/app/internal/service"
)

// EmailHandler handles all /emails/* read endpoints.
type EmailHandler struct {
	svc *service.EmailService
}

// NewEmailHandler creates an EmailHandler.
func NewEmailHandler(svc *service.EmailService) *EmailHandler {
	return &EmailHandler{svc: svc}
}

// RegisterRoutes mounts all email read routes onto r.
// Write/import routes (PUT, DELETE, POST /process) are registered in later phases.
func (h *EmailHandler) RegisterRoutes(r chi.Router) {
	// Specific sub-paths before the parameterised {email_id} routes to avoid shadowing
	r.Get("/emails/folders", h.GetFolders)
	r.Get("/emails/label", h.GetByLabel)
	r.Get("/emails/search", h.Search)

	r.Get("/emails/{email_id}/html", h.GetHTML)
	r.Get("/emails/{email_id}/text", h.GetText)
	r.Get("/emails/{email_id}/snippet", h.GetSnippet)
	r.Get("/emails/{email_id}/metadata", h.GetMetadata)
}

// ── Read endpoints ─────────────────────────────────────────────────────────────

// GetFolders is a placeholder until the Gmail client is ported in Phase 5.
func (h *EmailHandler) GetFolders(w http.ResponseWriter, r *http.Request) {
	writeError(w, http.StatusNotImplemented, "folder listing requires Gmail client (available in Phase 5)")
}

// GetByLabel handles GET /emails/label?labels=INBOX&labels=IMPORTANT
func (h *EmailHandler) GetByLabel(w http.ResponseWriter, r *http.Request) {
	labels := r.URL.Query()["labels"]
	if len(labels) == 0 {
		writeError(w, http.StatusBadRequest,
			"at least one label must be provided as query parameter (e.g., ?labels=INBOX&labels=IMPORTANT)")
		return
	}

	result, err := h.svc.GetByLabels(r.Context(), labels)
	if err != nil {
		writeError(w, http.StatusInternalServerError, fmt.Sprintf("error fetching emails: %s", err))
		return
	}
	writeJSON(w, result)
}

// Search handles GET /emails/search with optional query parameters.
func (h *EmailHandler) Search(w http.ResponseWriter, r *http.Request) {
	q := r.URL.Query()

	params := model.EmailSearchParams{}

	if v := q.Get("from_address"); v != "" {
		params.FromAddress = &v
	}
	if v := q.Get("to_address"); v != "" {
		params.ToAddress = &v
	}
	if v := q.Get("subject"); v != "" {
		params.Subject = &v
	}
	if v := q.Get("to_from"); v != "" {
		params.ToFrom = &v
	}
	if v := q.Get("month"); v != "" {
		m, err := strconv.Atoi(v)
		if err != nil || m < 1 || m > 12 {
			writeError(w, http.StatusBadRequest, "month must be an integer between 1 and 12")
			return
		}
		params.Month = &m
	}
	if v := q.Get("year"); v != "" {
		yr, err := strconv.Atoi(v)
		if err != nil {
			writeError(w, http.StatusBadRequest, "year must be an integer")
			return
		}
		params.Year = &yr
	}
	if v := q.Get("has_attachments"); v != "" {
		b, err := strconv.ParseBool(v)
		if err != nil {
			writeError(w, http.StatusBadRequest, "has_attachments must be true or false")
			return
		}
		params.HasAttachments = &b
	}

	result, err := h.svc.Search(r.Context(), params)
	if err != nil {
		writeError(w, http.StatusInternalServerError, fmt.Sprintf("error searching emails: %s", err))
		return
	}
	writeJSON(w, result)
}

// GetHTML handles GET /emails/{email_id}/html
// Returns the raw HTML message; falls back to plain_text wrapped in minimal HTML.
func (h *EmailHandler) GetHTML(w http.ResponseWriter, r *http.Request) {
	id, ok := parseEmailID(w, r)
	if !ok {
		return
	}

	email, err := h.svc.GetByID(r.Context(), id)
	if err != nil {
		writeError(w, http.StatusInternalServerError, fmt.Sprintf("error fetching email: %s", err))
		return
	}
	if email == nil {
		writeError(w, http.StatusNotFound, fmt.Sprintf("email with ID %d not found", id))
		return
	}

	if email.RawMessage != nil && *email.RawMessage != "" {
		w.Header().Set("Content-Type", "text/html; charset=utf-8")
		_, _ = w.Write([]byte(*email.RawMessage))
		return
	}

	if email.PlainText != nil && *email.PlainText != "" {
		html := fmt.Sprintf(`<!DOCTYPE html>
<html>
<head>
    <meta charset="utf-8">
    <style>
        body {
            font-family: Arial, sans-serif;
            line-height: 1.6;
            max-width: 800px;
            margin: 20px auto;
            padding: 20px;
            white-space: pre-wrap;
            word-wrap: break-word;
        }
    </style>
</head>
<body>
%s
</body>
</html>`, escapeHTML(*email.PlainText))
		w.Header().Set("Content-Type", "text/html; charset=utf-8")
		_, _ = w.Write([]byte(html))
		return
	}

	writeError(w, http.StatusNotFound, fmt.Sprintf("email with ID %d has no HTML or text content", id))
}

// GetText handles GET /emails/{email_id}/text
func (h *EmailHandler) GetText(w http.ResponseWriter, r *http.Request) {
	id, ok := parseEmailID(w, r)
	if !ok {
		return
	}

	email, err := h.svc.GetByID(r.Context(), id)
	if err != nil {
		writeError(w, http.StatusInternalServerError, fmt.Sprintf("error fetching email: %s", err))
		return
	}
	if email == nil {
		writeError(w, http.StatusNotFound, fmt.Sprintf("email with ID %d not found", id))
		return
	}
	if email.PlainText == nil || *email.PlainText == "" {
		writeError(w, http.StatusNotFound, fmt.Sprintf("email with ID %d has no text content", id))
		return
	}

	w.Header().Set("Content-Type", "text/plain; charset=utf-8")
	_, _ = w.Write([]byte(*email.PlainText))
}

// GetSnippet handles GET /emails/{email_id}/snippet
func (h *EmailHandler) GetSnippet(w http.ResponseWriter, r *http.Request) {
	id, ok := parseEmailID(w, r)
	if !ok {
		return
	}

	email, err := h.svc.GetByID(r.Context(), id)
	if err != nil {
		writeError(w, http.StatusInternalServerError, fmt.Sprintf("error fetching email: %s", err))
		return
	}
	if email == nil {
		writeError(w, http.StatusNotFound, fmt.Sprintf("email with ID %d not found", id))
		return
	}
	if email.Snippet == nil || *email.Snippet == "" {
		writeError(w, http.StatusNotFound, fmt.Sprintf("email with ID %d has no snippet", id))
		return
	}

	w.Header().Set("Content-Type", "text/plain; charset=utf-8")
	_, _ = w.Write([]byte(*email.Snippet))
}

// GetMetadata handles GET /emails/{email_id}/metadata
func (h *EmailHandler) GetMetadata(w http.ResponseWriter, r *http.Request) {
	id, ok := parseEmailID(w, r)
	if !ok {
		return
	}

	resp, err := h.svc.GetMetadata(r.Context(), id)
	if err != nil {
		writeError(w, http.StatusInternalServerError, fmt.Sprintf("error fetching email metadata: %s", err))
		return
	}
	if resp == nil {
		writeError(w, http.StatusNotFound, fmt.Sprintf("email with ID %d not found", id))
		return
	}
	writeJSON(w, resp)
}

// ── helpers ───────────────────────────────────────────────────────────────────

func parseEmailID(w http.ResponseWriter, r *http.Request) (int64, bool) {
	raw := chi.URLParam(r, "email_id")
	id, err := strconv.ParseInt(raw, 10, 64)
	if err != nil {
		writeError(w, http.StatusBadRequest, "email_id must be an integer")
		return 0, false
	}
	return id, true
}

func writeJSON(w http.ResponseWriter, v any) {
	w.Header().Set("Content-Type", "application/json")
	if err := json.NewEncoder(w).Encode(v); err != nil {
		// Header already sent — can't change status; log would happen via middleware
		_ = err
	}
}

func writeError(w http.ResponseWriter, status int, detail string) {
	w.Header().Set("Content-Type", "application/json")
	w.WriteHeader(status)
	_ = json.NewEncoder(w).Encode(map[string]string{"detail": detail})
}

// escapeHTML replaces the five HTML special characters.
// Used when wrapping plain_text inside an HTML body.
func escapeHTML(s string) string {
	s = strings.ReplaceAll(s, "&", "&amp;")
	s = strings.ReplaceAll(s, "<", "&lt;")
	s = strings.ReplaceAll(s, ">", "&gt;")
	s = strings.ReplaceAll(s, `"`, "&#34;")
	s = strings.ReplaceAll(s, "'", "&#39;")
	return s
}
