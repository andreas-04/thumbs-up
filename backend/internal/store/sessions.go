package store

import (
	"database/sql"
	"errors"
	"time"
)

// Session is a revocable bearer session; the token itself is never stored,
// only its SHA-256 hash.
type Session struct {
	ID        int
	UserID    int
	CreatedAt time.Time
	ExpiresAt time.Time
	RevokedAt *time.Time
}

// Valid reports whether the session is usable at the given instant.
func (s *Session) Valid(at time.Time) bool {
	return s.RevokedAt == nil && at.Before(s.ExpiresAt)
}

func (s *Store) CreateSession(tokenHash string, userID int, expiresAt time.Time) (*Session, error) {
	created := now()
	res, err := s.db.Exec(`INSERT INTO sessions (token_hash, user_id, created_at, expires_at)
		VALUES (?, ?, ?, ?)`,
		tokenHash, userID, created.UnixMicro(), expiresAt.UnixMicro())
	if err != nil {
		return nil, err
	}
	id, err := res.LastInsertId()
	if err != nil {
		return nil, err
	}
	return &Session{ID: int(id), UserID: userID, CreatedAt: created, ExpiresAt: expiresAt}, nil
}

// SessionByTokenHash returns the session for a presented token hash, or nil.
func (s *Store) SessionByTokenHash(tokenHash string) (*Session, error) {
	var sess Session
	var createdAt, expiresAt int64
	var revokedAt sql.NullInt64
	err := s.db.QueryRow(`SELECT id, user_id, created_at, expires_at, revoked_at
		FROM sessions WHERE token_hash = ?`, tokenHash).
		Scan(&sess.ID, &sess.UserID, &createdAt, &expiresAt, &revokedAt)
	if errors.Is(err, sql.ErrNoRows) {
		return nil, nil
	}
	if err != nil {
		return nil, err
	}
	sess.CreatedAt = timeOf(createdAt)
	sess.ExpiresAt = timeOf(expiresAt)
	sess.RevokedAt = timePtr(revokedAt)
	return &sess, nil
}

func (s *Store) RevokeSession(id int) error {
	_, err := s.db.Exec(`UPDATE sessions SET revoked_at = ? WHERE id = ? AND revoked_at IS NULL`,
		now().UnixMicro(), id)
	return err
}

// RevokeUserSessions revokes every active session for a user (password
// change, account compromise).
func (s *Store) RevokeUserSessions(userID int) error {
	_, err := s.db.Exec(`UPDATE sessions SET revoked_at = ? WHERE user_id = ? AND revoked_at IS NULL`,
		now().UnixMicro(), userID)
	return err
}

// DeleteExpiredSessions garbage-collects sessions that expired before the
// cutoff.
func (s *Store) DeleteExpiredSessions(before time.Time) error {
	_, err := s.db.Exec(`DELETE FROM sessions WHERE expires_at < ?`, before.UnixMicro())
	return err
}
