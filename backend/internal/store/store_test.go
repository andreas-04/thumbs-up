package store

import (
	"path/filepath"
	"testing"
	"time"
)

func testStore(t *testing.T) *Store {
	t.Helper()
	s, err := Open(filepath.Join(t.TempDir(), "test.db"))
	if err != nil {
		t.Fatal(err)
	}
	t.Cleanup(func() { s.Close() })
	if err := s.Migrate(); err != nil {
		t.Fatal(err)
	}
	return s
}

func TestMigrateIsIdempotent(t *testing.T) {
	s := testStore(t)
	if err := s.Migrate(); err != nil {
		t.Fatalf("second Migrate() must be a no-op: %v", err)
	}
}

func TestUserTimestampRoundTrip(t *testing.T) {
	s := testStore(t)
	login := time.Date(2026, 7, 13, 9, 5, 7, 123456000, time.UTC)
	u := &User{Email: "u@x.com", PasswordHash: "h", Role: "user", LastLogin: &login}
	if err := s.CreateUser(u); err != nil {
		t.Fatal(err)
	}

	got, err := s.UserByID(u.ID)
	if err != nil || got == nil {
		t.Fatalf("read back: %v %v", got, err)
	}
	if got.CreatedAt.IsZero() {
		t.Fatal("created_at lost in round trip")
	}
	if got.LastLogin == nil || !got.LastLogin.Equal(login) {
		t.Fatalf("last_login = %v, want %v", got.LastLogin, login)
	}
}

func TestRoleCheckConstraint(t *testing.T) {
	s := testStore(t)
	err := s.CreateUser(&User{Email: "u@x.com", PasswordHash: "h", Role: "superuser"})
	if err == nil {
		t.Fatal("invalid role must violate the CHECK constraint")
	}
}

func TestSettingsRoundTrip(t *testing.T) {
	s := testStore(t)
	if err := s.CreateSettings(&SystemSettings{AuthMethod: "email+password", HTTPSPort: 8443}); err != nil {
		t.Fatal(err)
	}
	got, err := s.Settings()
	if err != nil || got == nil {
		t.Fatalf("read settings: %v %v", got, err)
	}
	if got.UpdatedAt.IsZero() {
		t.Fatal("updated_at lost in round trip")
	}
	if got.AuthMethod != "email+password" || got.HTTPSPort != 8443 {
		t.Fatalf("fields wrong: %+v", got)
	}
}

// Foreign keys are enforced: deleting a user cascades its dependents.
func TestDeleteUserCascades(t *testing.T) {
	s := testStore(t)
	u := &User{Email: "u@x.com", PasswordHash: "h", Role: "user"}
	if err := s.CreateUser(u); err != nil {
		t.Fatal(err)
	}
	allow := "allow"
	if err := s.ReplaceFolderPermissions(u.ID, []*FolderPermission{
		{UserID: u.ID, FolderPath: "/docs", CanRead: &allow},
	}); err != nil {
		t.Fatal(err)
	}
	grp, err := s.CreateGroup("g", nil)
	if err != nil {
		t.Fatal(err)
	}
	if err := s.SetGroupMembers(grp.ID, []int{u.ID}); err != nil {
		t.Fatal(err)
	}
	if _, err := s.CreateSession("hash1", u.ID, time.Now().Add(time.Hour)); err != nil {
		t.Fatal(err)
	}
	if err := s.CreateCertClaim("claimhash1", u.ID, time.Now().Add(time.Hour)); err != nil {
		t.Fatal(err)
	}

	if err := s.DeleteUser(u.ID); err != nil {
		t.Fatal(err)
	}
	if perms, _ := s.FolderPermissionsForUser(u.ID); len(perms) != 0 {
		t.Fatal("folder permissions not cascaded")
	}
	grp, _ = s.GroupByID(grp.ID)
	if len(grp.Members) != 0 {
		t.Fatal("group membership not cascaded")
	}
	if sess, _ := s.SessionByTokenHash("hash1"); sess != nil {
		t.Fatal("sessions not cascaded")
	}
	if claim, _ := s.CertClaimByTokenHash("claimhash1"); claim != nil {
		t.Fatal("cert claims not cascaded")
	}
}

func TestSessionLifecycle(t *testing.T) {
	s := testStore(t)
	u := &User{Email: "u@x.com", PasswordHash: "h", Role: "user"}
	if err := s.CreateUser(u); err != nil {
		t.Fatal(err)
	}

	now := time.Now().UTC()
	sess, err := s.CreateSession("hashA", u.ID, now.Add(time.Hour))
	if err != nil {
		t.Fatal(err)
	}
	got, err := s.SessionByTokenHash("hashA")
	if err != nil || got == nil || got.UserID != u.ID {
		t.Fatalf("lookup: %+v %v", got, err)
	}
	if !got.Valid(now) {
		t.Fatal("fresh session must be valid")
	}
	if got.Valid(now.Add(2 * time.Hour)) {
		t.Fatal("expired session must be invalid")
	}

	if err := s.RevokeSession(sess.ID); err != nil {
		t.Fatal(err)
	}
	got, _ = s.SessionByTokenHash("hashA")
	if got.Valid(now) {
		t.Fatal("revoked session must be invalid")
	}

	// Revoke-all hits every active session for the user.
	_, _ = s.CreateSession("hashB", u.ID, now.Add(time.Hour))
	_, _ = s.CreateSession("hashC", u.ID, now.Add(time.Hour))
	if err := s.RevokeUserSessions(u.ID); err != nil {
		t.Fatal(err)
	}
	for _, h := range []string{"hashB", "hashC"} {
		if got, _ := s.SessionByTokenHash(h); got.Valid(now) {
			t.Fatalf("session %s survived revoke-all", h)
		}
	}

	// GC removes expired rows.
	_, _ = s.CreateSession("hashD", u.ID, now.Add(-time.Minute))
	if err := s.DeleteExpiredSessions(now); err != nil {
		t.Fatal(err)
	}
	if got, _ := s.SessionByTokenHash("hashD"); got != nil {
		t.Fatal("expired session not garbage-collected")
	}
}

func TestCertClaimLifecycle(t *testing.T) {
	s := testStore(t)
	u := &User{Email: "u@x.com", PasswordHash: "h", Role: "user"}
	if err := s.CreateUser(u); err != nil {
		t.Fatal(err)
	}
	now := time.Now().UTC()

	if err := s.CreateCertClaim("c1", u.ID, now.Add(time.Hour)); err != nil {
		t.Fatal(err)
	}
	// Issuing a new claim supersedes the outstanding unused one.
	if err := s.CreateCertClaim("c2", u.ID, now.Add(time.Hour)); err != nil {
		t.Fatal(err)
	}
	if old, _ := s.CertClaimByTokenHash("c1"); old != nil {
		t.Fatal("superseded claim must be gone")
	}

	claim, err := s.CertClaimByTokenHash("c2")
	if err != nil || claim == nil || !claim.Claimable(now) {
		t.Fatalf("claim not claimable: %+v %v", claim, err)
	}

	ok, err := s.MarkCertClaimUsed(claim.ID)
	if err != nil || !ok {
		t.Fatalf("first use: %v %v", ok, err)
	}
	ok, err = s.MarkCertClaimUsed(claim.ID)
	if err != nil || ok {
		t.Fatal("second use must fail (one-time)")
	}
	claim, _ = s.CertClaimByTokenHash("c2")
	if claim.Claimable(now) {
		t.Fatal("used claim must not be claimable")
	}
}

func TestUnknownIDsSkippedInMembership(t *testing.T) {
	s := testStore(t)
	u := &User{Email: "u@x.com", PasswordHash: "h", Role: "user"}
	if err := s.CreateUser(u); err != nil {
		t.Fatal(err)
	}
	grp, err := s.CreateGroup("g", nil)
	if err != nil {
		t.Fatal(err)
	}
	if err := s.SetGroupMembers(grp.ID, []int{u.ID, 9999}); err != nil {
		t.Fatal(err)
	}
	grp, _ = s.GroupByID(grp.ID)
	if len(grp.Members) != 1 || grp.Members[0].Email != "u@x.com" {
		t.Fatalf("members = %+v", grp.Members)
	}
}
