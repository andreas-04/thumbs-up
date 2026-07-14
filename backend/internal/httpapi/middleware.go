package httpapi

import (
	"context"
	"log/slog"
	"net/http"
	"strings"
	"time"

	"github.com/andreas-04/terra-crate/backend/internal/auth"
	"github.com/andreas-04/terra-crate/backend/internal/store"
)

type ctxKey int

const (
	ctxUserKey ctxKey = iota
	ctxSessionKey
)

// adminSessionTTL caps admin sessions regardless of the configured expiry.
const adminSessionTTL = 2 * time.Hour

// currentUser returns the authenticated user attached by
// requireAuth/requireAdmin.
func currentUser(r *http.Request) *store.User {
	u, _ := r.Context().Value(ctxUserKey).(*store.User)
	return u
}

// currentSession returns the session backing this request.
func currentSession(r *http.Request) *store.Session {
	s, _ := r.Context().Value(ctxSessionKey).(*store.Session)
	return s
}

// newSessionToken creates a DB-backed session and returns the bearer token.
func (s *Server) newSessionToken(u *store.User) (string, error) {
	plain, hash, err := auth.NewToken()
	if err != nil {
		return "", err
	}
	ttl := time.Duration(s.cfg.TokenExpiryHours) * time.Hour
	if u.Role == "admin" {
		ttl = adminSessionTTL
	}
	if _, err := s.store.CreateSession(hash, u.ID, time.Now().UTC().Add(ttl)); err != nil {
		return "", err
	}
	return plain, nil
}

// authenticate resolves the request's bearer token to a live session and its
// user; both nil when the token is missing, unknown, expired, or revoked.
func (s *Server) authenticate(r *http.Request) (*store.User, *store.Session) {
	token := auth.TokenFromRequest(r)
	if token == "" {
		return nil, nil
	}
	sess, err := s.store.SessionByTokenHash(auth.HashToken(token))
	if err != nil || sess == nil || !sess.Valid(time.Now().UTC()) {
		return nil, nil
	}
	user, err := s.store.UserByID(sess.UserID)
	if err != nil || user == nil {
		return nil, nil
	}
	return user, sess
}

func withAuth(r *http.Request, user *store.User, sess *store.Session) *http.Request {
	ctx := context.WithValue(r.Context(), ctxUserKey, user)
	ctx = context.WithValue(ctx, ctxSessionKey, sess)
	return r.WithContext(ctx)
}

func (s *Server) requireAuth(next http.HandlerFunc) http.HandlerFunc {
	return func(w http.ResponseWriter, r *http.Request) {
		if auth.TokenFromRequest(r) == "" {
			writeError(w, http.StatusUnauthorized, "No token provided", "NO_TOKEN")
			return
		}
		user, sess := s.authenticate(r)
		if user == nil {
			writeError(w, http.StatusUnauthorized, "Invalid or expired token", "INVALID_TOKEN")
			return
		}
		next(w, withAuth(r, user, sess))
	}
}

func (s *Server) requireAdmin(next http.HandlerFunc) http.HandlerFunc {
	return func(w http.ResponseWriter, r *http.Request) {
		if auth.TokenFromRequest(r) == "" {
			writeError(w, http.StatusUnauthorized, "Admin authentication required", "ADMIN_AUTH_REQUIRED")
			return
		}
		user, sess := s.authenticate(r)
		if user == nil || user.Role != "admin" {
			writeError(w, http.StatusForbidden, "Admin access required", "ADMIN_ACCESS_REQUIRED")
			return
		}
		next(w, withAuth(r, user, sess))
	}
}

func (s *Server) corsMiddleware(next http.Handler) http.Handler {
	allowAll := s.cfg.CORSOrigins == "*"
	var allowed []string
	if !allowAll {
		for _, o := range strings.Split(s.cfg.CORSOrigins, ",") {
			if o = strings.TrimSpace(o); o != "" {
				allowed = append(allowed, o)
			}
		}
	}

	return http.HandlerFunc(func(w http.ResponseWriter, r *http.Request) {
		origin := r.Header.Get("Origin")
		switch {
		case allowAll:
			w.Header().Set("Access-Control-Allow-Origin", "*")
		case origin != "":
			for _, o := range allowed {
				if o == origin {
					w.Header().Set("Access-Control-Allow-Origin", origin)
					w.Header().Add("Vary", "Origin")
					break
				}
			}
		}
		if r.Method == http.MethodOptions {
			w.Header().Set("Access-Control-Allow-Methods", "GET, POST, PUT, DELETE, OPTIONS")
			w.Header().Set("Access-Control-Allow-Headers", "Content-Type, Authorization")
			w.Header().Set("Access-Control-Max-Age", "3600")
			w.WriteHeader(http.StatusNoContent)
			return
		}
		next.ServeHTTP(w, r)
	})
}

func (s *Server) recoverMiddleware(next http.Handler) http.Handler {
	return http.HandlerFunc(func(w http.ResponseWriter, r *http.Request) {
		defer func() {
			if rec := recover(); rec != nil {
				slog.Error("panic serving request", "method", r.Method, "path", r.URL.Path, "panic", rec)
				writeError(w, http.StatusInternalServerError, "Internal server error", "INTERNAL_ERROR")
			}
		}()
		next.ServeHTTP(w, r)
	})
}

// clientIP prefers X-Forwarded-For (set by nginx), falling back to the peer
// address.
func clientIP(r *http.Request) string {
	if xff := r.Header.Get("X-Forwarded-For"); xff != "" {
		return xff
	}
	host := r.RemoteAddr
	if i := strings.LastIndex(host, ":"); i > 0 {
		host = host[:i]
	}
	return host
}
