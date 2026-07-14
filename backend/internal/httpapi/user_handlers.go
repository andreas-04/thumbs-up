package httpapi

import (
	"fmt"
	"math/big"
	"net/http"
	"strconv"
	"strings"

	pb "github.com/andreas-04/terra-crate/backend/gen/terracrate/v1"
	"github.com/andreas-04/terra-crate/backend/internal/audit"
	"github.com/andreas-04/terra-crate/backend/internal/auth"
	"github.com/andreas-04/terra-crate/backend/internal/certs"
	"github.com/andreas-04/terra-crate/backend/internal/mailer"
	"github.com/andreas-04/terra-crate/backend/internal/store"
)

// pathID parses a numeric route segment; -1 on failure (which then misses
// every lookup, yielding a 404).
func pathID(r *http.Request, name string) int {
	id, err := strconv.Atoi(r.PathValue(name))
	if err != nil {
		return -1
	}
	return id
}

func queryInt(r *http.Request, name string, def int) int {
	if v := r.URL.Query().Get(name); v != "" {
		if n, err := strconv.Atoi(v); err == nil {
			return n
		}
	}
	return def
}

func (s *Server) handleListUsers(w http.ResponseWriter, r *http.Request) {
	search := strings.TrimSpace(r.URL.Query().Get("search"))
	page := queryInt(r, "page", 1)
	limit := queryInt(r, "limit", 50)

	users, total, err := s.store.ListUsers(search, page, limit)
	if err != nil {
		writeError(w, http.StatusInternalServerError, err.Error(), "INTERNAL_ERROR")
		return
	}
	out := []*pb.UserDetail{}
	for _, u := range users {
		out = append(out, s.pbUserDetail(u))
	}
	writeProto(w, http.StatusOK, &pb.ListUsersResponse{
		Users: out,
		Total: int32(total),
		Page:  int32(page),
		Limit: int32(limit),
	})
}

// handleCreateUser invites a new user: the account starts with an
// unguessable random password (unless one was provided) and receives its
// certificate — plus a temporary login password — through a one-time claim
// link.
func (s *Server) handleCreateUser(w http.ResponseWriter, r *http.Request) {
	var req pb.CreateUserRequest
	raw, ok := bodyInto(r, &req)
	if !ok {
		writeError(w, http.StatusBadRequest, "Request body required", "MISSING_BODY")
		return
	}
	email := strings.TrimSpace(req.GetEmail())
	password := strings.TrimSpace(req.GetPassword())
	role := "user" // default when the key is absent
	if _, present := raw["role"]; present {
		role = strings.TrimSpace(req.GetRole())
	}

	if email == "" || !strings.Contains(email, "@") {
		writeError(w, http.StatusBadRequest, "Valid email required", "INVALID_EMAIL")
		return
	}
	if role != "admin" && role != "user" {
		writeError(w, http.StatusBadRequest, "Invalid role", "INVALID_ROLE")
		return
	}
	if password != "" && len(password) < minPasswordLen {
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
		writeError(w, http.StatusConflict, "Email already exists", "EMAIL_EXISTS")
		return
	}

	initialPassword := password
	if initialPassword == "" {
		// Unguessable placeholder; the claim flow issues the real temporary
		// password.
		random, _, terr := auth.NewToken()
		if terr != nil {
			writeError(w, http.StatusInternalServerError, terr.Error(), "INTERNAL_ERROR")
			return
		}
		initialPassword = random
	}
	hash, err := auth.HashPassword(initialPassword)
	if err != nil {
		writeError(w, http.StatusInternalServerError, err.Error(), "INTERNAL_ERROR")
		return
	}

	user := &store.User{Email: email, PasswordHash: hash, Role: role, IsDefaultPIN: true, IsApproved: true}
	if err := s.store.CreateUser(user); err != nil {
		writeError(w, http.StatusInternalServerError, err.Error(), "INTERNAL_ERROR")
		return
	}

	claimURL, err := s.issueClaim(user)
	if err != nil {
		writeError(w, http.StatusInternalServerError, err.Error(), "INTERNAL_ERROR")
		return
	}
	if settings, serr := s.store.Settings(); serr == nil && settings != nil && settings.SMTPEnabled {
		s.emailClaimLink(settings, user, claimURL, true)
	}

	s.logAudit(r, "user.create", audit.Entry{
		TargetType:  "user",
		TargetID:    fmt.Sprint(user.ID),
		Description: fmt.Sprintf("Created user %s", user.Email),
	})
	writeProto(w, http.StatusCreated, &pb.CreateUserResponse{User: s.pbUser(user), ClaimUrl: claimURL})
}

func (s *Server) handleGetUser(w http.ResponseWriter, r *http.Request) {
	user, err := s.store.UserByID(pathID(r, "user_id"))
	if err != nil {
		writeError(w, http.StatusInternalServerError, err.Error(), "INTERNAL_ERROR")
		return
	}
	if user == nil {
		writeError(w, http.StatusNotFound, "User not found", "USER_NOT_FOUND")
		return
	}
	writeProto(w, http.StatusOK, &pb.UserDetailResponse{User: s.pbUserDetail(user)})
}

func (s *Server) handleUpdateUser(w http.ResponseWriter, r *http.Request) {
	userID := pathID(r, "user_id")
	user, err := s.store.UserByID(userID)
	if err != nil {
		writeError(w, http.StatusInternalServerError, err.Error(), "INTERNAL_ERROR")
		return
	}
	if user == nil {
		writeError(w, http.StatusNotFound, "User not found", "USER_NOT_FOUND")
		return
	}

	var req pb.UpdateUserRequest
	if _, ok := bodyInto(r, &req); !ok {
		writeError(w, http.StatusBadRequest, "Request body required", "MISSING_BODY")
		return
	}

	if req.Email != nil {
		email := strings.TrimSpace(req.GetEmail())
		if email == "" || !strings.Contains(email, "@") {
			writeError(w, http.StatusBadRequest, "Valid email required", "INVALID_EMAIL")
			return
		}
		other, oerr := s.store.UserByEmail(email)
		if oerr != nil {
			writeError(w, http.StatusInternalServerError, oerr.Error(), "INTERNAL_ERROR")
			return
		}
		if other != nil && other.ID != userID {
			writeError(w, http.StatusConflict, "Email already exists", "EMAIL_EXISTS")
			return
		}
		user.Email = email
	}

	if req.Password != nil && req.GetPassword() != "" {
		if len(req.GetPassword()) < minPasswordLen {
			writeError(w, http.StatusBadRequest,
				fmt.Sprintf("Password must be at least %d characters", minPasswordLen), "INVALID_PASSWORD")
			return
		}
		hash, herr := auth.HashPassword(req.GetPassword())
		if herr != nil {
			writeError(w, http.StatusInternalServerError, herr.Error(), "INTERNAL_ERROR")
			return
		}
		user.PasswordHash = hash
	}

	if req.Role != nil {
		if req.GetRole() != "admin" && req.GetRole() != "user" {
			writeError(w, http.StatusBadRequest, "Invalid role", "INVALID_ROLE")
			return
		}
		user.Role = req.GetRole()
	}

	wasApproved := user.IsApproved
	if req.Approved != nil {
		user.IsApproved = req.GetApproved()
	}

	if err := s.store.UpdateUser(user); err != nil {
		writeError(w, http.StatusInternalServerError, err.Error(), "INTERNAL_ERROR")
		return
	}

	// A password set by the admin invalidates the user's live sessions.
	if req.Password != nil && req.GetPassword() != "" {
		_ = s.store.RevokeUserSessions(user.ID)
	}

	// When approval flips on, issue a certificate claim link.
	if req.Approved != nil && req.GetApproved() && !wasApproved {
		if claimURL, cerr := s.issueClaim(user); cerr == nil {
			if settings, serr := s.store.Settings(); serr == nil && settings != nil && settings.SMTPEnabled {
				s.emailClaimLink(settings, user, claimURL, false)
			}
		}
	}

	s.logAudit(r, "user.update", audit.Entry{
		TargetType:  "user",
		TargetID:    fmt.Sprint(user.ID),
		Description: fmt.Sprintf("Updated user %s", user.Email),
	})
	writeProto(w, http.StatusOK, &pb.UserResponse{User: s.pbUser(user)})
}

func (s *Server) handleDeleteUser(w http.ResponseWriter, r *http.Request) {
	userID := pathID(r, "user_id")
	user, err := s.store.UserByID(userID)
	if err != nil {
		writeError(w, http.StatusInternalServerError, err.Error(), "INTERNAL_ERROR")
		return
	}
	if user == nil {
		writeError(w, http.StatusNotFound, "User not found", "USER_NOT_FOUND")
		return
	}
	if cu := currentUser(r); cu != nil && cu.ID == userID {
		writeError(w, http.StatusBadRequest, "Cannot delete yourself", "CANNOT_DELETE_SELF")
		return
	}

	deletedEmail := user.Email
	if err := s.store.DeleteUser(userID); err != nil {
		writeError(w, http.StatusInternalServerError, err.Error(), "INTERNAL_ERROR")
		return
	}
	s.logAudit(r, "user.delete", audit.Entry{
		TargetType:  "user",
		TargetID:    fmt.Sprint(userID),
		Description: fmt.Sprintf("Deleted user %s", deletedEmail),
	})
	writeSuccess(w)
}

func (s *Server) handleUpdateUserGroups(w http.ResponseWriter, r *http.Request) {
	userID := pathID(r, "user_id")
	user, err := s.store.UserByID(userID)
	if err != nil {
		writeError(w, http.StatusInternalServerError, err.Error(), "INTERNAL_ERROR")
		return
	}
	if user == nil {
		writeError(w, http.StatusNotFound, "User not found", "USER_NOT_FOUND")
		return
	}

	var req pb.UpdateUserGroupsRequest
	raw, ok := bodyInto(r, &req)
	if !ok {
		writeError(w, http.StatusBadRequest, "Request body required", "MISSING_BODY")
		return
	}
	if _, present := raw["groupIds"]; !present {
		writeError(w, http.StatusBadRequest, "groupIds array required", "MISSING_GROUP_IDS")
		return
	}

	ids := make([]int, 0, len(req.GetGroupIds()))
	for _, gid := range req.GetGroupIds() {
		ids = append(ids, int(gid))
	}
	if err := s.store.SetUserGroups(userID, ids); err != nil {
		writeError(w, http.StatusInternalServerError, err.Error(), "INTERNAL_ERROR")
		return
	}

	s.logAudit(r, "permission.user_update", audit.Entry{
		TargetType:  "user",
		TargetID:    fmt.Sprint(user.ID),
		Description: fmt.Sprintf("Updated group membership for %s", user.Email),
	})
	writeProto(w, http.StatusOK, &pb.UserDetailResponse{User: s.pbUserDetail(user)})
}

// -- Certificate lifecycle ------------------------------------------------------

// rebuildCRL regenerates crl.pem from every revocation record.
func (s *Server) rebuildCRL() error {
	records, err := s.store.AllRevokedCertificates()
	if err != nil {
		return err
	}
	entries := make([]certs.RevokedEntry, 0, len(records))
	for _, rc := range records {
		serial, ok := new(big.Int).SetString(rc.SerialNumber, 16)
		if !ok {
			continue
		}
		entries = append(entries, certs.RevokedEntry{Serial: serial, RevokedAt: rc.RevokedAt})
	}
	crlPEM, err := certs.GenerateCRL(s.cfg.CACertPath, s.cfg.CAKeyPath, entries)
	if err != nil {
		return err
	}
	return certs.UpdateCRLFile(crlPEM, s.cfg.CRLPath())
}

// revokeUserCert revokes the user's current certificate (account and
// permissions are preserved) and refreshes the CRL. Returns the revocation
// record, or nil when the user has no cert.
func (s *Server) revokeUserCert(user *store.User, reason string, revokedByID *int) (*store.RevokedCertificate, error) {
	if user.CertSerialNumber == nil {
		return nil, nil
	}
	uid := user.ID
	record := &store.RevokedCertificate{
		SerialNumber: *user.CertSerialNumber,
		UserID:       &uid,
		Reason:       reason,
		RevokedBy:    revokedByID,
	}
	if err := s.store.InsertRevokedCertificate(record); err != nil {
		return nil, err
	}
	user.CertRevoked = true
	user.CertSerialNumber = nil
	user.CertIssuedAt = nil
	user.CertExpiresAt = nil
	if err := s.store.UpdateUser(user); err != nil {
		return nil, err
	}
	if err := s.rebuildCRL(); err != nil {
		return nil, err
	}
	return record, nil
}

func (s *Server) handleRevokeCert(w http.ResponseWriter, r *http.Request) {
	user, err := s.store.UserByID(pathID(r, "user_id"))
	if err != nil {
		writeError(w, http.StatusInternalServerError, err.Error(), "INTERNAL_ERROR")
		return
	}
	if user == nil {
		writeError(w, http.StatusNotFound, "User not found", "USER_NOT_FOUND")
		return
	}
	if user.CertRevoked || user.CertSerialNumber == nil {
		writeError(w, http.StatusBadRequest, "User has no active certificate to revoke", "NO_ACTIVE_CERT")
		return
	}

	var revokedBy *int
	if admin := currentUser(r); admin != nil {
		revokedBy = &admin.ID
	}
	record, err := s.revokeUserCert(user, "admin_revoked", revokedBy)
	if err != nil {
		writeError(w, http.StatusInternalServerError, err.Error(), "INTERNAL_ERROR")
		return
	}

	if settings, serr := s.store.Settings(); serr == nil && settings != nil && settings.SMTPEnabled {
		deviceName := settings.DeviceName
		if deviceName == "" {
			deviceName = "TerraCrate"
		}
		_ = mailer.SendRevocationEmail(settings, user.Email, deviceName, "")
	}

	s.logAudit(r, "cert.revoke", audit.Entry{
		TargetType:  "user",
		TargetID:    fmt.Sprint(user.ID),
		Description: fmt.Sprintf("Revoked certificate for %s", user.Email),
	})

	resp := &pb.RevokeCertResponse{
		Message: fmt.Sprintf("Certificate revoked for %s", user.Email),
		User:    s.pbUser(user),
	}
	if record != nil {
		resp.RevokedSerial = &record.SerialNumber
	}
	writeProto(w, http.StatusOK, resp)
}

// handleReissueCert issues a fresh one-time claim link; the replacement
// certificate is generated when the user redeems it.
func (s *Server) handleReissueCert(w http.ResponseWriter, r *http.Request) {
	user, err := s.store.UserByID(pathID(r, "user_id"))
	if err != nil {
		writeError(w, http.StatusInternalServerError, err.Error(), "INTERNAL_ERROR")
		return
	}
	if user == nil {
		writeError(w, http.StatusNotFound, "User not found", "USER_NOT_FOUND")
		return
	}
	if user.CertSerialNumber != nil && !user.CertRevoked {
		writeError(w, http.StatusBadRequest, "User already has an active certificate. Revoke it first.", "CERT_STILL_ACTIVE")
		return
	}

	claimURL, err := s.issueClaim(user)
	if err != nil {
		writeError(w, http.StatusInternalServerError, err.Error(), "INTERNAL_ERROR")
		return
	}
	if settings, serr := s.store.Settings(); serr == nil && settings != nil && settings.SMTPEnabled {
		s.emailClaimLink(settings, user, claimURL, true)
	}

	s.logAudit(r, "cert.reissue", audit.Entry{
		TargetType:  "user",
		TargetID:    fmt.Sprint(user.ID),
		Description: fmt.Sprintf("Issued certificate claim link for %s", user.Email),
	})
	writeProto(w, http.StatusOK, &pb.ReissueCertResponse{
		Message:  fmt.Sprintf("Certificate claim link issued for %s", user.Email),
		User:     s.pbUser(user),
		ClaimUrl: claimURL,
	})
}

func (s *Server) handleCertStatus(w http.ResponseWriter, r *http.Request) {
	userID := pathID(r, "user_id")
	user, err := s.store.UserByID(userID)
	if err != nil {
		writeError(w, http.StatusInternalServerError, err.Error(), "INTERNAL_ERROR")
		return
	}
	if user == nil {
		writeError(w, http.StatusNotFound, "User not found", "USER_NOT_FOUND")
		return
	}

	history, err := s.store.RevocationHistory(userID)
	if err != nil {
		writeError(w, http.StatusInternalServerError, err.Error(), "INTERNAL_ERROR")
		return
	}
	pbHistory := []*pb.RevokedCertificate{}
	for _, rc := range history {
		pbHistory = append(pbHistory, pbRevokedCert(rc))
	}
	writeProto(w, http.StatusOK, &pb.CertStatusResponse{
		Serial:            user.CertSerialNumber,
		IssuedAt:          ts(user.CertIssuedAt),
		ExpiresAt:         ts(user.CertExpiresAt),
		IsRevoked:         user.CertRevoked,
		RevocationHistory: pbHistory,
	})
}
