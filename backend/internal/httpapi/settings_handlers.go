package httpapi

import (
	"encoding/json"
	"fmt"
	"io/fs"
	"net/http"
	"path/filepath"
	"strings"

	pb "github.com/andreas-04/terra-crate/backend/gen/terracrate/v1"
	"github.com/andreas-04/terra-crate/backend/internal/audit"
)

func (s *Server) handleGetSettings(w http.ResponseWriter, r *http.Request) {
	settings, err := s.store.Settings()
	if err != nil {
		writeError(w, http.StatusInternalServerError, err.Error(), "INTERNAL_ERROR")
		return
	}
	if settings == nil {
		writeError(w, http.StatusNotFound, "Settings not found", "SETTINGS_NOT_FOUND")
		return
	}
	writeProto(w, http.StatusOK, pbSettings(settings))
}

func (s *Server) handleUpdateSettings(w http.ResponseWriter, r *http.Request) {
	raw := readBody(r)
	if raw == nil {
		writeError(w, http.StatusBadRequest, "Request body required", "MISSING_BODY")
		return
	}
	settings, err := s.store.Settings()
	if err != nil {
		writeError(w, http.StatusInternalServerError, err.Error(), "INTERNAL_ERROR")
		return
	}
	if settings == nil {
		writeError(w, http.StatusNotFound, "Settings not found", "SETTINGS_NOT_FOUND")
		return
	}

	getString := func(key string) (string, bool) {
		v, ok := raw[key]
		if !ok {
			return "", false
		}
		var out string
		if json.Unmarshal(v, &out) != nil {
			return "", false
		}
		return out, true
	}
	getBool := func(key string) (bool, bool) {
		v, ok := raw[key]
		if !ok {
			return false, false
		}
		// Legacy bool(...) coercion: accept any truthy JSON value.
		var b bool
		if json.Unmarshal(v, &b) == nil {
			return b, true
		}
		var anyVal any
		if json.Unmarshal(v, &anyVal) == nil {
			switch t := anyVal.(type) {
			case float64:
				return t != 0, true
			case string:
				return t != "", true
			case nil:
				return false, true
			}
		}
		return false, false
	}
	getInt := func(key string) (int, bool) {
		v, ok := raw[key]
		if !ok {
			return 0, false
		}
		var n float64
		if json.Unmarshal(v, &n) == nil {
			return int(n), true
		}
		var str string
		if json.Unmarshal(v, &str) == nil {
			var parsed int
			if _, err := fmt.Sscanf(strings.TrimSpace(str), "%d", &parsed); err == nil {
				return parsed, true
			}
		}
		return 0, false
	}

	if v, ok := getString("authMethod"); ok || raw["authMethod"] != nil {
		if v != "email" && v != "email+password" && v != "username+password" {
			writeError(w, http.StatusBadRequest, "Invalid authMethod value", "INVALID_AUTH_METHOD")
			return
		}
		settings.AuthMethod = v
	}
	if v, ok := getBool("tlsEnabled"); ok {
		settings.TLSEnabled = v
	}
	if _, present := raw["httpsPort"]; present {
		port, ok := getInt("httpsPort")
		if !ok || port < 1 || port > 65535 {
			writeError(w, http.StatusBadRequest, "Invalid port number", "INVALID_PORT")
			return
		}
		settings.HTTPSPort = port
	}
	if v, ok := getString("deviceName"); ok {
		settings.DeviceName = strings.TrimSpace(v)
	}

	if v, ok := getBool("smtpEnabled"); ok {
		settings.SMTPEnabled = v
	}
	if v, ok := getString("smtpHost"); ok {
		settings.SMTPHost = strings.TrimSpace(v)
	}
	if _, present := raw["smtpPort"]; present {
		port, ok := getInt("smtpPort")
		if !ok || port < 1 || port > 65535 {
			writeError(w, http.StatusBadRequest, "Invalid SMTP port number", "INVALID_SMTP_PORT")
			return
		}
		settings.SMTPPort = port
	}
	if v, ok := getString("smtpUsername"); ok {
		settings.SMTPUsername = strings.TrimSpace(v)
	}
	if v, ok := getString("smtpPassword"); ok && v != "*****" {
		settings.SMTPPassword = v
	}
	if v, ok := getString("smtpFromEmail"); ok {
		settings.SMTPFromEmail = strings.TrimSpace(v)
	}
	if v, ok := getBool("smtpUseTls"); ok {
		settings.SMTPUseTLS = v
	}

	if rawDomains, present := raw["allowedDomains"]; present {
		var domains []any
		if json.Unmarshal(rawDomains, &domains) != nil {
			writeError(w, http.StatusBadRequest, "allowedDomains must be a list", "INVALID_DOMAINS")
			return
		}
		cleaned := []string{}
		for _, d := range domains {
			dom := cleanDomain(fmt.Sprint(d))
			if dom == "" || !strings.Contains(dom, ".") {
				writeError(w, http.StatusBadRequest, fmt.Sprintf("Invalid domain: %s", dom), "INVALID_DOMAIN")
				return
			}
			cleaned = append(cleaned, dom)
		}
		settings.AllowedDomains = strings.Join(cleaned, ",")

		// Auto-create DomainConfig rows so new domains appear on the Domains
		// page immediately.
		existing := map[string]bool{}
		if list, derr := s.store.ListDomains(); derr == nil {
			for _, dc := range list {
				existing[dc.Domain] = true
			}
		}
		for _, d := range cleaned {
			if !existing[d] {
				_, _ = s.store.CreateDomain(d, nil)
				existing[d] = true
			}
		}
	}

	if err := s.store.UpdateSettings(settings); err != nil {
		writeError(w, http.StatusInternalServerError, err.Error(), "INTERNAL_ERROR")
		return
	}

	s.logAudit(r, "settings.update", audit.Entry{
		TargetType:  "settings",
		Description: "System settings updated",
	})
	writeProto(w, http.StatusOK, pbSettings(settings))
}

func (s *Server) handleDashboardStats(w http.ResponseWriter, r *http.Request) {
	userCount, err := s.store.CountUsersByRole("user")
	if err != nil {
		writeError(w, http.StatusInternalServerError, err.Error(), "INTERNAL_ERROR")
		return
	}

	var fileCount, folderCount int
	var totalSize int64
	filesRoot := s.cfg.FilesRoot()
	_ = filepath.WalkDir(filesRoot, func(path string, d fs.DirEntry, err error) error {
		if err != nil || path == filesRoot {
			return nil
		}
		if d.IsDir() {
			folderCount++
		} else {
			fileCount++
			if info, ierr := d.Info(); ierr == nil {
				totalSize += info.Size()
			}
		}
		return nil
	})

	tlsEnabled := true
	if settings, serr := s.store.Settings(); serr == nil && settings != nil {
		tlsEnabled = settings.TLSEnabled
	}
	writeProto(w, http.StatusOK, &pb.DashboardStats{
		UserCount:   int32(userCount),
		FileCount:   int32(fileCount),
		FolderCount: int32(folderCount),
		TotalSize:   totalSize,
		TlsEnabled:  tlsEnabled,
	})
}
