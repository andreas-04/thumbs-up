package httpapi

import (
	"fmt"
	"net/http"
	"strings"

	pb "github.com/andreas-04/terra-crate/backend/gen/terracrate/v1"
	"github.com/andreas-04/terra-crate/backend/internal/audit"
	"github.com/andreas-04/terra-crate/backend/internal/store"
)

// cleanDomain applies the legacy normalisation: strip, remove leading '@',
// lowercase.
func cleanDomain(d string) string {
	return strings.ToLower(strings.TrimLeft(strings.TrimSpace(d), "@"))
}

func boolPermRows(inputs []*pb.BoolPermissionInput) []*store.DomainPermission {
	rows := []*store.DomainPermission{}
	for _, in := range inputs {
		path := in.GetPath()
		if path == "" {
			path = "/"
		}
		rows = append(rows, &store.DomainPermission{FolderPath: path, CanRead: in.GetRead(), CanWrite: in.GetWrite()})
	}
	return rows
}

func (s *Server) handleListDomains(w http.ResponseWriter, r *http.Request) {
	// Auto-create configs for allowlisted domains that don't have one yet so
	// the admin sees them prepopulated.
	if settings, err := s.store.Settings(); err == nil && settings != nil && settings.AllowedDomains != "" {
		existing := map[string]bool{}
		if domains, derr := s.store.ListDomains(); derr == nil {
			for _, dc := range domains {
				existing[dc.Domain] = true
			}
		}
		for _, d := range strings.Split(settings.AllowedDomains, ",") {
			if d = strings.ToLower(strings.TrimSpace(d)); d != "" && !existing[d] {
				_, _ = s.store.CreateDomain(d, nil)
			}
		}
	}

	domains, err := s.store.ListDomains()
	if err != nil {
		writeError(w, http.StatusInternalServerError, err.Error(), "INTERNAL_ERROR")
		return
	}
	out := []*pb.DomainConfig{}
	for _, dc := range domains {
		out = append(out, pbDomain(dc))
	}
	writeProto(w, http.StatusOK, &pb.ListDomainsResponse{Domains: out})
}

func (s *Server) handleCreateDomain(w http.ResponseWriter, r *http.Request) {
	var req pb.CreateDomainRequest
	if _, ok := bodyInto(r, &req); !ok {
		writeError(w, http.StatusBadRequest, "Request body required", "MISSING_BODY")
		return
	}
	domain := cleanDomain(req.GetDomain())
	if domain == "" || !strings.Contains(domain, ".") {
		writeError(w, http.StatusBadRequest, "Valid domain required", "INVALID_DOMAIN")
		return
	}
	if existing, err := s.store.DomainByName(domain); err == nil && existing != nil {
		writeError(w, http.StatusConflict, "Domain already exists", "DOMAIN_EXISTS")
		return
	}

	dc, err := s.store.CreateDomain(domain, boolPermRows(req.GetPermissions()))
	if err != nil {
		writeError(w, http.StatusInternalServerError, err.Error(), "INTERNAL_ERROR")
		return
	}

	s.logAudit(r, "domain.create", audit.Entry{
		TargetType:  "domain",
		TargetID:    fmt.Sprint(dc.ID),
		Description: fmt.Sprintf("Created domain %s", dc.Domain),
	})
	writeProto(w, http.StatusCreated, &pb.DomainResponse{Domain: pbDomain(dc)})
}

func (s *Server) handleGetDomain(w http.ResponseWriter, r *http.Request) {
	dc, err := s.store.DomainByID(pathID(r, "domain_id"))
	if err != nil {
		writeError(w, http.StatusInternalServerError, err.Error(), "INTERNAL_ERROR")
		return
	}
	if dc == nil {
		writeError(w, http.StatusNotFound, "Domain not found", "DOMAIN_NOT_FOUND")
		return
	}
	writeProto(w, http.StatusOK, &pb.DomainResponse{Domain: pbDomain(dc)})
}

func (s *Server) handleUpdateDomain(w http.ResponseWriter, r *http.Request) {
	domainID := pathID(r, "domain_id")
	dc, err := s.store.DomainByID(domainID)
	if err != nil {
		writeError(w, http.StatusInternalServerError, err.Error(), "INTERNAL_ERROR")
		return
	}
	if dc == nil {
		writeError(w, http.StatusNotFound, "Domain not found", "DOMAIN_NOT_FOUND")
		return
	}

	var req pb.UpdateDomainRequest
	raw, ok := bodyInto(r, &req)
	if !ok {
		writeError(w, http.StatusBadRequest, "Request body required", "MISSING_BODY")
		return
	}

	if req.Domain != nil {
		newDomain := cleanDomain(req.GetDomain())
		if newDomain == "" || !strings.Contains(newDomain, ".") {
			writeError(w, http.StatusBadRequest, "Valid domain required", "INVALID_DOMAIN")
			return
		}
		existing, eerr := s.store.DomainByName(newDomain)
		if eerr != nil {
			writeError(w, http.StatusInternalServerError, eerr.Error(), "INTERNAL_ERROR")
			return
		}
		if existing != nil && existing.ID != domainID {
			writeError(w, http.StatusConflict, "Domain already exists", "DOMAIN_EXISTS")
			return
		}
		if err := s.store.RenameDomain(domainID, newDomain); err != nil {
			writeError(w, http.StatusInternalServerError, err.Error(), "INTERNAL_ERROR")
			return
		}
	}

	if _, present := raw["permissions"]; present {
		if err := s.store.ReplaceDomainPermissions(domainID, boolPermRows(req.GetPermissions())); err != nil {
			writeError(w, http.StatusInternalServerError, err.Error(), "INTERNAL_ERROR")
			return
		}
	}

	dc, err = s.store.DomainByID(domainID)
	if err != nil || dc == nil {
		writeError(w, http.StatusInternalServerError, "Failed to reload domain", "INTERNAL_ERROR")
		return
	}
	s.logAudit(r, "domain.update", audit.Entry{
		TargetType:  "domain",
		TargetID:    fmt.Sprint(dc.ID),
		Description: fmt.Sprintf("Updated domain %s", dc.Domain),
	})
	writeProto(w, http.StatusOK, &pb.DomainResponse{Domain: pbDomain(dc)})
}

func (s *Server) handleDeleteDomain(w http.ResponseWriter, r *http.Request) {
	domainID := pathID(r, "domain_id")
	dc, err := s.store.DomainByID(domainID)
	if err != nil {
		writeError(w, http.StatusInternalServerError, err.Error(), "INTERNAL_ERROR")
		return
	}
	if dc == nil {
		writeError(w, http.StatusNotFound, "Domain not found", "DOMAIN_NOT_FOUND")
		return
	}

	deletedDomain := dc.Domain
	if err := s.store.DeleteDomain(domainID); err != nil {
		writeError(w, http.StatusInternalServerError, err.Error(), "INTERNAL_ERROR")
		return
	}
	s.logAudit(r, "domain.delete", audit.Entry{
		TargetType:  "domain",
		TargetID:    fmt.Sprint(domainID),
		Description: fmt.Sprintf("Deleted domain %s", deletedDomain),
	})
	writeSuccess(w)
}
