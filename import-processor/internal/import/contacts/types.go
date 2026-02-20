package contacts

import "import-processor/internal/database"

// InputRecord represents a contact record from input (JSON or database)
type InputRecord struct {
	Email string   `json:"email"`
	Names []string `json:"names"`
}

// FormattedOutputRecord is the output format (comma-separated strings)
type FormattedOutputRecord struct {
	ID               int    `json:"id"`
	PrimaryName      string `json:"primary_name"`
	AlternativeNames string `json:"alternative_names"`
	Emails           string `json:"emails"`
	NumWhatsApp      int64  `json:"num_whatsapp,omitempty"`
	NumIMessage      int64  `json:"num_imessage,omitempty"`
	NumFacebook      int64  `json:"num_facebook,omitempty"`
	NumSMS           int64  `json:"num_sms,omitempty"`
	NumInstagram     int64  `json:"num_instagram,omitempty"`
	IsGroupChat      bool   `json:"is_group_chat,omitempty"`
}

// Group holds merged contact data during processing
type Group struct {
	Names         map[string]struct{}
	Emails        map[string]struct{}
	Normalized    map[string]struct{}
	NameFrequency map[string]int
	MergeScores   []float64
}

// RelationshipRecord represents a from-to relationship
type RelationshipRecord struct {
	From string
	To   string
}

// SocialMediaRecord holds per-chat message counts by service
type SocialMediaRecord struct {
	ChatSession  *string
	IsGroupChat  bool
	NumWhatsApp  int64
	NumIMessage  int64
	NumFacebook  int64
	NumSMS       int64
	NumInstagram int64
	Total        int64
}

// RunOptions holds options for RunContactsNormalise
type RunOptions struct {
	Workers             int
	InputFile           string // "" or filename (stdin not supported)
	EmailMatchesFile    string
	ExclusionsFile      string
	ClassificationsFile string // JSON file for rel_type mappings (applied after DB write)
	ContactsQuery       string
	RelationshipQuery   string
	ContactsDB          *database.DB // DB for contacts and relationships; used for ReadFromDatabase, WriteContactsToDatabase, findRelationships
}
