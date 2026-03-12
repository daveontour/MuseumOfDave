package service

import (
	"context"

	"github.com/daveontour/digitalmuseum/internal/model"
	"github.com/daveontour/digitalmuseum/internal/repository"
)

// DocumentService orchestrates reference document operations.
type DocumentService struct {
	repo *repository.DocumentRepo
}

// NewDocumentService creates a DocumentService.
func NewDocumentService(repo *repository.DocumentRepo) *DocumentService {
	return &DocumentService{repo: repo}
}

func (s *DocumentService) List(ctx context.Context, search, category, tag, contentType string, availableForTask *bool) ([]*model.ReferenceDocument, error) {
	return s.repo.List(ctx, search, category, tag, contentType, availableForTask)
}

func (s *DocumentService) GetByID(ctx context.Context, id int64) (*model.ReferenceDocument, error) {
	return s.repo.GetByID(ctx, id)
}

func (s *DocumentService) GetData(ctx context.Context, id int64) ([]byte, error) {
	return s.repo.GetData(ctx, id)
}

func (s *DocumentService) Create(ctx context.Context,
	filename, contentType string, size int64, data []byte,
	title, description, author, tags, categories, notes *string,
	availableForTask bool,
) (*model.ReferenceDocument, error) {
	return s.repo.Create(ctx, filename, contentType, size, data,
		title, description, author, tags, categories, notes, availableForTask)
}

func (s *DocumentService) Update(ctx context.Context, id int64,
	title, description, author, tags, categories, notes *string,
	availableForTask *bool,
) (*model.ReferenceDocument, error) {
	return s.repo.Update(ctx, id, title, description, author, tags, categories, notes, availableForTask)
}

func (s *DocumentService) Delete(ctx context.Context, id int64) error {
	return s.repo.Delete(ctx, id)
}
