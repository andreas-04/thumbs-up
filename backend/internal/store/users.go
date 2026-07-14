package store

import (
	"database/sql"
	"errors"
	"fmt"
	"time"
)

type User struct {
	ID               int
	Email            string
	PasswordHash     string
	Role             string
	IsDefaultPIN     bool
	IsApproved       bool
	CreatedAt        time.Time
	LastLogin        *time.Time
	CertSerialNumber *string
	CertRevoked      bool
	CertIssuedAt     *time.Time
	CertExpiresAt    *time.Time
}

const userCols = `id, email, password_hash, role, is_default_pin, is_approved,
	created_at, last_login, cert_serial_number, cert_revoked, cert_issued_at, cert_expires_at`

func scanUser(row interface{ Scan(...any) error }) (*User, error) {
	var u User
	var createdAt int64
	var lastLogin, issuedAt, expiresAt sql.NullInt64
	var serial sql.NullString
	err := row.Scan(&u.ID, &u.Email, &u.PasswordHash, &u.Role,
		&u.IsDefaultPIN, &u.IsApproved,
		&createdAt, &lastLogin,
		&serial, &u.CertRevoked, &issuedAt, &expiresAt)
	if err != nil {
		return nil, err
	}
	u.CreatedAt = timeOf(createdAt)
	u.LastLogin = timePtr(lastLogin)
	u.CertSerialNumber = strPtr(serial)
	u.CertIssuedAt = timePtr(issuedAt)
	u.CertExpiresAt = timePtr(expiresAt)
	return &u, nil
}

func (s *Store) userQuery(where string, args ...any) (*User, error) {
	row := s.db.QueryRow(`SELECT `+userCols+` FROM users WHERE `+where+` LIMIT 1`, args...)
	u, err := scanUser(row)
	if errors.Is(err, sql.ErrNoRows) {
		return nil, nil
	}
	return u, err
}

func (s *Store) UserByEmail(email string) (*User, error) { return s.userQuery(`email = ?`, email) }
func (s *Store) UserByID(id int) (*User, error)          { return s.userQuery(`id = ?`, id) }

// FirstAdmin returns any admin user, or nil.
func (s *Store) FirstAdmin() (*User, error) { return s.userQuery(`role = 'admin'`) }

func (s *Store) CreateUser(u *User) error {
	if u.CreatedAt.IsZero() {
		u.CreatedAt = now()
	}
	res, err := s.db.Exec(`INSERT INTO users
		(email, password_hash, role, is_default_pin, is_approved, created_at, last_login,
		 cert_serial_number, cert_revoked, cert_issued_at, cert_expires_at)
		VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)`,
		u.Email, u.PasswordHash, u.Role, u.IsDefaultPIN, u.IsApproved,
		u.CreatedAt.UnixMicro(), timeVal(u.LastLogin),
		strVal(u.CertSerialNumber), u.CertRevoked, timeVal(u.CertIssuedAt), timeVal(u.CertExpiresAt))
	if err != nil {
		return err
	}
	id, err := res.LastInsertId()
	if err != nil {
		return err
	}
	u.ID = int(id)
	return nil
}

func (s *Store) UpdateUser(u *User) error {
	_, err := s.db.Exec(`UPDATE users SET
		email = ?, password_hash = ?, role = ?, is_default_pin = ?, is_approved = ?,
		created_at = ?, last_login = ?,
		cert_serial_number = ?, cert_revoked = ?, cert_issued_at = ?, cert_expires_at = ?
		WHERE id = ?`,
		u.Email, u.PasswordHash, u.Role, u.IsDefaultPIN, u.IsApproved,
		u.CreatedAt.UnixMicro(), timeVal(u.LastLogin),
		strVal(u.CertSerialNumber), u.CertRevoked, timeVal(u.CertIssuedAt), timeVal(u.CertExpiresAt),
		u.ID)
	return err
}

// DeleteUser removes the user; the schema cascades permissions, memberships,
// sessions, and claim tokens, and nulls out revocation-history references.
func (s *Store) DeleteUser(id int) error {
	_, err := s.db.Exec(`DELETE FROM users WHERE id = ?`, id)
	return err
}

// ListUsers returns a page of users (email substring search) plus the total
// match count.
func (s *Store) ListUsers(search string, page, limit int) ([]*User, int, error) {
	where, args := `1=1`, []any{}
	if search != "" {
		where = `email LIKE ? ESCAPE '\'`
		args = append(args, "%"+escapeLike(search)+"%")
	}

	var total int
	if err := s.db.QueryRow(`SELECT COUNT(*) FROM users WHERE `+where, args...).Scan(&total); err != nil {
		return nil, 0, err
	}

	query := fmt.Sprintf(`SELECT %s FROM users WHERE %s LIMIT ? OFFSET ?`, userCols, where)
	rows, err := s.db.Query(query, append(args, limit, (page-1)*limit)...)
	if err != nil {
		return nil, 0, err
	}
	defer rows.Close()

	var users []*User
	for rows.Next() {
		u, err := scanUser(rows)
		if err != nil {
			return nil, 0, err
		}
		users = append(users, u)
	}
	return users, total, rows.Err()
}

func (s *Store) CountUsersByRole(role string) (int, error) {
	var n int
	err := s.db.QueryRow(`SELECT COUNT(*) FROM users WHERE role = ?`, role).Scan(&n)
	return n, err
}

// UsersWithExpiringCerts returns non-revoked cert holders whose certificate
// expires at or before threshold.
func (s *Store) UsersWithExpiringCerts(threshold time.Time) ([]*User, error) {
	rows, err := s.db.Query(`SELECT `+userCols+` FROM users
		WHERE cert_expires_at IS NOT NULL
		  AND cert_expires_at <= ?
		  AND cert_revoked = 0
		  AND cert_serial_number IS NOT NULL`,
		threshold.UnixMicro())
	if err != nil {
		return nil, err
	}
	defer rows.Close()

	var users []*User
	for rows.Next() {
		u, err := scanUser(rows)
		if err != nil {
			return nil, err
		}
		users = append(users, u)
	}
	return users, rows.Err()
}

func escapeLike(s string) string {
	out := make([]byte, 0, len(s))
	for i := 0; i < len(s); i++ {
		switch s[i] {
		case '%', '_', '\\':
			out = append(out, '\\')
		}
		out = append(out, s[i])
	}
	return string(out)
}
