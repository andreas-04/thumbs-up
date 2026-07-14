package httpapi

import (
	"fmt"
	"net/http"
	"strings"
	"time"

	pb "github.com/andreas-04/terra-crate/backend/gen/terracrate/v1"
	"github.com/andreas-04/terra-crate/backend/internal/audit"
	"github.com/andreas-04/terra-crate/backend/internal/auth"
	"github.com/andreas-04/terra-crate/backend/internal/store"
)

const minPasswordLen = 8

func (s *Server) handleLogin(w http.ResponseWriter, r *http.Request) {
	var req pb.LoginRequest
	if _, ok := bodyInto(r, &req); !ok {
		writeError(w, http.StatusBadRequest, "Request body required", "MISSING_BODY")
		return
	}
	email := strings.TrimSpace(req.GetEmail())
	password := strings.TrimSpace(req.GetPassword())
	if email == "" || password == "" {
		writeError(w, http.StatusBadRequest, "Email and password required", "MISSING_CREDENTIALS")
		return
	}

	user, err := s.store.UserByEmail(email)
	if err != nil {
		writeError(w, http.StatusInternalServerError, err.Error(), "INTERNAL_ERROR")
		return
	}
	if user != nil && !auth.VerifyPassword(password, user.PasswordHash) {
		user = nil
	}
	if user == nil {
		s.logAudit(r, "auth.login_failed", audit.Entry{
			TargetType:  "user",
			Description: fmt.Sprintf("Failed login attempt for %s", email),
			Status:      "failure",
			UserEmail:   email,
		})
		writeError(w, http.StatusUnauthorized, "Invalid credentials", "INVALID_CREDENTIALS")
		return
	}

	now := time.Now().UTC()
	user.LastLogin = &now
	if err := s.store.UpdateUser(user); err != nil {
		writeError(w, http.StatusInternalServerError, err.Error(), "INTERNAL_ERROR")
		return
	}
	token, err := s.newSessionToken(user)
	if err != nil {
		writeError(w, http.StatusInternalServerError, err.Error(), "INTERNAL_ERROR")
		return
	}

	s.logAudit(r, "auth.login", audit.Entry{
		TargetType:  "user",
		TargetID:    fmt.Sprint(user.ID),
		Description: fmt.Sprintf("User %s logged in", user.Email),
		UserID:      user.ID,
		UserEmail:   user.Email,
	})
	writeProto(w, http.StatusOK, &pb.TokenUserResponse{Token: token, User: s.pbUser(user)})
}

func (s *Server) handleSignup(w http.ResponseWriter, r *http.Request) {
	var req pb.SignupRequest
	if _, ok := bodyInto(r, &req); !ok {
		writeError(w, http.StatusBadRequest, "Request body required", "MISSING_BODY")
		return
	}
	email := strings.TrimSpace(req.GetEmail())
	password := strings.TrimSpace(req.GetPassword())

	if email == "" || !strings.Contains(email, "@") {
		writeError(w, http.StatusBadRequest, "Valid email required", "INVALID_EMAIL")
		return
	}
	if len(password) < minPasswordLen {
		writeError(w, http.StatusBadRequest,
			fmt.Sprintf("Password must be at least %d characters", minPasswordLen), "INVALID_PASSWORD")
		return
	}

	existing, err := s.store.UserByEmail(email)
	if err != nil {
		writeError(w, http.StatusInternalServerError, err.Error(), "INTERNAL_ERROR")
		return
	}
	if existing != nil {
		// A pre-approved, admin-created account still on its temporary
		// password may be claimed via signup.
		if existing.IsApproved && existing.IsDefaultPIN {
			hash, herr := auth.HashPassword(password)
			if herr != nil {
				writeError(w, http.StatusInternalServerError, herr.Error(), "INTERNAL_ERROR")
				return
			}
			now := time.Now().UTC()
			existing.PasswordHash = hash
			existing.IsDefaultPIN = false
			existing.LastLogin = &now
			if err := s.store.UpdateUser(existing); err != nil {
				writeError(w, http.StatusInternalServerError, err.Error(), "INTERNAL_ERROR")
				return
			}
			token, terr := s.newSessionToken(existing)
			if terr != nil {
				writeError(w, http.StatusInternalServerError, terr.Error(), "INTERNAL_ERROR")
				return
			}
			writeProto(w, http.StatusOK, &pb.SignupResponse{Token: token, User: s.pbUser(existing)})
			return
		}
		writeError(w, http.StatusConflict, "Email already registered", "EMAIL_EXISTS")
		return
	}

	// Domain allowlist: settings allowlist plus DomainConfig entries.
	emailDomain := strings.ToLower(email[strings.LastIndex(email, "@")+1:])
	settings, err := s.store.Settings()
	if err != nil {
		writeError(w, http.StatusInternalServerError, err.Error(), "INTERNAL_ERROR")
		return
	}
	allowed := false
	if settings != nil {
		for _, d := range strings.Split(settings.AllowedDomains, ",") {
			if d = strings.ToLower(strings.TrimSpace(d)); d != "" && d == emailDomain {
				allowed = true
				break
			}
		}
	}
	if !allowed {
		if dc, derr := s.store.DomainByName(emailDomain); derr == nil && dc != nil {
			allowed = true
		}
	}
	if !allowed {
		writeError(w, http.StatusForbidden,
			"Registration is not open for this email domain. Contact your administrator.", "DOMAIN_NOT_ALLOWED")
		return
	}

	hash, err := auth.HashPassword(password)
	if err != nil {
		writeError(w, http.StatusInternalServerError, err.Error(), "INTERNAL_ERROR")
		return
	}
	// Domain-allowlisted signups are auto-approved for protected files.
	user := &store.User{Email: email, PasswordHash: hash, Role: "user", IsDefaultPIN: false, IsApproved: true}
	if err := s.store.CreateUser(user); err != nil {
		writeError(w, http.StatusInternalServerError, err.Error(), "INTERNAL_ERROR")
		return
	}

	// Certificate delivery: a one-time claim link, returned in the response
	// and emailed when SMTP is configured.
	claimURL, err := s.issueClaim(user)
	if err != nil {
		writeError(w, http.StatusInternalServerError, err.Error(), "INTERNAL_ERROR")
		return
	}
	if settings != nil && settings.SMTPEnabled {
		s.emailClaimLink(settings, user, claimURL, false)
	}

	token, err := s.newSessionToken(user)
	if err != nil {
		writeError(w, http.StatusInternalServerError, err.Error(), "INTERNAL_ERROR")
		return
	}
	s.logAudit(r, "auth.signup", audit.Entry{
		TargetType:  "user",
		TargetID:    fmt.Sprint(user.ID),
		Description: fmt.Sprintf("New signup: %s", user.Email),
		UserID:      user.ID,
		UserEmail:   user.Email,
	})
	writeProto(w, http.StatusCreated, &pb.SignupResponse{Token: token, User: s.pbUser(user), ClaimUrl: claimURL})
}

func (s *Server) handleLogout(w http.ResponseWriter, r *http.Request) {
	if sess := currentSession(r); sess != nil {
		if err := s.store.RevokeSession(sess.ID); err != nil {
			writeError(w, http.StatusInternalServerError, err.Error(), "INTERNAL_ERROR")
			return
		}
	}
	s.logAudit(r, "auth.logout", audit.Entry{Description: "User logged out"})
	writeSuccess(w)
}

func (s *Server) handleMe(w http.ResponseWriter, r *http.Request) {
	writeProto(w, http.StatusOK, &pb.MeResponse{User: s.pbUserDetail(currentUser(r))})
}

// handleRefresh rotates the session: a new token is issued and the presented
// one is revoked.
func (s *Server) handleRefresh(w http.ResponseWriter, r *http.Request) {
	user := currentUser(r)
	token, err := s.newSessionToken(user)
	if err != nil {
		writeError(w, http.StatusInternalServerError, err.Error(), "INTERNAL_ERROR")
		return
	}
	if sess := currentSession(r); sess != nil {
		_ = s.store.RevokeSession(sess.ID)
	}
	writeProto(w, http.StatusOK, &pb.TokenResponse{Token: token})
}

func (s *Server) handleChangePassword(w http.ResponseWriter, r *http.Request) {
	var req pb.ChangePasswordRequest
	if _, ok := bodyInto(r, &req); !ok {
		writeError(w, http.StatusBadRequest, "Request body required", "MISSING_BODY")
		return
	}
	currentPassword := strings.TrimSpace(req.GetCurrentPassword())
	newPassword := strings.TrimSpace(req.GetNewPassword())

	if len(newPassword) < minPasswordLen {
		writeError(w, http.StatusBadRequest,
			fmt.Sprintf("New password must be at least %d characters", minPasswordLen), "INVALID_PASSWORD")
		return
	}
	user := currentUser(r)

	// A forced first-time change (still on the initial PIN) skips the
	// current-password check.
	if !user.IsDefaultPIN {
		if currentPassword == "" {
			writeError(w, http.StatusBadRequest, "Current password required", "MISSING_CURRENT_PASSWORD")
			return
		}
		if !auth.VerifyPassword(currentPassword, user.PasswordHash) {
			writeError(w, http.StatusUnauthorized, "Current password is incorrect", "INVALID_CURRENT_PASSWORD")
			return
		}
	}

	hash, err := auth.HashPassword(newPassword)
	if err != nil {
		writeError(w, http.StatusInternalServerError, err.Error(), "INTERNAL_ERROR")
		return
	}
	user.PasswordHash = hash
	user.IsDefaultPIN = false
	if err := s.store.UpdateUser(user); err != nil {
		writeError(w, http.StatusInternalServerError, err.Error(), "INTERNAL_ERROR")
		return
	}

	// Changing the password invalidates every existing session, then issues
	// a fresh one for this client.
	if err := s.store.RevokeUserSessions(user.ID); err != nil {
		writeError(w, http.StatusInternalServerError, err.Error(), "INTERNAL_ERROR")
		return
	}
	token, err := s.newSessionToken(user)
	if err != nil {
		writeError(w, http.StatusInternalServerError, err.Error(), "INTERNAL_ERROR")
		return
	}

	s.logAudit(r, "auth.password_change", audit.Entry{
		TargetType:  "user",
		TargetID:    fmt.Sprint(user.ID),
		Description: "Password changed",
		UserID:      user.ID,
		UserEmail:   user.Email,
	})
	writeProto(w, http.StatusOK, &pb.TokenUserResponse{Token: token, User: s.pbUser(user)})
}
