package httpapi

import (
	"fmt"
	"net/http"
	"strings"
	"time"

	pb "github.com/andreas-04/terra-crate/backend/gen/terracrate/v1"
	"github.com/andreas-04/terra-crate/backend/internal/audit"
	"github.com/andreas-04/terra-crate/backend/internal/auth"
	"github.com/andreas-04/terra-crate/backend/internal/certs"
	"github.com/andreas-04/terra-crate/backend/internal/mailer"
	"github.com/andreas-04/terra-crate/backend/internal/store"
)

const (
	clientCertValidityDays = 365
	claimValidity          = 7 * 24 * time.Hour
	p12Filename            = "terracrate-client.p12"
)

func (s *Server) newClientP12(email string) (*certs.P12Bundle, error) {
	return certs.GenerateClientP12(s.cfg.CACertPath, s.cfg.CAKeyPath, email, clientCertValidityDays)
}

// issueClaim creates a one-time certificate claim token for the user
// (superseding any outstanding one) and returns the public claim URL.
func (s *Server) issueClaim(user *store.User) (string, error) {
	plain, hash, err := auth.NewToken()
	if err != nil {
		return "", err
	}
	if err := s.store.CreateCertClaim(hash, user.ID, time.Now().UTC().Add(claimValidity)); err != nil {
		return "", err
	}
	return strings.TrimRight(s.cfg.PublicURL, "/") + "/claim/" + plain, nil
}

// emailClaimLink sends the claim URL; invite covers admin-created accounts,
// otherwise the approval wording is used. Failures are non-fatal.
func (s *Server) emailClaimLink(settings *store.SystemSettings, user *store.User, claimURL string, invite bool) {
	deviceName := settings.DeviceName
	if deviceName == "" {
		deviceName = "TerraCrate"
	}
	if invite {
		_ = mailer.SendInviteEmail(settings, user.Email, deviceName, claimURL)
		return
	}
	_ = mailer.SendApprovalEmail(settings, user.Email, deviceName, claimURL)
}

// handleClaimCert redeems a one-time claim token: the client certificate is
// generated on the spot and never stored or emailed. For admin-invited
// accounts the .p12 password doubles as the temporary login password.
func (s *Server) handleClaimCert(w http.ResponseWriter, r *http.Request) {
	var req pb.ClaimCertRequest
	if _, ok := bodyInto(r, &req); !ok {
		writeError(w, http.StatusBadRequest, "Request body required", "MISSING_BODY")
		return
	}
	token := strings.TrimSpace(req.GetToken())
	if token == "" {
		writeError(w, http.StatusBadRequest, "Claim token required", "MISSING_TOKEN")
		return
	}

	invalid := func() {
		writeError(w, http.StatusBadRequest,
			"This certificate link is invalid, expired, or has already been used.", "INVALID_CLAIM")
	}

	claim, err := s.store.CertClaimByTokenHash(auth.HashToken(token))
	if err != nil {
		writeError(w, http.StatusInternalServerError, err.Error(), "INTERNAL_ERROR")
		return
	}
	if claim == nil || !claim.Claimable(time.Now().UTC()) {
		invalid()
		return
	}
	user, err := s.store.UserByID(claim.UserID)
	if err != nil {
		writeError(w, http.StatusInternalServerError, err.Error(), "INTERNAL_ERROR")
		return
	}
	if user == nil {
		invalid()
		return
	}

	// Consume the claim first so concurrent redeems can't both succeed.
	used, err := s.store.MarkCertClaimUsed(claim.ID)
	if err != nil {
		writeError(w, http.StatusInternalServerError, err.Error(), "INTERNAL_ERROR")
		return
	}
	if !used {
		invalid()
		return
	}

	bundle, err := s.newClientP12(user.Email)
	if err != nil {
		writeError(w, http.StatusInternalServerError, "Failed to generate certificate", "CERT_GEN_FAILED")
		return
	}

	serial := fmt.Sprintf("%x", bundle.Serial)
	user.CertSerialNumber = &serial
	user.CertIssuedAt = &bundle.NotBefore
	user.CertExpiresAt = &bundle.NotAfter
	user.CertRevoked = false

	// Admin-invited accounts get the bundle password as their temporary
	// login password (a change is forced on first login).
	passwordIsLogin := user.IsDefaultPIN
	if passwordIsLogin {
		hash, herr := auth.HashPassword(bundle.Password)
		if herr != nil {
			writeError(w, http.StatusInternalServerError, herr.Error(), "INTERNAL_ERROR")
			return
		}
		user.PasswordHash = hash
	}
	if err := s.store.UpdateUser(user); err != nil {
		writeError(w, http.StatusInternalServerError, err.Error(), "INTERNAL_ERROR")
		return
	}

	s.logAudit(r, "cert.claim", audit.Entry{
		TargetType:  "user",
		TargetID:    fmt.Sprint(user.ID),
		Description: fmt.Sprintf("Certificate claimed for %s", user.Email),
		UserID:      user.ID,
		UserEmail:   user.Email,
	})
	writeProto(w, http.StatusOK, &pb.ClaimCertResponse{
		P12:             bundle.Data,
		Filename:        p12Filename,
		Password:        bundle.Password,
		PasswordIsLogin: passwordIsLogin,
		Email:           user.Email,
	})
}
