package repository

import (
	"context"
	"fmt"

	"github.com/jackc/pgx/v5/pgxpool"
	"github.com/museum-of-dave/app/internal/model"
)

// DocumentRepo accesses the reference_documents table.
type DocumentRepo struct {
	pool *pgxpool.Pool
}

// NewDocumentRepo creates a DocumentRepo.
func NewDocumentRepo(pool *pgxpool.Pool) *DocumentRepo {
	return &DocumentRepo{pool: pool}
}

const documentCols = `id, filename, title, description, author, content_type, size,
	tags, categories, notes, available_for_task, created_at, updated_at`

func scanDocument(row interface{ Scan(...any) error }) (*model.ReferenceDocument, error) {
	var d model.ReferenceDocument
	err := row.Scan(
		&d.ID, &d.Filename, &d.Title, &d.Description, &d.Author,
		&d.ContentType, &d.Size, &d.Tags, &d.Categories, &d.Notes,
		&d.AvailableForTask, &d.CreatedAt, &d.UpdatedAt,
	)
	if err != nil {
		return nil, err
	}
	return &d, nil
}

// List returns documents with optional filters.
func (r *DocumentRepo) List(ctx context.Context, search, category, tag, contentType string, availableForTask *bool) ([]*model.ReferenceDocument, error) {
	q := `SELECT ` + documentCols + ` FROM reference_documents`
	var args []any
	var conds []string

	if search != "" {
		args = append(args, "%"+search+"%")
		idx := len(args)
		conds = append(conds, fmt.Sprintf(
			`(filename ILIKE $%d OR title ILIKE $%d OR description ILIKE $%d OR author ILIKE $%d)`,
			idx, idx, idx, idx,
		))
	}
	if category != "" {
		args = append(args, "%"+category+"%")
		conds = append(conds, fmt.Sprintf("categories ILIKE $%d", len(args)))
	}
	if tag != "" {
		args = append(args, "%"+tag+"%")
		conds = append(conds, fmt.Sprintf("tags ILIKE $%d", len(args)))
	}
	if availableForTask != nil {
		args = append(args, *availableForTask)
		conds = append(conds, fmt.Sprintf("available_for_task = $%d", len(args)))
	}
	if contentType != "" {
		args = append(args, "%"+contentType+"%")
		conds = append(conds, fmt.Sprintf("content_type ILIKE $%d", len(args)))
	}
	if len(conds) > 0 {
		q += " WHERE " + joinAnd(conds)
	}
	q += " ORDER BY created_at DESC"

	rows, err := r.pool.Query(ctx, q, args...)
	if err != nil {
		return nil, fmt.Errorf("ListDocuments: %w", err)
	}
	defer rows.Close()

	var out []*model.ReferenceDocument
	for rows.Next() {
		d, err := scanDocument(rows)
		if err != nil {
			return nil, err
		}
		out = append(out, d)
	}
	return out, rows.Err()
}

// GetByID returns a document's metadata (no blob data).
func (r *DocumentRepo) GetByID(ctx context.Context, id int64) (*model.ReferenceDocument, error) {
	d, err := scanDocument(r.pool.QueryRow(ctx,
		`SELECT `+documentCols+` FROM reference_documents WHERE id = $1`, id))
	if err != nil {
		if isNoRows(err) {
			return nil, nil
		}
		return nil, fmt.Errorf("GetDocumentByID %d: %w", id, err)
	}
	return d, nil
}

// GetData returns the raw file bytes for a document.
func (r *DocumentRepo) GetData(ctx context.Context, id int64) ([]byte, error) {
	var data []byte
	err := r.pool.QueryRow(ctx, `SELECT data FROM reference_documents WHERE id = $1`, id).Scan(&data)
	if err != nil {
		if isNoRows(err) {
			return nil, nil
		}
		return nil, err
	}
	return data, nil
}

// Create inserts a new reference document.
func (r *DocumentRepo) Create(ctx context.Context,
	filename, contentType string, size int64, data []byte,
	title, description, author, tags, categories, notes *string,
	availableForTask bool,
) (*model.ReferenceDocument, error) {
	d, err := scanDocument(r.pool.QueryRow(ctx,
		`INSERT INTO reference_documents
		 (filename, title, description, author, content_type, size, data,
		  tags, categories, notes, available_for_task)
		 VALUES ($1,$2,$3,$4,$5,$6,$7,$8,$9,$10,$11)
		 RETURNING `+documentCols,
		filename, title, description, author, contentType, size, data,
		tags, categories, notes, availableForTask,
	))
	if err != nil {
		return nil, fmt.Errorf("CreateDocument: %w", err)
	}
	return d, nil
}

// Update modifies document metadata fields.
func (r *DocumentRepo) Update(ctx context.Context, id int64,
	title, description, author, tags, categories, notes *string,
	availableForTask *bool,
) (*model.ReferenceDocument, error) {
	d, err := scanDocument(r.pool.QueryRow(ctx,
		`UPDATE reference_documents SET
		 title            = COALESCE($1, title),
		 description      = COALESCE($2, description),
		 author           = COALESCE($3, author),
		 tags             = COALESCE($4, tags),
		 categories       = COALESCE($5, categories),
		 notes            = COALESCE($6, notes),
		 available_for_task = COALESCE($7, available_for_task),
		 updated_at       = NOW()
		 WHERE id = $8
		 RETURNING `+documentCols,
		title, description, author, tags, categories, notes, availableForTask, id,
	))
	if err != nil {
		if isNoRows(err) {
			return nil, nil
		}
		return nil, fmt.Errorf("UpdateDocument %d: %w", id, err)
	}
	return d, nil
}

// Delete removes a reference document.
func (r *DocumentRepo) Delete(ctx context.Context, id int64) error {
	_, err := r.pool.Exec(ctx, `DELETE FROM reference_documents WHERE id = $1`, id)
	return err
}
