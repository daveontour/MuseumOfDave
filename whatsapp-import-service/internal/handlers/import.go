package handlers

import (
	"context"
	"fmt"
	"net/http"
	"os"
	"sync"
	"time"

	"github.com/gin-gonic/gin"
	"whatsapp-import-service/internal/database"
	whatsappimport "whatsapp-import-service/internal/import"
)

// ImportRequest represents the request body for starting an import
type ImportRequest struct {
	DirectoryPath string `json:"directory_path" binding:"required"`
}

// ImportResponse represents the response for import operations
type ImportResponse struct {
	Message string `json:"message"`
	Status  string `json:"status"`
}

// ImportStatusResponse represents the current import status
type ImportStatusResponse struct {
	Status                   string   `json:"status"`
	ConversationsProcessed   int      `json:"conversations_processed"`
	TotalConversations       int      `json:"total_conversations"`
	MessagesImported        int      `json:"messages_imported"`
	MessagesCreated          int      `json:"messages_created"`
	MessagesUpdated          int      `json:"messages_updated"`
	AttachmentsFound         int      `json:"attachments_found"`
	AttachmentsMissing       int      `json:"attachments_missing"`
	MissingAttachmentFilenames []string `json:"missing_attachment_filenames"`
	Errors                   int      `json:"errors"`
	CurrentConversation      string   `json:"current_conversation,omitempty"`
}

// ImportHandler handles WhatsApp import operations
type ImportHandler struct {
	db              *database.DB
	importInProgress bool
	importStats     *whatsappimport.ImportStats
	importMutex     sync.RWMutex
	cancelFunc      context.CancelFunc
	cancelMutex     sync.Mutex
}

// NewImportHandler creates a new import handler
func NewImportHandler(db *database.DB) *ImportHandler {
	return &ImportHandler{
		db:              db,
		importInProgress: false,
		importStats:     nil,
	}
}

// StartImport handles POST /whatsapp/import
func (h *ImportHandler) StartImport(c *gin.Context) {
	h.importMutex.Lock()
	if h.importInProgress {
		h.importMutex.Unlock()
		c.JSON(http.StatusConflict, gin.H{
			"error": "WhatsApp import is already in progress. Please cancel it first or wait for it to complete.",
		})
		return
	}
	h.importInProgress = true
	h.importMutex.Unlock()

	var req ImportRequest
	if err := c.ShouldBindJSON(&req); err != nil {
		h.importMutex.Lock()
		h.importInProgress = false
		h.importMutex.Unlock()
		c.JSON(http.StatusBadRequest, gin.H{"error": err.Error()})
		return
	}

	// Validate directory exists
	dirInfo, err := os.Stat(req.DirectoryPath)
	if err != nil {
		h.importMutex.Lock()
		h.importInProgress = false
		h.importMutex.Unlock()
		c.JSON(http.StatusBadRequest, gin.H{
			"error": fmt.Sprintf("Directory does not exist or is not a directory: %s", req.DirectoryPath),
		})
		return
	}
	if !dirInfo.IsDir() {
		h.importMutex.Lock()
		h.importInProgress = false
		h.importMutex.Unlock()
		c.JSON(http.StatusBadRequest, gin.H{
			"error": fmt.Sprintf("Path is not a directory: %s", req.DirectoryPath),
		})
		return
	}

	// Initialize stats
	h.importMutex.Lock()
	h.importStats = &whatsappimport.ImportStats{
		MissingAttachmentFilenames: []string{},
	}
	h.importMutex.Unlock()

	// Create context with cancellation
	ctx, cancel := context.WithCancel(context.Background())
	h.cancelMutex.Lock()
	h.cancelFunc = cancel
	h.cancelMutex.Unlock()

	// Start import in goroutine
	go func() {
		defer func() {
			h.importMutex.Lock()
			h.importInProgress = false
			h.importMutex.Unlock()
		}()

		stats, err := whatsappimport.ImportWhatsAppFromDirectory(
			ctx,
			h.db,
			req.DirectoryPath,
			func(s whatsappimport.ImportStats) {
				// Progress callback - update stats
				h.importMutex.Lock()
				h.importStats = &s
				h.importMutex.Unlock()
			},
			func() bool {
				// Cancellation check
				select {
				case <-ctx.Done():
					return true
				default:
					return false
				}
			},
		)

		if err != nil {
			fmt.Printf("Import failed: %v\n", err)
			h.importMutex.Lock()
			if h.importStats != nil {
				h.importStats.Errors++
			}
			h.importMutex.Unlock()
			return
		}

		// Update final stats
		h.importMutex.Lock()
		h.importStats = stats
		h.importMutex.Unlock()
	}()

	c.JSON(http.StatusOK, ImportResponse{
		Message: "WhatsApp import has been initiated.",
		Status:  "started",
	})
}

// GetImportStatus handles GET /whatsapp/import/status
func (h *ImportHandler) GetImportStatus(c *gin.Context) {
	h.importMutex.RLock()
	inProgress := h.importInProgress
	stats := h.importStats
	h.importMutex.RUnlock()

	status := "idle"
	if inProgress {
		status = "in_progress"
	} else if stats != nil && stats.MessagesImported > 0 {
		status = "completed"
	}

	response := ImportStatusResponse{
		Status:                   status,
		ConversationsProcessed:   0,
		TotalConversations:       0,
		MessagesImported:         0,
		MessagesCreated:          0,
		MessagesUpdated:          0,
		AttachmentsFound:         0,
		AttachmentsMissing:       0,
		MissingAttachmentFilenames: []string{},
		Errors:                   0,
	}

	if stats != nil {
		response.ConversationsProcessed = stats.ConversationsProcessed
		response.TotalConversations = stats.TotalConversations
		response.MessagesImported = stats.MessagesImported
		response.MessagesCreated = stats.MessagesCreated
		response.MessagesUpdated = stats.MessagesUpdated
		response.AttachmentsFound = stats.AttachmentsFound
		response.AttachmentsMissing = stats.AttachmentsMissing
		response.MissingAttachmentFilenames = stats.MissingAttachmentFilenames
		response.Errors = stats.Errors
		response.CurrentConversation = stats.CurrentConversation
	}

	c.JSON(http.StatusOK, response)
}

// CancelImport handles POST /whatsapp/import/cancel
func (h *ImportHandler) CancelImport(c *gin.Context) {
	h.importMutex.Lock()
	inProgress := h.importInProgress
	h.importMutex.Unlock()

	if !inProgress {
		c.JSON(http.StatusBadRequest, gin.H{
			"error": "No import is currently in progress.",
		})
		return
	}

	// Cancel the import
	h.cancelMutex.Lock()
	if h.cancelFunc != nil {
		h.cancelFunc()
	}
	h.cancelMutex.Unlock()

	// Wait a bit for cancellation to take effect
	time.Sleep(100 * time.Millisecond)

	h.importMutex.Lock()
	h.importInProgress = false
	h.importMutex.Unlock()

	c.JSON(http.StatusOK, ImportResponse{
		Message: "Import cancellation requested.",
		Status:  "cancelled",
	})
}

// HealthCheck handles GET /health
func (h *ImportHandler) HealthCheck(c *gin.Context) {
	c.JSON(http.StatusOK, gin.H{
		"status": "healthy",
		"time":   time.Now().UTC().Format(time.RFC3339),
	})
}
