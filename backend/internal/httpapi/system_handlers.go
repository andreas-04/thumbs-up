package httpapi

import (
	"bufio"
	"context"
	"encoding/binary"
	"fmt"
	"io"
	"net"
	"net/http"
	"net/url"
	"os"
	"strconv"
	"strings"
	"time"

	pb "github.com/andreas-04/terra-crate/backend/gen/terracrate/v1"
)

const dockerSocket = "/var/run/docker.sock"

var allowedContainers = map[string]string{
	"backend":  "terracrate-backend",
	"frontend": "terracrate-frontend",
}

func (s *Server) handleHealth(w http.ResponseWriter, r *http.Request) {
	writeProto(w, http.StatusOK, &pb.HealthResponse{
		Status:  "healthy",
		Version: "2.0",
		Service: s.cfg.ServiceName,
	})
}

// handleSystemLogs streams Docker container logs through the mounted Docker
// socket, using only net/http over a unix dial (no Docker SDK).
func (s *Server) handleSystemLogs(w http.ResponseWriter, r *http.Request) {
	containerName := strings.TrimSpace(r.URL.Query().Get("container"))
	if containerName == "" {
		containerName = "backend"
	}
	tail := queryInt(r, "tail", 200)
	if tail > 1000 {
		tail = 1000
	}
	dockerName, ok := allowedContainers[containerName]
	if !ok {
		writeError(w, http.StatusBadRequest, "Invalid container name", "INVALID_CONTAINER")
		return
	}

	unavailable := func(status int, msg string) {
		errMsg := msg
		writeProto(w, status, &pb.GetSystemLogsResponse{
			Logs:      []*pb.SystemLogLine{},
			Container: dockerName,
			Available: false,
			Error:     &errMsg,
		})
	}

	if _, err := os.Stat(dockerSocket); err != nil {
		unavailable(http.StatusOK, "Docker socket not available. Mount /var/run/docker.sock to enable system logs.")
		return
	}

	params := url.Values{}
	params.Set("stdout", "1")
	params.Set("stderr", "1")
	params.Set("timestamps", "1")
	params.Set("tail", strconv.Itoa(tail))
	if since := strings.TrimSpace(r.URL.Query().Get("since")); since != "" {
		if t, ok := parseSince(since); ok {
			params.Set("since", strconv.FormatInt(t.Unix(), 10))
		}
	}

	client := &http.Client{
		Timeout: 15 * time.Second,
		Transport: &http.Transport{
			DialContext: func(ctx context.Context, _, _ string) (net.Conn, error) {
				return (&net.Dialer{}).DialContext(ctx, "unix", dockerSocket)
			},
		},
	}
	resp, err := client.Get("http://docker/containers/" + url.PathEscape(dockerName) + "/logs?" + params.Encode())
	if err != nil {
		unavailable(http.StatusOK, "Docker socket not available. Mount /var/run/docker.sock to enable system logs.")
		return
	}
	defer resp.Body.Close()
	if resp.StatusCode != http.StatusOK {
		body, _ := io.ReadAll(io.LimitReader(resp.Body, 4096))
		unavailable(http.StatusInternalServerError,
			fmt.Sprintf("Failed to fetch logs: %s", strings.TrimSpace(string(body))))
		return
	}

	raw, err := io.ReadAll(io.LimitReader(resp.Body, 8<<20))
	if err != nil {
		unavailable(http.StatusInternalServerError, fmt.Sprintf("Failed to fetch logs: %v", err))
		return
	}

	lines := splitDockerLogLines(raw, resp.Header.Get("Content-Type"))
	parsed := []*pb.SystemLogLine{}
	for _, line := range lines {
		if line == "" {
			continue
		}
		timestamp, message := "", line
		// Docker timestamp format: 2026-04-06T14:23:01.123456789Z <message>
		if len(line) > 30 && line[4] == '-' && strings.Contains(line[:25], "T") {
			if sp := strings.IndexByte(line, ' '); sp > 0 {
				timestamp = line[:sp]
				message = line[sp+1:]
			}
		}
		parsed = append(parsed, &pb.SystemLogLine{Timestamp: timestamp, Line: message})
	}

	writeProto(w, http.StatusOK, &pb.GetSystemLogsResponse{
		Logs:      parsed,
		Container: dockerName,
		Available: true,
	})
}

// splitDockerLogLines handles both raw (TTY) log streams and the multiplexed
// stdout/stderr framing (8-byte header per frame) used for non-TTY
// containers.
func splitDockerLogLines(raw []byte, contentType string) []string {
	if strings.Contains(contentType, "application/vnd.docker.multiplexed-stream") || looksMultiplexed(raw) {
		var payload strings.Builder
		rd := bufio.NewReader(strings.NewReader(string(raw)))
		header := make([]byte, 8)
		for {
			if _, err := io.ReadFull(rd, header); err != nil {
				break
			}
			size := binary.BigEndian.Uint32(header[4:8])
			frame := make([]byte, size)
			if _, err := io.ReadFull(rd, frame); err != nil {
				break
			}
			payload.Write(frame)
		}
		return strings.Split(strings.TrimSpace(payload.String()), "\n")
	}
	return strings.Split(strings.TrimSpace(string(raw)), "\n")
}

func looksMultiplexed(raw []byte) bool {
	if len(raw) < 8 {
		return false
	}
	// Stream byte 0-2 with three zero padding bytes.
	return raw[0] <= 2 && raw[1] == 0 && raw[2] == 0 && raw[3] == 0
}
