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
	// WhatsAppDirectoryPath is required for whatsapp subcommand
	WhatsAppDirectoryPath string
	// IMessageDirectoryPath is required for imessage subcommand
	IMessageDirectoryPath string
	// FacebookDirectoryPath is required for facebook subcommand
	FacebookDirectoryPath string
	// FacebookAlbumsDirectoryPath is required for facebook-albums subcommand
	FacebookAlbumsDirectoryPath string
	// FacebookPlacesPath is required for facebook-places subcommand (file or directory)
	FacebookPlacesPath string
	// InstagramDirectoryPath is required for instagram subcommand
	InstagramDirectoryPath string
	// FilesystemImportDirectories is comma-separated list for filesystem subcommand
	FilesystemImportDirectories string
	// FilesystemExcludePatterns is comma-separated fnmatch patterns
	FilesystemExcludePatterns string
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

	cfg.WhatsAppDirectoryPath = os.Getenv("WHATSAPP_DIRECTORY_PATH")
	cfg.IMessageDirectoryPath = os.Getenv("IMESSAGE_DIRECTORY_PATH")
	cfg.FacebookDirectoryPath = os.Getenv("FACEBOOK_DIRECTORY_PATH")
	cfg.FacebookAlbumsDirectoryPath = os.Getenv("FACEBOOK_ALBUMS_DIRECTORY_PATH")
	cfg.FacebookPlacesPath = os.Getenv("FACEBOOK_PLACES_PATH")
	cfg.InstagramDirectoryPath = os.Getenv("INSTAGRAM_DIRECTORY_PATH")
	cfg.FilesystemImportDirectories = os.Getenv("FILESYSTEM_IMPORT_DIRECTORIES")
	cfg.FilesystemExcludePatterns = os.Getenv("FILESYSTEM_EXCLUDE_PATTERNS")

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
