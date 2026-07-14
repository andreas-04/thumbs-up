package httpapi

import (
	"strings"
	"time"
)

var sinceLayouts = []string{
	time.RFC3339Nano,
	time.RFC3339,
	"2006-01-02T15:04:05.999999",
	"2006-01-02T15:04:05",
	"2006-01-02",
}

// parseSince parses the `since` query parameter; RFC 3339 preferred, naive
// timestamps interpreted as UTC.
func parseSince(s string) (time.Time, bool) {
	s = strings.TrimSpace(s)
	for _, layout := range sinceLayouts {
		if t, err := time.ParseInLocation(layout, s, time.UTC); err == nil {
			return t, true
		}
	}
	return time.Time{}, false
}
