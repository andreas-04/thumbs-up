package httpapi

import (
	"fmt"
	"net/http"
	"strings"

	pb "github.com/andreas-04/terra-crate/backend/gen/terracrate/v1"
	"github.com/andreas-04/terra-crate/backend/internal/audit"
	"github.com/andreas-04/terra-crate/backend/internal/store"
)

func (s *Server) handleListGroups(w http.ResponseWriter, r *http.Request) {
	groups, err := s.store.ListGroups()
	if err != nil {
		writeError(w, http.StatusInternalServerError, err.Error(), "INTERNAL_ERROR")
		return
	}
	out := []*pb.GroupSummary{}
	for _, g := range groups {
		out = append(out, pbGroupSummary(g))
	}
	writeProto(w, http.StatusOK, &pb.ListGroupsResponse{Groups: out})
}

func (s *Server) handleCreateGroup(w http.ResponseWriter, r *http.Request) {
	var req pb.CreateGroupRequest
	if _, ok := bodyInto(r, &req); !ok {
		writeError(w, http.StatusBadRequest, "Request body required", "MISSING_BODY")
		return
	}
	name := strings.TrimSpace(req.GetName())
	if name == "" {
		writeError(w, http.StatusBadRequest, "Group name required", "MISSING_NAME")
		return
	}
	if existing, err := s.store.GroupByName(name); err == nil && existing != nil {
		writeError(w, http.StatusConflict, "Group name already exists", "GROUP_EXISTS")
		return
	}

	var description *string
	if d := strings.TrimSpace(req.GetDescription()); d != "" {
		description = &d
	}
	grp, err := s.store.CreateGroup(name, description)
	if err != nil {
		writeError(w, http.StatusInternalServerError, err.Error(), "INTERNAL_ERROR")
		return
	}

	s.logAudit(r, "group.create", audit.Entry{
		TargetType:  "group",
		TargetID:    fmt.Sprint(grp.ID),
		Description: fmt.Sprintf("Created group %s", grp.Name),
	})
	writeProto(w, http.StatusCreated, &pb.GroupSummaryResponse{Group: pbGroupSummary(grp)})
}

func (s *Server) handleGetGroup(w http.ResponseWriter, r *http.Request) {
	grp, err := s.store.GroupByID(pathID(r, "group_id"))
	if err != nil {
		writeError(w, http.StatusInternalServerError, err.Error(), "INTERNAL_ERROR")
		return
	}
	if grp == nil {
		writeError(w, http.StatusNotFound, "Group not found", "GROUP_NOT_FOUND")
		return
	}
	writeProto(w, http.StatusOK, &pb.GroupDetailResponse{Group: pbGroupDetail(grp)})
}

func (s *Server) handleUpdateGroup(w http.ResponseWriter, r *http.Request) {
	groupID := pathID(r, "group_id")
	grp, err := s.store.GroupByID(groupID)
	if err != nil {
		writeError(w, http.StatusInternalServerError, err.Error(), "INTERNAL_ERROR")
		return
	}
	if grp == nil {
		writeError(w, http.StatusNotFound, "Group not found", "GROUP_NOT_FOUND")
		return
	}

	var req pb.UpdateGroupRequest
	if _, ok := bodyInto(r, &req); !ok {
		writeError(w, http.StatusBadRequest, "Request body required", "MISSING_BODY")
		return
	}

	name := grp.Name
	if req.Name != nil {
		name = strings.TrimSpace(req.GetName())
		if name == "" {
			writeError(w, http.StatusBadRequest, "Group name required", "MISSING_NAME")
			return
		}
		existing, eerr := s.store.GroupByName(name)
		if eerr != nil {
			writeError(w, http.StatusInternalServerError, eerr.Error(), "INTERNAL_ERROR")
			return
		}
		if existing != nil && existing.ID != groupID {
			writeError(w, http.StatusConflict, "Group name already exists", "GROUP_EXISTS")
			return
		}
	}

	description := grp.Description
	if req.Description != nil {
		if d := strings.TrimSpace(req.GetDescription()); d != "" {
			description = &d
		} else {
			description = nil
		}
	}

	if err := s.store.UpdateGroupMeta(groupID, name, description); err != nil {
		writeError(w, http.StatusInternalServerError, err.Error(), "INTERNAL_ERROR")
		return
	}
	grp, err = s.store.GroupByID(groupID)
	if err != nil || grp == nil {
		writeError(w, http.StatusInternalServerError, "Failed to reload group", "INTERNAL_ERROR")
		return
	}

	s.logAudit(r, "group.update", audit.Entry{
		TargetType:  "group",
		TargetID:    fmt.Sprint(grp.ID),
		Description: fmt.Sprintf("Updated group %s", grp.Name),
	})
	writeProto(w, http.StatusOK, &pb.GroupDetailResponse{Group: pbGroupDetail(grp)})
}

func (s *Server) handleDeleteGroup(w http.ResponseWriter, r *http.Request) {
	groupID := pathID(r, "group_id")
	grp, err := s.store.GroupByID(groupID)
	if err != nil {
		writeError(w, http.StatusInternalServerError, err.Error(), "INTERNAL_ERROR")
		return
	}
	if grp == nil {
		writeError(w, http.StatusNotFound, "Group not found", "GROUP_NOT_FOUND")
		return
	}

	deletedName := grp.Name
	if err := s.store.DeleteGroup(groupID); err != nil {
		writeError(w, http.StatusInternalServerError, err.Error(), "INTERNAL_ERROR")
		return
	}
	s.logAudit(r, "group.delete", audit.Entry{
		TargetType:  "group",
		TargetID:    fmt.Sprint(groupID),
		Description: fmt.Sprintf("Deleted group %s", deletedName),
	})
	writeSuccess(w)
}

func (s *Server) handleUpdateGroupPermissions(w http.ResponseWriter, r *http.Request) {
	groupID := pathID(r, "group_id")
	grp, err := s.store.GroupByID(groupID)
	if err != nil {
		writeError(w, http.StatusInternalServerError, err.Error(), "INTERNAL_ERROR")
		return
	}
	if grp == nil {
		writeError(w, http.StatusNotFound, "Group not found", "GROUP_NOT_FOUND")
		return
	}

	var req pb.UpdateGroupPermissionsRequest
	raw, ok := bodyInto(r, &req)
	if !ok {
		writeError(w, http.StatusBadRequest, "Request body required", "MISSING_BODY")
		return
	}
	if _, present := raw["permissions"]; !present {
		writeError(w, http.StatusBadRequest, "Permissions array required", "MISSING_PERMISSIONS")
		return
	}

	rows := []*store.GroupPermission{}
	for _, in := range req.GetPermissions() {
		path := in.GetPath()
		if path == "" {
			path = "/"
		}
		rows = append(rows, &store.GroupPermission{FolderPath: path, CanRead: in.GetRead(), CanWrite: in.GetWrite()})
	}
	if err := s.store.ReplaceGroupPermissions(groupID, rows); err != nil {
		writeError(w, http.StatusInternalServerError, err.Error(), "INTERNAL_ERROR")
		return
	}

	perms, err := s.store.GroupPermissions(groupID)
	if err != nil {
		writeError(w, http.StatusInternalServerError, err.Error(), "INTERNAL_ERROR")
		return
	}
	out := []*pb.GroupPermission{}
	for _, p := range perms {
		out = append(out, pbGroupPermission(p))
	}

	s.logAudit(r, "permission.group_update", audit.Entry{
		TargetType:  "group",
		TargetID:    fmt.Sprint(grp.ID),
		Description: fmt.Sprintf("Updated permissions for group %s", grp.Name),
	})
	writeProto(w, http.StatusOK, &pb.GroupPermissionsResponse{Permissions: out})
}

func (s *Server) handleUpdateGroupMembers(w http.ResponseWriter, r *http.Request) {
	groupID := pathID(r, "group_id")
	grp, err := s.store.GroupByID(groupID)
	if err != nil {
		writeError(w, http.StatusInternalServerError, err.Error(), "INTERNAL_ERROR")
		return
	}
	if grp == nil {
		writeError(w, http.StatusNotFound, "Group not found", "GROUP_NOT_FOUND")
		return
	}

	var req pb.UpdateGroupMembersRequest
	raw, ok := bodyInto(r, &req)
	if !ok {
		writeError(w, http.StatusBadRequest, "Request body required", "MISSING_BODY")
		return
	}
	if _, present := raw["userIds"]; !present {
		writeError(w, http.StatusBadRequest, "userIds array required", "MISSING_USER_IDS")
		return
	}

	ids := make([]int, 0, len(req.GetUserIds()))
	for _, uid := range req.GetUserIds() {
		ids = append(ids, int(uid))
	}
	if err := s.store.SetGroupMembers(groupID, ids); err != nil {
		writeError(w, http.StatusInternalServerError, err.Error(), "INTERNAL_ERROR")
		return
	}

	grp, err = s.store.GroupByID(groupID)
	if err != nil || grp == nil {
		writeError(w, http.StatusInternalServerError, "Failed to reload group", "INTERNAL_ERROR")
		return
	}
	s.logAudit(r, "group.members_update", audit.Entry{
		TargetType:  "group",
		TargetID:    fmt.Sprint(grp.ID),
		Description: fmt.Sprintf("Updated members for group %s", grp.Name),
	})
	writeProto(w, http.StatusOK, &pb.GroupDetailResponse{Group: pbGroupDetail(grp)})
}
