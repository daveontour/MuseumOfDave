package handler

import (
	"encoding/json"
	"fmt"
	"net/http"
	"os"
	"regexp"
	"strconv"
	"strings"

	"github.com/go-chi/chi/v5"
	"github.com/museum-of-dave/app/internal/importer"
)

// ── Job singletons ────────────────────────────────────────────────────────────

var (
	whatsappJob = importer.NewImportJob("WhatsApp import", map[string]any{
		"status": "idle", "status_line": nil, "error_message": nil,
		"conversations": 0, "messages_imported": 0, "messages_created": 0,
		"messages_updated": 0, "attachments_found": 0, "attachments_missing": 0,
		"missing_attachment_filenames": []string{}, "errors": 0,
	})

	imessageJob = importer.NewImportJob("iMessage import", map[string]any{
		"status": "idle", "status_line": nil, "error_message": nil,
		"conversations": 0, "messages_imported": 0, "messages_created": 0,
		"messages_updated": 0, "attachments_found": 0, "attachments_missing": 0,
		"missing_attachment_filenames": []string{}, "errors": 0,
	})

	instagramJob = importer.NewImportJob("Instagram import", map[string]any{
		"status": "idle", "status_line": nil, "error_message": nil,
		"conversations": 0, "messages_imported": 0, "messages_created": 0,
		"messages_updated": 0, "errors": 0,
	})

	emailProcessJob = importer.NewImportJob("Email (Gmail) import", map[string]any{
		"status": "idle", "status_line": nil, "error_message": nil,
		"emails_processed": 0, "current_label": nil, "total_labels": 0,
	})

	facebookMessengerJob = importer.NewImportJob("Facebook Messenger import", map[string]any{
		"status": "idle", "status_line": nil, "error_message": nil,
		"conversations": 0, "messages_imported": 0, "messages_created": 0,
		"messages_updated": 0, "attachments_found": 0, "attachments_missing": 0,
		"missing_attachment_filenames": []string{}, "errors": 0,
	})

	filesystemJob = importer.NewImportJob("Filesystem images import", map[string]any{
		"status": "idle", "status_line": nil, "current_file": nil,
		"files_processed": 0, "total_files": 0, "images_imported": 0,
		"images_referenced": 0, "images_updated": 0,
		"errors": 0, "error_messages": []string{},
	})

	facebookAlbumsJob = importer.NewImportJob("Facebook Albums import", map[string]any{
		"status": "idle", "status_line": nil, "current_album": nil,
		"albums_processed": 0, "total_albums": 0, "albums_imported": 0,
		"images_imported": 0, "images_found": 0, "images_missing": 0,
		"missing_image_filenames": []string{},
		"errors": 0, "error_message": nil,
	})

	facebookPostsJob = importer.NewImportJob("Facebook Posts import", map[string]any{
		"status": "idle", "status_line": nil, "error_message": nil,
		"posts_processed": 0, "posts_imported": 0, "posts_updated": 0,
		"with_media": 0, "images_imported": 0, "images_found": 0,
		"images_missing": 0, "errors": 0,
	})

	facebookPlacesJob = importer.NewImportJob("Facebook Places import", map[string]any{
		"status": "idle", "status_line": nil, "error_message": nil,
		"places_imported": 0, "places_created": 0, "places_updated": 0,
	})

	facebookAllJob = importer.NewImportJob("Facebook All import", map[string]any{
		"status": "idle", "status_line": nil, "error_message": nil,
		"conversations": 0, "messages_imported": 0, "messages_created": 0,
		"messages_updated": 0, "att_found": 0, "att_missing": 0, "messenger_errors": 0,
		"albums_processed": 0, "albums_imported": 0, "album_images_imported": 0,
		"album_images_found": 0, "album_images_missing": 0, "albums_errors": 0,
		"places_imported": 0, "places_created": 0, "places_updated": 0,
		"posts_processed": 0, "posts_imported": 0, "posts_updated": 0,
		"with_media": 0, "images_imported": 0, "images_found": 0,
		"images_missing": 0, "posts_errors": 0,
	})

	thumbnailsJob = importer.NewImportJob("Thumbnail processing", map[string]any{
		"status": "idle", "status_line": nil, "error_message": nil,
		"phase": nil, "phase1_scanned": 0, "phase1_updated": 0,
		"phase2_scanned": 0, "phase2_total": 0,
		"phase2_processed": 0, "phase2_errors": 0,
	})

	contactsExtractJob = importer.NewImportJob("Contacts extract", map[string]any{
		"status": "idle", "status_line": nil, "error_message": nil,
		"contacts_processed": 0, "contacts_merged": 0, "contacts_created": 0,
	})
)

// ── ImporterHandler ───────────────────────────────────────────────────────────

// ImporterHandler handles all import job HTTP endpoints.
type ImporterHandler struct {
	excludePatterns []string // from config
}

// NewImporterHandler creates an ImporterHandler.
func NewImporterHandler(excludePatterns []string) *ImporterHandler {
	return &ImporterHandler{excludePatterns: excludePatterns}
}

// RegisterRoutes mounts all import job routes.
func (h *ImporterHandler) RegisterRoutes(r chi.Router) {
	// Filesystem
	r.Post("/images/import", h.FilesystemStart)
	r.Get("/images/import/stream", h.FilesystemStream)
	r.Post("/images/import/cancel", h.FilesystemCancel)
	r.Get("/images/import/status", h.FilesystemStatus)

	// Thumbnails
	r.Post("/images/process-thumbnails", h.ThumbnailsStart)
	r.Post("/images/process-thumbnails/async", h.ThumbnailsStart) // same handler
	r.Get("/images/process-thumbnails/stream", h.ThumbnailsStream)
	r.Post("/images/process-thumbnails/cancel", h.ThumbnailsCancel)
	r.Get("/images/process-thumbnails/status", h.ThumbnailsStatus)

	// Facebook Albums
	r.Post("/facebook/albums/import", h.FacebookAlbumsStart)
	r.Get("/facebook/albums/import/stream", h.FacebookAlbumsStream)
	r.Post("/facebook/albums/import/cancel", h.FacebookAlbumsCancel)
	r.Get("/facebook/albums/import/status", h.FacebookAlbumsStatus)

	// Facebook Posts
	r.Post("/facebook/posts/import", h.FacebookPostsStart)
	r.Get("/facebook/posts/import/stream", h.FacebookPostsStream)
	r.Post("/facebook/posts/import/cancel", h.FacebookPostsCancel)
	r.Get("/facebook/posts/import/status", h.FacebookPostsStatus)

	// Facebook Places
	r.Post("/facebook/import-places", h.FacebookPlacesStart)
	r.Get("/facebook/import-places/stream", h.FacebookPlacesStream)
	r.Post("/facebook/import-places/cancel", h.FacebookPlacesCancel)
	r.Get("/facebook/import-places/status", h.FacebookPlacesStatus)

	// Facebook All
	r.Post("/facebook/all/import", h.FacebookAllStart)
	r.Get("/facebook/all/import/stream", h.FacebookAllStream)
	r.Post("/facebook/all/import/cancel", h.FacebookAllCancel)
	r.Get("/facebook/all/import/status", h.FacebookAllStatus)

	// Contacts extract
	r.Post("/contacts/extract", h.ContactsExtractStart)
	r.Get("/contacts/extract/stream", h.ContactsExtractStream)
	r.Post("/contacts/extract/cancel", h.ContactsExtractCancel)
	r.Get("/contacts/extract/status", h.ContactsExtractStatus)

	// WhatsApp
	r.Post("/whatsapp/import", h.WhatsAppStart)
	r.Get("/whatsapp/import/stream", h.WhatsAppStream)
	r.Post("/whatsapp/import/cancel", h.WhatsAppCancel)
	r.Get("/whatsapp/import/status", h.WhatsAppStatus)

	// iMessage
	r.Post("/imessages/import", h.IMessageStart)
	r.Get("/imessages/import/stream", h.IMessageStream)
	r.Post("/imessages/import/cancel", h.IMessageCancel)
	r.Get("/imessages/import/status", h.IMessageStatus)

	// Instagram
	r.Post("/instagram/import", h.InstagramStart)
	r.Get("/instagram/import/stream", h.InstagramStream)
	r.Post("/instagram/import/cancel", h.InstagramCancel)
	r.Get("/instagram/import/status", h.InstagramStatus)

	// Facebook Messenger (standalone)
	r.Post("/facebook/import", h.FacebookMessengerStart)
	r.Get("/facebook/import/stream", h.FacebookMessengerStream)
	r.Post("/facebook/import/cancel", h.FacebookMessengerCancel)
	r.Get("/facebook/import/status", h.FacebookMessengerStatus)

	// Email (Gmail) process — stub: Gmail OAuth is not implemented in Go; use /imap/process
	r.Post("/emails/process", h.EmailProcessStart)
	r.Get("/emails/process/stream", h.EmailProcessStream)
	r.Post("/emails/process/cancel", h.EmailProcessCancel)
	r.Get("/emails/process/status", h.EmailProcessStatus)
}

// ── Helpers ───────────────────────────────────────────────────────────────────

func dirExists(path string) bool {
	info, err := os.Stat(path)
	return err == nil && info.IsDir()
}

func runJob(job *importer.ImportJob, args []string, onComplete func(stdout string)) {
	go func() {
		stdout, rc, err := importer.RunSubprocess(job, args)
		if err != nil || job.IsCancelled() {
			if job.IsCancelled() {
				job.UpdateState(map[string]any{"status": "cancelled", "status_line": "Import cancelled."})
				job.Broadcast("cancelled", job.GetState())
			} else {
				msg := fmt.Sprintf("subprocess error: %s", err)
				job.UpdateState(map[string]any{"status": "error", "status_line": msg, "error_message": msg})
				job.Broadcast("error", job.GetState())
			}
		} else if rc != 0 {
			msg := strings.TrimSpace(stdout)
			if msg == "" {
				msg = fmt.Sprintf("process exited with code %d", rc)
			}
			job.UpdateState(map[string]any{"status": "error", "status_line": msg, "error_message": msg})
			job.Broadcast("error", job.GetState())
		} else {
			onComplete(stdout)
		}
		job.Finish()
	}()
}

// ── Filesystem ────────────────────────────────────────────────────────────────

func (h *ImporterHandler) FilesystemStart(w http.ResponseWriter, r *http.Request) {
	if err := filesystemJob.AssertNotRunning(); err != nil {
		writeError(w, http.StatusBadRequest, err.Error())
		return
	}

	var req struct {
		RootDirectory string `json:"root_directory"`
		MaxImages     *int   `json:"max_images"`
		ReferenceMode bool   `json:"reference_mode"`
	}
	if err := json.NewDecoder(r.Body).Decode(&req); err != nil {
		writeError(w, http.StatusBadRequest, "invalid JSON body")
		return
	}

	paths := strings.Split(req.RootDirectory, ";")
	var validPaths []string
	var invalidPaths []string
	for _, p := range paths {
		p = strings.TrimSpace(p)
		if p == "" {
			continue
		}
		if dirExists(p) {
			validPaths = append(validPaths, p)
		} else {
			invalidPaths = append(invalidPaths, p)
		}
	}
	if len(invalidPaths) > 0 {
		writeError(w, http.StatusBadRequest, fmt.Sprintf("directory does not exist: %s", strings.Join(invalidPaths, ", ")))
		return
	}
	if len(validPaths) == 0 {
		writeError(w, http.StatusBadRequest, "at least one directory path is required")
		return
	}

	filesystemJob.Start()
	filesystemJob.UpdateState(map[string]any{
		"status": "in_progress", "status_line": "Starting import-processor...",
		"current_file": nil, "files_processed": 0, "total_files": 0,
		"images_imported": 0, "images_referenced": 0, "images_updated": 0,
		"errors": 0, "error_messages": []string{},
	})
	filesystemJob.Broadcast("status", map[string]any{"status_line": "Starting import-processor..."})

	args := []string{"filesystem"}
	for _, p := range validPaths {
		args = append(args, "--path", p)
	}
	for _, pat := range h.excludePatterns {
		args = append(args, "--exclude", pat)
	}
	if req.MaxImages != nil && *req.MaxImages > 0 {
		args = append(args, "--max", strconv.Itoa(*req.MaxImages))
	}
	if req.ReferenceMode {
		args = append(args, "--reference")
	}

	runJob(filesystemJob, args, func(stdout string) {
		total, processed, imp, ref, upd, errs, errMsgs, msg := parseFilesystemStdout(stdout)
		filesystemJob.UpdateState(map[string]any{
			"status": "completed", "status_line": msg,
			"total_files": total, "files_processed": processed,
			"images_imported": imp, "images_referenced": ref,
			"images_updated": upd, "errors": errs, "error_messages": errMsgs,
		})
		filesystemJob.Broadcast("completed", filesystemJob.GetState())
	})

	writeJSON(w, map[string]any{
		"message": "Filesystem images import started",
		"root_directory": req.RootDirectory,
	})
}

func (h *ImporterHandler) FilesystemStream(w http.ResponseWriter, r *http.Request) {
	filesystemJob.ServeSSE(w, r)
}
func (h *ImporterHandler) FilesystemCancel(w http.ResponseWriter, r *http.Request) {
	writeJSON(w, filesystemJob.Cancel())
}
func (h *ImporterHandler) FilesystemStatus(w http.ResponseWriter, r *http.Request) {
	writeJSON(w, filesystemJob.Status())
}

// ── Thumbnails ────────────────────────────────────────────────────────────────

func (h *ImporterHandler) ThumbnailsStart(w http.ResponseWriter, r *http.Request) {
	if err := thumbnailsJob.AssertNotRunning(); err != nil {
		writeError(w, http.StatusBadRequest, err.Error())
		return
	}

	reprocess := r.URL.Query().Get("reprocess") == "true" || r.URL.Query().Get("reprocess") == "1"

	thumbnailsJob.Start()
	thumbnailsJob.UpdateState(map[string]any{
		"status": "in_progress", "status_line": "Starting import-processor...",
		"phase": nil, "phase1_scanned": 0, "phase1_updated": 0,
		"phase2_scanned": 0, "phase2_total": 0, "phase2_processed": 0, "phase2_errors": 0,
	})
	thumbnailsJob.Broadcast("status", map[string]any{"status_line": "Starting import-processor..."})

	args := []string{"thumbnails"}
	if reprocess {
		args = append(args, "--reprocess")
	}

	runJob(thumbnailsJob, args, func(stdout string) {
		total, processed, errs, msg := parseThumbnailsStdout(stdout)
		thumbnailsJob.UpdateState(map[string]any{
			"status": "completed", "status_line": msg,
			"phase2_total": total, "phase2_processed": processed, "phase2_errors": errs,
		})
		thumbnailsJob.Broadcast("completed", thumbnailsJob.GetState())
	})

	writeJSON(w, map[string]any{"message": "Thumbnail processing started", "status": "started"})
}

func (h *ImporterHandler) ThumbnailsStream(w http.ResponseWriter, r *http.Request) {
	thumbnailsJob.ServeSSE(w, r)
}
func (h *ImporterHandler) ThumbnailsCancel(w http.ResponseWriter, r *http.Request) {
	writeJSON(w, thumbnailsJob.Cancel())
}
func (h *ImporterHandler) ThumbnailsStatus(w http.ResponseWriter, r *http.Request) {
	writeJSON(w, thumbnailsJob.Status())
}

// ── Facebook Albums ───────────────────────────────────────────────────────────

func (h *ImporterHandler) FacebookAlbumsStart(w http.ResponseWriter, r *http.Request) {
	if err := facebookAlbumsJob.AssertNotRunning(); err != nil {
		writeError(w, http.StatusBadRequest, err.Error())
		return
	}
	var req struct {
		DirectoryPath string `json:"directory_path"`
	}
	if err := json.NewDecoder(r.Body).Decode(&req); err != nil {
		writeError(w, http.StatusBadRequest, "invalid JSON body")
		return
	}
	if !dirExists(req.DirectoryPath) {
		writeError(w, http.StatusBadRequest, fmt.Sprintf("directory does not exist: %s", req.DirectoryPath))
		return
	}

	facebookAlbumsJob.Start()
	facebookAlbumsJob.UpdateState(map[string]any{
		"status": "in_progress", "status_line": "Starting import-processor...",
		"albums_processed": 0, "total_albums": 0, "albums_imported": 0,
		"images_imported": 0, "images_found": 0, "images_missing": 0,
		"missing_image_filenames": []string{}, "errors": 0,
	})
	facebookAlbumsJob.Broadcast("status", map[string]any{"status_line": "Starting import-processor..."})

	runJob(facebookAlbumsJob, []string{"facebook-albums", "--path", req.DirectoryPath}, func(stdout string) {
		ap, ai, ii, ifound, imiss, errs, missing, msg := parseFacebookAlbumsStdout(stdout)
		facebookAlbumsJob.UpdateState(map[string]any{
			"status": "completed", "status_line": msg,
			"albums_processed": ap, "total_albums": ap, "albums_imported": ai,
			"images_imported": ii, "images_found": ifound, "images_missing": imiss,
			"missing_image_filenames": missing, "errors": errs,
		})
		facebookAlbumsJob.Broadcast("completed", facebookAlbumsJob.GetState())
	})

	writeJSON(w, map[string]any{"message": "Facebook Albums import started", "directory_path": req.DirectoryPath})
}

func (h *ImporterHandler) FacebookAlbumsStream(w http.ResponseWriter, r *http.Request) {
	facebookAlbumsJob.ServeSSE(w, r)
}
func (h *ImporterHandler) FacebookAlbumsCancel(w http.ResponseWriter, r *http.Request) {
	writeJSON(w, facebookAlbumsJob.Cancel())
}
func (h *ImporterHandler) FacebookAlbumsStatus(w http.ResponseWriter, r *http.Request) {
	writeJSON(w, facebookAlbumsJob.Status())
}

// ── Facebook Posts ────────────────────────────────────────────────────────────

func (h *ImporterHandler) FacebookPostsStart(w http.ResponseWriter, r *http.Request) {
	if err := facebookPostsJob.AssertNotRunning(); err != nil {
		writeError(w, http.StatusBadRequest, err.Error())
		return
	}
	var req struct {
		DirectoryPath string `json:"directory_path"`
	}
	if err := json.NewDecoder(r.Body).Decode(&req); err != nil {
		writeError(w, http.StatusBadRequest, "invalid JSON body")
		return
	}
	if !dirExists(req.DirectoryPath) {
		writeError(w, http.StatusBadRequest, fmt.Sprintf("directory does not exist: %s", req.DirectoryPath))
		return
	}

	facebookPostsJob.Start()
	facebookPostsJob.UpdateState(map[string]any{
		"status": "in_progress", "status_line": "Starting import-processor...",
		"posts_processed": 0, "posts_imported": 0, "posts_updated": 0,
		"with_media": 0, "images_imported": 0, "images_found": 0, "images_missing": 0, "errors": 0,
	})
	facebookPostsJob.Broadcast("status", map[string]any{"status_line": "Starting import-processor..."})

	runJob(facebookPostsJob, []string{"facebook-posts", "--path", req.DirectoryPath}, func(stdout string) {
		stats := parseFacebookPostsStdout(stdout)
		stats["status"] = "completed"
		stats["status_line"] = "Import completed"
		facebookPostsJob.UpdateState(stats)
		facebookPostsJob.Broadcast("completed", facebookPostsJob.GetState())
	})

	writeJSON(w, map[string]any{"message": "Facebook Posts import started", "directory_path": req.DirectoryPath})
}

func (h *ImporterHandler) FacebookPostsStream(w http.ResponseWriter, r *http.Request) {
	facebookPostsJob.ServeSSE(w, r)
}
func (h *ImporterHandler) FacebookPostsCancel(w http.ResponseWriter, r *http.Request) {
	writeJSON(w, facebookPostsJob.Cancel())
}
func (h *ImporterHandler) FacebookPostsStatus(w http.ResponseWriter, r *http.Request) {
	writeJSON(w, facebookPostsJob.Status())
}

// ── Facebook Places ───────────────────────────────────────────────────────────

func (h *ImporterHandler) FacebookPlacesStart(w http.ResponseWriter, r *http.Request) {
	if err := facebookPlacesJob.AssertNotRunning(); err != nil {
		writeError(w, http.StatusBadRequest, err.Error())
		return
	}
	var req struct {
		DirectoryPath string `json:"directory_path"`
	}
	if err := json.NewDecoder(r.Body).Decode(&req); err != nil {
		writeError(w, http.StatusBadRequest, "invalid JSON body")
		return
	}
	if !dirExists(req.DirectoryPath) {
		writeError(w, http.StatusBadRequest, fmt.Sprintf("directory does not exist: %s", req.DirectoryPath))
		return
	}

	facebookPlacesJob.Start()
	facebookPlacesJob.UpdateState(map[string]any{
		"status": "in_progress", "status_line": "Starting import-processor...",
		"places_imported": 0, "places_created": 0, "places_updated": 0,
	})
	facebookPlacesJob.Broadcast("status", map[string]any{"status_line": "Starting import-processor..."})

	runJob(facebookPlacesJob, []string{"facebook-places", "--path", req.DirectoryPath}, func(stdout string) {
		stats := parseFacebookPlacesStdout(stdout)
		stats["status"] = "completed"
		stats["status_line"] = "Import completed"
		facebookPlacesJob.UpdateState(stats)
		facebookPlacesJob.Broadcast("completed", facebookPlacesJob.GetState())
	})

	writeJSON(w, map[string]any{"message": "Facebook Places import started", "directory_path": req.DirectoryPath})
}

func (h *ImporterHandler) FacebookPlacesStream(w http.ResponseWriter, r *http.Request) {
	facebookPlacesJob.ServeSSE(w, r)
}
func (h *ImporterHandler) FacebookPlacesCancel(w http.ResponseWriter, r *http.Request) {
	writeJSON(w, facebookPlacesJob.Cancel())
}
func (h *ImporterHandler) FacebookPlacesStatus(w http.ResponseWriter, r *http.Request) {
	writeJSON(w, facebookPlacesJob.Status())
}

// ── Facebook All ──────────────────────────────────────────────────────────────

func (h *ImporterHandler) FacebookAllStart(w http.ResponseWriter, r *http.Request) {
	if err := facebookAllJob.AssertNotRunning(); err != nil {
		writeError(w, http.StatusBadRequest, err.Error())
		return
	}
	var req struct {
		DirectoryPath string  `json:"directory_path"`
		UserName      *string `json:"user_name"`
	}
	if err := json.NewDecoder(r.Body).Decode(&req); err != nil {
		writeError(w, http.StatusBadRequest, "invalid JSON body")
		return
	}
	if !dirExists(req.DirectoryPath) {
		writeError(w, http.StatusBadRequest, fmt.Sprintf("path does not exist: %s", req.DirectoryPath))
		return
	}

	facebookAllJob.Start()
	facebookAllJob.UpdateState(map[string]any{
		"status": "in_progress", "status_line": "Starting import-processor...",
		"conversations": 0, "messages_imported": 0, "messages_created": 0,
		"messages_updated": 0, "att_found": 0, "att_missing": 0, "messenger_errors": 0,
		"albums_processed": 0, "albums_imported": 0, "album_images_imported": 0,
		"album_images_found": 0, "album_images_missing": 0, "albums_errors": 0,
		"places_imported": 0, "places_created": 0, "places_updated": 0,
		"posts_processed": 0, "posts_imported": 0, "posts_updated": 0,
		"with_media": 0, "images_imported": 0, "images_found": 0,
		"images_missing": 0, "posts_errors": 0,
	})
	facebookAllJob.Broadcast("status", map[string]any{"status_line": "Starting import-processor..."})

	args := []string{"facebook-all", "--path", req.DirectoryPath}
	if req.UserName != nil && *req.UserName != "" {
		args = append(args, "--user-name", *req.UserName)
	}

	runJob(facebookAllJob, args, func(stdout string) {
		stats := parseFacebookAllStdout(stdout)
		stats["status"] = "completed"
		stats["status_line"] = "Import completed"
		facebookAllJob.UpdateState(stats)
		facebookAllJob.Broadcast("completed", facebookAllJob.GetState())
	})

	writeJSON(w, map[string]any{"message": "Facebook All import started", "directory_path": req.DirectoryPath})
}

func (h *ImporterHandler) FacebookAllStream(w http.ResponseWriter, r *http.Request) {
	facebookAllJob.ServeSSE(w, r)
}
func (h *ImporterHandler) FacebookAllCancel(w http.ResponseWriter, r *http.Request) {
	writeJSON(w, facebookAllJob.Cancel())
}
func (h *ImporterHandler) FacebookAllStatus(w http.ResponseWriter, r *http.Request) {
	writeJSON(w, facebookAllJob.Status())
}

// ── Contacts extract ──────────────────────────────────────────────────────────

func (h *ImporterHandler) ContactsExtractStart(w http.ResponseWriter, r *http.Request) {
	if err := contactsExtractJob.AssertNotRunning(); err != nil {
		writeError(w, http.StatusBadRequest, err.Error())
		return
	}

	contactsExtractJob.Start()
	contactsExtractJob.UpdateState(map[string]any{
		"status": "in_progress", "status_line": "Starting import-processor...",
		"contacts_processed": 0, "contacts_merged": 0, "contacts_created": 0,
	})
	contactsExtractJob.Broadcast("status", map[string]any{"status_line": "Starting import-processor..."})

	runJob(contactsExtractJob, []string{"contacts"}, func(stdout string) {
		contactsExtractJob.UpdateState(map[string]any{
			"status": "completed", "status_line": strings.TrimSpace(stdout),
		})
		contactsExtractJob.Broadcast("completed", contactsExtractJob.GetState())
	})

	writeJSON(w, map[string]any{"message": "Contacts extract started", "status": "started"})
}

func (h *ImporterHandler) ContactsExtractStream(w http.ResponseWriter, r *http.Request) {
	contactsExtractJob.ServeSSE(w, r)
}
func (h *ImporterHandler) ContactsExtractCancel(w http.ResponseWriter, r *http.Request) {
	writeJSON(w, contactsExtractJob.Cancel())
}
func (h *ImporterHandler) ContactsExtractStatus(w http.ResponseWriter, r *http.Request) {
	writeJSON(w, contactsExtractJob.Status())
}

// ── WhatsApp ──────────────────────────────────────────────────────────────────

func (h *ImporterHandler) WhatsAppStart(w http.ResponseWriter, r *http.Request) {
	if err := whatsappJob.AssertNotRunning(); err != nil {
		writeError(w, http.StatusBadRequest, err.Error())
		return
	}
	var req struct {
		DirectoryPath string `json:"directory_path"`
	}
	if err := json.NewDecoder(r.Body).Decode(&req); err != nil {
		writeError(w, http.StatusBadRequest, "invalid JSON body")
		return
	}
	if !dirExists(req.DirectoryPath) {
		writeError(w, http.StatusBadRequest, fmt.Sprintf("directory does not exist: %s", req.DirectoryPath))
		return
	}

	whatsappJob.Start()
	whatsappJob.UpdateState(map[string]any{
		"status": "in_progress", "status_line": "Starting import-processor...",
		"conversations": 0, "messages_imported": 0, "messages_created": 0,
		"messages_updated": 0, "attachments_found": 0, "attachments_missing": 0,
		"missing_attachment_filenames": []string{}, "errors": 0,
	})
	whatsappJob.Broadcast("status", map[string]any{"status_line": "Starting import-processor..."})

	runJob(whatsappJob, []string{"whatsapp", "--path", req.DirectoryPath}, func(stdout string) {
		stats := parseMessageStdout(stdout, true)
		stats["status"] = "completed"
		stats["status_line"] = "Import completed"
		whatsappJob.UpdateState(stats)
		whatsappJob.Broadcast("completed", whatsappJob.GetState())
	})

	writeJSON(w, map[string]any{"message": "WhatsApp import started", "directory_path": req.DirectoryPath})
}

func (h *ImporterHandler) WhatsAppStream(w http.ResponseWriter, r *http.Request) {
	whatsappJob.ServeSSE(w, r)
}
func (h *ImporterHandler) WhatsAppCancel(w http.ResponseWriter, r *http.Request) {
	writeJSON(w, whatsappJob.Cancel())
}
func (h *ImporterHandler) WhatsAppStatus(w http.ResponseWriter, r *http.Request) {
	writeJSON(w, whatsappJob.Status())
}

// ── iMessage ──────────────────────────────────────────────────────────────────

func (h *ImporterHandler) IMessageStart(w http.ResponseWriter, r *http.Request) {
	if err := imessageJob.AssertNotRunning(); err != nil {
		writeError(w, http.StatusBadRequest, err.Error())
		return
	}
	var req struct {
		DirectoryPath string `json:"directory_path"`
	}
	if err := json.NewDecoder(r.Body).Decode(&req); err != nil {
		writeError(w, http.StatusBadRequest, "invalid JSON body")
		return
	}
	if !dirExists(req.DirectoryPath) {
		writeError(w, http.StatusBadRequest, fmt.Sprintf("directory does not exist: %s", req.DirectoryPath))
		return
	}

	imessageJob.Start()
	imessageJob.UpdateState(map[string]any{
		"status": "in_progress", "status_line": "Starting import-processor...",
		"conversations": 0, "messages_imported": 0, "messages_created": 0,
		"messages_updated": 0, "attachments_found": 0, "attachments_missing": 0,
		"missing_attachment_filenames": []string{}, "errors": 0,
	})
	imessageJob.Broadcast("status", map[string]any{"status_line": "Starting import-processor..."})

	runJob(imessageJob, []string{"imessage", "--path", req.DirectoryPath}, func(stdout string) {
		stats := parseMessageStdout(stdout, true)
		stats["status"] = "completed"
		stats["status_line"] = "Import completed"
		imessageJob.UpdateState(stats)
		imessageJob.Broadcast("completed", imessageJob.GetState())
	})

	writeJSON(w, map[string]any{"message": "iMessage import started", "directory_path": req.DirectoryPath})
}

func (h *ImporterHandler) IMessageStream(w http.ResponseWriter, r *http.Request) {
	imessageJob.ServeSSE(w, r)
}
func (h *ImporterHandler) IMessageCancel(w http.ResponseWriter, r *http.Request) {
	writeJSON(w, imessageJob.Cancel())
}
func (h *ImporterHandler) IMessageStatus(w http.ResponseWriter, r *http.Request) {
	writeJSON(w, imessageJob.Status())
}

// ── Instagram ─────────────────────────────────────────────────────────────────

func (h *ImporterHandler) InstagramStart(w http.ResponseWriter, r *http.Request) {
	if err := instagramJob.AssertNotRunning(); err != nil {
		writeError(w, http.StatusBadRequest, err.Error())
		return
	}
	var req struct {
		DirectoryPath string  `json:"directory_path"`
		UserName      *string `json:"user_name"`
		ExportRoot    *string `json:"export_root"`
	}
	if err := json.NewDecoder(r.Body).Decode(&req); err != nil {
		writeError(w, http.StatusBadRequest, "invalid JSON body")
		return
	}
	if !dirExists(req.DirectoryPath) {
		writeError(w, http.StatusBadRequest, fmt.Sprintf("directory does not exist: %s", req.DirectoryPath))
		return
	}

	instagramJob.Start()
	instagramJob.UpdateState(map[string]any{
		"status": "in_progress", "status_line": "Starting import-processor...",
		"conversations": 0, "messages_imported": 0, "messages_created": 0,
		"messages_updated": 0, "errors": 0,
	})
	instagramJob.Broadcast("status", map[string]any{"status_line": "Starting import-processor..."})

	args := []string{"instagram", "--path", req.DirectoryPath}
	if req.ExportRoot != nil && *req.ExportRoot != "" {
		args = append(args, "--export-root", *req.ExportRoot)
	}

	runJob(instagramJob, args, func(stdout string) {
		stats := parseMessageStdout(stdout, false)
		stats["status"] = "completed"
		stats["status_line"] = "Import completed"
		instagramJob.UpdateState(stats)
		instagramJob.Broadcast("completed", instagramJob.GetState())
	})

	writeJSON(w, map[string]any{"message": "Instagram import started", "directory_path": req.DirectoryPath})
}

func (h *ImporterHandler) InstagramStream(w http.ResponseWriter, r *http.Request) {
	instagramJob.ServeSSE(w, r)
}
func (h *ImporterHandler) InstagramCancel(w http.ResponseWriter, r *http.Request) {
	writeJSON(w, instagramJob.Cancel())
}
func (h *ImporterHandler) InstagramStatus(w http.ResponseWriter, r *http.Request) {
	writeJSON(w, instagramJob.Status())
}

// ── Facebook Messenger (standalone) ───────────────────────────────────────────

func (h *ImporterHandler) FacebookMessengerStart(w http.ResponseWriter, r *http.Request) {
	if err := facebookMessengerJob.AssertNotRunning(); err != nil {
		writeError(w, http.StatusBadRequest, err.Error())
		return
	}
	var req struct {
		DirectoryPath string  `json:"directory_path"`
		UserName      *string `json:"user_name"`
	}
	if err := json.NewDecoder(r.Body).Decode(&req); err != nil {
		writeError(w, http.StatusBadRequest, "invalid JSON body")
		return
	}
	if !dirExists(req.DirectoryPath) {
		writeError(w, http.StatusBadRequest, fmt.Sprintf("directory does not exist: %s", req.DirectoryPath))
		return
	}

	facebookMessengerJob.Start()
	facebookMessengerJob.UpdateState(map[string]any{
		"status": "in_progress", "status_line": "Starting import-processor...",
		"conversations": 0, "messages_imported": 0, "messages_created": 0,
		"messages_updated": 0, "attachments_found": 0, "attachments_missing": 0,
		"missing_attachment_filenames": []string{}, "errors": 0,
	})
	facebookMessengerJob.Broadcast("status", map[string]any{"status_line": "Starting import-processor..."})

	args := []string{"facebook", "--path", req.DirectoryPath}
	if req.UserName != nil && *req.UserName != "" {
		args = append(args, "--user-name", *req.UserName)
	}

	runJob(facebookMessengerJob, args, func(stdout string) {
		stats := parseMessageStdout(stdout, true)
		stats["status"] = "completed"
		stats["status_line"] = "Import completed"
		facebookMessengerJob.UpdateState(stats)
		facebookMessengerJob.Broadcast("completed", facebookMessengerJob.GetState())
	})

	writeJSON(w, map[string]any{"message": "Facebook Messenger import started", "directory_path": req.DirectoryPath})
}

func (h *ImporterHandler) FacebookMessengerStream(w http.ResponseWriter, r *http.Request) {
	facebookMessengerJob.ServeSSE(w, r)
}
func (h *ImporterHandler) FacebookMessengerCancel(w http.ResponseWriter, r *http.Request) {
	writeJSON(w, facebookMessengerJob.Cancel())
}
func (h *ImporterHandler) FacebookMessengerStatus(w http.ResponseWriter, r *http.Request) {
	writeJSON(w, facebookMessengerJob.Status())
}

// ── Email (Gmail) process — stub ──────────────────────────────────────────────
// Gmail import uses OAuth and is not implemented in Go.
// Use POST /imap/process for IMAP-based email import instead.

func (h *ImporterHandler) EmailProcessStart(w http.ResponseWriter, _ *http.Request) {
	writeError(w, http.StatusNotImplemented,
		"Gmail import via OAuth is not implemented in the Go server. Use POST /imap/process for IMAP-based email import.")
}
func (h *ImporterHandler) EmailProcessStream(w http.ResponseWriter, r *http.Request) {
	emailProcessJob.ServeSSE(w, r)
}
func (h *ImporterHandler) EmailProcessCancel(w http.ResponseWriter, r *http.Request) {
	writeJSON(w, emailProcessJob.Cancel())
}
func (h *ImporterHandler) EmailProcessStatus(w http.ResponseWriter, r *http.Request) {
	writeJSON(w, emailProcessJob.Status())
}

// ── stdout parsers ────────────────────────────────────────────────────────────

var reInt = regexp.MustCompile(`\d+`)

// parseMessageStdout parses the shared stdout format used by whatsapp, imessage,
// and instagram import commands. Pass includeAttachments=true for whatsapp/imessage.
func parseMessageStdout(s string, includeAttachments bool) map[string]any {
	reConvs := regexp.MustCompile(`Processed (\d+) conversation`)
	reImported := regexp.MustCompile(`Imported (\d+) message.*\((\d+) created, (\d+) updated\)`)
	reAttach := regexp.MustCompile(`Found (\d+) attachment.*?, (\d+) missing`)
	reSkipped := regexp.MustCompile(`Skipped invalid messages.*?:\s*(\d+)`)

	stats := map[string]any{
		"conversations":    0,
		"messages_imported": 0,
		"messages_created": 0,
		"messages_updated": 0,
		"errors":           0,
	}
	if includeAttachments {
		stats["attachments_found"] = 0
		stats["attachments_missing"] = 0
		stats["missing_attachment_filenames"] = []string{}
	}

	var missingFiles []string
	inMissing := false
	for _, line := range strings.Split(s, "\n") {
		if m := reConvs.FindStringSubmatch(line); len(m) > 1 {
			n, _ := strconv.Atoi(m[1])
			stats["conversations"] = n
		} else if m := reImported.FindStringSubmatch(line); len(m) > 3 {
			total, _ := strconv.Atoi(m[1])
			created, _ := strconv.Atoi(m[2])
			updated, _ := strconv.Atoi(m[3])
			stats["messages_imported"] = total
			stats["messages_created"] = created
			stats["messages_updated"] = updated
		} else if includeAttachments {
			if m := reAttach.FindStringSubmatch(line); len(m) > 2 {
				found, _ := strconv.Atoi(m[1])
				missing, _ := strconv.Atoi(m[2])
				stats["attachments_found"] = found
				stats["attachments_missing"] = missing
			}
			if strings.TrimSpace(line) == "Missing attachment files:" {
				inMissing = true
				continue
			}
			if inMissing && strings.HasPrefix(line, "  - ") {
				missingFiles = append(missingFiles, strings.TrimPrefix(line, "  - "))
			} else if inMissing && !strings.HasPrefix(line, "  ") {
				inMissing = false
			}
		}
		if m := reSkipped.FindStringSubmatch(line); len(m) > 1 {
			n, _ := strconv.Atoi(m[1])
			stats["errors"] = n
		}
	}
	if includeAttachments && missingFiles != nil {
		stats["missing_attachment_filenames"] = missingFiles
	}
	return stats
}

func parseInt(s string) int {
	m := reInt.FindString(s)
	if m == "" {
		return 0
	}
	n, _ := strconv.Atoi(m)
	return n
}

func parseFilesystemStdout(s string) (total, processed, imp, ref, upd, errs int, errMsgs []string, msg string) {
	for _, line := range strings.Split(s, "\n") {
		switch {
		case strings.HasPrefix(line, "Total files:"):
			total = parseInt(line)
		case strings.HasPrefix(line, "Files processed:"):
			processed = parseInt(line)
		case strings.HasPrefix(line, "Images imported:"):
			imp = parseInt(line)
		case strings.HasPrefix(line, "Images referenced:"):
			ref = parseInt(line)
		case strings.HasPrefix(line, "Images updated:"):
			upd = parseInt(line)
		case strings.HasPrefix(line, "Errors:"):
			errs = parseInt(line)
		case strings.HasPrefix(line, "  - "):
			errMsgs = append(errMsgs, strings.TrimPrefix(line, "  - "))
		}
	}
	parts := []string{"Import completed"}
	if total > 0 {
		parts = append(parts, fmt.Sprintf("Total files: %d", total))
	}
	if processed > 0 {
		parts = append(parts, fmt.Sprintf("Processed: %d", processed))
	}
	if imp > 0 || ref > 0 || upd > 0 {
		parts = append(parts, fmt.Sprintf("Imported: %d, Referenced: %d, Updated: %d", imp, ref, upd))
	}
	if errs > 0 {
		parts = append(parts, fmt.Sprintf("Errors: %d", errs))
	}
	msg = strings.Join(parts, ". ")
	return
}

func parseThumbnailsStdout(s string) (total, processed, errs int, msg string) {
	for _, line := range strings.Split(s, "\n") {
		switch {
		case strings.Contains(line, "Total items to process:"):
			total = parseInt(line)
		case strings.Contains(line, "Successfully processed:"):
			processed = parseInt(line)
		case strings.HasPrefix(line, "Errors:"):
			errs = parseInt(line)
		}
	}
	parts := []string{"Thumbnail processing completed"}
	if total > 0 {
		parts = append(parts, fmt.Sprintf("Total: %d", total))
	}
	if processed > 0 {
		parts = append(parts, fmt.Sprintf("Processed: %d", processed))
	}
	if errs > 0 {
		parts = append(parts, fmt.Sprintf("Errors: %d", errs))
	}
	msg = strings.Join(parts, ". ")
	return
}

func parseFacebookAlbumsStdout(s string) (albumsProcessed, albumsImported, imagesImported, imagesFound, imagesMissing, errs int, missing []string, msg string) {
	reAlbums := regexp.MustCompile(`Processed (\d+) album\(s\)`)
	reAlbumsImported := regexp.MustCompile(`Albums imported: (\d+)`)
	reImages := regexp.MustCompile(`Images imported: (\d+) \(found: (\d+), missing: (\d+)\)`)
	reErrors := regexp.MustCompile(`Errors: (\d+)`)

	if m := reAlbums.FindStringSubmatch(s); len(m) > 1 {
		albumsProcessed, _ = strconv.Atoi(m[1])
	}
	if m := reAlbumsImported.FindStringSubmatch(s); len(m) > 1 {
		albumsImported, _ = strconv.Atoi(m[1])
	}
	if m := reImages.FindStringSubmatch(s); len(m) > 3 {
		imagesImported, _ = strconv.Atoi(m[1])
		imagesFound, _ = strconv.Atoi(m[2])
		imagesMissing, _ = strconv.Atoi(m[3])
	}
	if m := reErrors.FindStringSubmatch(s); len(m) > 1 {
		errs, _ = strconv.Atoi(m[1])
	}
	inMissing := false
	for _, line := range strings.Split(s, "\n") {
		if strings.TrimSpace(line) == "Missing image files:" {
			inMissing = true
			continue
		}
		if inMissing && strings.HasPrefix(line, "  - ") {
			missing = append(missing, strings.TrimPrefix(line, "  - "))
		}
	}

	parts := []string{"Import completed"}
	if albumsProcessed > 0 {
		parts = append(parts, fmt.Sprintf("Processed %d album(s)", albumsProcessed))
	}
	if albumsImported > 0 {
		parts = append(parts, fmt.Sprintf("Imported %d album(s) with %d image(s)", albumsImported, imagesImported))
	}
	msg = strings.Join(parts, ". ")
	return
}

func parseFacebookPostsStdout(s string) map[string]any {
	stats := map[string]any{}
	for _, line := range strings.Split(s, "\n") {
		if strings.HasPrefix(line, "POSTS_COMPLETE: ") {
			for _, part := range strings.Fields(line[len("POSTS_COMPLETE: "):]) {
				kv := strings.SplitN(part, "=", 2)
				if len(kv) == 2 {
					n, _ := strconv.Atoi(kv[1])
					switch kv[0] {
					case "posts":
						stats["posts_processed"] = n
					case "new":
						stats["posts_imported"] = n
					case "updated":
						stats["posts_updated"] = n
					case "with_media":
						stats["with_media"] = n
					case "images":
						stats["images_imported"] = n
					case "found":
						stats["images_found"] = n
					case "missing":
						stats["images_missing"] = n
					case "errors":
						stats["errors"] = n
					}
				}
			}
		}
	}
	return stats
}

func parseFacebookPlacesStdout(s string) map[string]any {
	stats := map[string]any{}
	for _, line := range strings.Split(s, "\n") {
		if strings.HasPrefix(line, "PLACES_COMPLETE: ") {
			for _, part := range strings.Fields(line[len("PLACES_COMPLETE: "):]) {
				kv := strings.SplitN(part, "=", 2)
				if len(kv) == 2 {
					n, _ := strconv.Atoi(kv[1])
					switch kv[0] {
					case "places":
						stats["places_imported"] = n
					case "created":
						stats["places_created"] = n
					case "updated":
						stats["places_updated"] = n
					}
				}
			}
		}
	}
	return stats
}

func parseFacebookAllStdout(s string) map[string]any {
	stats := map[string]any{}
	for _, line := range strings.Split(s, "\n") {
		line = strings.TrimSpace(line)
		switch {
		case strings.HasPrefix(line, "FACEBOOK_COMPLETE: "):
			for _, part := range strings.Fields(line[len("FACEBOOK_COMPLETE: "):]) {
				kv := strings.SplitN(part, "=", 2)
				if len(kv) == 2 {
					n, _ := strconv.Atoi(kv[1])
					switch kv[0] {
					case "conversations":
						stats["conversations"] = n
					case "messages":
						stats["messages_imported"] = n
					case "created":
						stats["messages_created"] = n
					case "updated":
						stats["messages_updated"] = n
					case "att_found":
						stats["att_found"] = n
					case "att_missing":
						stats["att_missing"] = n
					case "errors":
						stats["messenger_errors"] = n
					}
				}
			}
		case strings.HasPrefix(line, "ALBUMS_COMPLETE: "):
			for _, part := range strings.Fields(line[len("ALBUMS_COMPLETE: "):]) {
				kv := strings.SplitN(part, "=", 2)
				if len(kv) == 2 {
					n, _ := strconv.Atoi(kv[1])
					switch kv[0] {
					case "albums":
						stats["albums_processed"] = n
					case "albums_imported":
						stats["albums_imported"] = n
					case "images":
						stats["album_images_imported"] = n
					case "found":
						stats["album_images_found"] = n
					case "missing":
						stats["album_images_missing"] = n
					case "errors":
						stats["albums_errors"] = n
					}
				}
			}
		case strings.HasPrefix(line, "PLACES_COMPLETE: "):
			for _, part := range strings.Fields(line[len("PLACES_COMPLETE: "):]) {
				kv := strings.SplitN(part, "=", 2)
				if len(kv) == 2 {
					n, _ := strconv.Atoi(kv[1])
					switch kv[0] {
					case "places":
						stats["places_imported"] = n
					case "created":
						stats["places_created"] = n
					case "updated":
						stats["places_updated"] = n
					}
				}
			}
		case strings.HasPrefix(line, "POSTS_COMPLETE: "):
			for _, part := range strings.Fields(line[len("POSTS_COMPLETE: "):]) {
				kv := strings.SplitN(part, "=", 2)
				if len(kv) == 2 {
					n, _ := strconv.Atoi(kv[1])
					switch kv[0] {
					case "posts":
						stats["posts_processed"] = n
					case "new":
						stats["posts_imported"] = n
					case "updated":
						stats["posts_updated"] = n
					case "with_media":
						stats["with_media"] = n
					case "images":
						stats["images_imported"] = n
					case "found":
						stats["images_found"] = n
					case "missing":
						stats["images_missing"] = n
					case "errors":
						stats["posts_errors"] = n
					}
				}
			}
		}
	}
	return stats
}
