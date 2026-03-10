// Package service contains business logic that sits between handlers and repositories.
package service

import (
	"context"
	"fmt"

	"github.com/museum-of-dave/app/internal/model"
	"github.com/museum-of-dave/app/internal/repository"
)

// EmailService coordinates email read operations.
type EmailService struct {
	repo *repository.EmailRepo
}

// NewEmailService creates an EmailService.
func NewEmailService(repo *repository.EmailRepo) *EmailService {
	return &EmailService{repo: repo}
}

// Search returns email metadata matching the given optional filters.
func (s *EmailService) Search(ctx context.Context, p model.EmailSearchParams) ([]model.EmailMetadataResponse, error) {
	emails, err := s.repo.Search(ctx, p)
	if err != nil {
		return nil, err
	}
	return s.hydrateMetadata(ctx, emails)
}

// GetByLabels returns email metadata for emails whose folder matches any label.
func (s *EmailService) GetByLabels(ctx context.Context, labels []string) ([]model.EmailMetadataResponse, error) {
	emails, err := s.repo.GetByLabels(ctx, labels)
	if err != nil {
		return nil, err
	}
	return s.hydrateMetadata(ctx, emails)
}

// GetMetadata returns a single email's metadata, including attachment IDs.
// Returns nil, nil when the email does not exist (handler maps to 404).
func (s *EmailService) GetMetadata(ctx context.Context, id int64) (*model.EmailMetadataResponse, error) {
	email, err := s.repo.GetByID(ctx, id)
	if err != nil {
		return nil, err
	}
	if email == nil {
		return nil, nil
	}

	attMap, err := s.repo.GetAttachmentIDsForEmails(ctx, []int64{id})
	if err != nil {
		return nil, fmt.Errorf("get attachment ids: %w", err)
	}

	resp := toMetadataResponse(email, attMap[id])
	return &resp, nil
}

// GetByID returns the raw email record without attachment hydration.
// Returns nil, nil when not found (handler maps to 404).
func (s *EmailService) GetByID(ctx context.Context, id int64) (*model.Email, error) {
	return s.repo.GetByID(ctx, id)
}

// ── helpers ───────────────────────────────────────────────────────────────────

// hydrateMetadata batch-fetches attachment IDs for a slice of emails and returns the
// combined response slice. An empty (not nil) attachment_ids list is always returned.
func (s *EmailService) hydrateMetadata(ctx context.Context, emails []*model.Email) ([]model.EmailMetadataResponse, error) {
	if len(emails) == 0 {
		return []model.EmailMetadataResponse{}, nil
	}

	ids := make([]int64, len(emails))
	for i, e := range emails {
		ids[i] = e.ID
	}

	attMap, err := s.repo.GetAttachmentIDsForEmails(ctx, ids)
	if err != nil {
		return nil, fmt.Errorf("get attachment ids: %w", err)
	}

	result := make([]model.EmailMetadataResponse, len(emails))
	for i, e := range emails {
		result[i] = toMetadataResponse(e, attMap[e.ID])
	}
	return result, nil
}

// toMetadataResponse converts an Email domain model and its attachment IDs into
// the JSON response struct. attachmentIDs may be nil (treated as empty).
func toMetadataResponse(e *model.Email, attachmentIDs []int64) model.EmailMetadataResponse {
	if attachmentIDs == nil {
		attachmentIDs = []int64{}
	}
	return model.EmailMetadataResponse{
		ID:            e.ID,
		UID:           e.UID,
		Folder:        e.Folder,
		Subject:       e.Subject,
		FromAddress:   e.FromAddress,
		ToAddresses:   e.ToAddresses,
		CCAddresses:   e.CCAddresses,
		BCCAddresses:  e.BCCAddresses,
		Date:          e.Date,
		Snippet:       e.Snippet,
		AttachmentIDs: attachmentIDs,
		CreatedAt:     e.CreatedAt,
		UpdatedAt:     e.UpdatedAt,
		IsPersonal:    e.IsPersonal,
		IsBusiness:    e.IsBusiness,
		IsImportant:   e.IsImportant,
		UseByAI:       e.UseByAI,
	}
}
