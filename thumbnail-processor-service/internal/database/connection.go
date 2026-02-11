package database

import (
	"context"
	"fmt"
	"runtime"

	"github.com/jackc/pgx/v5/pgxpool"
	"thumbnail-processor-service/internal/config"
)

// DB wraps the PostgreSQL connection pool
type DB struct {
	Pool *pgxpool.Pool
}

// NewDB creates a new database connection pool
func NewDB(cfg *config.Config) (*DB, error) {
	connString := cfg.DB.ConnectionString()

	poolConfig, err := pgxpool.ParseConfig(connString)
	if err != nil {
		return nil, fmt.Errorf("failed to parse connection string: %w", err)
	}

	// Set connection pool settings
	// Use CPU count * 2 for parallel processing, minimum 10, maximum 50
	maxConns := runtime.NumCPU() * 2
	if maxConns < 10 {
		maxConns = 10
	}
	if maxConns > 50 {
		maxConns = 50
	}
	poolConfig.MaxConns = int32(maxConns)
	poolConfig.MinConns = 2
	poolConfig.MaxConnLifetime = 0 // No max lifetime
	poolConfig.MaxConnIdleTime = 0 // No max idle time

	pool, err := pgxpool.NewWithConfig(context.Background(), poolConfig)
	if err != nil {
		return nil, fmt.Errorf("failed to create connection pool: %w", err)
	}

	// Test the connection
	ctx := context.Background()
	if err := pool.Ping(ctx); err != nil {
		pool.Close()
		return nil, fmt.Errorf("failed to ping database: %w", err)
	}

	return &DB{Pool: pool}, nil
}

// Close closes the database connection pool
func (db *DB) Close() {
	if db.Pool != nil {
		db.Pool.Close()
	}
}

// GetPool returns the connection pool
func (db *DB) GetPool() *pgxpool.Pool {
	return db.Pool
}
