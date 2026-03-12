package handler

import (
	"encoding/json"
	"fmt"
	"io"
	"net/http"
	"strconv"
	"strings"

	"github.com/daveontour/digitalmuseum/internal/service"
	"github.com/go-chi/chi/v5"
)

// DocumentHandler handles all /reference-documents/* endpoints.
type DocumentHandler struct {
	svc *service.DocumentService
}

// NewDocumentHandler creates a DocumentHandler.
func NewDocumentHandler(svc *service.DocumentService) *DocumentHandler {
	return &DocumentHandler{svc: svc}
}

// RegisterRoutes mounts all reference document routes.
func (h *DocumentHandler) RegisterRoutes(r chi.Router) {
	r.Get("/reference-documents", h.List)
	r.Post("/reference-documents", h.Create)
	r.Get("/reference-documents/{doc_id}", h.GetByID)
	r.Put("/reference-documents/{doc_id}", h.Update)
	r.Delete("/reference-documents/{doc_id}", h.Delete)
	r.Get("/reference-documents/{doc_id}/download", h.Download)
}

// ── helpers ───────────────────────────────────────────────────────────────────

func parseDocID(w http.ResponseWriter, r *http.Request) (int64, bool) {
	raw := chi.URLParam(r, "doc_id")
	id, err := strconv.ParseInt(raw, 10, 64)
	if err != nil {
		writeError(w, http.StatusBadRequest, "doc_id must be an integer")
		return 0, false
	}
	return id, true
}

type docJSON struct {
	ID               int64   `json:"id"`
	Filename         string  `json:"filename"`
	Title            *string `json:"title"`
	Description      *string `json:"description"`
	Author           *string `json:"author"`
	ContentType      string  `json:"content_type"`
	Size             int64   `json:"size"`
	Tags             *string `json:"tags"`
	Categories       *string `json:"categories"`
	Notes            *string `json:"notes"`
	AvailableForTask bool    `json:"available_for_task"`
	CreatedAt        string  `json:"created_at"`
	UpdatedAt        string  `json:"updated_at"`
}

// ── List ──────────────────────────────────────────────────────────────────────

func (h *DocumentHandler) List(w http.ResponseWriter, r *http.Request) {
	q := r.URL.Query()
	search := q.Get("search")
	category := q.Get("category")
	tag := q.Get("tag")
	contentType := q.Get("content_type")
	var availableForTask *bool
	if v := q.Get("available_for_task"); v != "" {
		b, err := strconv.ParseBool(v)
		if err != nil {
			writeError(w, http.StatusBadRequest, "available_for_task must be true or false")
			return
		}
		availableForTask = &b
	}

	docs, err := h.svc.List(r.Context(), search, category, tag, contentType, availableForTask)
	if err != nil {
		writeError(w, http.StatusInternalServerError, fmt.Sprintf("error listing documents: %s", err))
		return
	}

	out := make([]docJSON, 0, len(docs))
	for _, d := range docs {
		out = append(out, docJSON{
			ID: d.ID, Filename: d.Filename, Title: d.Title, Description: d.Description,
			Author: d.Author, ContentType: d.ContentType, Size: d.Size, Tags: d.Tags,
			Categories: d.Categories, Notes: d.Notes, AvailableForTask: d.AvailableForTask,
			CreatedAt: d.CreatedAt.Format("2006-01-02T15:04:05.999999"),
			UpdatedAt: d.UpdatedAt.Format("2006-01-02T15:04:05.999999"),
		})
	}
	writeJSON(w, out)
}

// ── GetByID ───────────────────────────────────────────────────────────────────

func (h *DocumentHandler) GetByID(w http.ResponseWriter, r *http.Request) {
	id, ok := parseDocID(w, r)
	if !ok {
		return
	}
	d, err := h.svc.GetByID(r.Context(), id)
	if err != nil {
		writeError(w, http.StatusInternalServerError, fmt.Sprintf("error retrieving document: %s", err))
		return
	}
	if d == nil {
		writeError(w, http.StatusNotFound, fmt.Sprintf("reference document with ID %d not found", id))
		return
	}
	writeJSON(w, docJSON{
		ID: d.ID, Filename: d.Filename, Title: d.Title, Description: d.Description,
		Author: d.Author, ContentType: d.ContentType, Size: d.Size, Tags: d.Tags,
		Categories: d.Categories, Notes: d.Notes, AvailableForTask: d.AvailableForTask,
		CreatedAt: d.CreatedAt.Format("2006-01-02T15:04:05.999999"),
		UpdatedAt: d.UpdatedAt.Format("2006-01-02T15:04:05.999999"),
	})
}

// ── Download ──────────────────────────────────────────────────────────────────

func (h *DocumentHandler) Download(w http.ResponseWriter, r *http.Request) {
	id, ok := parseDocID(w, r)
	if !ok {
		return
	}
	d, err := h.svc.GetByID(r.Context(), id)
	if err != nil {
		writeError(w, http.StatusInternalServerError, fmt.Sprintf("error retrieving document: %s", err))
		return
	}
	if d == nil {
		writeError(w, http.StatusNotFound, fmt.Sprintf("reference document with ID %d not found", id))
		return
	}
	data, err := h.svc.GetData(r.Context(), id)
	if err != nil {
		writeError(w, http.StatusInternalServerError, fmt.Sprintf("error retrieving document data: %s", err))
		return
	}
	if len(data) == 0 {
		writeError(w, http.StatusNotFound, fmt.Sprintf("reference document with ID %d has no file data", id))
		return
	}
	filename := d.Filename
	if filename == "" {
		filename = "document"
	}
	ct := d.ContentType
	if ct == "" {
		ct = "application/octet-stream"
	}
	safe := strings.ReplaceAll(filename, `"`, `\"`)
	w.Header().Set("Content-Type", ct)
	w.Header().Set("Content-Disposition", fmt.Sprintf(`inline; filename="%s"`, safe))
	_, _ = w.Write(data)
}

// ── Create ────────────────────────────────────────────────────────────────────

func (h *DocumentHandler) Create(w http.ResponseWriter, r *http.Request) {
	if err := r.ParseMultipartForm(64 << 20); err != nil {
		writeError(w, http.StatusBadRequest, "could not parse multipart form")
		return
	}
	f, fh, err := r.FormFile("file")
	if err != nil {
		writeError(w, http.StatusBadRequest, "file field is required")
		return
	}
	defer f.Close()

	data, err := io.ReadAll(f)
	if err != nil {
		writeError(w, http.StatusInternalServerError, "could not read uploaded file")
		return
	}
	if len(data) == 0 {
		writeError(w, http.StatusBadRequest, "uploaded file is empty")
		return
	}

	ct := fh.Header.Get("Content-Type")
	if ct == "" {
		ct = "application/octet-stream"
	}

	availableForTask := false
	if v := r.FormValue("available_for_task"); v != "" {
		availableForTask, _ = strconv.ParseBool(v)
	}

	optForm := func(key string) *string {
		if v := r.FormValue(key); v != "" {
			return &v
		}
		return nil
	}

	d, err := h.svc.Create(r.Context(),
		fh.Filename, ct, int64(len(data)), data,
		optForm("title"), optForm("description"), optForm("author"),
		optForm("tags"), optForm("categories"), optForm("notes"),
		availableForTask,
	)
	if err != nil {
		writeError(w, http.StatusInternalServerError, fmt.Sprintf("error creating document: %s", err))
		return
	}
	w.WriteHeader(http.StatusCreated)
	writeJSON(w, docJSON{
		ID: d.ID, Filename: d.Filename, Title: d.Title, Description: d.Description,
		Author: d.Author, ContentType: d.ContentType, Size: d.Size, Tags: d.Tags,
		Categories: d.Categories, Notes: d.Notes, AvailableForTask: d.AvailableForTask,
		CreatedAt: d.CreatedAt.Format("2006-01-02T15:04:05.999999"),
		UpdatedAt: d.UpdatedAt.Format("2006-01-02T15:04:05.999999"),
	})
}

// ── Update ────────────────────────────────────────────────────────────────────

func (h *DocumentHandler) Update(w http.ResponseWriter, r *http.Request) {
	id, ok := parseDocID(w, r)
	if !ok {
		return
	}
	var req struct {
		Title            *string `json:"title"`
		Description      *string `json:"description"`
		Author           *string `json:"author"`
		Tags             *string `json:"tags"`
		Categories       *string `json:"categories"`
		Notes            *string `json:"notes"`
		AvailableForTask *bool   `json:"available_for_task"`
	}
	if err := json.NewDecoder(r.Body).Decode(&req); err != nil {
		writeError(w, http.StatusBadRequest, "invalid JSON body")
		return
	}

	d, err := h.svc.Update(r.Context(), id,
		req.Title, req.Description, req.Author, req.Tags, req.Categories, req.Notes, req.AvailableForTask)
	if err != nil {
		writeError(w, http.StatusInternalServerError, fmt.Sprintf("error updating document: %s", err))
		return
	}
	if d == nil {
		writeError(w, http.StatusNotFound, fmt.Sprintf("reference document with ID %d not found", id))
		return
	}
	writeJSON(w, docJSON{
		ID: d.ID, Filename: d.Filename, Title: d.Title, Description: d.Description,
		Author: d.Author, ContentType: d.ContentType, Size: d.Size, Tags: d.Tags,
		Categories: d.Categories, Notes: d.Notes, AvailableForTask: d.AvailableForTask,
		CreatedAt: d.CreatedAt.Format("2006-01-02T15:04:05.999999"),
		UpdatedAt: d.UpdatedAt.Format("2006-01-02T15:04:05.999999"),
	})
}

// ── Delete ────────────────────────────────────────────────────────────────────

func (h *DocumentHandler) Delete(w http.ResponseWriter, r *http.Request) {
	id, ok := parseDocID(w, r)
	if !ok {
		return
	}
	d, err := h.svc.GetByID(r.Context(), id)
	if err != nil {
		writeError(w, http.StatusInternalServerError, fmt.Sprintf("error retrieving document: %s", err))
		return
	}
	if d == nil {
		writeError(w, http.StatusNotFound, fmt.Sprintf("reference document with ID %d not found", id))
		return
	}
	if err := h.svc.Delete(r.Context(), id); err != nil {
		writeError(w, http.StatusInternalServerError, fmt.Sprintf("error deleting document: %s", err))
		return
	}
	writeJSON(w, map[string]string{"message": fmt.Sprintf("Reference document %d deleted successfully", id)})
}
