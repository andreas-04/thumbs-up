package store

import (
	"database/sql"
	"errors"
	"time"
)

type SystemSettings struct {
	ID             int
	AuthMethod     string
	TLSEnabled     bool
	HTTPSPort      int
	DeviceName     string
	UpdatedAt      time.Time
	SMTPEnabled    bool
	SMTPHost       string
	SMTPPort       int
	SMTPUsername   string
	SMTPPassword   string
	SMTPFromEmail  string
	SMTPUseTLS     bool
	AllowedDomains string // comma-separated
}

const settingsCols = `id, auth_method, tls_enabled, https_port, device_name, updated_at,
	smtp_enabled, smtp_host, smtp_port, smtp_username, smtp_password, smtp_from_email,
	smtp_use_tls, allowed_domains`

// Settings returns the singleton settings row, or nil when missing.
func (s *Store) Settings() (*SystemSettings, error) {
	var st SystemSettings
	var updatedAt int64
	err := s.db.QueryRow(`SELECT `+settingsCols+` FROM system_settings LIMIT 1`).Scan(
		&st.ID, &st.AuthMethod, &st.TLSEnabled, &st.HTTPSPort, &st.DeviceName, &updatedAt,
		&st.SMTPEnabled, &st.SMTPHost, &st.SMTPPort, &st.SMTPUsername, &st.SMTPPassword,
		&st.SMTPFromEmail, &st.SMTPUseTLS, &st.AllowedDomains)
	if errors.Is(err, sql.ErrNoRows) {
		return nil, nil
	}
	if err != nil {
		return nil, err
	}
	st.UpdatedAt = timeOf(updatedAt)
	return &st, nil
}

func (s *Store) CreateSettings(st *SystemSettings) error {
	st.UpdatedAt = now()
	res, err := s.db.Exec(`INSERT INTO system_settings
		(auth_method, tls_enabled, https_port, device_name, updated_at,
		 smtp_enabled, smtp_host, smtp_port, smtp_username, smtp_password,
		 smtp_from_email, smtp_use_tls, allowed_domains)
		VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)`,
		st.AuthMethod, st.TLSEnabled, st.HTTPSPort, st.DeviceName, st.UpdatedAt.UnixMicro(),
		st.SMTPEnabled, st.SMTPHost, st.SMTPPort, st.SMTPUsername, st.SMTPPassword,
		st.SMTPFromEmail, st.SMTPUseTLS, st.AllowedDomains)
	if err != nil {
		return err
	}
	id, err := res.LastInsertId()
	if err != nil {
		return err
	}
	st.ID = int(id)
	return nil
}

func (s *Store) UpdateSettings(st *SystemSettings) error {
	st.UpdatedAt = now()
	_, err := s.db.Exec(`UPDATE system_settings SET
		auth_method = ?, tls_enabled = ?, https_port = ?, device_name = ?, updated_at = ?,
		smtp_enabled = ?, smtp_host = ?, smtp_port = ?, smtp_username = ?, smtp_password = ?,
		smtp_from_email = ?, smtp_use_tls = ?, allowed_domains = ?
		WHERE id = ?`,
		st.AuthMethod, st.TLSEnabled, st.HTTPSPort, st.DeviceName, st.UpdatedAt.UnixMicro(),
		st.SMTPEnabled, st.SMTPHost, st.SMTPPort, st.SMTPUsername, st.SMTPPassword,
		st.SMTPFromEmail, st.SMTPUseTLS, st.AllowedDomains,
		st.ID)
	return err
}
