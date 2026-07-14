// TerraCrate API server.
//
// The HTTP/JSON contract is defined by the protos in proto/terracrate/v1.
// TLS uses a server leaf certificate signed by a dedicated long-lived CA;
// the same CA signs mTLS client certificates and the CRL.
package main

import (
	"context"
	"errors"
	"fmt"
	"log/slog"
	"net"
	"net/http"
	"os"
	"os/signal"
	"path/filepath"
	"strconv"
	"syscall"
	"time"

	"github.com/andreas-04/terra-crate/backend/internal/auth"
	"github.com/andreas-04/terra-crate/backend/internal/certs"
	"github.com/andreas-04/terra-crate/backend/internal/config"
	"github.com/andreas-04/terra-crate/backend/internal/httpapi"
	"github.com/andreas-04/terra-crate/backend/internal/store"
)

func main() {
	if err := run(); err != nil {
		slog.Error("server exited", "error", err)
		os.Exit(1)
	}
}

func run() error {
	slog.SetDefault(slog.New(slog.NewTextHandler(os.Stderr, nil)))
	cfg := config.Load()

	slog.Info("starting TerraCrate API", "service", cfg.ServiceName)

	if cfg.AdminPIN == "" {
		return fmt.Errorf("ADMIN_PIN environment variable is not set")
	}

	// Storage directories (including the unauthenticated guest area).
	if err := os.MkdirAll(cfg.GuestRoot(), 0o755); err != nil {
		return fmt.Errorf("create storage directories: %w", err)
	}

	if err := ensurePKI(cfg); err != nil {
		return err
	}

	// Database.
	if err := os.MkdirAll(filepath.Dir(cfg.DatabasePath), 0o755); err != nil {
		return fmt.Errorf("create database directory: %w", err)
	}
	st, err := store.Open(cfg.DatabasePath)
	if err != nil {
		return fmt.Errorf("open database: %w", err)
	}
	defer st.Close()
	if err := st.Migrate(); err != nil {
		return fmt.Errorf("migrate database: %w", err)
	}
	slog.Info("database ready", "path", cfg.DatabasePath)

	// An empty CRL must exist (and match the CA) so nginx can start with
	// ssl_crl configured.
	if err := certs.GenerateEmptyCRL(cfg.CACertPath, cfg.CAKeyPath, cfg.CRLPath()); err != nil {
		return fmt.Errorf("generate CRL: %w", err)
	}

	if err := ensureDefaults(cfg, st); err != nil {
		return fmt.Errorf("seed defaults: %w", err)
	}

	ctx, stop := signal.NotifyContext(context.Background(), os.Interrupt, syscall.SIGTERM)
	defer stop()

	server := httpapi.NewServer(cfg, st)
	server.StartBackgroundTasks(ctx)

	addr := net.JoinHostPort(cfg.Host, strconv.Itoa(cfg.Port))
	httpServer := &http.Server{
		Addr:              addr,
		Handler:           server.Handler(),
		ReadHeaderTimeout: 10 * time.Second,
	}

	errCh := make(chan error, 1)
	go func() {
		errCh <- httpServer.ListenAndServeTLS(cfg.CertPath, cfg.KeyPath)
	}()
	slog.Info("listening", "addr", "https://"+addr, "publicUrl", cfg.PublicURL)

	select {
	case err := <-errCh:
		return err
	case <-ctx.Done():
		slog.Info("shutting down")
		shutdownCtx, cancel := context.WithTimeout(context.Background(), 10*time.Second)
		defer cancel()
		if err := httpServer.Shutdown(shutdownCtx); err != nil {
			return fmt.Errorf("shutdown: %w", err)
		}
		if err := <-errCh; err != nil && !errors.Is(err, http.ErrServerClosed) {
			return err
		}
		return nil
	}
}

// ensurePKI bootstraps the CA on first boot and (re)issues the server leaf
// whenever it is missing or was signed by a different CA.
func ensurePKI(cfg config.Config) error {
	if !fileExists(cfg.CACertPath) || !fileExists(cfg.CAKeyPath) {
		slog.Info("generating certificate authority", "path", cfg.CACertPath)
		if err := certs.GenerateCA(cfg.CACertPath, cfg.CAKeyPath); err != nil {
			return fmt.Errorf("generate CA: %w", err)
		}
	}
	needServer := !fileExists(cfg.CertPath) || !fileExists(cfg.KeyPath) ||
		!certs.ServerCertSignedBy(cfg.CertPath, cfg.CACertPath)
	if needServer {
		slog.Info("generating server certificate", "hostname", cfg.MDNSHostname)
		if err := certs.GenerateServerCert(cfg.CACertPath, cfg.CAKeyPath,
			cfg.CertPath, cfg.KeyPath, cfg.MDNSHostname, 365); err != nil {
			return fmt.Errorf("generate server certificate: %w", err)
		}
	}
	return nil
}

func fileExists(path string) bool {
	_, err := os.Stat(path)
	return err == nil
}

// ensureDefaults seeds the system settings row and the default admin user on
// first boot.
func ensureDefaults(cfg config.Config, st *store.Store) error {
	settings, err := st.Settings()
	if err != nil {
		return err
	}
	if settings == nil {
		if err := st.CreateSettings(&store.SystemSettings{
			AuthMethod: "email+password",
			TLSEnabled: true,
			HTTPSPort:  cfg.Port,
			DeviceName: cfg.ServiceName,
			SMTPPort:   587,
			SMTPUseTLS: true,
		}); err != nil {
			return err
		}
		slog.Info("default system settings created")
	}

	admin, err := st.FirstAdmin()
	if err != nil {
		return err
	}
	if admin == nil {
		hash, herr := auth.HashPassword(cfg.AdminPIN)
		if herr != nil {
			return herr
		}
		email := fmt.Sprintf("admin@%s.local", cfg.MDNSHostname)
		if err := st.CreateUser(&store.User{
			Email:        email,
			PasswordHash: hash,
			Role:         "admin",
			IsDefaultPIN: true,
		}); err != nil {
			return err
		}
		slog.Info("default admin user created (password = ADMIN_PIN, must be changed on first login)",
			"email", email)
	}
	return nil
}
