package httpapi

import (
	"context"
	"log/slog"
	"time"

	"github.com/andreas-04/terra-crate/backend/internal/mailer"
)

// CheckExpiringCerts revokes certificates nearing expiry, notifies their
// owners, and always rebuilds the CRL so its next_update stays fresh (a
// stale CRL would make nginx reject every client).
func (s *Server) CheckExpiringCerts() {
	threshold := time.Now().UTC().AddDate(0, 0, s.cfg.CertExpiryCheckDays)
	expiring, err := s.store.UsersWithExpiringCerts(threshold)
	if err != nil {
		slog.Error("cert-expiry: query failed", "error", err)
	}

	if len(expiring) > 0 {
		settings, _ := s.store.Settings()
		for _, user := range expiring {
			slog.Info("cert-expiry: auto-revoking expiring cert", "email", user.Email, "expiresAt", user.CertExpiresAt)
			if _, err := s.revokeUserCert(user, "expiry_approaching", nil); err != nil {
				slog.Error("cert-expiry: revoke failed", "email", user.Email, "error", err)
				continue
			}
			if settings != nil && settings.SMTPEnabled {
				deviceName := settings.DeviceName
				if deviceName == "" {
					deviceName = "TerraCrate"
				}
				_ = mailer.SendRevocationEmail(settings, user.Email, deviceName,
					"Your certificate is expiring soon.")
			}
		}
	}

	if err := s.rebuildCRL(); err != nil {
		slog.Error("cert-expiry: CRL rebuild failed", "error", err)
	}
}

// StartBackgroundTasks runs the certificate expiry check and garbage
// collection of expired sessions/claims immediately, then on the configured
// interval, until ctx is cancelled.
func (s *Server) StartBackgroundTasks(ctx context.Context) {
	go func() {
		interval := time.Duration(s.cfg.CertExpiryCheckIntervalHours) * time.Hour
		ticker := time.NewTicker(interval)
		defer ticker.Stop()
		for {
			func() {
				defer func() {
					if r := recover(); r != nil {
						slog.Error("background: task panicked", "panic", r)
					}
				}()
				s.CheckExpiringCerts()
				cutoff := time.Now().UTC()
				if err := s.store.DeleteExpiredSessions(cutoff); err != nil {
					slog.Error("background: session cleanup failed", "error", err)
				}
				if err := s.store.DeleteExpiredCertClaims(cutoff); err != nil {
					slog.Error("background: claim cleanup failed", "error", err)
				}
			}()
			select {
			case <-ctx.Done():
				return
			case <-ticker.C:
			}
		}
	}()
}
