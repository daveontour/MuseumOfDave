package services

import (
	"context"
	"fmt"

	"github.com/jackc/pgx/v5"
	"whatsapp-import-service/internal/database"
)

// SubjectConfigurationService handles subject configuration operations
type SubjectConfigurationService struct {
	db *database.DB
}

// NewSubjectConfigurationService creates a new subject configuration service
func NewSubjectConfigurationService(db *database.DB) *SubjectConfigurationService {
	return &SubjectConfigurationService{db: db}
}

// GetConfiguration retrieves the current subject configuration
// Returns nil if no configuration exists
func (s *SubjectConfigurationService) GetConfiguration(ctx context.Context) (*database.SubjectConfiguration, error) {
	query := `SELECT id, subject_name, gender, family_name, other_names, email_addresses, 
		phone_numbers, whatsapp_handle, instagram_handle, system_instructions, 
		core_system_instructions, created_at, updated_at 
		FROM subject_configuration 
		LIMIT 1`

	var config database.SubjectConfiguration
	err := s.db.Pool.QueryRow(ctx, query).Scan(
		&config.ID,
		&config.SubjectName,
		&config.Gender,
		&config.FamilyName,
		&config.OtherNames,
		&config.EmailAddresses,
		&config.PhoneNumbers,
		&config.WhatsAppHandle,
		&config.InstagramHandle,
		&config.SystemInstructions,
		&config.CoreSystemInstructions,
		&config.CreatedAt,
		&config.UpdatedAt,
	)

	if err == pgx.ErrNoRows {
		return nil, nil
	}
	if err != nil {
		return nil, fmt.Errorf("failed to get subject configuration: %w", err)
	}

	return &config, nil
}

// GetSubjectFullName returns the full name (subject_name + family_name) if available
func (s *SubjectConfigurationService) GetSubjectFullName(ctx context.Context) (*string, error) {
	config, err := s.GetConfiguration(ctx)
	if err != nil {
		return nil, err
	}
	if config == nil {
		return nil, nil
	}

	var fullName string
	if config.FamilyName != nil && *config.FamilyName != "" {
		fullName = config.SubjectName + " " + *config.FamilyName
	} else {
		fullName = config.SubjectName
	}

	return &fullName, nil
}
