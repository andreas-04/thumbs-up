package store

import (
	"database/sql"
	"time"
)

// FolderPermission is a user-level tri-state ACL row: CanRead/CanWrite hold
// "allow", "deny", or nil (defer to lower tiers).
type FolderPermission struct {
	ID         int
	UserID     int
	FolderPath string
	CanRead    *string
	CanWrite   *string
	CreatedAt  time.Time
}

func (s *Store) FolderPermissionsForUser(userID int) ([]*FolderPermission, error) {
	rows, err := s.db.Query(`SELECT id, user_id, folder_path, can_read, can_write, created_at
		FROM folder_permissions WHERE user_id = ? ORDER BY id`, userID)
	if err != nil {
		return nil, err
	}
	defer rows.Close()

	var perms []*FolderPermission
	for rows.Next() {
		var p FolderPermission
		var canRead, canWrite sql.NullString
		var createdAt int64
		if err := rows.Scan(&p.ID, &p.UserID, &p.FolderPath, &canRead, &canWrite, &createdAt); err != nil {
			return nil, err
		}
		p.CanRead = strPtr(canRead)
		p.CanWrite = strPtr(canWrite)
		p.CreatedAt = timeOf(createdAt)
		perms = append(perms, &p)
	}
	return perms, rows.Err()
}

// ReplaceFolderPermissions deletes all of the user's ACL rows and inserts the
// given set.
func (s *Store) ReplaceFolderPermissions(userID int, perms []*FolderPermission) error {
	tx, err := s.db.Begin()
	if err != nil {
		return err
	}
	defer tx.Rollback()

	if _, err := tx.Exec(`DELETE FROM folder_permissions WHERE user_id = ?`, userID); err != nil {
		return err
	}
	created := now().UnixMicro()
	for _, p := range perms {
		if _, err := tx.Exec(`INSERT INTO folder_permissions
			(user_id, folder_path, can_read, can_write, created_at) VALUES (?, ?, ?, ?, ?)`,
			userID, p.FolderPath, strVal(p.CanRead), strVal(p.CanWrite), created); err != nil {
			return err
		}
	}
	return tx.Commit()
}
