package httpapi

import (
	"fmt"
	"io/fs"
	"net/http"
	"os"
	"path/filepath"

	pb "github.com/andreas-04/terra-crate/backend/gen/terracrate/v1"
	"github.com/andreas-04/terra-crate/backend/internal/audit"
	"github.com/andreas-04/terra-crate/backend/internal/perms"
	"github.com/andreas-04/terra-crate/backend/internal/store"
)

func (s *Server) handleGetUserPermissions(w http.ResponseWriter, r *http.Request) {
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
	s.writeUserPermissions(w, userID)
}

func (s *Server) writeUserPermissions(w http.ResponseWriter, userID int) {
	permsRows, err := s.store.FolderPermissionsForUser(userID)
	if err != nil {
		writeError(w, http.StatusInternalServerError, err.Error(), "INTERNAL_ERROR")
		return
	}
	out := []*pb.FolderPermission{}
	for _, p := range permsRows {
		out = append(out, pbFolderPermission(p))
	}
	writeProto(w, http.StatusOK, &pb.FolderPermissionsResponse{Permissions: out})
}

func (s *Server) handleUpdateUserPermissions(w http.ResponseWriter, r *http.Request) {
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

	var req pb.UpdateUserPermissionsRequest
	raw, ok := bodyInto(r, &req)
	if !ok {
		writeError(w, http.StatusBadRequest, "Request body required", "MISSING_BODY")
		return
	}
	if _, present := raw["permissions"]; !present {
		writeError(w, http.StatusBadRequest, "Permissions array required", "MISSING_PERMISSIONS")
		return
	}

	// Only rows with at least one valid tri-state flag are kept.
	isValid := func(v *string) *string {
		if v != nil && (*v == "allow" || *v == "deny") {
			return v
		}
		return nil
	}
	var rows []*store.FolderPermission
	for _, in := range req.GetPermissions() {
		readVal := isValid(in.Read)
		writeVal := isValid(in.Write)
		if readVal == nil && writeVal == nil {
			continue
		}
		path := in.GetPath()
		if path == "" {
			path = "/"
		}
		rows = append(rows, &store.FolderPermission{
			UserID:     userID,
			FolderPath: path,
			CanRead:    readVal,
			CanWrite:   writeVal,
		})
	}
	if err := s.store.ReplaceFolderPermissions(userID, rows); err != nil {
		writeError(w, http.StatusInternalServerError, err.Error(), "INTERNAL_ERROR")
		return
	}

	s.logAudit(r, "permission.user_update", audit.Entry{
		TargetType:  "user",
		TargetID:    fmt.Sprint(userID),
		Description: fmt.Sprintf("Updated permissions for %s", user.Email),
	})
	s.writeUserPermissions(w, userID)
}

func (s *Server) handleEffectivePermissions(w http.ResponseWriter, r *http.Request) {
	user, err := s.store.UserByID(pathID(r, "user_id"))
	if err != nil {
		writeError(w, http.StatusInternalServerError, err.Error(), "INTERNAL_ERROR")
		return
	}
	if user == nil {
		writeError(w, http.StatusNotFound, "User not found", "USER_NOT_FOUND")
		return
	}

	domain, groups, userPerms, err := s.permInputs(user)
	if err != nil {
		writeError(w, http.StatusInternalServerError, err.Error(), "INTERNAL_ERROR")
		return
	}
	detailed := perms.ResolveDetailed(domain, groups, userPerms)

	out := map[string]*pb.EffectivePermissionEntry{}
	for path, entry := range detailed {
		pbEntry := &pb.EffectivePermissionEntry{
			Groups: []*pb.GroupTierEntry{},
			Effective: &pb.EffectiveFlags{
				CanRead:  entry.Effective.CanRead,
				CanWrite: entry.Effective.CanWrite,
				Source:   entry.Effective.Source,
			},
		}
		if entry.Domain != nil {
			pbEntry.Domain = &pb.TierFlags{CanRead: entry.Domain.CanRead, CanWrite: entry.Domain.CanWrite}
		}
		for _, g := range entry.Groups {
			pbEntry.Groups = append(pbEntry.Groups, &pb.GroupTierEntry{
				GroupId:   int32(g.GroupID),
				GroupName: g.GroupName,
				CanRead:   g.CanRead,
				CanWrite:  g.CanWrite,
			})
		}
		if entry.GroupMerged != nil {
			pbEntry.GroupMerged = &pb.TierFlags{CanRead: entry.GroupMerged.CanRead, CanWrite: entry.GroupMerged.CanWrite}
		}
		if entry.User != nil {
			pbEntry.User = &pb.UserTierFlags{CanRead: entry.User.CanRead, CanWrite: entry.User.CanWrite}
		}
		out[path] = pbEntry
	}
	writeProto(w, http.StatusOK, &pb.EffectivePermissionsResponse{Permissions: out})
}

func (s *Server) handleListFolders(w http.ResponseWriter, r *http.Request) {
	folders := []*pb.Folder{}
	filesRoot := s.cfg.FilesRoot()

	if _, err := os.Stat(filesRoot); err == nil {
		walkErr := filepath.WalkDir(filesRoot, func(path string, d fs.DirEntry, err error) error {
			if err != nil {
				return err
			}
			if !d.IsDir() || path == filesRoot {
				return nil
			}
			rel, rerr := filepath.Rel(filesRoot, path)
			if rerr != nil {
				return rerr
			}
			folders = append(folders, &pb.Folder{
				Path: "/" + filepath.ToSlash(rel),
				Name: d.Name(),
			})
			return nil
		})
		if walkErr != nil {
			writeError(w, http.StatusInternalServerError, walkErr.Error(), "FOLDER_SCAN_ERROR")
			return
		}
	}
	writeProto(w, http.StatusOK, &pb.ListFoldersResponse{Folders: folders})
}
