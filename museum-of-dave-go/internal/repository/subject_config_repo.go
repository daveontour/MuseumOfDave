package repository

import (
	"context"
	"fmt"

	"github.com/jackc/pgx/v5/pgxpool"
	"github.com/museum-of-dave/app/internal/model"
)

// SubjectConfigRepo reads the singleton subject_configuration table.
type SubjectConfigRepo struct {
	pool *pgxpool.Pool
}

// NewSubjectConfigRepo creates a SubjectConfigRepo.
func NewSubjectConfigRepo(pool *pgxpool.Pool) *SubjectConfigRepo {
	return &SubjectConfigRepo{pool: pool}
}

// GetFirst returns the first (and only) subject configuration row.
// Returns nil, nil if no row exists yet.
func (r *SubjectConfigRepo) GetFirst(ctx context.Context) (*model.SubjectConfig, error) {
	row := r.pool.QueryRow(ctx, `
		SELECT id, subject_name, gender, family_name, other_names,
		       email_addresses, phone_numbers, whatsapp_handle, instagram_handle,
		       writing_style_ai, psychological_profile_ai,
		       system_instructions, core_system_instructions,
		       created_at, updated_at
		FROM subject_configuration
		LIMIT 1`)

	cfg := &model.SubjectConfig{}
	err := row.Scan(
		&cfg.ID, &cfg.SubjectName, &cfg.Gender, &cfg.FamilyName, &cfg.OtherNames,
		&cfg.EmailAddresses, &cfg.PhoneNumbers, &cfg.WhatsAppHandle, &cfg.InstagramHandle,
		&cfg.WritingStyleAI, &cfg.PsychologicalProfileAI,
		&cfg.SystemInstructions, &cfg.CoreSystemInstructions,
		&cfg.CreatedAt, &cfg.UpdatedAt,
	)
	if err != nil {
		if isNoRows(err) {
			return nil, nil
		}
		return nil, fmt.Errorf("GetFirst subject_configuration: %w", err)
	}
	return cfg, nil
}
