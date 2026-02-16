package instagramimport

import (
	"encoding/json"
	"fmt"
	"io"
	"path/filepath"
	"regexp"
	"strings"
	"time"
)

var cleanStringRegex = regexp.MustCompile(`[^\w\s]`)

// InstagramExport represents the top-level structure of an Instagram message JSON file
type InstagramExport struct {
	Title        string                 `json:"title"`
	Participants []InstagramParticipant `json:"participants"`
	Messages     []InstagramMessage     `json:"messages"`
}

// InstagramParticipant represents a participant in a conversation
type InstagramParticipant struct {
	Name string `json:"name"`
}

// InstagramMessage represents a single message in the export
type InstagramMessage struct {
	TimestampMs *int64                `json:"timestamp_ms"`
	SenderName  string                `json:"sender_name"`
	Content     string                `json:"content"`
	Photos      []InstagramAttachment `json:"photos"`
}

// InstagramAttachment represents a photo attachment
type InstagramAttachment struct {
	URI string `json:"uri"`
}

// ParseInstagramJSON parses an Instagram message JSON file
func ParseInstagramJSON(reader io.Reader) (*InstagramExport, error) {
	var export InstagramExport
	dec := json.NewDecoder(reader)
	dec.UseNumber()
	if err := dec.Decode(&export); err != nil {
		return nil, fmt.Errorf("failed to parse JSON: %w", err)
	}
	return &export, nil
}

// ParseTimestampMs converts Unix timestamp in milliseconds to time.Time
func ParseTimestampMs(ts *int64) (*time.Time, error) {
	if ts == nil {
		return nil, nil
	}
	t := time.UnixMilli(*ts)
	return &t, nil
}

// DetermineMessageType returns "Incoming" or "Outgoing" based on sender
func DetermineMessageType(senderName, userName string, participants []InstagramParticipant) string {
	if userName != "" {
		if senderName == userName {
			return "Outgoing"
		}
		return "Incoming"
	}
	if len(participants) > 0 {
		first := participants[0].Name
		if senderName == first {
			return "Outgoing"
		}
		return "Incoming"
	}
	return "Incoming"
}

// CleanString strips non-word characters (except spaces) from a string
func CleanString(s string) string {
	return strings.TrimSpace(cleanStringRegex.ReplaceAllString(s, ""))
}

// FilenameFromURI extracts filename from a URI/path
func FilenameFromURI(uri string) string {
	return filepath.Base(uri)
}
