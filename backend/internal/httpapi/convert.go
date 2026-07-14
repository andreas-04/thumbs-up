package httpapi

import (
	"net/http"
	"strings"
	"time"

	"google.golang.org/protobuf/types/known/timestamppb"

	pb "github.com/andreas-04/terra-crate/backend/gen/terracrate/v1"
	"github.com/andreas-04/terra-crate/backend/internal/audit"
	"github.com/andreas-04/terra-crate/backend/internal/perms"
	"github.com/andreas-04/terra-crate/backend/internal/store"
)

func ts(t *time.Time) *timestamppb.Timestamp {
	if t == nil {
		return nil
	}
	return timestamppb.New(*t)
}

func tsv(t time.Time) *timestamppb.Timestamp { return timestamppb.New(t) }

func intp(i *int) *int32 {
	if i == nil {
		return nil
	}
	v := int32(*i)
	return &v
}

// logAudit records an entry, filling user/IP context from the request the
// same way log_audit() pulled it off the Flask request.
func (s *Server) logAudit(r *http.Request, action string, e audit.Entry) {
	if u := currentUser(r); u != nil {
		if e.UserID == 0 {
			e.UserID = u.ID
		}
		if e.UserEmail == "" {
			e.UserEmail = u.Email
		}
	}
	if e.IPAddress == "" {
		e.IPAddress = clientIP(r)
	}
	s.audit.Log(action, e)
}

// userGroups loads the group refs embedded in user payloads.
func (s *Server) userGroups(userID int) []*pb.GroupRef {
	refs := []*pb.GroupRef{}
	groups, err := s.store.GroupsForUser(userID)
	if err != nil {
		return refs
	}
	for _, g := range groups {
		refs = append(refs, &pb.GroupRef{Id: int32(g.ID), Name: g.Name})
	}
	return refs
}

func (s *Server) pbUser(u *store.User) *pb.User {
	return &pb.User{
		Id:                     int32(u.ID),
		Email:                  u.Email,
		Role:                   u.Role,
		RequiresPasswordChange: u.IsDefaultPIN,
		IsApproved:             u.IsApproved,
		CreatedAt:              tsv(u.CreatedAt),
		LastLogin:              ts(u.LastLogin),
		Groups:                 s.userGroups(u.ID),
		CertRevoked:            u.CertRevoked,
		CertIssuedAt:           ts(u.CertIssuedAt),
		CertExpiresAt:          ts(u.CertExpiresAt),
	}
}

func (s *Server) pbUserDetail(u *store.User) *pb.UserDetail {
	base := s.pbUser(u)
	folderPerms := []*pb.FolderPermission{}
	if perms, err := s.store.FolderPermissionsForUser(u.ID); err == nil {
		for _, p := range perms {
			folderPerms = append(folderPerms, pbFolderPermission(p))
		}
	}
	return &pb.UserDetail{
		Id:                     base.Id,
		Email:                  base.Email,
		Role:                   base.Role,
		RequiresPasswordChange: base.RequiresPasswordChange,
		IsApproved:             base.IsApproved,
		CreatedAt:              base.CreatedAt,
		LastLogin:              base.LastLogin,
		Groups:                 base.Groups,
		CertRevoked:            base.CertRevoked,
		CertIssuedAt:           base.CertIssuedAt,
		CertExpiresAt:          base.CertExpiresAt,
		FolderPermissions:      folderPerms,
	}
}

func pbFolderPermission(p *store.FolderPermission) *pb.FolderPermission {
	return &pb.FolderPermission{
		Id:        int32(p.ID),
		UserId:    int32(p.UserID),
		Path:      p.FolderPath,
		Read:      p.CanRead,
		Write:     p.CanWrite,
		CreatedAt: tsv(p.CreatedAt),
	}
}

func pbDomain(dc *store.DomainConfig) *pb.DomainConfig {
	permsOut := []*pb.DomainPermission{}
	for _, p := range dc.Permissions {
		permsOut = append(permsOut, &pb.DomainPermission{
			Id:        int32(p.ID),
			DomainId:  int32(p.DomainID),
			Path:      p.FolderPath,
			Read:      p.CanRead,
			Write:     p.CanWrite,
			CreatedAt: tsv(p.CreatedAt),
		})
	}
	return &pb.DomainConfig{
		Id:          int32(dc.ID),
		Domain:      dc.Domain,
		Permissions: permsOut,
		CreatedAt:   tsv(dc.CreatedAt),
		UpdatedAt:   tsv(dc.UpdatedAt),
	}
}

func pbGroupPermission(p *store.GroupPermission) *pb.GroupPermission {
	return &pb.GroupPermission{
		Id:        int32(p.ID),
		GroupId:   int32(p.GroupID),
		Path:      p.FolderPath,
		Read:      p.CanRead,
		Write:     p.CanWrite,
		CreatedAt: tsv(p.CreatedAt),
	}
}

func pbGroupSummary(g *store.Group) *pb.GroupSummary {
	return &pb.GroupSummary{
		Id:              int32(g.ID),
		Name:            g.Name,
		Description:     g.Description,
		MemberCount:     int32(len(g.Members)),
		PermissionCount: int32(len(g.Permissions)),
		CreatedAt:       tsv(g.CreatedAt),
		UpdatedAt:       tsv(g.UpdatedAt),
	}
}

func pbGroupDetail(g *store.Group) *pb.GroupDetail {
	members := []*pb.GroupMember{}
	for _, m := range g.Members {
		members = append(members, &pb.GroupMember{Id: int32(m.ID), Email: m.Email})
	}
	permsOut := []*pb.GroupPermission{}
	for _, p := range g.Permissions {
		permsOut = append(permsOut, pbGroupPermission(p))
	}
	return &pb.GroupDetail{
		Id:              int32(g.ID),
		Name:            g.Name,
		Description:     g.Description,
		MemberCount:     int32(len(g.Members)),
		PermissionCount: int32(len(g.Permissions)),
		CreatedAt:       tsv(g.CreatedAt),
		UpdatedAt:       tsv(g.UpdatedAt),
		Members:         members,
		Permissions:     permsOut,
	}
}

func pbSettings(st *store.SystemSettings) *pb.SystemSettings {
	masked := ""
	if st.SMTPPassword != "" {
		masked = "*****"
	}
	allowed := []string{}
	for _, d := range strings.Split(st.AllowedDomains, ",") {
		if d = strings.TrimSpace(d); d != "" {
			allowed = append(allowed, d)
		}
	}
	return &pb.SystemSettings{
		Id:             int32(st.ID),
		AuthMethod:     st.AuthMethod,
		TlsEnabled:     st.TLSEnabled,
		HttpsPort:      int32(st.HTTPSPort),
		DeviceName:     st.DeviceName,
		UpdatedAt:      tsv(st.UpdatedAt),
		SmtpEnabled:    st.SMTPEnabled,
		SmtpHost:       st.SMTPHost,
		SmtpPort:       int32(st.SMTPPort),
		SmtpUsername:   st.SMTPUsername,
		SmtpPassword:   masked,
		SmtpFromEmail:  st.SMTPFromEmail,
		SmtpUseTls:     st.SMTPUseTLS,
		AllowedDomains: allowed,
	}
}

func pbRevokedCert(rc *store.RevokedCertificate) *pb.RevokedCertificate {
	return &pb.RevokedCertificate{
		Id:           int32(rc.ID),
		SerialNumber: rc.SerialNumber,
		UserId:       intp(rc.UserID),
		RevokedAt:    tsv(rc.RevokedAt),
		Reason:       rc.Reason,
		RevokedBy:    intp(rc.RevokedBy),
	}
}

func pbAuditLog(l *store.AuditLog) *pb.AuditLogEntry {
	return &pb.AuditLogEntry{
		Id:          int32(l.ID),
		Timestamp:   tsv(l.Timestamp),
		UserId:      intp(l.UserID),
		UserEmail:   l.UserEmail,
		Action:      l.Action,
		TargetType:  l.TargetType,
		TargetId:    l.TargetID,
		Description: l.Description,
		IpAddress:   l.IPAddress,
		Status:      l.Status,
	}
}

// permInputs converts the user's stored state into resolver inputs.
func (s *Server) permInputs(u *store.User) (domain []perms.BoolPerm, groups []perms.GroupPerms, user []perms.TriPerm, err error) {
	if at := strings.LastIndex(u.Email, "@"); at >= 0 {
		emailDomain := strings.ToLower(u.Email[at+1:])
		dc, derr := s.store.DomainByName(emailDomain)
		if derr != nil {
			return nil, nil, nil, derr
		}
		if dc != nil {
			for _, dp := range dc.Permissions {
				domain = append(domain, perms.BoolPerm{Path: dp.FolderPath, Read: dp.CanRead, Write: dp.CanWrite})
			}
		}
	}
	userGroups, err := s.store.GroupsForUser(u.ID)
	if err != nil {
		return nil, nil, nil, err
	}
	for _, g := range userGroups {
		gp := perms.GroupPerms{GroupID: g.ID, GroupName: g.Name}
		for _, p := range g.Permissions {
			gp.Perms = append(gp.Perms, perms.BoolPerm{Path: p.FolderPath, Read: p.CanRead, Write: p.CanWrite})
		}
		groups = append(groups, gp)
	}
	userPerms, err := s.store.FolderPermissionsForUser(u.ID)
	if err != nil {
		return nil, nil, nil, err
	}
	for _, p := range userPerms {
		user = append(user, perms.TriPerm{Path: p.FolderPath, Read: p.CanRead, Write: p.CanWrite})
	}
	return domain, groups, user, nil
}

// resolveEffective builds the user's effective permission map.
func (s *Server) resolveEffective(u *store.User) (map[string]perms.Effective, error) {
	domain, groups, user, err := s.permInputs(u)
	if err != nil {
		return nil, err
	}
	return perms.Resolve(domain, groups, user), nil
}

// userHasAccess ports server.user_has_access / permissions.check_access.
func (s *Server) userHasAccess(u *store.User, folderPath string, requireWrite bool) bool {
	effective, err := s.resolveEffective(u)
	if err != nil {
		return false
	}
	return perms.CheckAccess(effective, folderPath, requireWrite)
}
