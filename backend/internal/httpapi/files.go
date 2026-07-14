package httpapi

import (
	"os"
	"path/filepath"
	"regexp"
	"sort"
	"strings"
	"unicode"

	"golang.org/x/text/unicode/norm"
	"google.golang.org/protobuf/types/known/timestamppb"

	pb "github.com/andreas-04/terra-crate/backend/gen/terracrate/v1"
)

var filenameStripRe = regexp.MustCompile(`[^A-Za-z0-9_.-]`)

// secureFilename ports werkzeug.utils.secure_filename: NFKD-normalise to
// ASCII, turn path separators into spaces, join runs of whitespace with '_',
// drop everything outside [A-Za-z0-9_.-], and trim leading/trailing '.'/'_'.
func secureFilename(filename string) string {
	normalized := norm.NFKD.String(filename)
	ascii := make([]rune, 0, len(normalized))
	for _, r := range normalized {
		if r < 128 {
			ascii = append(ascii, r)
		}
	}
	s := string(ascii)
	s = strings.ReplaceAll(s, "/", " ")
	s = strings.ReplaceAll(s, "\\", " ")
	s = strings.Join(strings.FieldsFunc(s, unicode.IsSpace), "_")
	s = filenameStripRe.ReplaceAllString(s, "")
	return strings.Trim(s, "._")
}

// underRoot reports whether candidate is base itself or inside it.
func underRoot(candidate, base string) bool {
	return candidate == base || strings.HasPrefix(candidate, base+string(filepath.Separator))
}

// resolveUnder joins rel onto base and verifies the result stays inside base
// (directory-traversal guard). Symlinks are resolved when the path exists.
func resolveUnder(base, rel string) (string, bool) {
	absBase, err := filepath.Abs(base)
	if err != nil {
		return "", false
	}
	if resolved, err := filepath.EvalSymlinks(absBase); err == nil {
		absBase = resolved
	}
	candidate := filepath.Clean(filepath.Join(absBase, rel))
	if resolved, err := filepath.EvalSymlinks(candidate); err == nil {
		candidate = resolved
	}
	return candidate, underRoot(candidate, absBase)
}

// resolveExistingFile resolves a virtual path to a real one under base;
// nil-equivalent ("", false) when it escapes the root or doesn't exist.
func resolveExistingFile(base, rel string) (string, bool) {
	candidate, ok := resolveUnder(base, rel)
	if !ok {
		return "", false
	}
	if _, err := os.Stat(candidate); err != nil {
		return "", false
	}
	return candidate, true
}

// listDirectory returns one level of directory entries; hidden files and
// broken symlinks are skipped.
func listDirectory(basePath, path string) []*pb.FileItem {
	full, ok := resolveUnder(basePath, path)
	if !ok {
		return []*pb.FileItem{}
	}
	entries, err := os.ReadDir(full)
	if err != nil {
		return []*pb.FileItem{}
	}

	items := []*pb.FileItem{}
	for _, entry := range entries {
		name := entry.Name()
		if strings.HasPrefix(name, ".") {
			continue
		}
		itemPath := filepath.Join(full, name)
		info, err := os.Stat(itemPath) // follows symlinks; fails for broken ones
		if err != nil {
			continue
		}

		relPath := name
		if path != "" {
			relPath = filepath.ToSlash(filepath.Join(path, name))
		}
		itemType := "file"
		var size int64
		if info.IsDir() {
			itemType = "folder"
		} else {
			size = info.Size()
		}
		parentPath := "/"
		if path != "" {
			parentPath = "/" + path
		}
		items = append(items, &pb.FileItem{
			Id:         relPath,
			Name:       name,
			Path:       relPath,
			Type:       itemType,
			Size:       size,
			ModifiedAt: timestamppb.New(info.ModTime()),
			ParentPath: parentPath,
		})
	}

	// Folders first, then case-insensitive by name.
	sort.SliceStable(items, func(i, j int) bool {
		fi, fj := items[i].Type != "folder", items[j].Type != "folder"
		if fi != fj {
			return !fi
		}
		return strings.ToLower(items[i].Name) < strings.ToLower(items[j].Name)
	})
	return items
}

// parentPathOf returns the virtual parent of a listing path: nil for the
// root, "/" for top-level entries, "/<dir>" otherwise.
func parentPathOf(path string) *string {
	if path == "" || path == "." {
		return nil
	}
	parent := "/"
	if dir := filepath.ToSlash(filepath.Dir(path)); dir != "." {
		parent = "/" + dir
	}
	return &parent
}

// filterSearch applies the case-insensitive name filter.
func filterSearch(items []*pb.FileItem, search string) []*pb.FileItem {
	if search == "" {
		return items
	}
	needle := strings.ToLower(search)
	out := []*pb.FileItem{}
	for _, it := range items {
		if strings.Contains(strings.ToLower(it.Name), needle) {
			out = append(out, it)
		}
	}
	return out
}
