package httpapi

import (
	"os"
	"path/filepath"
	"testing"
)

// Cases chosen to match werkzeug.utils.secure_filename outputs.
func TestSecureFilename(t *testing.T) {
	cases := map[string]string{
		"My cool movie.mov":          "My_cool_movie.mov",
		"../../../etc/passwd":        "etc_passwd",
		"i contain cool ümläuts.txt": "i_contain_cool_umlauts.txt",
		"..hidden":                   "hidden",
		"normal.txt":                 "normal.txt",
		"a/b\\c.txt":                 "a_b_c.txt",
		"___":                        "",
	}
	for in, want := range cases {
		if got := secureFilename(in); got != want {
			t.Errorf("secureFilename(%q) = %q, want %q", in, got, want)
		}
	}
}

// Mirrors tests/test_utils.py::TestGetFileList / TestResolveFilePath.

func TestListDirectory(t *testing.T) {
	root := t.TempDir()
	mustWrite(t, filepath.Join(root, "b.txt"), "hello")
	mustWrite(t, filepath.Join(root, "A.txt"), "hi")
	mustWrite(t, filepath.Join(root, ".hidden"), "x")
	mustWrite(t, filepath.Join(root, "._DSStoreish"), "x")
	if err := os.MkdirAll(filepath.Join(root, "zfolder"), 0o755); err != nil {
		t.Fatal(err)
	}

	items := listDirectory(root, "")
	if len(items) != 3 {
		t.Fatalf("expected 3 visible items, got %d", len(items))
	}
	// Folders first, then case-insensitive name order.
	if items[0].Name != "zfolder" || items[0].Type != "folder" {
		t.Fatalf("folder must sort first: %+v", items[0])
	}
	if items[1].Name != "A.txt" || items[2].Name != "b.txt" {
		t.Fatalf("case-insensitive sort broken: %s, %s", items[1].Name, items[2].Name)
	}
	if items[2].Size != 5 {
		t.Fatalf("size = %d, want 5", items[2].Size)
	}
	if items[0].Size != 0 {
		t.Fatal("folder size must be 0")
	}
	// Legacy field shape.
	if items[1].Id != "A.txt" || items[1].Path != "A.txt" || items[1].ParentPath != "/" || items[1].ModifiedAt == nil {
		t.Fatalf("item shape wrong: %+v", items[1])
	}
}

func TestListDirectorySubpathAndTraversal(t *testing.T) {
	root := t.TempDir()
	mustWrite(t, filepath.Join(root, "docs", "file.txt"), "x")
	mustWrite(t, filepath.Join(filepath.Dir(root), "outside.txt"), "secret")

	items := listDirectory(root, "docs")
	if len(items) != 1 || items[0].Path != "docs/file.txt" || items[0].ParentPath != "/docs" {
		t.Fatalf("subdir listing wrong: %+v", items)
	}

	if got := listDirectory(root, "../"); len(got) != 0 {
		t.Fatalf("traversal must return empty, got %+v", got)
	}
	if got := listDirectory(root, "missing"); len(got) != 0 {
		t.Fatalf("nonexistent path must return empty, got %+v", got)
	}
}

func TestResolveExistingFile(t *testing.T) {
	root := t.TempDir()
	mustWrite(t, filepath.Join(root, "docs", "file.txt"), "x")

	if p, ok := resolveExistingFile(root, "docs/file.txt"); !ok || p == "" {
		t.Fatal("existing file not resolved")
	}
	if _, ok := resolveExistingFile(root, "missing.txt"); ok {
		t.Fatal("missing file resolved")
	}
	if _, ok := resolveExistingFile(root, "../../etc/passwd"); ok {
		t.Fatal("traversal escaped the root")
	}
	// A sibling directory sharing the root's name prefix must not pass the
	// containment check.
	sibling := root + "evil"
	mustWrite(t, filepath.Join(sibling, "f.txt"), "x")
	if _, ok := resolveExistingFile(root, "../"+filepath.Base(sibling)+"/f.txt"); ok {
		t.Fatal("prefix-sibling escape allowed")
	}
}

func TestParentPathOf(t *testing.T) {
	if got := parentPathOf(""); got != nil {
		t.Fatalf("root parent = %v, want nil", *got)
	}
	if got := parentPathOf("docs"); got == nil || *got != "/" {
		t.Fatalf("got %v, want /", got)
	}
	if got := parentPathOf("docs/sub"); got == nil || *got != "/docs" {
		t.Fatalf("got %v, want /docs", got)
	}
}

func mustWrite(t *testing.T, path, content string) {
	t.Helper()
	if err := os.MkdirAll(filepath.Dir(path), 0o755); err != nil {
		t.Fatal(err)
	}
	if err := os.WriteFile(path, []byte(content), 0o644); err != nil {
		t.Fatal(err)
	}
}
