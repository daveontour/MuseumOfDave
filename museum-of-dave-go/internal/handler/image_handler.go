package handler

import (
	"fmt"
	"net/http"
	"strconv"
	"strings"

	"github.com/go-chi/chi/v5"
	"github.com/museum-of-dave/app/internal/model"
	"github.com/museum-of-dave/app/internal/service"
)

// ImageHandler handles all /images/*, /getLocations, and /facebook/albums/* read endpoints.
type ImageHandler struct {
	svc *service.ImageService
}

// NewImageHandler creates an ImageHandler.
func NewImageHandler(svc *service.ImageService) *ImageHandler {
	return &ImageHandler{svc: svc}
}

// RegisterRoutes mounts all image read routes onto r.
// Write/delete routes are registered in Phase 4.
func (h *ImageHandler) RegisterRoutes(r chi.Router) {
	// Specific sub-paths must be registered before parameterised {image_id} routes.
	r.Get("/images/search", h.Search)
	r.Get("/images/years", h.GetYears)
	r.Get("/images/tags", h.GetTags)

	r.Get("/images/{image_id}/metadata", h.GetMetadata)
	r.Get("/images/{image_id}/thumbnail", h.GetThumbnail)
	r.Get("/images/{image_id}", h.GetContent)

	// Location map endpoint
	r.Get("/getLocations", h.GetLocations)

	// Facebook album read endpoints
	r.Get("/facebook/albums", h.GetFacebookAlbums)
	// Note: /facebook/albums/images/{id} must come before /facebook/albums/{album_id}/images
	// to avoid chi treating "images" as an album_id value.
	r.Get("/facebook/albums/images/{image_id}", h.GetAlbumImageContent)
	r.Get("/facebook/albums/{album_id}/images", h.GetAlbumImages)
}

// ── /images/search ────────────────────────────────────────────────────────────

func (h *ImageHandler) Search(w http.ResponseWriter, r *http.Request) {
	q := r.URL.Query()
	p := model.ImageSearchParams{}

	if v := q.Get("title"); v != "" {
		p.Title = &v
	}
	if v := q.Get("description"); v != "" {
		p.Description = &v
	}
	if v := q.Get("author"); v != "" {
		p.Author = &v
	}
	if v := q.Get("tags"); v != "" {
		p.Tags = &v
	}
	if v := q.Get("categories"); v != "" {
		p.Categories = &v
	}
	if v := q.Get("source"); v != "" {
		p.Source = &v
	}
	if v := q.Get("source_reference"); v != "" {
		p.SourceReference = &v
	}
	if v := q.Get("media_type"); v != "" {
		p.MediaType = &v
	}
	if v := q.Get("region"); v != "" {
		p.Region = &v
	}
	if v := q.Get("year"); v != "" {
		yr, err := strconv.Atoi(v)
		if err != nil {
			writeError(w, http.StatusBadRequest, "year must be an integer")
			return
		}
		p.Year = &yr
	}
	if v := q.Get("month"); v != "" {
		m, err := strconv.Atoi(v)
		if err != nil || m < 1 || m > 12 {
			writeError(w, http.StatusBadRequest, "month must be an integer between 1 and 12")
			return
		}
		p.Month = &m
	}
	if v := q.Get("rating"); v != "" {
		rt, err := strconv.Atoi(v)
		if err != nil || rt < 1 || rt > 5 {
			writeError(w, http.StatusBadRequest, "rating must be an integer between 1 and 5")
			return
		}
		p.Rating = &rt
	}
	if v := q.Get("rating_min"); v != "" {
		rt, err := strconv.Atoi(v)
		if err != nil || rt < 1 || rt > 5 {
			writeError(w, http.StatusBadRequest, "rating_min must be an integer between 1 and 5")
			return
		}
		p.RatingMin = &rt
	}
	if v := q.Get("rating_max"); v != "" {
		rt, err := strconv.Atoi(v)
		if err != nil || rt < 1 || rt > 5 {
			writeError(w, http.StatusBadRequest, "rating_max must be an integer between 1 and 5")
			return
		}
		p.RatingMax = &rt
	}
	if v := q.Get("has_gps"); v != "" {
		b, err := strconv.ParseBool(v)
		if err != nil {
			writeError(w, http.StatusBadRequest, "has_gps must be true or false")
			return
		}
		p.HasGPS = &b
	}
	if v := q.Get("available_for_task"); v != "" {
		b, err := strconv.ParseBool(v)
		if err != nil {
			writeError(w, http.StatusBadRequest, "available_for_task must be true or false")
			return
		}
		p.AvailableForTask = &b
	}
	if v := q.Get("processed"); v != "" {
		b, err := strconv.ParseBool(v)
		if err != nil {
			writeError(w, http.StatusBadRequest, "processed must be true or false")
			return
		}
		p.Processed = &b
	}

	result, err := h.svc.Search(r.Context(), p)
	if err != nil {
		writeError(w, http.StatusInternalServerError, fmt.Sprintf("error searching images: %s", err))
		return
	}
	writeJSON(w, result)
}

// ── /images/years ─────────────────────────────────────────────────────────────

func (h *ImageHandler) GetYears(w http.ResponseWriter, r *http.Request) {
	years, err := h.svc.GetDistinctYears(r.Context())
	if err != nil {
		writeError(w, http.StatusInternalServerError, fmt.Sprintf("error retrieving distinct years: %s", err))
		return
	}
	if years == nil {
		years = []int{}
	}
	writeJSON(w, map[string]any{"years": years})
}

// ── /images/tags ──────────────────────────────────────────────────────────────

func (h *ImageHandler) GetTags(w http.ResponseWriter, r *http.Request) {
	tags, err := h.svc.GetDistinctTags(r.Context())
	if err != nil {
		writeError(w, http.StatusInternalServerError, fmt.Sprintf("error retrieving distinct tags: %s", err))
		return
	}
	if tags == nil {
		tags = []string{}
	}
	writeJSON(w, map[string]any{"tags": tags})
}

// ── /getLocations ─────────────────────────────────────────────────────────────

func (h *ImageHandler) GetLocations(w http.ResponseWriter, r *http.Request) {
	locations, err := h.svc.GetLocations(r.Context())
	if err != nil {
		writeError(w, http.StatusInternalServerError, fmt.Sprintf("error retrieving locations: %s", err))
		return
	}
	if locations == nil {
		locations = []model.LocationItem{}
	}
	writeJSON(w, map[string]any{"locations": locations})
}

// ── /images/{image_id} ────────────────────────────────────────────────────────

// GetContent handles GET /images/{image_id}
// Query params:
//   - type: "blob" (default) | "metadata"
//   - preview: bool (default false) — returns thumbnail if true
//   - convert_heic_to_jpg: bool (default true) — accepted but HEIC conversion is not
//     implemented in Go; the image is returned as-is with its original content type.
func (h *ImageHandler) GetContent(w http.ResponseWriter, r *http.Request) {
	id, ok := parseImageID(w, r, "image_id")
	if !ok {
		return
	}

	idType := r.URL.Query().Get("type")
	if idType == "" {
		idType = "blob"
	}
	if idType != "blob" && idType != "metadata" {
		writeError(w, http.StatusBadRequest, `type must be "blob" or "metadata"`)
		return
	}

	preview := false
	if v := r.URL.Query().Get("preview"); v != "" {
		var err error
		preview, err = strconv.ParseBool(v)
		if err != nil {
			writeError(w, http.StatusBadRequest, "preview must be true or false")
			return
		}
	}

	h.serveImageContent(w, r, id, idType, preview)
}

// GetThumbnail handles GET /images/{image_id}/thumbnail — convenience alias for ?preview=true.
func (h *ImageHandler) GetThumbnail(w http.ResponseWriter, r *http.Request) {
	id, ok := parseImageID(w, r, "image_id")
	if !ok {
		return
	}
	h.serveImageContent(w, r, id, "metadata", true)
}

// GetMetadata handles GET /images/{image_id}/metadata
func (h *ImageHandler) GetMetadata(w http.ResponseWriter, r *http.Request) {
	id, ok := parseImageID(w, r, "image_id")
	if !ok {
		return
	}

	resp, err := h.svc.GetMetadata(r.Context(), id)
	if err != nil {
		writeError(w, http.StatusInternalServerError, fmt.Sprintf("error retrieving image metadata: %s", err))
		return
	}
	if resp == nil {
		writeError(w, http.StatusNotFound, fmt.Sprintf("image with ID %d not found", id))
		return
	}
	writeJSON(w, resp)
}

// ── /facebook/albums/* ────────────────────────────────────────────────────────

func (h *ImageHandler) GetFacebookAlbums(w http.ResponseWriter, r *http.Request) {
	albums, err := h.svc.GetFacebookAlbums(r.Context())
	if err != nil {
		writeError(w, http.StatusInternalServerError, fmt.Sprintf("error retrieving albums: %s", err))
		return
	}
	writeJSON(w, albums)
}

func (h *ImageHandler) GetAlbumImages(w http.ResponseWriter, r *http.Request) {
	albumID, ok := parseImageID(w, r, "album_id")
	if !ok {
		return
	}

	images, err := h.svc.GetAlbumImages(r.Context(), albumID)
	if err != nil {
		writeError(w, http.StatusInternalServerError, fmt.Sprintf("error retrieving album images: %s", err))
		return
	}
	writeJSON(w, images)
}

func (h *ImageHandler) GetAlbumImageContent(w http.ResponseWriter, r *http.Request) {
	id, ok := parseImageID(w, r, "image_id")
	if !ok {
		return
	}

	content, err := h.svc.GetAlbumImageContent(r.Context(), id)
	if err != nil {
		if strings.Contains(err.Error(), "no image data") {
			writeError(w, http.StatusNotFound, fmt.Sprintf("image with ID %d has no image data", id))
			return
		}
		writeError(w, http.StatusInternalServerError, fmt.Sprintf("error retrieving image: %s", err))
		return
	}
	if content == nil {
		writeError(w, http.StatusNotFound, fmt.Sprintf("image with ID %d not found or not linked to an album", id))
		return
	}

	serveBinaryContent(w, content)
}

// ── helpers ───────────────────────────────────────────────────────────────────

func (h *ImageHandler) serveImageContent(w http.ResponseWriter, r *http.Request, id int64, idType string, preview bool) {
	content, err := h.svc.GetImageContent(r.Context(), id, idType, preview)
	if err != nil {
		msg := err.Error()
		if strings.Contains(msg, "no thumbnail") {
			writeError(w, http.StatusNotFound, fmt.Sprintf("image with ID %d has no thumbnail available", id))
			return
		}
		if strings.Contains(msg, "no image data") || strings.Contains(msg, "not found") {
			writeError(w, http.StatusNotFound, fmt.Sprintf("image with ID %d not found or has no data", id))
			return
		}
		writeError(w, http.StatusInternalServerError, fmt.Sprintf("error retrieving image: %s", err))
		return
	}
	if content == nil {
		writeError(w, http.StatusNotFound, fmt.Sprintf("image with ID %d not found", id))
		return
	}
	serveBinaryContent(w, content)
}

func serveBinaryContent(w http.ResponseWriter, c *model.ImageContent) {
	w.Header().Set("Content-Type", c.ContentType)
	if c.Filename != "" {
		safe := strings.ReplaceAll(c.Filename, `"`, `\"`)
		w.Header().Set("Content-Disposition", fmt.Sprintf(`inline; filename="%s"`, safe))
	}
	_, _ = w.Write(c.Data)
}

func parseImageID(w http.ResponseWriter, r *http.Request, param string) (int64, bool) {
	raw := chi.URLParam(r, param)
	id, err := strconv.ParseInt(raw, 10, 64)
	if err != nil {
		writeError(w, http.StatusBadRequest, param+" must be an integer")
		return 0, false
	}
	return id, true
}
