package contacts

import (
	"context"
	"encoding/json"
	"fmt"
	"os"
	"strings"

	"import-processor/internal/database"
)

// EmailClassifications maps rel_type values to lists of contact names
type EmailClassifications map[string][]string

var relTypeKeys = []string{
	"friend", "family", "colleague", "acquaintance",
	"business", "social", "promotional", "spam", "important",
}

// LoadEmailClassifications loads classifications from a JSON file.
// Keys are rel_type values (friend, family, colleague, etc.).
func LoadEmailClassifications(filename string) (EmailClassifications, error) {
	raw, err := os.ReadFile(filename)
	if err != nil {
		return nil, fmt.Errorf("read classifications file: %w", err)
	}
	var m map[string][]string
	if err := json.Unmarshal(raw, &m); err != nil {
		return nil, fmt.Errorf("parse classifications JSON: %w", err)
	}
	result := make(EmailClassifications)
	for k, names := range m {
		if names == nil {
			result[k] = nil
		} else {
			result[k] = names
		}
	}
	for _, key := range relTypeKeys {
		if _, ok := result[key]; !ok {
			result[key] = nil
		}
	}
	return result, nil
}

// ApplyClassificationsToContacts updates contacts by name using the classification lists.
// Matches against contact name and alternative_names (comma-separated). Case-insensitive.
func ApplyClassificationsToContacts(ctx context.Context, db *database.DB, classifications EmailClassifications) error {
	if len(classifications) == 0 {
		return nil
	}

	// Build normalized name set for each rel_type
	relTypeToNames := make(map[string]map[string]struct{})
	for relType, names := range classifications {
		if len(names) == 0 {
			continue
		}
		m := make(map[string]struct{})
		for _, n := range names {
			norm := strings.ToLower(strings.TrimSpace(n))
			if norm != "" {
				m[norm] = struct{}{}
			}
		}
		if len(m) > 0 {
			relTypeToNames[relType] = m
		}
	}
	if len(relTypeToNames) == 0 {
		return nil
	}

	// Fetch all contacts
	rows, err := db.Pool.Query(ctx, "SELECT id, name, alternative_names FROM contacts")
	if err != nil {
		return fmt.Errorf("query contacts: %w", err)
	}
	defer rows.Close()

	type contact struct {
		id               int
		name             string
		alternativeNames *string
	}

	var contacts []contact
	for rows.Next() {
		var c contact
		if err := rows.Scan(&c.id, &c.name, &c.alternativeNames); err != nil {
			return fmt.Errorf("scan contact: %w", err)
		}
		contacts = append(contacts, c)
	}
	if err := rows.Err(); err != nil {
		return fmt.Errorf("iterate contacts: %w", err)
	}

	// For each rel_type, collect contact IDs that match
	updates := make(map[string][]int)
	for relType, nameSet := range relTypeToNames {
		for _, c := range contacts {
			names := []string{strings.TrimSpace(c.name)}
			if c.alternativeNames != nil && *c.alternativeNames != "" {
				for _, alt := range strings.Split(*c.alternativeNames, ",") {
					alt = strings.TrimSpace(alt)
					if alt != "" {
						names = append(names, alt)
					}
				}
			}
			for _, n := range names {
				if _, ok := nameSet[strings.ToLower(n)]; ok {
					if c.id != 0 {
						updates[relType] = append(updates[relType], c.id)
					}
					break
				}
			}
		}
	}

	// Reset all contacts to unknown
	_, err = db.Pool.Exec(ctx, "UPDATE contacts SET rel_type = 'unknown' WHERE id != 0")
	if err != nil {
		return fmt.Errorf("update contacts: %w", err)
	}

	// Apply each rel_type to matching contacts
	for _, relType := range relTypeKeys {
		ids := updates[relType]
		if len(ids) == 0 {
			continue
		}
		placeholders := make([]string, len(ids))
		args := make([]interface{}, len(ids)+1)
		args[0] = relType
		for i, id := range ids {
			placeholders[i] = fmt.Sprintf("$%d", i+2)
			args[i+1] = id
		}
		query := fmt.Sprintf("UPDATE contacts SET rel_type = $1 WHERE id IN (%s)", strings.Join(placeholders, ","))
		_, err = db.Pool.Exec(ctx, query, args...)
		if err != nil {
			return fmt.Errorf("update rel_type=%s: %w", relType, err)
		}
	}

	// Ensure subject (id=0) always stays unknown
	_, err = db.Pool.Exec(ctx, "UPDATE contacts SET rel_type = 'unknown' WHERE id = 0")
	if err != nil {
		return fmt.Errorf("reset subject rel_type: %w", err)
	}

	return nil
}
