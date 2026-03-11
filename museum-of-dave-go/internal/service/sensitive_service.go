package service

import (
	"context"
	"crypto/rand"
	"encoding/hex"
	"fmt"
	"strings"
	"time"

	"github.com/jackc/pgx/v5/pgxpool"
	appcrypto "github.com/museum-of-dave/app/internal/crypto"
	"github.com/museum-of-dave/app/internal/model"
	"github.com/museum-of-dave/app/internal/repository"
)

const redacted = "*****************"

// SensitiveService handles sensitive-data CRUD and key management.
type SensitiveService struct {
	repo   *repository.SensitiveRepo
	pool   *pgxpool.Pool
	pepper string
}

// NewSensitiveService creates a SensitiveService.
// pepper is ATTACHMENT_ALLOWED_TYPES from config.
func NewSensitiveService(repo *repository.SensitiveRepo, pool *pgxpool.Pool, pepper string) *SensitiveService {
	return &SensitiveService{repo: repo, pool: pool, pepper: pepper}
}

// Count returns the total number of sensitive_data records.
func (s *SensitiveService) Count(ctx context.Context) (int64, error) {
	return s.repo.Count(ctx)
}

// KeyCount returns the total number of trusted_keys.
func (s *SensitiveService) KeyCount(ctx context.Context) (int64, error) {
	return s.repo.KeyCount(ctx)
}

// ListAll returns all records. If password is empty a random token is used so
// the call succeeds but details remain unreadable (matching Python behaviour).
func (s *SensitiveService) ListAll(ctx context.Context, password string) ([]model.SensitiveDataResponse, error) {
	if !hasPassword(password) {
		password = randomToken()
	}
	privateKey, err := appcrypto.GetPrivateKey(ctx, s.pool, password, s.pepper)
	if err != nil {
		return nil, err
	}

	rows, err := s.repo.GetAll(ctx)
	if err != nil {
		return nil, err
	}
	return s.toResponses(rows, privateKey), nil
}

// GetByID returns a single record, decrypting if password is valid.
func (s *SensitiveService) GetByID(ctx context.Context, id int64, password string) (*model.SensitiveDataResponse, error) {
	if !hasPassword(password) {
		password = randomToken()
	}
	privateKey, err := appcrypto.GetPrivateKey(ctx, s.pool, password, s.pepper)
	if err != nil {
		return nil, err
	}

	row, err := s.repo.GetByID(ctx, id)
	if err != nil {
		return nil, err
	}
	if row == nil {
		return nil, nil
	}
	responses := s.toResponses([]model.SensitiveData{*row}, privateKey)
	return &responses[0], nil
}

// Create encrypts details with the master public key and inserts a new record.
func (s *SensitiveService) Create(ctx context.Context, masterPassword, description, details string, isPrivate, isSensitive bool) error {
	encDetails, err := appcrypto.EncryptRecord(ctx, s.pool, masterPassword, details, s.pepper)
	if err != nil {
		return fmt.Errorf("encrypt record: %w", err)
	}
	return s.repo.Create(ctx, description, encDetails, isPrivate, isSensitive)
}

// Update re-encrypts details and updates the record.
func (s *SensitiveService) Update(ctx context.Context, id int64, masterPassword, description, details string, isPrivate, isSensitive bool) error {
	encDetails, err := appcrypto.EncryptRecord(ctx, s.pool, masterPassword, details, s.pepper)
	if err != nil {
		return fmt.Errorf("encrypt record: %w", err)
	}
	return s.repo.Update(ctx, id, description, encDetails, isPrivate, isSensitive)
}

// Delete removes a record. Requires a valid master password.
func (s *SensitiveService) Delete(ctx context.Context, id int64, masterPassword string) error {
	ok, err := appcrypto.CheckMasterPassword(ctx, s.pool, masterPassword, s.pepper)
	if err != nil {
		return err
	}
	if !ok {
		return fmt.Errorf("invalid master password")
	}
	return s.repo.Delete(ctx, id)
}

// GenerateMasterKey creates a fresh RSA key pair, wiping existing keys and records.
func (s *SensitiveService) GenerateMasterKey(ctx context.Context, masterPassword string) error {
	return appcrypto.GenerateMasterKey(ctx, s.pool, masterPassword, s.pepper)
}

// GenerateTrustedKey adds a trusted key for userPassword using masterPassword.
func (s *SensitiveService) GenerateTrustedKey(ctx context.Context, userPassword, masterPassword string) error {
	return appcrypto.GenerateTrustedKey(ctx, s.pool, userPassword, masterPassword, s.pepper)
}

// DeleteTrustedKey removes the trusted key for userPassword (master key cannot be deleted).
func (s *SensitiveService) DeleteTrustedKey(ctx context.Context, userPassword, masterPassword string) error {
	return appcrypto.DeleteTrustedKey(ctx, s.pool, userPassword, masterPassword, s.pepper)
}

// ── helpers ───────────────────────────────────────────────────────────────────

func (s *SensitiveService) toResponses(rows []model.SensitiveData, privateKey string) []model.SensitiveDataResponse {
	out := make([]model.SensitiveDataResponse, len(rows))
	for i, r := range rows {
		desc := r.Description
		details := redacted
		if privateKey != "" {
			plain, err := appcrypto.DecryptRecord(privateKey, r.Details)
			if err == nil {
				details = plain
			}
			// On decryption failure leave details as redacted; description stays.
		} else {
			desc = redacted
		}
		out[i] = model.SensitiveDataResponse{
			ID:          r.ID,
			Description: desc,
			Details:     details,
			IsPrivate:   r.IsPrivate,
			IsSensitive: r.IsSensitive,
			CreatedAt:   r.CreatedAt.Format(time.RFC3339),
			UpdatedAt:   r.UpdatedAt.Format(time.RFC3339),
		}
	}
	return out
}

func hasPassword(p string) bool {
	return strings.TrimSpace(p) != ""
}

func randomToken() string {
	b := make([]byte, 32)
	_, _ = rand.Read(b)
	return hex.EncodeToString(b)
}
