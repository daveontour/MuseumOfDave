package contacts

import (
	"encoding/json"
	"fmt"
	"os"
)

// EmailMatchSet represents a set of emails that are the same person
type EmailMatchSet struct {
	PrimaryName string   `json:"primary_name"`
	Emails      []string `json:"emails"`
}

func buildTransitiveClosure(emailSets []EmailMatchSet) (map[string]string, map[string]string) {
	canonical := make(map[string]string)
	var find func(string) string
	find = func(email string) string {
		if rep, ok := canonical[email]; ok {
			if rep != email {
				root := find(rep)
				canonical[email] = root
				return root
			}
			return rep
		}
		canonical[email] = email
		return email
	}
	union := func(email1, email2 string) {
		root1 := find(email1)
		root2 := find(email2)
		if root1 != root2 {
			if root1 < root2 {
				canonical[root2] = root1
			} else {
				canonical[root1] = root2
			}
		}
	}
	canonicalToPrimaryName := make(map[string]string)
	for _, emailSet := range emailSets {
		if len(emailSet.Emails) == 0 {
			continue
		}
		normalizedEmails := make([]string, len(emailSet.Emails))
		for i, email := range emailSet.Emails {
			normalizedEmails[i] = NormalizeEmailForMatching(email)
		}
		if len(normalizedEmails) > 0 {
			firstEmail := normalizedEmails[0]
			for i := 1; i < len(normalizedEmails); i++ {
				union(firstEmail, normalizedEmails[i])
			}
			canonicalRep := find(firstEmail)
			if emailSet.PrimaryName != "" {
				canonicalToPrimaryName[canonicalRep] = emailSet.PrimaryName
			}
		}
	}
	result := make(map[string]string)
	for _, emailSet := range emailSets {
		for _, email := range emailSet.Emails {
			normalized := NormalizeEmailForMatching(email)
			result[normalized] = find(normalized)
		}
	}
	return result, canonicalToPrimaryName
}

// LoadEmailMatchSets loads email match sets from a JSON file
func LoadEmailMatchSets(filename string) (map[string]string, map[string]string, error) {
	raw, err := os.ReadFile(filename)
	if err != nil {
		return nil, nil, fmt.Errorf("failed to read email matches file: %w", err)
	}
	var emailSets []EmailMatchSet
	if err := json.Unmarshal(raw, &emailSets); err != nil {
		return nil, nil, fmt.Errorf("failed to parse email matches JSON: %w", err)
	}
	canonicalMap, primaryNameMap := buildTransitiveClosure(emailSets)
	return canonicalMap, primaryNameMap, nil
}
