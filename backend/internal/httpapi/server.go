// Package httpapi serves the /api/v1 REST surface with the standard
// library's net/http. The wire contract is defined by proto/terracrate/v1
// and rendered with the canonical proto3 JSON mapping (protojson).
package httpapi

import (
	"net/http"

	"github.com/andreas-04/terra-crate/backend/internal/audit"
	"github.com/andreas-04/terra-crate/backend/internal/config"
	"github.com/andreas-04/terra-crate/backend/internal/store"
)

type Server struct {
	cfg   config.Config
	store *store.Store
	audit *audit.Logger
}

func NewServer(cfg config.Config, st *store.Store) *Server {
	return &Server{cfg: cfg, store: st, audit: audit.New(st)}
}

// Handler builds the route table. Route patterns match the google.api.http
// annotations in the proto service definitions one-to-one (see
// routes_test.go for the enforcement).
func (s *Server) Handler() http.Handler {
	mux := http.NewServeMux()

	// AuthService
	mux.HandleFunc("POST /api/v1/auth/login", s.handleLogin)
	mux.HandleFunc("POST /api/v1/auth/signup", s.handleSignup)
	mux.HandleFunc("POST /api/v1/auth/logout", s.requireAuth(s.handleLogout))
	mux.HandleFunc("GET /api/v1/auth/me", s.requireAuth(s.handleMe))
	mux.HandleFunc("POST /api/v1/auth/refresh", s.requireAuth(s.handleRefresh))
	mux.HandleFunc("POST /api/v1/auth/change-password", s.requireAuth(s.handleChangePassword))

	// SettingsService
	mux.HandleFunc("GET /api/v1/settings", s.handleGetSettings)
	mux.HandleFunc("PUT /api/v1/settings", s.requireAdmin(s.handleUpdateSettings))
	mux.HandleFunc("GET /api/v1/stats/dashboard", s.requireAdmin(s.handleDashboardStats))

	// UserService
	mux.HandleFunc("GET /api/v1/users", s.requireAdmin(s.handleListUsers))
	mux.HandleFunc("POST /api/v1/users", s.requireAdmin(s.handleCreateUser))
	mux.HandleFunc("GET /api/v1/users/{user_id}", s.requireAdmin(s.handleGetUser))
	mux.HandleFunc("PUT /api/v1/users/{user_id}", s.requireAdmin(s.handleUpdateUser))
	mux.HandleFunc("DELETE /api/v1/users/{user_id}", s.requireAdmin(s.handleDeleteUser))
	mux.HandleFunc("PUT /api/v1/users/{user_id}/groups", s.requireAdmin(s.handleUpdateUserGroups))
	mux.HandleFunc("POST /api/v1/users/{user_id}/revoke-cert", s.requireAdmin(s.handleRevokeCert))
	mux.HandleFunc("POST /api/v1/users/{user_id}/reissue-cert", s.requireAdmin(s.handleReissueCert))
	mux.HandleFunc("GET /api/v1/users/{user_id}/cert-status", s.requireAdmin(s.handleCertStatus))

	// PermissionService
	mux.HandleFunc("GET /api/v1/users/{user_id}/permissions", s.requireAdmin(s.handleGetUserPermissions))
	mux.HandleFunc("PUT /api/v1/users/{user_id}/permissions", s.requireAdmin(s.handleUpdateUserPermissions))
	mux.HandleFunc("GET /api/v1/users/{user_id}/effective-permissions", s.requireAdmin(s.handleEffectivePermissions))
	mux.HandleFunc("GET /api/v1/folders", s.requireAdmin(s.handleListFolders))

	// DomainService
	mux.HandleFunc("GET /api/v1/domains", s.requireAdmin(s.handleListDomains))
	mux.HandleFunc("POST /api/v1/domains", s.requireAdmin(s.handleCreateDomain))
	mux.HandleFunc("GET /api/v1/domains/{domain_id}", s.requireAdmin(s.handleGetDomain))
	mux.HandleFunc("PUT /api/v1/domains/{domain_id}", s.requireAdmin(s.handleUpdateDomain))
	mux.HandleFunc("DELETE /api/v1/domains/{domain_id}", s.requireAdmin(s.handleDeleteDomain))

	// GroupService
	mux.HandleFunc("GET /api/v1/groups", s.requireAdmin(s.handleListGroups))
	mux.HandleFunc("POST /api/v1/groups", s.requireAdmin(s.handleCreateGroup))
	mux.HandleFunc("GET /api/v1/groups/{group_id}", s.requireAdmin(s.handleGetGroup))
	mux.HandleFunc("PUT /api/v1/groups/{group_id}", s.requireAdmin(s.handleUpdateGroup))
	mux.HandleFunc("DELETE /api/v1/groups/{group_id}", s.requireAdmin(s.handleDeleteGroup))
	mux.HandleFunc("PUT /api/v1/groups/{group_id}/permissions", s.requireAdmin(s.handleUpdateGroupPermissions))
	mux.HandleFunc("PUT /api/v1/groups/{group_id}/members", s.requireAdmin(s.handleUpdateGroupMembers))

	// FileService
	mux.HandleFunc("GET /api/v1/files", s.requireAuth(s.handleListFiles))
	mux.HandleFunc("POST /api/v1/files/upload", s.requireAuth(s.handleUploadFile))
	mux.HandleFunc("GET /api/v1/files/download", s.requireAuth(s.handleDownloadFile))
	mux.HandleFunc("GET /api/v1/files/preview", s.requireAuth(s.handlePreviewFile))
	mux.HandleFunc("POST /api/v1/files/mkdir", s.requireAuth(s.handleMkdir))
	mux.HandleFunc("DELETE /api/v1/files", s.requireAuth(s.handleDeleteFile))
	mux.HandleFunc("POST /api/v1/files/rename", s.requireAuth(s.handleRenameFile))
	mux.HandleFunc("POST /api/v1/files/move", s.requireAuth(s.handleMoveFile))

	// GuestFileService
	mux.HandleFunc("GET /api/v1/guest/files", s.handleGuestListFiles)
	mux.HandleFunc("GET /api/v1/guest/files/download", s.handleGuestDownloadFile)

	// CertClaimService (public: the one-time token is the credential)
	mux.HandleFunc("POST /api/v1/certs/claim", s.handleClaimCert)

	// AuditService
	mux.HandleFunc("GET /api/v1/audit-logs", s.requireAdmin(s.handleListAuditLogs))
	mux.HandleFunc("GET /api/v1/audit-logs/stats", s.requireAdmin(s.handleAuditLogStats))

	// SystemService
	mux.HandleFunc("GET /api/v1/system/logs", s.requireAdmin(s.handleSystemLogs))
	mux.HandleFunc("GET /health", s.handleHealth)

	return s.recoverMiddleware(s.corsMiddleware(mux))
}
