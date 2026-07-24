package store

import (
	"database/sql"
	"strings"
	"time"
)

type AuditLog struct {
	ID          int
	Timestamp   time.Time
	UserID      *int
	UserEmail   *string
	Action      string
	TargetType  *string
	TargetID    *string
	Description *string
	IPAddress   *string
	Status      string
}

func (s *Store) InsertAuditLog(entry *AuditLog) error {
	if entry.Timestamp.IsZero() {
		entry.Timestamp = now()
	}
	if entry.Status == "" {
		entry.Status = "success"
	}
	_, err := s.db.Exec(`INSERT INTO audit_logs
		(timestamp, user_id, user_email, action, target_type, target_id, description, ip_address, status)
		VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)`,
		entry.Timestamp.UnixMicro(), intVal(entry.UserID), strVal(entry.UserEmail), entry.Action,
		strVal(entry.TargetType), strVal(entry.TargetID), strVal(entry.Description),
		strVal(entry.IPAddress), entry.Status)
	return err
}

// AuditLogFilter mirrors the query parameters of GET /api/v1/audit-logs.
type AuditLogFilter struct {
	Page      int
	Limit     int
	Action    string
	Category  string // "files" or "security"
	UserEmail string
	Status    string
	Since     *time.Time
	Search    string
}

// QueryAuditLogs returns a page of logs (newest first) and the total count of
// matches.
func (s *Store) QueryAuditLogs(f AuditLogFilter) ([]*AuditLog, int, error) {
	var conds []string
	var args []any

	switch f.Category {
	case "files":
		conds = append(conds, `action LIKE 'file.%'`)
	case "security":
		conds = append(conds, `(action LIKE 'auth.%' OR action LIKE 'cert.%' OR action LIKE 'permission.%')`)
	default:
		if f.Action != "" {
			conds = append(conds, `action LIKE ? ESCAPE '\'`)
			args = append(args, escapeLike(f.Action)+"%")
		}
	}
	if f.UserEmail != "" {
		conds = append(conds, `user_email LIKE ? ESCAPE '\'`)
		args = append(args, "%"+escapeLike(f.UserEmail)+"%")
	}
	if f.Status == "success" || f.Status == "failure" {
		conds = append(conds, `status = ?`)
		args = append(args, f.Status)
	}
	if f.Since != nil {
		conds = append(conds, `timestamp > ?`)
		args = append(args, f.Since.UnixMicro())
	}
	if f.Search != "" {
		conds = append(conds, `description LIKE ? ESCAPE '\'`)
		args = append(args, "%"+escapeLike(f.Search)+"%")
	}

	where := "1=1"
	if len(conds) > 0 {
		where = strings.Join(conds, " AND ")
	}

	var total int
	if err := s.db.QueryRow(`SELECT COUNT(*) FROM audit_logs WHERE `+where, args...).Scan(&total); err != nil {
		return nil, 0, err
	}

	rows, err := s.db.Query(`SELECT id, timestamp, user_id, user_email, action, target_type, target_id,
		description, ip_address, status
		FROM audit_logs WHERE `+where+` ORDER BY timestamp DESC LIMIT ? OFFSET ?`,
		append(args, f.Limit, (f.Page-1)*f.Limit)...)
	if err != nil {
		return nil, 0, err
	}
	defer rows.Close()

	var logs []*AuditLog
	for rows.Next() {
		var l AuditLog
		var ts int64
		var email, ttype, tid, desc, ip sql.NullString
		var uid sql.NullInt64
		if err := rows.Scan(&l.ID, &ts, &uid, &email, &l.Action, &ttype, &tid, &desc, &ip, &l.Status); err != nil {
			return nil, 0, err
		}
		l.Timestamp = timeOf(ts)
		l.UserID = intPtr(uid)
		l.UserEmail = strPtr(email)
		l.TargetType = strPtr(ttype)
		l.TargetID = strPtr(tid)
		l.Description = strPtr(desc)
		l.IPAddress = strPtr(ip)
		logs = append(logs, &l)
	}
	return logs, total, rows.Err()
}

type AuditLogStats struct {
	Total            int
	Today            int
	FailedAuthToday  int
	ActiveUsersToday int
}

// AuditStats computes the dashboard counters; todayStart is midnight UTC.
func (s *Store) AuditStats(todayStart time.Time) (*AuditLogStats, error) {
	var st AuditLogStats
	ts := todayStart.UnixMicro()

	if err := s.db.QueryRow(`SELECT COUNT(*) FROM audit_logs`).Scan(&st.Total); err != nil {
		return nil, err
	}
	if err := s.db.QueryRow(`SELECT COUNT(*) FROM audit_logs WHERE timestamp >= ?`, ts).Scan(&st.Today); err != nil {
		return nil, err
	}
	if err := s.db.QueryRow(`SELECT COUNT(*) FROM audit_logs
		WHERE timestamp >= ? AND action = 'auth.login_failed'`, ts).Scan(&st.FailedAuthToday); err != nil {
		return nil, err
	}
	if err := s.db.QueryRow(`SELECT COUNT(DISTINCT user_id) FROM audit_logs
		WHERE timestamp >= ? AND user_id IS NOT NULL`, ts).Scan(&st.ActiveUsersToday); err != nil {
		return nil, err
	}
	return &st, nil
}
