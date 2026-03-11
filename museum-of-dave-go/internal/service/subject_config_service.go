package service

import (
	"context"
	"time"

	"github.com/museum-of-dave/app/internal/model"
	"github.com/museum-of-dave/app/internal/repository"
)

// SubjectConfigService handles GET /api/subject-configuration.
type SubjectConfigService struct {
	repo *repository.SubjectConfigRepo
}

// NewSubjectConfigService creates a SubjectConfigService.
func NewSubjectConfigService(repo *repository.SubjectConfigRepo) *SubjectConfigService {
	return &SubjectConfigService{repo: repo}
}

// GetConfiguration returns the singleton subject configuration, or nil if none exists.
func (s *SubjectConfigService) GetConfiguration(ctx context.Context) (*model.SubjectConfigResponse, error) {
	cfg, err := s.repo.GetFirst(ctx)
	if err != nil {
		return nil, err
	}
	if cfg == nil {
		return nil, nil
	}
	return toSubjectConfigResponse(cfg), nil
}

func toSubjectConfigResponse(cfg *model.SubjectConfig) *model.SubjectConfigResponse {
	return &model.SubjectConfigResponse{
		ID:                     cfg.ID,
		SubjectName:            cfg.SubjectName,
		Gender:                 cfg.Gender,
		FamilyName:             cfg.FamilyName,
		OtherNames:             cfg.OtherNames,
		EmailAddresses:         cfg.EmailAddresses,
		PhoneNumbers:           cfg.PhoneNumbers,
		WhatsAppHandle:         cfg.WhatsAppHandle,
		InstagramHandle:        cfg.InstagramHandle,
		WritingStyleAI:         cfg.WritingStyleAI,
		PsychologicalProfileAI: cfg.PsychologicalProfileAI,
		SystemInstructions:     cfg.SystemInstructions,
		CoreSystemInstructions: cfg.CoreSystemInstructions,
		CreatedAt:              isoString(ptrTime(cfg.CreatedAt)),
		UpdatedAt:              isoString(ptrTime(cfg.UpdatedAt)),
	}
}

// ptrTime converts a value time.Time to *time.Time so isoString can accept it.
func ptrTime(t time.Time) *time.Time {
	return &t
}
