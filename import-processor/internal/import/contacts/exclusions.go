package contacts

import (
	"encoding/json"
	"fmt"
	"os"
	"strings"
)

// NameEmailPair excludes a specific name when paired with a specific email
// (e.g. recipient name incorrectly paired with sender's email in source data)
type NameEmailPair struct {
	Name  string `json:"name"`
	Email string `json:"email"`
}

// ExclusionsConfig holds email and name exclusion patterns
type ExclusionsConfig struct {
	Email      []string       `json:"email"`
	Name       []string       `json:"name"`
	NameEmail  []NameEmailPair `json:"name_email"`
}

var defaultNameEmailExclusions = []NameEmailPair{
	{Name: "Kerri Whitney", Email: "dave_on_tour@yahoo.com"},
}

var defaultExclusions = ExclusionsConfig{
	Email: []string{
		"no-reply", "noreply", "no-response", "noresponse",
		"no-reply@", "noreply@", "no-response@", "noresponse@",
		"/O=", "thales", "marketing", "info@", "news@", "mail@",
		"help@", "contact@", "customer-service@",
		"customer-support@", "billing@", "accounts@", "hello@", "undisclosed@",
		"notification@", "ticket@", "tickets@", "ticketing@", "ticketing-system@",
		"ticketing-system-email@", "ticketing-system-email-address@", "do-not-reply@",
		"helpdesk@", "no_reply", "customerservice@", "support@",
		"feedback@", "online@", "order-update@", "shipment-tracking@",
		"auto-confirm@", "messages@", "socials@", "newsletters@", "admin@",
	},
	Name: []string{
		"news@", "mail@", "help@", "contact@", "customer-service@",
		"customer-support@", "billing@", "accounts@", "info@", "hello@",
		"undisclosed", "/O=", "satyam", "thales", "marketing",
	},
	NameEmail: defaultNameEmailExclusions,
}

var exclusions = defaultExclusions

// LoadExclusions loads exclusions from a JSON file
func LoadExclusions(filename string) error {
	raw, err := os.ReadFile(filename)
	if err != nil {
		return fmt.Errorf("failed to read exclusions file: %w", err)
	}
	var cfg ExclusionsConfig
	if err := json.Unmarshal(raw, &cfg); err != nil {
		return fmt.Errorf("failed to parse exclusions JSON: %w", err)
	}
	exclusions = cfg
	exclusions.NameEmail = append(defaultNameEmailExclusions, exclusions.NameEmail...)
	return nil
}

func isExcluded(name, email string) bool {
	for _, exclusion := range exclusions.Email {
		if strings.Contains(email, exclusion) {
			return true
		}
	}
	for _, exclusion := range exclusions.Name {
		if strings.Contains(name, exclusion) {
			return true
		}
	}
	for _, pair := range exclusions.NameEmail {
		if strings.EqualFold(name, pair.Name) && strings.EqualFold(email, pair.Email) {
			return true
		}
	}
	return false
}
