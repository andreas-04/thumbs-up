// Package config loads the server configuration from environment variables
// (compatible with existing deployments' .env files).
package config

import (
	"fmt"
	"os"
	"path/filepath"
	"strconv"
	"strings"
)

type Config struct {
	Host        string
	Port        int
	StoragePath string
	// Server (HTTPS) leaf certificate, signed by the CA.
	CertPath string
	KeyPath  string
	// Dedicated CA that signs the server leaf, client certs, and the CRL.
	CACertPath string
	CAKeyPath  string
	// Externally reachable base URL (used in claim links), e.g.
	// "https://terracrate.local".
	PublicURL        string
	TokenExpiryHours int
	EnableUploads    bool
	EnableDelete     bool
	ServiceName      string
	MDNSHostname     string
	MaxUploadSize    int64
	AdminPIN         string
	DatabasePath     string
	CORSOrigins      string

	CNMismatchThreshold     int
	CNMismatchWindowMinutes int

	CertExpiryCheckDays          int
	CertExpiryCheckIntervalHours int
}

func Load() Config {
	base, _ := os.Getwd()
	hostname, _ := os.Hostname()

	certPath := getStr("CERT_PATH", filepath.Join(base, "certs", "server_cert.pem"))
	certDir := filepath.Dir(certPath)

	return Config{
		Host:        getStr("HOST", "0.0.0.0"),
		Port:        getInt("PORT", 8443),
		StoragePath: getStr("STORAGE_PATH", filepath.Join(base, "storage")),
		CertPath:    certPath,
		KeyPath:     getStr("KEY_PATH", filepath.Join(base, "certs", "server_key.pem")),
		CACertPath:  getStr("CA_CERT_PATH", filepath.Join(certDir, "ca_cert.pem")),
		CAKeyPath:   getStr("CA_KEY_PATH", filepath.Join(certDir, "ca_key.pem")),
		PublicURL: getStr("PUBLIC_URL",
			fmt.Sprintf("https://%s.local", strings.TrimSuffix(getStr("MDNS_HOSTNAME", hostname), ".local"))),
		TokenExpiryHours: getInt("TOKEN_EXPIRY_HOURS", 24),
		EnableUploads:    getBool("ENABLE_UPLOADS", true),
		EnableDelete:     getBool("ENABLE_DELETE", true),
		ServiceName:      getStr("SERVICE_NAME", "TerraCrate File Share"),
		MDNSHostname:     getStr("MDNS_HOSTNAME", hostname),
		MaxUploadSize:    int64(getInt("MAX_UPLOAD_SIZE", 100*1024*1024)),
		AdminPIN:         os.Getenv("ADMIN_PIN"),
		DatabasePath:     databasePath(base),
		CORSOrigins:      getStr("CORS_ORIGINS", "*"),

		CNMismatchThreshold:     getInt("CN_MISMATCH_THRESHOLD", 3),
		CNMismatchWindowMinutes: getInt("CN_MISMATCH_WINDOW_MINUTES", 60),

		CertExpiryCheckDays:          getInt("CERT_EXPIRY_CHECK_DAYS", 7),
		CertExpiryCheckIntervalHours: getInt("CERT_EXPIRY_CHECK_INTERVAL_HOURS", 24),
	}
}

// databasePath resolves DATABASE_URI ("sqlite:///..." form) or falls
// back to <cwd>/data/terracrate.db.
func databasePath(base string) string {
	uri := getStr("DATABASE_URI", "sqlite:///"+filepath.Join(base, "data", "terracrate.db"))
	return strings.TrimPrefix(uri, "sqlite:///")
}

// FilesRoot is the base directory that all virtual file paths resolve under.
func (c Config) FilesRoot() string {
	return filepath.Join(c.StoragePath, "files")
}

// GuestRoot is the unauthenticated guest subtree.
func (c Config) GuestRoot() string {
	return filepath.Join(c.StoragePath, "files", "guest")
}

// CRLPath is the certificate revocation list, kept next to the CA cert.
func (c Config) CRLPath() string {
	return filepath.Join(filepath.Dir(c.CertPath), "crl.pem")
}

func getStr(key, def string) string {
	if v := os.Getenv(key); v != "" {
		return v
	}
	return def
}

func getInt(key string, def int) int {
	if v := os.Getenv(key); v != "" {
		if n, err := strconv.Atoi(v); err == nil {
			return n
		}
	}
	return def
}

func getBool(key string, def bool) bool {
	if v := os.Getenv(key); v != "" {
		return strings.EqualFold(v, "true")
	}
	return def
}
