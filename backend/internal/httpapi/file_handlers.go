package httpapi

import (
	"fmt"
	"io"
	"mime"
	"net/http"
	"os"
	"path/filepath"
	"strings"

	"google.golang.org/protobuf/types/known/timestamppb"

	pb "github.com/andreas-04/terra-crate/backend/gen/terracrate/v1"
	"github.com/andreas-04/terra-crate/backend/internal/audit"
	"github.com/andreas-04/terra-crate/backend/internal/perms"
	"github.com/andreas-04/terra-crate/backend/internal/store"
)

func (s *Server) handleListFiles(w http.ResponseWriter, r *http.Request) {
	user := currentUser(r)
	if user.Role != "admin" && s.requireMTLS(w, r, user) {
		return
	}
	path := r.URL.Query().Get("path")
	search := strings.TrimSpace(r.URL.Query().Get("search"))

	files := listDirectory(s.cfg.FilesRoot(), path)

	// Non-admins only see items they can reach (or folders leading toward
	// granted areas).
	if user.Role != "admin" {
		effective, err := s.resolveEffective(user)
		if err != nil {
			writeError(w, http.StatusInternalServerError, err.Error(), "FILE_LIST_ERROR")
			return
		}
		granted := perms.VisiblePaths(effective)
		if len(granted) == 0 {
			files = []*pb.FileItem{}
		} else {
			current := "/"
			if path != "" {
				current = "/" + path
			}
			filtered := []*pb.FileItem{}
			for _, f := range files {
				itemPath := "/" + f.Name
				if current != "/" {
					itemPath = strings.TrimRight(current, "/") + "/" + f.Name
				}
				if perms.IsItemVisible(itemPath, f.Type == "folder", granted) {
					filtered = append(filtered, f)
				}
			}
			files = filtered
		}
	}

	writeProto(w, http.StatusOK, &pb.ListFilesResponse{
		Files:       filterSearch(files, search),
		CurrentPath: currentPathOf(path),
		ParentPath:  parentPathOf(path),
	})
}

func currentPathOf(path string) string {
	if path == "" {
		return "/"
	}
	return "/" + path
}

func (s *Server) handleUploadFile(w http.ResponseWriter, r *http.Request) {
	if !s.cfg.EnableUploads {
		writeError(w, http.StatusForbidden, "Uploads are disabled", "UPLOADS_DISABLED")
		return
	}
	user := currentUser(r)
	if user.Role != "admin" && s.requireMTLS(w, r, user) {
		return
	}

	r.Body = http.MaxBytesReader(w, r.Body, s.cfg.MaxUploadSize)
	if err := r.ParseMultipartForm(32 << 20); err != nil {
		if _, ok := err.(*http.MaxBytesError); ok {
			writeError(w, http.StatusRequestEntityTooLarge, "Upload too large", "UPLOAD_TOO_LARGE")
			return
		}
		writeError(w, http.StatusBadRequest, "No file provided", "NO_FILE")
		return
	}
	path := strings.TrimLeft(strings.TrimSpace(r.FormValue("path")), "/")

	if user.Role != "admin" {
		checkPath := "/"
		if path != "" {
			checkPath = "/" + path
		}
		if !s.userHasAccess(user, checkPath, true) {
			writeError(w, http.StatusForbidden, "Write access denied", "WRITE_ACCESS_DENIED")
			return
		}
	}

	file, header, err := r.FormFile("file")
	if err != nil {
		writeError(w, http.StatusBadRequest, "No file provided", "NO_FILE")
		return
	}
	defer file.Close()
	if header.Filename == "" {
		writeError(w, http.StatusBadRequest, "No file selected", "NO_FILE")
		return
	}

	filename := secureFilename(header.Filename)
	targetDir, ok := resolveUnder(s.cfg.FilesRoot(), path)
	if !ok {
		writeError(w, http.StatusBadRequest, "Invalid path", "INVALID_PATH")
		return
	}
	if err := os.MkdirAll(targetDir, 0o755); err != nil {
		writeError(w, http.StatusInternalServerError, err.Error(), "UPLOAD_ERROR")
		return
	}
	targetPath := filepath.Join(targetDir, filename)

	dst, err := os.Create(targetPath)
	if err != nil {
		writeError(w, http.StatusInternalServerError, err.Error(), "UPLOAD_ERROR")
		return
	}
	if _, err := io.Copy(dst, file); err != nil {
		dst.Close()
		os.Remove(targetPath)
		writeError(w, http.StatusInternalServerError, err.Error(), "UPLOAD_ERROR")
		return
	}
	dst.Close()

	info, err := os.Stat(targetPath)
	if err != nil {
		writeError(w, http.StatusInternalServerError, err.Error(), "UPLOAD_ERROR")
		return
	}
	relPath := filename
	if path != "" {
		relPath = filepath.ToSlash(filepath.Join(path, filename))
	}

	desc := fmt.Sprintf("Uploaded %s", filename)
	if path != "" {
		desc = fmt.Sprintf("Uploaded %s to /%s", filename, path)
	}
	s.logAudit(r, "file.upload", audit.Entry{TargetType: "file", TargetID: relPath, Description: desc})

	writeProto(w, http.StatusCreated, &pb.UploadFileResponse{File: &pb.UploadedFile{
		Name:       filename,
		Path:       relPath,
		Size:       info.Size(),
		ModifiedAt: timestamppb.New(info.ModTime()),
	}})
}

// checkParentRead verifies read access on the file's containing folder.
func (s *Server) checkParentRead(user *store.User, path string) bool {
	parent := filepath.ToSlash(filepath.Dir(path))
	folderPath := "/" + parent
	if parent == "." {
		folderPath = "/"
	}
	return s.userHasAccess(user, folderPath, false)
}

func (s *Server) serveFile(w http.ResponseWriter, r *http.Request, asAttachment bool) {
	path := r.URL.Query().Get("path")
	if path == "" {
		writeError(w, http.StatusBadRequest, "Path required", "MISSING_PATH")
		return
	}
	user := currentUser(r)
	if user.Role != "admin" {
		if s.requireMTLS(w, r, user) {
			return
		}
		if !s.checkParentRead(user, path) {
			writeError(w, http.StatusForbidden, "Read access denied", "READ_ACCESS_DENIED")
			return
		}
	}

	filePath, ok := resolveExistingFile(s.cfg.FilesRoot(), path)
	if ok {
		if info, err := os.Stat(filePath); err != nil || info.IsDir() {
			ok = false
		}
	}
	if !ok {
		writeError(w, http.StatusNotFound, "File not found", "FILE_NOT_FOUND")
		return
	}

	if asAttachment {
		s.logAudit(r, "file.download", audit.Entry{
			TargetType:  "file",
			TargetID:    path,
			Description: fmt.Sprintf("Downloaded %s", path),
		})
	}
	sendFile(w, r, filePath, asAttachment)
}

func (s *Server) handleDownloadFile(w http.ResponseWriter, r *http.Request) {
	s.serveFile(w, r, true)
}

func (s *Server) handlePreviewFile(w http.ResponseWriter, r *http.Request) {
	s.serveFile(w, r, false)
}

// sendFile streams a file with range-request support (http.ServeContent),
// inline or as an attachment.
func sendFile(w http.ResponseWriter, r *http.Request, filePath string, asAttachment bool) {
	f, err := os.Open(filePath)
	if err != nil {
		writeError(w, http.StatusInternalServerError, "Error downloading file", "DOWNLOAD_ERROR")
		return
	}
	defer f.Close()
	info, err := f.Stat()
	if err != nil {
		writeError(w, http.StatusInternalServerError, "Error downloading file", "DOWNLOAD_ERROR")
		return
	}

	name := filepath.Base(filePath)
	mimeType := mime.TypeByExtension(filepath.Ext(name))
	if mimeType == "" {
		mimeType = "application/octet-stream"
	}
	w.Header().Set("Content-Type", mimeType)
	disposition := "inline"
	if asAttachment {
		disposition = "attachment"
	}
	w.Header().Set("Content-Disposition", fmt.Sprintf("%s; filename=%q", disposition, name))
	http.ServeContent(w, r, name, info.ModTime(), f)
}

func (s *Server) handleMkdir(w http.ResponseWriter, r *http.Request) {
	var req pb.MkdirRequest
	if _, ok := bodyInto(r, &req); !ok {
		writeError(w, http.StatusBadRequest, "Request body required", "MISSING_BODY")
		return
	}
	path := strings.TrimLeft(strings.TrimSpace(req.GetPath()), "/")
	name := strings.TrimSpace(req.GetName())
	if name == "" {
		writeError(w, http.StatusBadRequest, "Directory name required", "MISSING_NAME")
		return
	}

	user := currentUser(r)
	if user.Role != "admin" {
		if s.requireMTLS(w, r, user) {
			return
		}
		checkPath := "/"
		if path != "" {
			checkPath = "/" + path
		}
		if !s.userHasAccess(user, checkPath, true) {
			writeError(w, http.StatusForbidden, "Write access denied", "WRITE_ACCESS_DENIED")
			return
		}
	}

	safeName := secureFilename(name)
	if safeName == "" {
		writeError(w, http.StatusBadRequest, "Invalid directory name", "INVALID_NAME")
		return
	}
	targetDir, ok := resolveUnder(s.cfg.FilesRoot(), filepath.Join(path, safeName))
	if !ok {
		writeError(w, http.StatusBadRequest, "Invalid path", "INVALID_PATH")
		return
	}
	if _, err := os.Stat(targetDir); err == nil {
		writeError(w, http.StatusConflict, "Directory already exists", "DIR_EXISTS")
		return
	}
	if err := os.MkdirAll(targetDir, 0o755); err != nil {
		writeError(w, http.StatusInternalServerError, err.Error(), "CREATE_DIR_ERROR")
		return
	}

	relPath := safeName
	if path != "" {
		relPath = filepath.ToSlash(filepath.Join(path, safeName))
	}
	desc := fmt.Sprintf("Created directory %s", safeName)
	if path != "" {
		desc = fmt.Sprintf("Created directory %s in /%s", safeName, path)
	}
	s.logAudit(r, "file.mkdir", audit.Entry{TargetType: "file", TargetID: relPath, Description: desc})

	writeProto(w, http.StatusCreated, &pb.MkdirResponse{Folder: &pb.CreatedFolder{Name: safeName, Path: relPath}})
}

func (s *Server) handleDeleteFile(w http.ResponseWriter, r *http.Request) {
	if !s.cfg.EnableDelete {
		writeError(w, http.StatusForbidden, "Delete is disabled", "DELETE_DISABLED")
		return
	}
	path := r.URL.Query().Get("path")
	if path == "" {
		writeError(w, http.StatusBadRequest, "Path required", "MISSING_PATH")
		return
	}
	user := currentUser(r)
	if user.Role != "admin" {
		if s.requireMTLS(w, r, user) {
			return
		}
		if !s.userHasAccessParentWrite(user, path) {
			writeError(w, http.StatusForbidden, "Write access denied", "WRITE_ACCESS_DENIED")
			return
		}
	}

	targetPath, ok := resolveExistingFile(s.cfg.FilesRoot(), path)
	if !ok {
		writeError(w, http.StatusNotFound, "File not found", "FILE_NOT_FOUND")
		return
	}

	if err := os.RemoveAll(targetPath); err != nil {
		writeError(w, http.StatusInternalServerError, err.Error(), "DELETE_ERROR")
		return
	}
	s.logAudit(r, "file.delete", audit.Entry{
		TargetType:  "file",
		TargetID:    path,
		Description: fmt.Sprintf("Deleted %s", path),
	})
	writeSuccess(w)
}

func (s *Server) handleRenameFile(w http.ResponseWriter, r *http.Request) {
	var req pb.RenameFileRequest
	if _, ok := bodyInto(r, &req); !ok {
		writeError(w, http.StatusBadRequest, "Request body required", "MISSING_BODY")
		return
	}
	path := strings.TrimLeft(strings.TrimSpace(req.GetPath()), "/")
	newName := strings.TrimSpace(req.GetNewName())
	if path == "" {
		writeError(w, http.StatusBadRequest, "Path required", "MISSING_PATH")
		return
	}
	if newName == "" {
		writeError(w, http.StatusBadRequest, "New name required", "MISSING_NAME")
		return
	}

	user := currentUser(r)
	if user.Role != "admin" {
		if s.requireMTLS(w, r, user) {
			return
		}
		if !s.userHasAccessParentWrite(user, path) {
			writeError(w, http.StatusForbidden, "Write access denied", "WRITE_ACCESS_DENIED")
			return
		}
	}

	targetPath, ok := resolveExistingFile(s.cfg.FilesRoot(), path)
	if !ok {
		writeError(w, http.StatusNotFound, "File not found", "FILE_NOT_FOUND")
		return
	}

	safeName := secureFilename(newName)
	if safeName == "" {
		writeError(w, http.StatusBadRequest, "Invalid file name", "INVALID_NAME")
		return
	}
	newPath := filepath.Join(filepath.Dir(targetPath), safeName)
	if _, err := os.Stat(newPath); err == nil {
		writeError(w, http.StatusConflict, "A file with that name already exists", "NAME_EXISTS")
		return
	}
	if absBase, err := filepath.Abs(s.cfg.FilesRoot()); err != nil || !underRoot(filepath.Clean(newPath), absBase) {
		writeError(w, http.StatusBadRequest, "Invalid path", "INVALID_PATH")
		return
	}

	if err := os.Rename(targetPath, newPath); err != nil {
		writeError(w, http.StatusInternalServerError, err.Error(), "RENAME_ERROR")
		return
	}

	newRel := safeName
	if parent := filepath.ToSlash(filepath.Dir(path)); parent != "." {
		newRel = parent + "/" + safeName
	}

	s.logAudit(r, "file.rename", audit.Entry{
		TargetType:  "file",
		TargetID:    path,
		Description: fmt.Sprintf("Renamed %s to %s", path, newRel),
	})
	writeProto(w, http.StatusOK, &pb.RenameFileResponse{Success: true, NewPath: newRel, NewName: safeName})
}

// userHasAccessParentWrite checks write access on a path's parent folder
// ("." maps to "/").
func (s *Server) userHasAccessParentWrite(user *store.User, path string) bool {
	parent := filepath.ToSlash(filepath.Dir(path))
	checkPath := "/"
	if parent != "." {
		checkPath = "/" + parent
	}
	return s.userHasAccess(user, checkPath, true)
}

func (s *Server) handleMoveFile(w http.ResponseWriter, r *http.Request) {
	var req pb.MoveFileRequest
	if _, ok := bodyInto(r, &req); !ok {
		writeError(w, http.StatusBadRequest, "Request body required", "MISSING_BODY")
		return
	}
	srcPath := strings.TrimLeft(strings.TrimSpace(req.GetSrcPath()), "/")
	destDir := strings.TrimLeft(strings.TrimSpace(req.GetDestDir()), "/")
	if srcPath == "" {
		writeError(w, http.StatusBadRequest, "Source path required", "MISSING_SRC")
		return
	}

	user := currentUser(r)
	if user.Role != "admin" {
		if s.requireMTLS(w, r, user) {
			return
		}
		destCheck := "/"
		if destDir != "" {
			destCheck = "/" + destDir
		}
		if !s.userHasAccessParentWrite(user, srcPath) {
			writeError(w, http.StatusForbidden, "Write access denied on source", "WRITE_ACCESS_DENIED")
			return
		}
		if !s.userHasAccess(user, destCheck, true) {
			writeError(w, http.StatusForbidden, "Write access denied on destination", "WRITE_ACCESS_DENIED")
			return
		}
	}

	source, ok := resolveExistingFile(s.cfg.FilesRoot(), srcPath)
	if !ok {
		writeError(w, http.StatusNotFound, "Source not found", "FILE_NOT_FOUND")
		return
	}

	destParent, ok := resolveUnder(s.cfg.FilesRoot(), destDir)
	if !ok {
		writeError(w, http.StatusBadRequest, "Invalid destination", "INVALID_PATH")
		return
	}
	if info, err := os.Stat(destParent); err != nil || !info.IsDir() {
		writeError(w, http.StatusNotFound, "Destination directory not found", "DEST_NOT_FOUND")
		return
	}

	newLocation := filepath.Join(destParent, filepath.Base(source))
	if _, err := os.Stat(newLocation); err == nil {
		writeError(w, http.StatusConflict, "An item with that name already exists in the destination", "NAME_EXISTS")
		return
	}
	if info, err := os.Stat(source); err == nil && info.IsDir() && underRoot(newLocation, source) {
		writeError(w, http.StatusBadRequest, "Cannot move a directory into itself", "INVALID_MOVE")
		return
	}

	if err := os.Rename(source, newLocation); err != nil {
		writeError(w, http.StatusInternalServerError, err.Error(), "MOVE_ERROR")
		return
	}

	newRel := filepath.Base(source)
	if destDir != "" {
		newRel = filepath.ToSlash(filepath.Join(destDir, filepath.Base(source)))
	}
	s.logAudit(r, "file.move", audit.Entry{
		TargetType:  "file",
		TargetID:    srcPath,
		Description: fmt.Sprintf("Moved %s to %s", srcPath, newRel),
	})
	writeProto(w, http.StatusOK, &pb.MoveFileResponse{Success: true, NewPath: newRel})
}

// -- Guest endpoints ------------------------------------------------------------

func (s *Server) handleGuestListFiles(w http.ResponseWriter, r *http.Request) {
	path := r.URL.Query().Get("path")
	search := strings.TrimSpace(r.URL.Query().Get("search"))

	_ = os.MkdirAll(s.cfg.GuestRoot(), 0o755)
	files := listDirectory(s.cfg.GuestRoot(), path)

	writeProto(w, http.StatusOK, &pb.ListFilesResponse{
		Files:       filterSearch(files, search),
		CurrentPath: currentPathOf(path),
		ParentPath:  parentPathOf(path),
	})
}

func (s *Server) handleGuestDownloadFile(w http.ResponseWriter, r *http.Request) {
	path := r.URL.Query().Get("path")
	if path == "" {
		writeError(w, http.StatusBadRequest, "Path required", "MISSING_PATH")
		return
	}
	filePath, ok := resolveExistingFile(s.cfg.GuestRoot(), path)
	if ok {
		if info, err := os.Stat(filePath); err != nil || info.IsDir() {
			ok = false
		}
	}
	if !ok {
		writeError(w, http.StatusNotFound, "File not found", "FILE_NOT_FOUND")
		return
	}

	s.logAudit(r, "file.guest_download", audit.Entry{
		TargetType:  "file",
		TargetID:    path,
		Description: fmt.Sprintf("Guest downloaded %s", path),
	})
	sendFile(w, r, filePath, true)
}
