package httpapi

import (
	"fmt"
	"log/slog"
	"net/http"
	"strings"
	"time"

	"github.com/andreas-04/terra-crate/backend/internal/audit"
	"github.com/andreas-04/terra-crate/backend/internal/store"
)

// requireMTLS enforces the client-certificate policy for non-admin users.
// nginx forwards X-SSL-Client-Verify ("SUCCESS" when the client cert chained
// to the CA) and X-SSL-Client-S-DN (the cert subject). The cert CN must match
// the authenticated user's email so one user's cert can't ride another's
// session. Returns true when an error response was written.
func (s *Server) requireMTLS(w http.ResponseWriter, r *http.Request, user *store.User) bool {
	if user == nil || user.Role == "admin" {
		return false
	}
	if r.Header.Get("X-SSL-Client-Verify") != "SUCCESS" {
		writeError(w, http.StatusForbidden,
			"A valid client certificate is required. Please install your .p12 certificate.",
			"CLIENT_CERT_REQUIRED")
		return true
	}

	var cn string
	for _, part := range strings.Split(r.Header.Get("X-SSL-Client-S-DN"), ",") {
		part = strings.TrimSpace(part)
		if strings.HasPrefix(strings.ToUpper(part), "CN=") {
			cn = strings.TrimSpace(part[3:])
			break
		}
	}
	if cn == "" || !strings.EqualFold(cn, user.Email) {
		s.logCNMismatch(r, cn, user.ID)
		writeError(w, http.StatusForbidden,
			"Client certificate does not match your account. Please install the correct .p12 certificate.",
			"CLIENT_CERT_MISMATCH")
		return true
	}
	return false
}

// logCNMismatch records the mismatch for abuse detection and auto-revokes the
// presented certificate once the threshold is exceeded within the window.
func (s *Server) logCNMismatch(r *http.Request, presentedCN string, authenticatedUserID int) {
	if presentedCN == "" {
		return
	}
	if err := s.store.InsertMtlsMismatch(presentedCN, authenticatedUserID); err != nil {
		slog.Error("mtls: failed to record mismatch", "error", err)
		return
	}
	s.logAudit(r, "cert.mtls_mismatch", audit.Entry{
		TargetType:  "user",
		TargetID:    fmt.Sprint(authenticatedUserID),
		Description: fmt.Sprintf("mTLS CN mismatch: presented %s", presentedCN),
		Status:      "failure",
		UserID:      authenticatedUserID,
	})

	windowStart := time.Now().UTC().Add(-time.Duration(s.cfg.CNMismatchWindowMinutes) * time.Minute)
	count, err := s.store.CountRecentMismatches(presentedCN, windowStart)
	if err != nil || count < s.cfg.CNMismatchThreshold {
		return
	}

	// The CN identifies the certificate being abused; revoke it.
	abused, err := s.store.UserByEmail(presentedCN)
	if err != nil || abused == nil || abused.CertSerialNumber == nil || abused.CertRevoked {
		return
	}
	slog.Warn("mtls: auto-revoking abused certificate",
		"cn", presentedCN, "mismatches", count, "windowMinutes", s.cfg.CNMismatchWindowMinutes)
	if _, err := s.revokeUserCert(abused, "cn_mismatch_abuse", nil); err != nil {
		slog.Error("mtls: auto-revoke failed", "error", err)
	}
}
