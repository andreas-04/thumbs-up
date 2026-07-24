// Package audit writes best-effort entries to the audit_logs table; a
// failure to log never breaks the request flow (matching utils/audit.py).
package audit

import (
	"log/slog"

	"github.com/andreas-04/terra-crate/backend/internal/store"
)

type Logger struct {
	store *store.Store
}

func New(s *store.Store) *Logger { return &Logger{store: s} }

// Entry captures the optional context for one audit record.
type Entry struct {
	TargetType  string
	TargetID    string
	Description string
	Status      string // "" defaults to "success"
	UserID      int    // 0 = unknown
	UserEmail   string
	IPAddress   string
}

// Log records an action; errors are swallowed (logged at debug level only).
func (l *Logger) Log(action string, e Entry) {
	rec := &store.AuditLog{Action: action, Status: e.Status}
	if e.TargetType != "" {
		rec.TargetType = &e.TargetType
	}
	if e.TargetID != "" {
		rec.TargetID = &e.TargetID
	}
	if e.Description != "" {
		rec.Description = &e.Description
	}
	if e.UserID != 0 {
		rec.UserID = &e.UserID
	}
	if e.UserEmail != "" {
		rec.UserEmail = &e.UserEmail
	}
	if e.IPAddress != "" {
		rec.IPAddress = &e.IPAddress
	}
	if err := l.store.InsertAuditLog(rec); err != nil {
		slog.Warn("audit: failed to write log entry", "error", err)
	}
}
