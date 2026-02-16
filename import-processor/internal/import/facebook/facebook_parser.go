package facebookimport

import (
	"encoding/json"
	"fmt"
	"io"
	"path/filepath"
	"strings"
	"time"
)

// FacebookExport represents the top-level structure of a Facebook message JSON file
type FacebookExport struct {
	Title        string                `json:"title"`
	Participants []FacebookParticipant `json:"participants"`
	Messages     []FacebookMessage     `json:"messages"`
}

// FacebookParticipant represents a participant in a conversation
type FacebookParticipant struct {
	Name string `json:"name"`
}

// FacebookMessage represents a single message in the export
type FacebookMessage struct {
	TimestampMs *int64               `json:"timestamp_ms"`
	SenderName  string               `json:"sender_name"`
	Content     string               `json:"content"`
	Photos      []FacebookAttachment `json:"photos"`
	Videos      []FacebookAttachment `json:"videos"`
	Files       []FacebookAttachment `json:"files"`
	Share       *FacebookShare       `json:"share"`
	Sticker     interface{}          `json:"sticker"`
}

// FacebookAttachment represents a photo, video, or file attachment
type FacebookAttachment struct {
	URI string `json:"uri"`
}

// FacebookShare represents shared link content
type FacebookShare struct {
	Link      string `json:"link"`
	ShareText string `json:"share_text"`
}

// ParseFacebookJSON parses a Facebook message JSON file
func ParseFacebookJSON(reader io.Reader) (*FacebookExport, error) {
	var export FacebookExport
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
func DetermineMessageType(senderName, userName string, participants []FacebookParticipant) string {
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

// ExtractSubject builds subject from share link and text
func ExtractSubject(share *FacebookShare) *string {
	if share == nil {
		return nil
	}
	parts := []string{}
	if share.ShareText != "" {
		parts = append(parts, share.ShareText)
	}
	if share.Link != "" {
		parts = append(parts, share.Link)
	}
	if len(parts) == 0 {
		return nil
	}
	s := strings.TrimSpace(strings.Join(parts, " "))
	return &s
}

// FilenameFromURI extracts filename from a URI/path
func FilenameFromURI(uri string) string {
	return filepath.Base(uri)
}
