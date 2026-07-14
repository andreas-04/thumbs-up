package store

import (
	"database/sql"
	"errors"
	"time"
)

type GroupPermission struct {
	ID         int
	GroupID    int
	FolderPath string
	CanRead    bool
	CanWrite   bool
	CreatedAt  time.Time
}

type GroupMember struct {
	ID    int
	Email string
}

type Group struct {
	ID          int
	Name        string
	Description *string
	CreatedAt   time.Time
	UpdatedAt   time.Time
	Members     []*GroupMember
	Permissions []*GroupPermission
}

func (s *Store) GroupPermissions(groupID int) ([]*GroupPermission, error) {
	rows, err := s.db.Query(`SELECT id, group_id, folder_path, can_read, can_write, created_at
		FROM group_permissions WHERE group_id = ? ORDER BY id`, groupID)
	if err != nil {
		return nil, err
	}
	defer rows.Close()

	var perms []*GroupPermission
	for rows.Next() {
		var p GroupPermission
		var createdAt int64
		if err := rows.Scan(&p.ID, &p.GroupID, &p.FolderPath, &p.CanRead, &p.CanWrite, &createdAt); err != nil {
			return nil, err
		}
		p.CreatedAt = timeOf(createdAt)
		perms = append(perms, &p)
	}
	return perms, rows.Err()
}

func (s *Store) groupMembers(groupID int) ([]*GroupMember, error) {
	rows, err := s.db.Query(`SELECT u.id, u.email FROM users u
		JOIN group_memberships gm ON gm.user_id = u.id
		WHERE gm.group_id = ? ORDER BY gm.id`, groupID)
	if err != nil {
		return nil, err
	}
	defer rows.Close()

	var members []*GroupMember
	for rows.Next() {
		var m GroupMember
		if err := rows.Scan(&m.ID, &m.Email); err != nil {
			return nil, err
		}
		members = append(members, &m)
	}
	return members, rows.Err()
}

func (s *Store) scanGroupRow(id int, name string, desc sql.NullString, createdAt, updatedAt int64) *Group {
	return &Group{
		ID:          id,
		Name:        name,
		Description: strPtr(desc),
		CreatedAt:   timeOf(createdAt),
		UpdatedAt:   timeOf(updatedAt),
	}
}

func (s *Store) loadGroup(row *sql.Row) (*Group, error) {
	var id int
	var name string
	var desc sql.NullString
	var createdAt, updatedAt int64
	err := row.Scan(&id, &name, &desc, &createdAt, &updatedAt)
	if errors.Is(err, sql.ErrNoRows) {
		return nil, nil
	}
	if err != nil {
		return nil, err
	}
	g := s.scanGroupRow(id, name, desc, createdAt, updatedAt)
	if g.Members, err = s.groupMembers(g.ID); err != nil {
		return nil, err
	}
	if g.Permissions, err = s.GroupPermissions(g.ID); err != nil {
		return nil, err
	}
	return g, nil
}

func (s *Store) GroupByID(id int) (*Group, error) {
	return s.loadGroup(s.db.QueryRow(
		`SELECT id, name, description, created_at, updated_at FROM groups WHERE id = ?`, id))
}

func (s *Store) GroupByName(name string) (*Group, error) {
	return s.loadGroup(s.db.QueryRow(
		`SELECT id, name, description, created_at, updated_at FROM groups WHERE name = ?`, name))
}

// ListGroups returns all groups (with members/permissions loaded) ordered by
// name.
func (s *Store) ListGroups() ([]*Group, error) {
	rows, err := s.db.Query(`SELECT id, name, description, created_at, updated_at FROM groups ORDER BY name`)
	if err != nil {
		return nil, err
	}
	defer rows.Close()

	var groups []*Group
	for rows.Next() {
		var id int
		var name string
		var desc sql.NullString
		var createdAt, updatedAt int64
		if err := rows.Scan(&id, &name, &desc, &createdAt, &updatedAt); err != nil {
			return nil, err
		}
		groups = append(groups, s.scanGroupRow(id, name, desc, createdAt, updatedAt))
	}
	if err := rows.Err(); err != nil {
		return nil, err
	}
	for _, g := range groups {
		if g.Members, err = s.groupMembers(g.ID); err != nil {
			return nil, err
		}
		if g.Permissions, err = s.GroupPermissions(g.ID); err != nil {
			return nil, err
		}
	}
	return groups, nil
}

func (s *Store) CreateGroup(name string, description *string) (*Group, error) {
	created := now().UnixMicro()
	res, err := s.db.Exec(`INSERT INTO groups (name, description, created_at, updated_at) VALUES (?, ?, ?, ?)`,
		name, strVal(description), created, created)
	if err != nil {
		return nil, err
	}
	id, err := res.LastInsertId()
	if err != nil {
		return nil, err
	}
	return s.GroupByID(int(id))
}

func (s *Store) UpdateGroupMeta(id int, name string, description *string) error {
	_, err := s.db.Exec(`UPDATE groups SET name = ?, description = ?, updated_at = ? WHERE id = ?`,
		name, strVal(description), now().UnixMicro(), id)
	return err
}

// DeleteGroup removes the group; memberships and permissions cascade.
func (s *Store) DeleteGroup(id int) error {
	_, err := s.db.Exec(`DELETE FROM groups WHERE id = ?`, id)
	return err
}

// ReplaceGroupPermissions swaps out all of the group's ACL rows.
func (s *Store) ReplaceGroupPermissions(groupID int, perms []*GroupPermission) error {
	tx, err := s.db.Begin()
	if err != nil {
		return err
	}
	defer tx.Rollback()

	if _, err := tx.Exec(`DELETE FROM group_permissions WHERE group_id = ?`, groupID); err != nil {
		return err
	}
	created := now().UnixMicro()
	for _, p := range perms {
		if _, err := tx.Exec(`INSERT INTO group_permissions
			(group_id, folder_path, can_read, can_write, created_at) VALUES (?, ?, ?, ?, ?)`,
			groupID, p.FolderPath, p.CanRead, p.CanWrite, created); err != nil {
			return err
		}
	}
	return tx.Commit()
}

// SetGroupMembers replaces the member list; unknown user IDs are skipped.
func (s *Store) SetGroupMembers(groupID int, userIDs []int) error {
	tx, err := s.db.Begin()
	if err != nil {
		return err
	}
	defer tx.Rollback()

	if _, err := tx.Exec(`DELETE FROM group_memberships WHERE group_id = ?`, groupID); err != nil {
		return err
	}
	created := now().UnixMicro()
	for _, uid := range userIDs {
		if _, err := tx.Exec(`INSERT OR IGNORE INTO group_memberships (group_id, user_id, created_at)
			SELECT ?, id, ? FROM users WHERE id = ?`,
			groupID, created, uid); err != nil {
			return err
		}
	}
	return tx.Commit()
}

// SetUserGroups replaces the user's group memberships; unknown group IDs are
// skipped.
func (s *Store) SetUserGroups(userID int, groupIDs []int) error {
	tx, err := s.db.Begin()
	if err != nil {
		return err
	}
	defer tx.Rollback()

	if _, err := tx.Exec(`DELETE FROM group_memberships WHERE user_id = ?`, userID); err != nil {
		return err
	}
	created := now().UnixMicro()
	for _, gid := range groupIDs {
		if _, err := tx.Exec(`INSERT OR IGNORE INTO group_memberships (group_id, user_id, created_at)
			SELECT id, ?, ? FROM groups WHERE id = ?`,
			userID, created, gid); err != nil {
			return err
		}
	}
	return tx.Commit()
}

// GroupsForUser returns the groups a user belongs to, with permissions
// loaded (for the permission resolver) in membership order.
func (s *Store) GroupsForUser(userID int) ([]*Group, error) {
	rows, err := s.db.Query(`SELECT g.id, g.name, g.description, g.created_at, g.updated_at
		FROM groups g JOIN group_memberships gm ON gm.group_id = g.id
		WHERE gm.user_id = ? ORDER BY gm.id`, userID)
	if err != nil {
		return nil, err
	}
	defer rows.Close()

	var groups []*Group
	for rows.Next() {
		var id int
		var name string
		var desc sql.NullString
		var createdAt, updatedAt int64
		if err := rows.Scan(&id, &name, &desc, &createdAt, &updatedAt); err != nil {
			return nil, err
		}
		groups = append(groups, s.scanGroupRow(id, name, desc, createdAt, updatedAt))
	}
	if err := rows.Err(); err != nil {
		return nil, err
	}
	for _, g := range groups {
		if g.Permissions, err = s.GroupPermissions(g.ID); err != nil {
			return nil, err
		}
	}
	return groups, nil
}
