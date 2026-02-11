package config

import (
	"fmt"
	"os"
	"strconv"

	"github.com/joho/godotenv"
)

// Config holds application configuration
type Config struct {
	DB DatabaseConfig
}

// DatabaseConfig holds database connection settings
type DatabaseConfig struct {
	Host     string
	Port     int
	Name     string
	User     string
	Password string
}

// ConnectionString returns PostgreSQL connection string for pgx
func (d *DatabaseConfig) ConnectionString() string {
	return fmt.Sprintf("host=%s port=%d dbname=%s user=%s password=%s", d.Host, d.Port, d.Name, d.User, d.Password)
}

// Load loads configuration from environment variables
func Load() (*Config, error) {
	// Try to load .env file (ignore error if not found)
	_ = godotenv.Load()

	cfg := &Config{}

	// Load database configuration
	dbConfig, err := loadDatabaseConfig()
	if err != nil {
		return nil, fmt.Errorf("failed to load database config: %w", err)
	}
	cfg.DB = *dbConfig

	return cfg, nil
}

func loadDatabaseConfig() (*DatabaseConfig, error) {
	host := os.Getenv("DB_HOST")
	portStr := os.Getenv("DB_PORT")
	name := os.Getenv("DB_NAME")
	user := os.Getenv("DB_USER")
	password := os.Getenv("DB_PASSWORD")

	if host == "" || name == "" || user == "" || password == "" {
		return nil, fmt.Errorf("missing required database configuration. Set DB_HOST, DB_NAME, DB_USER, and DB_PASSWORD environment variables")
	}

	port := 5432
	if portStr != "" {
		var err error
		port, err = strconv.Atoi(portStr)
		if err != nil {
			return nil, fmt.Errorf("DB_PORT must be an integer, got: %s", portStr)
		}
	}

	return &DatabaseConfig{
		Host:     host,
		Port:     port,
		Name:     name,
		User:     user,
		Password: password,
	}, nil
}
