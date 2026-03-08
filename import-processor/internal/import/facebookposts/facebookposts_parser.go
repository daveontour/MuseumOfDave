package facebookpostsimport

import (
	"encoding/json"
	"fmt"
	"time"
)

// PostsExport is the top-level array of posts in the JSON file
type PostsExport []PostEntry

// PostEntry represents a single Facebook post
type PostEntry struct {
	Timestamp   *int64          `json:"timestamp"`
	Title       string          `json:"title"`
	Data        []PostDataItem  `json:"data"`
	Attachments []PostAttachment `json:"attachments"`
}

// PostDataItem holds the text content of a post
type PostDataItem struct {
	Post            string `json:"post"`
	UpdateTimestamp *int64 `json:"update_timestamp"`
}

// PostAttachment wraps an array of attachment data items
type PostAttachment struct {
	Data []PostAttachmentData `json:"data"`
}

// PostAttachmentData can be a media item or an external link
type PostAttachmentData struct {
	Media           *PostMediaItem      `json:"media"`
	ExternalContext *PostExternalContext `json:"external_context"`
}

// PostMediaItem represents a photo or video attached to a post
type PostMediaItem struct {
	URI               string `json:"uri"`
	CreationTimestamp *int64 `json:"creation_timestamp"`
	Title             string `json:"title"`
	Description       string `json:"description"`
}

// PostExternalContext holds an external URL shared in a post
type PostExternalContext struct {
	URL string `json:"url"`
}

// ParsePostsJSON parses the top-level JSON array of posts
func ParsePostsJSON(data []byte) (PostsExport, error) {
	var posts PostsExport
	if err := json.Unmarshal(data, &posts); err != nil {
		return nil, fmt.Errorf("failed to parse posts JSON: %w", err)
	}
	return posts, nil
}

// ParseTimestampSec converts a Unix timestamp in seconds to time.Time
func ParseTimestampSec(ts *int64) *time.Time {
	if ts == nil {
		return nil
	}
	t := time.Unix(*ts, 0)
	return &t
}

// ExtractPostText returns the first non-empty post text from the Data array
func ExtractPostText(entry PostEntry) string {
	for _, d := range entry.Data {
		if d.Post != "" {
			return d.Post
		}
	}
	return ""
}

// ExtractExternalURL returns the first external URL found in attachments
func ExtractExternalURL(entry PostEntry) string {
	for _, att := range entry.Attachments {
		for _, d := range att.Data {
			if d.ExternalContext != nil && d.ExternalContext.URL != "" {
				return d.ExternalContext.URL
			}
		}
	}
	return ""
}

// ExtractMediaItems returns all media items (photos/videos) from attachments
func ExtractMediaItems(entry PostEntry) []PostMediaItem {
	var items []PostMediaItem
	for _, att := range entry.Attachments {
		for _, d := range att.Data {
			if d.Media != nil && d.Media.URI != "" {
				items = append(items, *d.Media)
			}
		}
	}
	return items
}

// DeterminePostType returns the post type based on content
func DeterminePostType(entry PostEntry) string {
	hasText := ExtractPostText(entry) != ""
	hasLink := ExtractExternalURL(entry) != ""
	hasMedia := len(ExtractMediaItems(entry)) > 0

	switch {
	case hasMedia && (hasText || hasLink):
		return "mixed"
	case hasMedia:
		return "photo"
	case hasLink:
		return "link"
	default:
		return "status"
	}
}
