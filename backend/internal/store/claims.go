package store

import (
	"database/sql"
	"errors"
	"time"
)

// CertClaim is a one-time certificate claim token (hash only).
type CertClaim struct {
	ID        int
	UserID    int
	CreatedAt time.Time
	ExpiresAt time.Time
	UsedAt    *time.Time
}

// Claimable reports whether the claim can still be redeemed.
func (c *CertClaim) Claimable(at time.Time) bool {
	return c.UsedAt == nil && at.Before(c.ExpiresAt)
}

// CreateCertClaim issues a new claim token, superseding any outstanding
// unused claims for the same user.
func (s *Store) CreateCertClaim(tokenHash string, userID int, expiresAt time.Time) error {
	tx, err := s.db.Begin()
	if err != nil {
		return err
	}
	defer tx.Rollback()

	if _, err := tx.Exec(`DELETE FROM cert_claims WHERE user_id = ? AND used_at IS NULL`, userID); err != nil {
		return err
	}
	if _, err := tx.Exec(`INSERT INTO cert_claims (token_hash, user_id, created_at, expires_at)
		VALUES (?, ?, ?, ?)`,
		tokenHash, userID, now().UnixMicro(), expiresAt.UnixMicro()); err != nil {
		return err
	}
	return tx.Commit()
}

// CertClaimByTokenHash returns the claim for a presented token hash, or nil.
func (s *Store) CertClaimByTokenHash(tokenHash string) (*CertClaim, error) {
	var c CertClaim
	var createdAt, expiresAt int64
	var usedAt sql.NullInt64
	err := s.db.QueryRow(`SELECT id, user_id, created_at, expires_at, used_at
		FROM cert_claims WHERE token_hash = ?`, tokenHash).
		Scan(&c.ID, &c.UserID, &createdAt, &expiresAt, &usedAt)
	if errors.Is(err, sql.ErrNoRows) {
		return nil, nil
	}
	if err != nil {
		return nil, err
	}
	c.CreatedAt = timeOf(createdAt)
	c.ExpiresAt = timeOf(expiresAt)
	c.UsedAt = timePtr(usedAt)
	return &c, nil
}

// MarkCertClaimUsed consumes the claim; returns false if it was already
// used (guards against concurrent double-claims).
func (s *Store) MarkCertClaimUsed(id int) (bool, error) {
	res, err := s.db.Exec(`UPDATE cert_claims SET used_at = ? WHERE id = ? AND used_at IS NULL`,
		now().UnixMicro(), id)
	if err != nil {
		return false, err
	}
	n, err := res.RowsAffected()
	return n == 1, err
}

// DeleteExpiredCertClaims garbage-collects claims that expired before the
// cutoff.
func (s *Store) DeleteExpiredCertClaims(before time.Time) error {
	_, err := s.db.Exec(`DELETE FROM cert_claims WHERE expires_at < ?`, before.UnixMicro())
	return err
}
