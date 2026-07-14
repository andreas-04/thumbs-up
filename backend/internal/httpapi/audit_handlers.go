package httpapi

import (
	"net/http"
	"strings"
	"time"

	pb "github.com/andreas-04/terra-crate/backend/gen/terracrate/v1"
	"github.com/andreas-04/terra-crate/backend/internal/store"
)

func (s *Server) handleListAuditLogs(w http.ResponseWriter, r *http.Request) {
	q := r.URL.Query()
	page := queryInt(r, "page", 1)
	limit := queryInt(r, "limit", 100)
	if limit > 500 {
		limit = 500
	}

	filter := store.AuditLogFilter{
		Page:      page,
		Limit:     limit,
		Action:    strings.TrimSpace(q.Get("action")),
		Category:  strings.TrimSpace(q.Get("category")),
		UserEmail: strings.TrimSpace(q.Get("user_email")),
		Status:    strings.TrimSpace(q.Get("status")),
		Search:    strings.TrimSpace(q.Get("search")),
	}
	if since := strings.TrimSpace(q.Get("since")); since != "" {
		if t, ok := parseSince(since); ok {
			filter.Since = &t
		}
	}

	logs, total, err := s.store.QueryAuditLogs(filter)
	if err != nil {
		writeError(w, http.StatusInternalServerError, err.Error(), "INTERNAL_ERROR")
		return
	}
	out := []*pb.AuditLogEntry{}
	for _, l := range logs {
		out = append(out, pbAuditLog(l))
	}
	writeProto(w, http.StatusOK, &pb.ListAuditLogsResponse{
		Logs:  out,
		Total: int32(total),
		Page:  int32(page),
		Limit: int32(limit),
	})
}

func (s *Server) handleAuditLogStats(w http.ResponseWriter, r *http.Request) {
	now := time.Now().UTC()
	todayStart := time.Date(now.Year(), now.Month(), now.Day(), 0, 0, 0, 0, time.UTC)

	stats, err := s.store.AuditStats(todayStart)
	if err != nil {
		writeError(w, http.StatusInternalServerError, err.Error(), "INTERNAL_ERROR")
		return
	}
	writeProto(w, http.StatusOK, &pb.AuditLogStats{
		Total:            int32(stats.Total),
		Today:            int32(stats.Today),
		FailedAuthToday:  int32(stats.FailedAuthToday),
		ActiveUsersToday: int32(stats.ActiveUsersToday),
	})
}
