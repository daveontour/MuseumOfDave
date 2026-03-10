// Package repository contains pgx query implementations.
package repository

import (
	"context"
	"fmt"
	"strings"

	"github.com/jackc/pgx/v5/pgxpool"
	"github.com/museum-of-dave/app/internal/model"
)

// EmailRepo runs queries against the emails and related tables.
type EmailRepo struct {
	pool *pgxpool.Pool
}

// NewEmailRepo creates an EmailRepo backed by the given pool.
func NewEmailRepo(pool *pgxpool.Pool) *EmailRepo {
	return &EmailRepo{pool: pool}
}

// GetByID returns a non-deleted email by primary key, or nil if not found.
func (r *EmailRepo) GetByID(ctx context.Context, id int64) (*model.Email, error) {
	row := r.pool.QueryRow(ctx, `
		SELECT id, uid, folder, subject, from_address, to_addresses, cc_addresses, bcc_addresses,
		       date, raw_message, plain_text, snippet, embedding,
		       has_attachments, user_deleted, is_personal, is_business, is_social, is_promotional,
		       is_spam, is_important, use_by_ai, created_at, updated_at
		FROM emails
		WHERE id = $1
		  AND user_deleted = FALSE`, id)

	e := &model.Email{}
	err := row.Scan(
		&e.ID, &e.UID, &e.Folder, &e.Subject, &e.FromAddress, &e.ToAddresses,
		&e.CCAddresses, &e.BCCAddresses, &e.Date, &e.RawMessage, &e.PlainText,
		&e.Snippet, &e.Embedding, &e.HasAttachments, &e.UserDeleted,
		&e.IsPersonal, &e.IsBusiness, &e.IsSocial, &e.IsPromotional,
		&e.IsSpam, &e.IsImportant, &e.UseByAI, &e.CreatedAt, &e.UpdatedAt,
	)
	if err != nil {
		if isNoRows(err) {
			return nil, nil
		}
		return nil, fmt.Errorf("email GetByID %d: %w", id, err)
	}
	return e, nil
}

// Search returns emails matching the given optional filters, ordered by date DESC.
// All filters are AND-combined; within to_from the addresses are OR-combined.
func (r *EmailRepo) Search(ctx context.Context, p model.EmailSearchParams) ([]*model.Email, error) {
	var (
		conds []string
		args  []any
		n     = 1
	)

	add := func(cond string, val any) {
		conds = append(conds, strings.ReplaceAll(cond, "?", fmt.Sprintf("$%d", n)))
		args = append(args, val)
		n++
	}

	if p.FromAddress != nil {
		add("from_address ILIKE ?", "%"+*p.FromAddress+"%")
	}
	if p.ToAddress != nil {
		add("to_addresses ILIKE ?", "%"+*p.ToAddress+"%")
	}
	if p.Month != nil {
		add("EXTRACT(month FROM date) = ?", *p.Month)
	}
	if p.Year != nil {
		add("EXTRACT(year FROM date) = ?", *p.Year)
	}
	if p.Subject != nil {
		add("subject ILIKE ?", "%"+*p.Subject+"%")
	}
	if p.ToFrom != nil {
		parts := splitTrim(*p.ToFrom, ',')
		if len(parts) > 0 {
			var orParts []string
			for _, addr := range parts {
				orParts = append(orParts,
					fmt.Sprintf("(to_addresses ILIKE $%d OR from_address ILIKE $%d)", n, n+1),
				)
				args = append(args, "%"+addr+"%", "%"+addr+"%")
				n += 2
			}
			conds = append(conds, "("+strings.Join(orParts, " OR ")+")")
		}
	}
	if p.HasAttachments != nil {
		add("has_attachments = ?", *p.HasAttachments)
	}
	// Always exclude soft-deleted rows
	conds = append(conds, "user_deleted = FALSE")

	sql := `SELECT id, uid, folder, subject, from_address, to_addresses, cc_addresses, bcc_addresses,
			       date, raw_message, plain_text, snippet, embedding,
			       has_attachments, user_deleted, is_personal, is_business, is_social, is_promotional,
			       is_spam, is_important, use_by_ai, created_at, updated_at
			FROM emails`
	if len(conds) > 0 {
		sql += " WHERE " + strings.Join(conds, " AND ")
	}
	sql += " ORDER BY date DESC"

	rows, err := r.pool.Query(ctx, sql, args...)
	if err != nil {
		return nil, fmt.Errorf("email Search: %w", err)
	}
	defer rows.Close()
	return scanEmails(rows)
}

// GetByLabels returns non-deleted emails whose folder column matches any of the given labels.
// The folder column can be a comma-separated list of labels (e.g. "INBOX,IMPORTANT").
func (r *EmailRepo) GetByLabels(ctx context.Context, labels []string) ([]*model.Email, error) {
	if len(labels) == 0 {
		return nil, nil
	}

	// Build OR conditions: exact match OR starts with "label," OR contains ",label," OR ends with ",label"
	var conds []string
	var args []any
	n := 1
	for _, label := range labels {
		conds = append(conds,
			fmt.Sprintf("(folder = $%d OR folder LIKE $%d OR folder LIKE $%d OR folder LIKE $%d)",
				n, n+1, n+2, n+3),
		)
		args = append(args,
			label,
			label+",%",
			"%, "+label+",%",
			"%, "+label,
		)
		n += 4
	}

	sql := `SELECT id, uid, folder, subject, from_address, to_addresses, cc_addresses, bcc_addresses,
			       date, raw_message, plain_text, snippet, embedding,
			       has_attachments, user_deleted, is_personal, is_business, is_social, is_promotional,
			       is_spam, is_important, use_by_ai, created_at, updated_at
			FROM emails
			WHERE (` + strings.Join(conds, " OR ") + `) AND user_deleted = FALSE`

	rows, err := r.pool.Query(ctx, sql, args...)
	if err != nil {
		return nil, fmt.Errorf("email GetByLabels: %w", err)
	}
	defer rows.Close()
	return scanEmails(rows)
}

// GetAttachmentIDsForEmails returns a map of emailID → []mediaItemID for all given email IDs.
// Uses a single query to avoid N+1 round trips.
func (r *EmailRepo) GetAttachmentIDsForEmails(ctx context.Context, emailIDs []int64) (map[int64][]int64, error) {
	result := make(map[int64][]int64, len(emailIDs))
	if len(emailIDs) == 0 {
		return result, nil
	}

	// source_reference is VARCHAR storing the string form of the email ID
	idStrs := make([]string, len(emailIDs))
	for i, id := range emailIDs {
		idStrs[i] = fmt.Sprintf("%d", id)
		result[id] = []int64{} // ensure key exists even if no attachments
	}

	rows, err := r.pool.Query(ctx, `
		SELECT source_reference, id
		FROM media_items
		WHERE source = 'email_attachment'
		  AND source_reference = ANY($1::text[])
		ORDER BY id`, idStrs)
	if err != nil {
		return nil, fmt.Errorf("GetAttachmentIDsForEmails: %w", err)
	}
	defer rows.Close()

	for rows.Next() {
		var ref string
		var mediaID int64
		if err := rows.Scan(&ref, &mediaID); err != nil {
			return nil, err
		}
		// parse back to int64
		var emailID int64
		if _, err := fmt.Sscanf(ref, "%d", &emailID); err == nil {
			result[emailID] = append(result[emailID], mediaID)
		}
	}
	return result, rows.Err()
}

// ── helpers ───────────────────────────────────────────────────────────────────

// scanEmails collects rows into a slice of Email pointers.
func scanEmails(rows interface {
	Next() bool
	Scan(dest ...any) error
	Err() error
}) ([]*model.Email, error) {
	var emails []*model.Email
	for rows.Next() {
		e := &model.Email{}
		if err := rows.Scan(
			&e.ID, &e.UID, &e.Folder, &e.Subject, &e.FromAddress, &e.ToAddresses,
			&e.CCAddresses, &e.BCCAddresses, &e.Date, &e.RawMessage, &e.PlainText,
			&e.Snippet, &e.Embedding, &e.HasAttachments, &e.UserDeleted,
			&e.IsPersonal, &e.IsBusiness, &e.IsSocial, &e.IsPromotional,
			&e.IsSpam, &e.IsImportant, &e.UseByAI, &e.CreatedAt, &e.UpdatedAt,
		); err != nil {
			return nil, err
		}
		emails = append(emails, e)
	}
	return emails, rows.Err()
}

// isNoRows returns true for pgx "no rows in result set" error.
func isNoRows(err error) bool {
	return err != nil && err.Error() == "no rows in result set"
}

// splitTrim splits s by sep and trims whitespace from each element, omitting blanks.
func splitTrim(s string, sep rune) []string {
	parts := strings.FieldsFunc(s, func(r rune) bool { return r == sep })
	out := make([]string, 0, len(parts))
	for _, p := range parts {
		if t := strings.TrimSpace(p); t != "" {
			out = append(out, t)
		}
	}
	return out
}
