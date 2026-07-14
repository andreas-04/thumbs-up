package store

import (
	"database/sql"
	"errors"
	"time"
)

type DomainPermission struct {
	ID         int
	DomainID   int
	FolderPath string
	CanRead    bool
	CanWrite   bool
	CreatedAt  time.Time
}

type DomainConfig struct {
	ID          int
	Domain      string
	CreatedAt   time.Time
	UpdatedAt   time.Time
	Permissions []*DomainPermission
}

func (s *Store) domainPermissions(domainID int) ([]*DomainPermission, error) {
	rows, err := s.db.Query(`SELECT id, domain_id, folder_path, can_read, can_write, created_at
		FROM domain_permissions WHERE domain_id = ? ORDER BY id`, domainID)
	if err != nil {
		return nil, err
	}
	defer rows.Close()

	var perms []*DomainPermission
	for rows.Next() {
		var p DomainPermission
		var createdAt int64
		if err := rows.Scan(&p.ID, &p.DomainID, &p.FolderPath, &p.CanRead, &p.CanWrite, &createdAt); err != nil {
			return nil, err
		}
		p.CreatedAt = timeOf(createdAt)
		perms = append(perms, &p)
	}
	return perms, rows.Err()
}

func (s *Store) scanDomain(row *sql.Row) (*DomainConfig, error) {
	var dc DomainConfig
	var createdAt, updatedAt int64
	err := row.Scan(&dc.ID, &dc.Domain, &createdAt, &updatedAt)
	if errors.Is(err, sql.ErrNoRows) {
		return nil, nil
	}
	if err != nil {
		return nil, err
	}
	dc.CreatedAt = timeOf(createdAt)
	dc.UpdatedAt = timeOf(updatedAt)
	dc.Permissions, err = s.domainPermissions(dc.ID)
	return &dc, err
}

func (s *Store) DomainByName(domain string) (*DomainConfig, error) {
	return s.scanDomain(s.db.QueryRow(
		`SELECT id, domain, created_at, updated_at FROM domain_configs WHERE domain = ?`, domain))
}

func (s *Store) DomainByID(id int) (*DomainConfig, error) {
	return s.scanDomain(s.db.QueryRow(
		`SELECT id, domain, created_at, updated_at FROM domain_configs WHERE id = ?`, id))
}

// ListDomains returns all domain configs ordered by domain name.
func (s *Store) ListDomains() ([]*DomainConfig, error) {
	rows, err := s.db.Query(`SELECT id, domain, created_at, updated_at FROM domain_configs ORDER BY domain`)
	if err != nil {
		return nil, err
	}
	defer rows.Close()

	var domains []*DomainConfig
	for rows.Next() {
		var dc DomainConfig
		var createdAt, updatedAt int64
		if err := rows.Scan(&dc.ID, &dc.Domain, &createdAt, &updatedAt); err != nil {
			return nil, err
		}
		dc.CreatedAt = timeOf(createdAt)
		dc.UpdatedAt = timeOf(updatedAt)
		domains = append(domains, &dc)
	}
	if err := rows.Err(); err != nil {
		return nil, err
	}
	for _, dc := range domains {
		if dc.Permissions, err = s.domainPermissions(dc.ID); err != nil {
			return nil, err
		}
	}
	return domains, nil
}

// CreateDomain inserts a config plus its permission rows.
func (s *Store) CreateDomain(domain string, perms []*DomainPermission) (*DomainConfig, error) {
	created := now().UnixMicro()
	res, err := s.db.Exec(`INSERT INTO domain_configs (domain, created_at, updated_at) VALUES (?, ?, ?)`,
		domain, created, created)
	if err != nil {
		return nil, err
	}
	id64, err := res.LastInsertId()
	if err != nil {
		return nil, err
	}
	id := int(id64)
	if err := s.replaceDomainPermissions(id, perms, false); err != nil {
		return nil, err
	}
	return s.DomainByID(id)
}

func (s *Store) RenameDomain(id int, domain string) error {
	_, err := s.db.Exec(`UPDATE domain_configs SET domain = ?, updated_at = ? WHERE id = ?`,
		domain, now().UnixMicro(), id)
	return err
}

// ReplaceDomainPermissions swaps out all permission rows for the domain.
func (s *Store) ReplaceDomainPermissions(id int, perms []*DomainPermission) error {
	return s.replaceDomainPermissions(id, perms, true)
}

func (s *Store) replaceDomainPermissions(id int, perms []*DomainPermission, deleteFirst bool) error {
	tx, err := s.db.Begin()
	if err != nil {
		return err
	}
	defer tx.Rollback()

	if deleteFirst {
		if _, err := tx.Exec(`DELETE FROM domain_permissions WHERE domain_id = ?`, id); err != nil {
			return err
		}
	}
	created := now().UnixMicro()
	for _, p := range perms {
		if _, err := tx.Exec(`INSERT INTO domain_permissions
			(domain_id, folder_path, can_read, can_write, created_at) VALUES (?, ?, ?, ?, ?)`,
			id, p.FolderPath, p.CanRead, p.CanWrite, created); err != nil {
			return err
		}
	}
	return tx.Commit()
}

// DeleteDomain removes the config; permission rows cascade.
func (s *Store) DeleteDomain(id int) error {
	_, err := s.db.Exec(`DELETE FROM domain_configs WHERE id = ?`, id)
	return err
}
