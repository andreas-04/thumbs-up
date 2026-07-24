package httpapi

import (
	"bytes"
	"encoding/json"
	"fmt"
	"io"
	"mime/multipart"
	"net/http/httptest"
	"os"
	"path/filepath"
	"strings"
	"testing"
	"time"

	"github.com/andreas-04/terra-crate/backend/internal/auth"
	"github.com/andreas-04/terra-crate/backend/internal/certs"
	"github.com/andreas-04/terra-crate/backend/internal/config"
	"github.com/andreas-04/terra-crate/backend/internal/store"
)

// newTestServer boots a full server against a temp SQLite DB, temp storage,
// and a real self-signed CA (client certs are actually issued in tests).
func newTestServer(t *testing.T) *Server {
	t.Helper()
	dir := t.TempDir()
	cfg := config.Config{
		Host:                         "127.0.0.1",
		Port:                         8443,
		StoragePath:                  filepath.Join(dir, "storage"),
		CertPath:                     filepath.Join(dir, "certs", "server_cert.pem"),
		KeyPath:                      filepath.Join(dir, "certs", "server_key.pem"),
		CACertPath:                   filepath.Join(dir, "certs", "ca_cert.pem"),
		CAKeyPath:                    filepath.Join(dir, "certs", "ca_key.pem"),
		PublicURL:                    "https://testhost.local",
		TokenExpiryHours:             24,
		EnableUploads:                true,
		EnableDelete:                 true,
		ServiceName:                  "TerraCrate Test",
		MDNSHostname:                 "testhost",
		MaxUploadSize:                10 << 20,
		AdminPIN:                     "123456",
		DatabasePath:                 filepath.Join(dir, "data", "test.db"),
		CORSOrigins:                  "*",
		CNMismatchThreshold:          3,
		CNMismatchWindowMinutes:      60,
		CertExpiryCheckDays:          7,
		CertExpiryCheckIntervalHours: 24,
	}
	if err := os.MkdirAll(cfg.GuestRoot(), 0o755); err != nil {
		t.Fatal(err)
	}
	if err := certs.GenerateCA(cfg.CACertPath, cfg.CAKeyPath); err != nil {
		t.Fatal(err)
	}
	if err := os.MkdirAll(filepath.Dir(cfg.DatabasePath), 0o755); err != nil {
		t.Fatal(err)
	}
	st, err := store.Open(cfg.DatabasePath)
	if err != nil {
		t.Fatal(err)
	}
	t.Cleanup(func() { st.Close() })
	if err := st.Migrate(); err != nil {
		t.Fatal(err)
	}
	if err := st.CreateSettings(&store.SystemSettings{
		AuthMethod: "email+password", TLSEnabled: true,
		HTTPSPort: 8443, DeviceName: "TerraCrate Test", SMTPPort: 587, SMTPUseTLS: true,
	}); err != nil {
		t.Fatal(err)
	}
	return NewServer(cfg, st)
}

// seedUser inserts a user directly and returns it with a session token.
func seedUser(t *testing.T, s *Server, email, password, role string) (*store.User, string) {
	t.Helper()
	hash, err := auth.HashPassword(password)
	if err != nil {
		t.Fatal(err)
	}
	u := &store.User{Email: email, PasswordHash: hash, Role: role, IsApproved: true}
	if err := s.store.CreateUser(u); err != nil {
		t.Fatal(err)
	}
	token, err := s.newSessionToken(u)
	if err != nil {
		t.Fatal(err)
	}
	return u, token
}

type resp struct {
	code int
	body map[string]any
	raw  []byte
}

func doJSON(t *testing.T, s *Server, method, path, token string, body any, hdrs ...map[string]string) resp {
	t.Helper()
	var rd io.Reader
	if body != nil {
		b, err := json.Marshal(body)
		if err != nil {
			t.Fatal(err)
		}
		rd = bytes.NewReader(b)
	}
	req := httptest.NewRequest(method, path, rd)
	if token != "" {
		req.Header.Set("Authorization", "Bearer "+token)
	}
	for _, h := range hdrs {
		for k, v := range h {
			req.Header.Set(k, v)
		}
	}
	rec := httptest.NewRecorder()
	s.Handler().ServeHTTP(rec, req)

	out := resp{code: rec.Code, raw: rec.Body.Bytes()}
	_ = json.Unmarshal(out.raw, &out.body)
	return out
}

// -- Auth flows (mirrors test_auth.py + parts of conftest) ---------------------

func TestLoginSuccessAndFailure(t *testing.T) {
	s := newTestServer(t)
	seedUser(t, s, "user@example.com", "hunter22", "user")

	ok := doJSON(t, s, "POST", "/api/v1/auth/login", "", map[string]any{
		"email": "user@example.com", "password": "hunter22",
	})
	if ok.code != 200 {
		t.Fatalf("login: %d %s", ok.code, ok.raw)
	}
	if ok.body["token"] == "" || ok.body["token"] == nil {
		t.Fatal("no token in response")
	}
	user := ok.body["user"].(map[string]any)
	for _, key := range []string{"id", "email", "role", "requiresPasswordChange", "isApproved",
		"createdAt", "lastLogin", "groups", "certRevoked", "certIssuedAt", "certExpiresAt"} {
		if _, present := user[key]; !present {
			t.Errorf("user payload missing key %q", key)
		}
	}
	if user["lastLogin"] == nil {
		t.Error("lastLogin should be set after login")
	}

	bad := doJSON(t, s, "POST", "/api/v1/auth/login", "", map[string]any{
		"email": "user@example.com", "password": "wrong",
	})
	if bad.code != 401 || bad.body["code"] != "INVALID_CREDENTIALS" {
		t.Fatalf("bad login: %d %s", bad.code, bad.raw)
	}

	missing := doJSON(t, s, "POST", "/api/v1/auth/login", "", map[string]any{"email": "user@example.com"})
	if missing.code != 400 || missing.body["code"] != "MISSING_CREDENTIALS" {
		t.Fatalf("missing creds: %d %s", missing.code, missing.raw)
	}

	// The failed attempt must be audited.
	logs, _, err := s.store.QueryAuditLogs(store.AuditLogFilter{Page: 1, Limit: 10, Action: "auth.login_failed"})
	if err != nil || len(logs) != 1 || logs[0].Status != "failure" {
		t.Fatalf("audit trail wrong: %v %v", logs, err)
	}
}

// -- Signup (mirrors test_signup.py) -------------------------------------------

func TestSignupDomainAllowlist(t *testing.T) {
	s := newTestServer(t)

	// No allowed domains configured: rejected.
	denied := doJSON(t, s, "POST", "/api/v1/auth/signup", "", map[string]any{
		"email": "new@nowhere.com", "password": "secret12",
	})
	if denied.code != 403 || denied.body["code"] != "DOMAIN_NOT_ALLOWED" {
		t.Fatalf("expected DOMAIN_NOT_ALLOWED: %d %s", denied.code, denied.raw)
	}

	// Allow example.com via settings.
	settings, _ := s.store.Settings()
	settings.AllowedDomains = "example.com,other.org"
	if err := s.store.UpdateSettings(settings); err != nil {
		t.Fatal(err)
	}

	created := doJSON(t, s, "POST", "/api/v1/auth/signup", "", map[string]any{
		"email": "new@example.com", "password": "secret12",
	})
	if created.code != 201 {
		t.Fatalf("signup: %d %s", created.code, created.raw)
	}
	user := created.body["user"].(map[string]any)
	if user["isApproved"] != true {
		t.Fatal("allowlisted signup must be auto-approved")
	}
	if url, _ := created.body["claimUrl"].(string); !strings.Contains(url, "/claim/") {
		t.Fatalf("signup must return a claim URL, got %v", created.body["claimUrl"])
	}

	dup := doJSON(t, s, "POST", "/api/v1/auth/signup", "", map[string]any{
		"email": "new@example.com", "password": "secret12",
	})
	if dup.code != 409 || dup.body["code"] != "EMAIL_EXISTS" {
		t.Fatalf("duplicate signup: %d %s", dup.code, dup.raw)
	}

	short := doJSON(t, s, "POST", "/api/v1/auth/signup", "", map[string]any{
		"email": "x@example.com", "password": "abc",
	})
	if short.code != 400 || short.body["code"] != "INVALID_PASSWORD" {
		t.Fatalf("short password: %d %s", short.code, short.raw)
	}
}

func TestSignupViaDomainConfig(t *testing.T) {
	s := newTestServer(t)
	if _, err := s.store.CreateDomain("corp.io", nil); err != nil {
		t.Fatal(err)
	}
	got := doJSON(t, s, "POST", "/api/v1/auth/signup", "", map[string]any{
		"email": "dev@corp.io", "password": "secret12",
	})
	if got.code != 201 {
		t.Fatalf("DomainConfig entry should allow signup: %d %s", got.code, got.raw)
	}
}

func TestSignupClaimPrecreatedAccount(t *testing.T) {
	s := newTestServer(t)
	// Admin-precreated: approved, still on temporary password.
	hash, _ := auth.HashPassword("temp-p12-pass")
	pre := &store.User{Email: "invited@example.com", PasswordHash: hash, Role: "user",
		IsDefaultPIN: true, IsApproved: true}
	if err := s.store.CreateUser(pre); err != nil {
		t.Fatal(err)
	}

	got := doJSON(t, s, "POST", "/api/v1/auth/signup", "", map[string]any{
		"email": "invited@example.com", "password": "chosen-password",
	})
	if got.code != 200 { // claim returns 200, not 201
		t.Fatalf("claim: %d %s", got.code, got.raw)
	}
	claimed, _ := s.store.UserByEmail("invited@example.com")
	if claimed.IsDefaultPIN {
		t.Fatal("claim must clear the default-pin flag")
	}
	if !auth.VerifyPassword("chosen-password", claimed.PasswordHash) {
		t.Fatal("claim must set the chosen password")
	}
}

func TestChangePasswordFlow(t *testing.T) {
	s := newTestServer(t)
	_, token := seedUser(t, s, "user@example.com", "oldpass1", "user")

	wrong := doJSON(t, s, "POST", "/api/v1/auth/change-password", token, map[string]any{
		"currentPassword": "nope", "newPassword": "newpass1",
	})
	if wrong.code != 401 || wrong.body["code"] != "INVALID_CURRENT_PASSWORD" {
		t.Fatalf("wrong current password: %d %s", wrong.code, wrong.raw)
	}

	ok := doJSON(t, s, "POST", "/api/v1/auth/change-password", token, map[string]any{
		"currentPassword": "oldpass1", "newPassword": "newpass1",
	})
	if ok.code != 200 || ok.body["token"] == nil {
		t.Fatalf("change password: %d %s", ok.code, ok.raw)
	}
	u, _ := s.store.UserByEmail("user@example.com")
	if !auth.VerifyPassword("newpass1", u.PasswordHash) {
		t.Fatal("password not updated")
	}

	// Every pre-existing session is revoked; the returned token still works.
	if got := doJSON(t, s, "GET", "/api/v1/auth/me", token, nil); got.code != 401 {
		t.Fatalf("old session must be revoked after password change: %d %s", got.code, got.raw)
	}
	newToken := ok.body["token"].(string)
	if got := doJSON(t, s, "GET", "/api/v1/auth/me", newToken, nil); got.code != 200 {
		t.Fatalf("fresh session must work: %d %s", got.code, got.raw)
	}
}

func TestLogoutRevokesSession(t *testing.T) {
	s := newTestServer(t)
	_, token := seedUser(t, s, "user@example.com", "hunter22", "user")

	if got := doJSON(t, s, "GET", "/api/v1/auth/me", token, nil); got.code != 200 {
		t.Fatalf("me before logout: %d %s", got.code, got.raw)
	}
	if got := doJSON(t, s, "POST", "/api/v1/auth/logout", token, nil); got.code != 200 {
		t.Fatalf("logout: %d %s", got.code, got.raw)
	}
	if got := doJSON(t, s, "GET", "/api/v1/auth/me", token, nil); got.code != 401 {
		t.Fatalf("session must be dead after logout: %d %s", got.code, got.raw)
	}
}

func TestRefreshRotatesSession(t *testing.T) {
	s := newTestServer(t)
	_, token := seedUser(t, s, "user@example.com", "hunter22", "user")

	refreshed := doJSON(t, s, "POST", "/api/v1/auth/refresh", token, nil)
	if refreshed.code != 200 || refreshed.body["token"] == nil {
		t.Fatalf("refresh: %d %s", refreshed.code, refreshed.raw)
	}
	if got := doJSON(t, s, "GET", "/api/v1/auth/me", token, nil); got.code != 401 {
		t.Fatalf("old token must be revoked after refresh: %d", got.code)
	}
	if got := doJSON(t, s, "GET", "/api/v1/auth/me", refreshed.body["token"].(string), nil); got.code != 200 {
		t.Fatalf("rotated token must work: %d %s", got.code, got.raw)
	}
}

// -- Admin guard ---------------------------------------------------------------

func TestAdminGuard(t *testing.T) {
	s := newTestServer(t)
	_, userToken := seedUser(t, s, "user@example.com", "hunter22", "user")

	noToken := doJSON(t, s, "GET", "/api/v1/users", "", nil)
	if noToken.code != 401 || noToken.body["code"] != "ADMIN_AUTH_REQUIRED" {
		t.Fatalf("no token: %d %s", noToken.code, noToken.raw)
	}
	nonAdmin := doJSON(t, s, "GET", "/api/v1/users", userToken, nil)
	if nonAdmin.code != 403 || nonAdmin.body["code"] != "ADMIN_ACCESS_REQUIRED" {
		t.Fatalf("non-admin: %d %s", nonAdmin.code, nonAdmin.raw)
	}
}

// -- Cert lifecycle: claim links, revocation, reissue ----------------------------

// claimToken extracts the one-time token from a claim URL.
func claimToken(t *testing.T, claimURL string) string {
	t.Helper()
	_, token, ok := strings.Cut(claimURL, "/claim/")
	if !ok || token == "" {
		t.Fatalf("malformed claim URL %q", claimURL)
	}
	return token
}

// redeemClaim posts the claim token and returns the response body.
func redeemClaim(t *testing.T, s *Server, claimURL string) map[string]any {
	t.Helper()
	got := doJSON(t, s, "POST", "/api/v1/certs/claim", "", map[string]any{
		"token": claimToken(t, claimURL),
	})
	if got.code != 200 {
		t.Fatalf("claim: %d %s", got.code, got.raw)
	}
	return got.body
}

func TestCertClaimAndRevocationLifecycle(t *testing.T) {
	s := newTestServer(t)
	_, adminToken := seedUser(t, s, "admin@example.com", "adminpass", "admin")

	// Invite: no certificate yet, just a claim link.
	created := doJSON(t, s, "POST", "/api/v1/users", adminToken, map[string]any{
		"email": "member@example.com",
	})
	if created.code != 201 {
		t.Fatalf("create user: %d %s", created.code, created.raw)
	}
	claimURL, _ := created.body["claimUrl"].(string)
	if !strings.Contains(claimURL, "/claim/") {
		t.Fatalf("create user must return a claim URL: %s", created.raw)
	}
	member, _ := s.store.UserByEmail("member@example.com")
	if member.CertSerialNumber != nil {
		t.Fatal("certificate must not exist before the claim is redeemed")
	}

	// Inviting the same email again is a conflict (approval is a PUT now).
	dup := doJSON(t, s, "POST", "/api/v1/users", adminToken, map[string]any{"email": "member@example.com"})
	if dup.code != 409 || dup.body["code"] != "EMAIL_EXISTS" {
		t.Fatalf("duplicate create: %d %s", dup.code, dup.raw)
	}

	// Redeem: certificate is generated, password doubles as temp login.
	claim := redeemClaim(t, s, claimURL)
	if claim["p12"] == nil || claim["p12"] == "" {
		t.Fatal("claim must return the p12 bundle")
	}
	password, _ := claim["password"].(string)
	if password == "" || claim["passwordIsLogin"] != true {
		t.Fatalf("invited user must get a temporary login password: %s", claim)
	}
	member, _ = s.store.UserByEmail("member@example.com")
	if member.CertSerialNumber == nil {
		t.Fatal("claim must issue the certificate")
	}
	firstSerial := *member.CertSerialNumber

	// The temp password logs in and forces a change.
	login := doJSON(t, s, "POST", "/api/v1/auth/login", "", map[string]any{
		"email": "member@example.com", "password": password,
	})
	if login.code != 200 {
		t.Fatalf("login with claim password: %d %s", login.code, login.raw)
	}
	if login.body["user"].(map[string]any)["requiresPasswordChange"] != true {
		t.Fatal("claimed account must still require a password change")
	}

	// One-time: the same token cannot be redeemed twice.
	second := doJSON(t, s, "POST", "/api/v1/certs/claim", "", map[string]any{
		"token": claimToken(t, claimURL),
	})
	if second.code != 400 || second.body["code"] != "INVALID_CLAIM" {
		t.Fatalf("double claim: %d %s", second.code, second.raw)
	}

	// Revoke.
	revoked := doJSON(t, s, "POST", fmt.Sprintf("/api/v1/users/%d/revoke-cert", member.ID), adminToken, nil)
	if revoked.code != 200 {
		t.Fatalf("revoke: %d %s", revoked.code, revoked.raw)
	}
	if revoked.body["revokedSerial"] != firstSerial {
		t.Fatalf("revokedSerial = %v, want %s", revoked.body["revokedSerial"], firstSerial)
	}
	member, _ = s.store.UserByID(member.ID)
	if !member.CertRevoked || member.CertSerialNumber != nil {
		t.Fatalf("user cert state wrong after revoke: %+v", member)
	}
	if !certs.CRLMatchesCA(s.cfg.CRLPath(), s.cfg.CACertPath) {
		t.Fatal("CRL missing or not signed by the CA")
	}

	again := doJSON(t, s, "POST", fmt.Sprintf("/api/v1/users/%d/revoke-cert", member.ID), adminToken, nil)
	if again.code != 400 || again.body["code"] != "NO_ACTIVE_CERT" {
		t.Fatalf("double revoke: %d %s", again.code, again.raw)
	}

	// Reissue hands out a fresh claim link; the new cert appears on redeem.
	reissued := doJSON(t, s, "POST", fmt.Sprintf("/api/v1/users/%d/reissue-cert", member.ID), adminToken, nil)
	if reissued.code != 200 {
		t.Fatalf("reissue: %d %s", reissued.code, reissued.raw)
	}
	redeemClaim(t, s, reissued.body["claimUrl"].(string))
	member, _ = s.store.UserByID(member.ID)
	if member.CertRevoked || member.CertSerialNumber == nil || *member.CertSerialNumber == firstSerial {
		t.Fatalf("reissue+claim state wrong: %+v", member)
	}

	// Reissue with an active cert fails.
	active := doJSON(t, s, "POST", fmt.Sprintf("/api/v1/users/%d/reissue-cert", member.ID), adminToken, nil)
	if active.code != 400 || active.body["code"] != "CERT_STILL_ACTIVE" {
		t.Fatalf("reissue while active: %d %s", active.code, active.raw)
	}

	// History shows the original revocation.
	status := doJSON(t, s, "GET", fmt.Sprintf("/api/v1/users/%d/cert-status", member.ID), adminToken, nil)
	if status.code != 200 || status.body["isRevoked"] != false {
		t.Fatalf("cert status: %d %s", status.code, status.raw)
	}
	history := status.body["revocationHistory"].([]any)
	if len(history) != 1 {
		t.Fatalf("history length = %d, want 1", len(history))
	}
	first := history[0].(map[string]any)
	if first["serialNumber"] != firstSerial || first["reason"] != "admin_revoked" {
		t.Fatalf("history entry wrong: %v", first)
	}
}

func TestExpiredClaimRejected(t *testing.T) {
	s := newTestServer(t)
	user, _ := seedUser(t, s, "late@example.com", "hunter22", "user")

	// A claim that expired yesterday.
	if err := s.store.CreateCertClaim(auth.HashToken("stale-token"), user.ID, timeNowAdd(-24)); err != nil {
		t.Fatal(err)
	}
	got := doJSON(t, s, "POST", "/api/v1/certs/claim", "", map[string]any{"token": "stale-token"})
	if got.code != 400 || got.body["code"] != "INVALID_CLAIM" {
		t.Fatalf("expired claim: %d %s", got.code, got.raw)
	}
}

// -- mTLS enforcement + CN mismatch auto-revoke ---------------------------------

func TestMTLSEnforcementAndAutoRevoke(t *testing.T) {
	s := newTestServer(t)
	_, adminToken := seedUser(t, s, "admin@example.com", "adminpass", "admin")
	_, userToken := seedUser(t, s, "user@example.com", "hunter22", "user")

	// Admins bypass mTLS entirely.
	if got := doJSON(t, s, "GET", "/api/v1/files", adminToken, nil); got.code != 200 {
		t.Fatalf("admin list files: %d %s", got.code, got.raw)
	}

	// Non-admin without a client cert is blocked.
	noCert := doJSON(t, s, "GET", "/api/v1/files", userToken, nil)
	if noCert.code != 403 || noCert.body["code"] != "CLIENT_CERT_REQUIRED" {
		t.Fatalf("no cert: %d %s", noCert.code, noCert.raw)
	}

	// A cert belonging to someone else trips the mismatch logger; the victim
	// (whose cert is being abused) holds a certificate.
	victim := doJSON(t, s, "POST", "/api/v1/users", adminToken, map[string]any{"email": "victim@example.com"})
	if victim.code != 201 {
		t.Fatalf("create victim: %d %s", victim.code, victim.raw)
	}
	redeemClaim(t, s, victim.body["claimUrl"].(string))
	mismatchHeaders := map[string]string{
		"X-SSL-Client-Verify": "SUCCESS",
		"X-SSL-Client-S-DN":   "O=terracrate,OU=member,CN=victim@example.com",
	}
	for i := 0; i < 3; i++ {
		got := doJSON(t, s, "GET", "/api/v1/files", userToken, nil, mismatchHeaders)
		if got.code != 403 || got.body["code"] != "CLIENT_CERT_MISMATCH" {
			t.Fatalf("mismatch attempt %d: %d %s", i, got.code, got.raw)
		}
	}
	// Threshold (3) reached: the abused cert is auto-revoked.
	abused, _ := s.store.UserByEmail("victim@example.com")
	if !abused.CertRevoked {
		t.Fatal("abused certificate was not auto-revoked")
	}
	records, _ := s.store.AllRevokedCertificates()
	if len(records) != 1 || records[0].Reason != "cn_mismatch_abuse" {
		t.Fatalf("revocation record wrong: %+v", records)
	}

	// Matching CN passes through to the listing.
	okHeaders := map[string]string{
		"X-SSL-Client-Verify": "SUCCESS",
		"X-SSL-Client-S-DN":   "O=terracrate,OU=member,CN=user@example.com",
	}
	if got := doJSON(t, s, "GET", "/api/v1/files", userToken, nil, okHeaders); got.code != 200 {
		t.Fatalf("matching cert: %d %s", got.code, got.raw)
	}
}

// -- Files (upload/list/permission filtering) ------------------------------------

func uploadFile(t *testing.T, s *Server, token, path, filename, content string) resp {
	t.Helper()
	var buf bytes.Buffer
	mw := multipart.NewWriter(&buf)
	_ = mw.WriteField("path", path)
	fw, _ := mw.CreateFormFile("file", filename)
	_, _ = fw.Write([]byte(content))
	mw.Close()

	req := httptest.NewRequest("POST", "/api/v1/files/upload", &buf)
	req.Header.Set("Authorization", "Bearer "+token)
	req.Header.Set("Content-Type", mw.FormDataContentType())
	rec := httptest.NewRecorder()
	s.Handler().ServeHTTP(rec, req)

	out := resp{code: rec.Code, raw: rec.Body.Bytes()}
	_ = json.Unmarshal(out.raw, &out.body)
	return out
}

func TestFileUploadListDownloadDelete(t *testing.T) {
	s := newTestServer(t)
	_, adminToken := seedUser(t, s, "admin@example.com", "adminpass", "admin")

	up := uploadFile(t, s, adminToken, "docs", "report final.pdf", "PDFDATA")
	if up.code != 201 {
		t.Fatalf("upload: %d %s", up.code, up.raw)
	}
	f := up.body["file"].(map[string]any)
	// int64 fields ride as strings in proto3 JSON.
	if f["name"] != "report_final.pdf" || f["path"] != "docs/report_final.pdf" || f["size"] != "7" {
		t.Fatalf("upload payload wrong: %v", f)
	}

	list := doJSON(t, s, "GET", "/api/v1/files?path=docs", adminToken, nil)
	if list.code != 200 {
		t.Fatalf("list: %d %s", list.code, list.raw)
	}
	files := list.body["files"].([]any)
	if len(files) != 1 || files[0].(map[string]any)["name"] != "report_final.pdf" {
		t.Fatalf("listing wrong: %v", files)
	}
	if list.body["currentPath"] != "/docs" {
		t.Fatalf("currentPath = %v", list.body["currentPath"])
	}

	// Download.
	req := httptest.NewRequest("GET", "/api/v1/files/download?path=docs/report_final.pdf", nil)
	req.Header.Set("Authorization", "Bearer "+adminToken)
	rec := httptest.NewRecorder()
	s.Handler().ServeHTTP(rec, req)
	if rec.Code != 200 || rec.Body.String() != "PDFDATA" {
		t.Fatalf("download: %d %q", rec.Code, rec.Body.String())
	}
	if cd := rec.Header().Get("Content-Disposition"); !strings.Contains(cd, "attachment") {
		t.Fatalf("Content-Disposition = %q", cd)
	}

	// Traversal is rejected as not-found.
	esc := doJSON(t, s, "GET", "/api/v1/files/download?path=../../etc/passwd", adminToken, nil)
	if esc.code != 404 {
		t.Fatalf("traversal: %d %s", esc.code, esc.raw)
	}

	// Delete.
	del := doJSON(t, s, "DELETE", "/api/v1/files?path=docs/report_final.pdf", adminToken, nil)
	if del.code != 200 || del.body["success"] != true {
		t.Fatalf("delete: %d %s", del.code, del.raw)
	}
}

func TestNonAdminListingIsPermissionFiltered(t *testing.T) {
	s := newTestServer(t)
	_, adminToken := seedUser(t, s, "admin@example.com", "adminpass", "admin")
	user, userToken := seedUser(t, s, "user@example.com", "hunter22", "user")

	// Two top-level folders with content; the user may only read /docs.
	if up := uploadFile(t, s, adminToken, "docs", "visible.txt", "a"); up.code != 201 {
		t.Fatalf("seed upload: %d %s", up.code, up.raw)
	}
	if up := uploadFile(t, s, adminToken, "private", "secret.txt", "b"); up.code != 201 {
		t.Fatalf("seed upload: %d %s", up.code, up.raw)
	}
	if err := s.store.ReplaceFolderPermissions(user.ID, []*store.FolderPermission{
		{UserID: user.ID, FolderPath: "/docs", CanRead: strPtrT("allow")},
	}); err != nil {
		t.Fatal(err)
	}

	headers := map[string]string{
		"X-SSL-Client-Verify": "SUCCESS",
		"X-SSL-Client-S-DN":   "CN=user@example.com",
	}
	root := doJSON(t, s, "GET", "/api/v1/files", userToken, nil, headers)
	if root.code != 200 {
		t.Fatalf("list: %d %s", root.code, root.raw)
	}
	files := root.body["files"].([]any)
	if len(files) != 2 {
		// storage always contains the guest folder; only docs+guest? guest is
		// not granted, so expect exactly 1 item: docs.
		t.Logf("root listing: %s", root.raw)
	}
	var names []string
	for _, f := range files {
		names = append(names, f.(map[string]any)["name"].(string))
	}
	if len(names) != 1 || names[0] != "docs" {
		t.Fatalf("filtered listing = %v, want [docs]", names)
	}

	// Upload into /docs denied without write.
	if up := uploadFileWithHeaders(t, s, userToken, "docs", "new.txt", "x", headers); up.code != 403 {
		t.Fatalf("write without grant: %d %s", up.code, up.raw)
	}
}

func uploadFileWithHeaders(t *testing.T, s *Server, token, path, filename, content string, hdrs map[string]string) resp {
	t.Helper()
	var buf bytes.Buffer
	mw := multipart.NewWriter(&buf)
	_ = mw.WriteField("path", path)
	fw, _ := mw.CreateFormFile("file", filename)
	_, _ = fw.Write([]byte(content))
	mw.Close()

	req := httptest.NewRequest("POST", "/api/v1/files/upload", &buf)
	req.Header.Set("Authorization", "Bearer "+token)
	req.Header.Set("Content-Type", mw.FormDataContentType())
	for k, v := range hdrs {
		req.Header.Set(k, v)
	}
	rec := httptest.NewRecorder()
	s.Handler().ServeHTTP(rec, req)
	out := resp{code: rec.Code, raw: rec.Body.Bytes()}
	_ = json.Unmarshal(out.raw, &out.body)
	return out
}

func strPtrT(s string) *string { return &s }

func timeNowAdd(hours int) time.Time { return time.Now().UTC().Add(time.Duration(hours) * time.Hour) }

// -- Settings (mirrors test_signup.py::TestSettingsAllowedDomains) ---------------

func TestSettingsUpdateAndMasking(t *testing.T) {
	s := newTestServer(t)
	_, adminToken := seedUser(t, s, "admin@example.com", "adminpass", "admin")

	upd := doJSON(t, s, "PUT", "/api/v1/settings", adminToken, map[string]any{
		"allowedDomains": []string{"@Example.COM", "corp.io"},
		"smtpPassword":   "hunter2",
		"smtpEnabled":    true,
	})
	if upd.code != 200 {
		t.Fatalf("update settings: %d %s", upd.code, upd.raw)
	}
	domains := upd.body["allowedDomains"].([]any)
	if len(domains) != 2 || domains[0] != "example.com" || domains[1] != "corp.io" {
		t.Fatalf("allowedDomains = %v (must strip @ and lowercase)", domains)
	}
	if upd.body["smtpPassword"] != "*****" {
		t.Fatalf("smtpPassword not masked: %v", upd.body["smtpPassword"])
	}

	// The masked placeholder must not overwrite the stored secret.
	doJSON(t, s, "PUT", "/api/v1/settings", adminToken, map[string]any{"smtpPassword": "*****"})
	settings, _ := s.store.Settings()
	if settings.SMTPPassword != "hunter2" {
		t.Fatalf("mask overwrote password: %q", settings.SMTPPassword)
	}

	// Domain configs were auto-created for the allowlist.
	if dc, _ := s.store.DomainByName("example.com"); dc == nil {
		t.Fatal("allowlisted domain has no auto-created DomainConfig")
	}

	invalid := doJSON(t, s, "PUT", "/api/v1/settings", adminToken, map[string]any{
		"allowedDomains": []string{"not-a-domain"},
	})
	if invalid.code != 400 || invalid.body["code"] != "INVALID_DOMAIN" {
		t.Fatalf("invalid domain: %d %s", invalid.code, invalid.raw)
	}

	badMethod := doJSON(t, s, "PUT", "/api/v1/settings", adminToken, map[string]any{"authMethod": "carrier-pigeon"})
	if badMethod.code != 400 || badMethod.body["code"] != "INVALID_AUTH_METHOD" {
		t.Fatalf("invalid auth method: %d %s", badMethod.code, badMethod.raw)
	}

	// GET is public and includes the allowlist.
	pub := doJSON(t, s, "GET", "/api/v1/settings", "", nil)
	if pub.code != 200 || len(pub.body["allowedDomains"].([]any)) != 2 {
		t.Fatalf("public settings: %d %s", pub.code, pub.raw)
	}
}

// -- Domains & groups (mirrors test_permissions.py CRUD + effective) -------------

func TestDomainAndGroupLifecycleAndEffectivePermissions(t *testing.T) {
	s := newTestServer(t)
	_, adminToken := seedUser(t, s, "admin@example.com", "adminpass", "admin")
	user, _ := seedUser(t, s, "dev@corp.io", "hunter22", "user")

	// Domain with default perms for corp.io.
	dom := doJSON(t, s, "POST", "/api/v1/domains", adminToken, map[string]any{
		"domain":      "corp.io",
		"permissions": []map[string]any{{"path": "/docs", "read": true, "write": false}},
	})
	if dom.code != 201 {
		t.Fatalf("create domain: %d %s", dom.code, dom.raw)
	}
	dup := doJSON(t, s, "POST", "/api/v1/domains", adminToken, map[string]any{"domain": "corp.io"})
	if dup.code != 409 {
		t.Fatalf("duplicate domain: %d %s", dup.code, dup.raw)
	}

	// Group granting write on /docs.
	grp := doJSON(t, s, "POST", "/api/v1/groups", adminToken, map[string]any{"name": "editors"})
	if grp.code != 201 {
		t.Fatalf("create group: %d %s", grp.code, grp.raw)
	}
	groupID := int(grp.body["group"].(map[string]any)["id"].(float64))
	if got := doJSON(t, s, "PUT", fmt.Sprintf("/api/v1/groups/%d/permissions", groupID), adminToken,
		map[string]any{"permissions": []map[string]any{{"path": "/docs", "read": true, "write": true}}}); got.code != 200 {
		t.Fatalf("group perms: %d %s", got.code, got.raw)
	}
	if got := doJSON(t, s, "PUT", fmt.Sprintf("/api/v1/groups/%d/members", groupID), adminToken,
		map[string]any{"userIds": []int{user.ID}}); got.code != 200 {
		t.Fatalf("group members: %d %s", got.code, got.raw)
	}

	// User-level deny on write.
	if got := doJSON(t, s, "PUT", fmt.Sprintf("/api/v1/users/%d/permissions", user.ID), adminToken,
		map[string]any{"permissions": []map[string]any{{"path": "/docs", "read": nil, "write": "deny"}}}); got.code != 200 {
		t.Fatalf("user perms: %d %s", got.code, got.raw)
	}

	eff := doJSON(t, s, "GET", fmt.Sprintf("/api/v1/users/%d/effective-permissions", user.ID), adminToken, nil)
	if eff.code != 200 {
		t.Fatalf("effective: %d %s", eff.code, eff.raw)
	}
	entry := eff.body["permissions"].(map[string]any)["/docs"].(map[string]any)
	effective := entry["effective"].(map[string]any)
	if effective["canRead"] != true || effective["canWrite"] != false || effective["source"] != "user" {
		t.Fatalf("effective resolution wrong: %v", effective)
	}
	if entry["domain"] == nil || entry["groupMerged"] == nil || entry["user"] == nil {
		t.Fatalf("tier attribution missing: %s", eff.raw)
	}

	// Group deletion cascades.
	if got := doJSON(t, s, "DELETE", fmt.Sprintf("/api/v1/groups/%d", groupID), adminToken, nil); got.code != 200 {
		t.Fatalf("delete group: %d %s", got.code, got.raw)
	}
	if got, _ := s.store.GroupPermissions(groupID); len(got) != 0 {
		t.Fatal("group permissions not cascaded")
	}
}

// -- Health -----------------------------------------------------------------------

func TestHealth(t *testing.T) {
	s := newTestServer(t)
	got := doJSON(t, s, "GET", "/health", "", nil)
	if got.code != 200 || got.body["status"] != "healthy" || got.body["version"] != "2.0" {
		t.Fatalf("health: %d %s", got.code, got.raw)
	}
}
