// Package store is the SQLite persistence layer: WAL mode, enforced foreign
// keys, and embedded versioned migrations. Timestamps are stored as INTEGER
// unix microseconds (UTC).
package store

import (
	"database/sql"
	"embed"
	"fmt"
	"sort"
	"strconv"
	"strings"
	"time"

	_ "modernc.org/sqlite"
)

//go:embed migrations/*.sql
var migrationsFS embed.FS

type Store struct {
	db *sql.DB
}

func Open(path string) (*Store, error) {
	dsn := "file:" + path +
		"?_pragma=busy_timeout(5000)" +
		"&_pragma=journal_mode(WAL)" +
		"&_pragma=foreign_keys(1)" +
		"&_pragma=synchronous(NORMAL)"
	db, err := sql.Open("sqlite", dsn)
	if err != nil {
		return nil, err
	}
	// WAL allows concurrent readers with a single writer; SQLITE_BUSY under
	// write contention is absorbed by the busy_timeout.
	db.SetMaxOpenConns(4)
	if err := db.Ping(); err != nil {
		return nil, err
	}
	return &Store{db: db}, nil
}

func (s *Store) Close() error { return s.db.Close() }

// Migrate applies any unapplied embedded migrations, in version order, each
// inside a transaction.
func (s *Store) Migrate() error {
	if _, err := s.db.Exec(`CREATE TABLE IF NOT EXISTS schema_migrations (
		version INTEGER PRIMARY KEY,
		applied_at INTEGER NOT NULL
	)`); err != nil {
		return err
	}

	var current int
	if err := s.db.QueryRow(`SELECT COALESCE(MAX(version), 0) FROM schema_migrations`).Scan(&current); err != nil {
		return err
	}

	entries, err := migrationsFS.ReadDir("migrations")
	if err != nil {
		return err
	}
	names := make([]string, 0, len(entries))
	for _, e := range entries {
		names = append(names, e.Name())
	}
	sort.Strings(names)

	for _, name := range names {
		versionStr, _, ok := strings.Cut(name, "_")
		if !ok {
			return fmt.Errorf("store: malformed migration filename %q", name)
		}
		version, err := strconv.Atoi(versionStr)
		if err != nil {
			return fmt.Errorf("store: malformed migration version in %q: %w", name, err)
		}
		if version <= current {
			continue
		}

		sqlBytes, err := migrationsFS.ReadFile("migrations/" + name)
		if err != nil {
			return err
		}
		tx, err := s.db.Begin()
		if err != nil {
			return err
		}
		if _, err := tx.Exec(string(sqlBytes)); err != nil {
			tx.Rollback()
			return fmt.Errorf("store: migration %s failed: %w", name, err)
		}
		if _, err := tx.Exec(`INSERT INTO schema_migrations (version, applied_at) VALUES (?, ?)`,
			version, now().UnixMicro()); err != nil {
			tx.Rollback()
			return err
		}
		if err := tx.Commit(); err != nil {
			return err
		}
	}
	return nil
}

// -- nullable column helpers --------------------------------------------------

// timePtr converts a nullable INTEGER (unix micros) column.
func timePtr(ni sql.NullInt64) *time.Time {
	if !ni.Valid {
		return nil
	}
	t := time.UnixMicro(ni.Int64).UTC()
	return &t
}

// timeVal converts an optional time for binding.
func timeVal(t *time.Time) any {
	if t == nil {
		return nil
	}
	return t.UnixMicro()
}

// timeOf converts a required INTEGER (unix micros) column.
func timeOf(us int64) time.Time { return time.UnixMicro(us).UTC() }

func strPtr(ns sql.NullString) *string {
	if !ns.Valid {
		return nil
	}
	v := ns.String
	return &v
}

func strVal(s *string) any {
	if s == nil {
		return nil
	}
	return *s
}

func intPtr(ni sql.NullInt64) *int {
	if !ni.Valid {
		return nil
	}
	v := int(ni.Int64)
	return &v
}

func intVal(i *int) any {
	if i == nil {
		return nil
	}
	return *i
}

func now() time.Time { return time.Now().UTC() }
