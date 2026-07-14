package store

import (
	"database/sql"
	"time"
)

type RevokedCertificate struct {
	ID           int
	SerialNumber string
	UserID       *int
	RevokedAt    time.Time
	Reason       string
	RevokedBy    *int
}

func (s *Store) InsertRevokedCertificate(rc *RevokedCertificate) error {
	if rc.RevokedAt.IsZero() {
		rc.RevokedAt = now()
	}
	res, err := s.db.Exec(`INSERT INTO revoked_certificates
		(serial_number, user_id, revoked_at, reason, revoked_by) VALUES (?, ?, ?, ?, ?)`,
		rc.SerialNumber, intVal(rc.UserID), rc.RevokedAt.UnixMicro(), rc.Reason, intVal(rc.RevokedBy))
	if err != nil {
		return err
	}
	id, err := res.LastInsertId()
	if err != nil {
		return err
	}
	rc.ID = int(id)
	return nil
}

func (s *Store) revokedQuery(query string, args ...any) ([]*RevokedCertificate, error) {
	rows, err := s.db.Query(query, args...)
	if err != nil {
		return nil, err
	}
	defer rows.Close()

	var out []*RevokedCertificate
	for rows.Next() {
		var rc RevokedCertificate
		var userID, revokedBy sql.NullInt64
		var revokedAt int64
		if err := rows.Scan(&rc.ID, &rc.SerialNumber, &userID, &revokedAt, &rc.Reason, &revokedBy); err != nil {
			return nil, err
		}
		rc.UserID = intPtr(userID)
		rc.RevokedBy = intPtr(revokedBy)
		rc.RevokedAt = timeOf(revokedAt)
		out = append(out, &rc)
	}
	return out, rows.Err()
}

// AllRevokedCertificates returns every revocation record (for CRL builds).
func (s *Store) AllRevokedCertificates() ([]*RevokedCertificate, error) {
	return s.revokedQuery(`SELECT id, serial_number, user_id, revoked_at, reason, revoked_by
		FROM revoked_certificates`)
}

// RevocationHistory returns a user's revocations, newest first.
func (s *Store) RevocationHistory(userID int) ([]*RevokedCertificate, error) {
	return s.revokedQuery(`SELECT id, serial_number, user_id, revoked_at, reason, revoked_by
		FROM revoked_certificates WHERE user_id = ? ORDER BY revoked_at DESC`, userID)
}

// -- mTLS CN mismatch tracking -------------------------------------------------

func (s *Store) InsertMtlsMismatch(presentedCN string, authenticatedUserID int) error {
	_, err := s.db.Exec(`INSERT INTO mtls_mismatch_logs (presented_cn, authenticated_user_id, timestamp)
		VALUES (?, ?, ?)`, presentedCN, authenticatedUserID, now().UnixMicro())
	return err
}

// CountRecentMismatches counts mismatch rows for a CN at or after windowStart.
func (s *Store) CountRecentMismatches(presentedCN string, windowStart time.Time) (int, error) {
	var n int
	err := s.db.QueryRow(`SELECT COUNT(*) FROM mtls_mismatch_logs
		WHERE presented_cn = ? AND timestamp >= ?`, presentedCN, windowStart.UnixMicro()).Scan(&n)
	return n, err
}
