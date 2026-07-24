package perms

import "testing"

func sp(s string) *string { return &s }

// Mirrors tests/test_permissions.py::TestResolvePermissions.

func TestNoPermissionsReturnsEmpty(t *testing.T) {
	got := Resolve(nil, nil, nil)
	if len(got) != 0 {
		t.Fatalf("expected empty map, got %v", got)
	}
}

func TestDomainOnly(t *testing.T) {
	got := Resolve([]BoolPerm{{Path: "/docs", Read: true, Write: false}}, nil, nil)
	e, ok := got["/docs"]
	if !ok {
		t.Fatal("missing /docs entry")
	}
	if !e.CanRead || e.CanWrite || e.Source != "domain" {
		t.Fatalf("unexpected entry: %+v", e)
	}
}

func TestGroupOverridesDomain(t *testing.T) {
	domain := []BoolPerm{{Path: "/docs", Read: true, Write: false}}
	groups := []GroupPerms{{GroupID: 1, GroupName: "g", Perms: []BoolPerm{{Path: "/docs", Read: true, Write: true}}}}
	got := Resolve(domain, groups, nil)
	e := got["/docs"]
	if !e.CanRead || !e.CanWrite || e.Source != "group" {
		t.Fatalf("group should override domain: %+v", e)
	}
}

func TestMultiGroupMostPermissive(t *testing.T) {
	groups := []GroupPerms{
		{GroupID: 1, GroupName: "a", Perms: []BoolPerm{{Path: "/shared", Read: true, Write: false}}},
		{GroupID: 2, GroupName: "b", Perms: []BoolPerm{{Path: "/shared", Read: false, Write: true}}},
	}
	e := Resolve(nil, groups, nil)["/shared"]
	if !e.CanRead || !e.CanWrite {
		t.Fatalf("OR across groups failed: %+v", e)
	}
}

func TestUserOverridesGroup(t *testing.T) {
	groups := []GroupPerms{{GroupID: 1, GroupName: "g", Perms: []BoolPerm{{Path: "/docs", Read: true, Write: true}}}}
	user := []TriPerm{{Path: "/docs", Read: sp("deny"), Write: sp("deny")}}
	e := Resolve(nil, groups, user)["/docs"]
	if e.CanRead || e.CanWrite || e.Source != "user" {
		t.Fatalf("user deny should override group: %+v", e)
	}
}

func TestFullThreeLayerStack(t *testing.T) {
	domain := []BoolPerm{{Path: "/docs", Read: true, Write: false}}
	groups := []GroupPerms{{GroupID: 1, GroupName: "g", Perms: []BoolPerm{{Path: "/docs", Read: true, Write: true}}}}
	user := []TriPerm{{Path: "/docs", Read: sp("allow"), Write: sp("deny")}}
	e := Resolve(domain, groups, user)["/docs"]
	if !e.CanRead || e.CanWrite || e.Source != "user" {
		t.Fatalf("three-layer resolution wrong: %+v", e)
	}
}

func TestAdditivePathsAcrossTiers(t *testing.T) {
	domain := []BoolPerm{{Path: "/a", Read: true}}
	groups := []GroupPerms{{GroupID: 1, GroupName: "g", Perms: []BoolPerm{{Path: "/b", Read: true}}}}
	user := []TriPerm{{Path: "/c", Read: sp("allow")}}
	got := Resolve(domain, groups, user)
	if len(got) != 3 {
		t.Fatalf("expected 3 paths, got %v", got)
	}
	for path, wantSource := range map[string]string{"/a": "domain", "/b": "group", "/c": "user"} {
		if got[path].Source != wantSource {
			t.Errorf("%s: source = %q, want %q", path, got[path].Source, wantSource)
		}
	}
}

func TestUserNilDefersToGroup(t *testing.T) {
	groups := []GroupPerms{{GroupID: 1, GroupName: "g", Perms: []BoolPerm{{Path: "/docs", Read: true, Write: true}}}}
	user := []TriPerm{{Path: "/docs", Read: nil, Write: sp("deny")}}
	e := Resolve(nil, groups, user)["/docs"]
	if !e.CanRead || e.CanWrite {
		t.Fatalf("nil read should fall through to group allow: %+v", e)
	}
}

func TestUserAllNilKeepsBaseSource(t *testing.T) {
	domain := []BoolPerm{{Path: "/docs", Read: true, Write: false}}
	user := []TriPerm{{Path: "/docs"}}
	e := Resolve(domain, nil, user)["/docs"]
	if e.Source != "domain" || !e.CanRead || e.CanWrite {
		t.Fatalf("all-nil user row must be a no-op: %+v", e)
	}
}

// Mirrors TestCheckAccess.

func TestCheckAccessNoPermsDeniesEverything(t *testing.T) {
	if CheckAccess(map[string]Effective{}, "/anything", false) {
		t.Fatal("empty effective set must deny")
	}
}

func TestCheckAccessReadAllowedWriteDenied(t *testing.T) {
	eff := Resolve(nil, nil, []TriPerm{{Path: "/docs", Read: sp("allow")}})
	if !CheckAccess(eff, "/docs", false) {
		t.Fatal("read should be allowed")
	}
	if CheckAccess(eff, "/docs", true) {
		t.Fatal("write should be denied")
	}
}

func TestCheckAccessCoversChildren(t *testing.T) {
	eff := Resolve(nil, nil, []TriPerm{{Path: "/docs", Read: sp("allow")}})
	if !CheckAccess(eff, "/docs/sub/deep", false) {
		t.Fatal("permission on /docs must cover /docs/sub/deep")
	}
}

func TestCheckAccessLongestPrefixMatch(t *testing.T) {
	eff := Resolve(nil, nil, []TriPerm{
		{Path: "/docs", Read: sp("allow"), Write: sp("allow")},
		{Path: "/docs/secret", Read: sp("deny"), Write: sp("deny")},
	})
	if !CheckAccess(eff, "/docs/public", false) {
		t.Fatal("/docs/public should inherit /docs allow")
	}
	if CheckAccess(eff, "/docs/secret", false) {
		t.Fatal("/docs/secret must use the more specific deny")
	}
	if CheckAccess(eff, "/docs/secret/inner", false) {
		t.Fatal("children of the deny must also be denied")
	}
}

func TestCheckAccessUncoveredPathDenied(t *testing.T) {
	eff := Resolve(nil, nil, []TriPerm{{Path: "/docs", Read: sp("allow")}})
	if CheckAccess(eff, "/other", false) {
		t.Fatal("uncovered path must be denied")
	}
	// A sibling with a shared name prefix must not match (/docs vs /docs2).
	if CheckAccess(eff, "/docs2", false) {
		t.Fatal("/docs2 must not match the /docs grant")
	}
}

// Mirrors test_item_visibility_filtering.

func TestItemVisibilityFiltering(t *testing.T) {
	granted := map[string]bool{"/docs/sub": true}

	if !IsItemVisible("/docs", true, granted) {
		t.Fatal("/docs is on the path toward /docs/sub and must be visible")
	}
	if !IsItemVisible("/docs/sub", true, granted) {
		t.Fatal("granted folder itself must be visible")
	}
	if !IsItemVisible("/docs/sub/file.txt", false, granted) {
		t.Fatal("items inside the grant must be visible")
	}
	if IsItemVisible("/other", true, granted) {
		t.Fatal("unrelated folder must be hidden")
	}
	if IsItemVisible("/docs/file.txt", false, granted) {
		t.Fatal("a file outside the grant must be hidden even inside a visible folder")
	}
}

func TestVisiblePathsOnlyReadGrants(t *testing.T) {
	eff := Resolve(nil, nil, []TriPerm{
		{Path: "/a", Read: sp("allow")},
		{Path: "/b", Write: sp("allow")}, // write-only: not visible
		{Path: "/c", Read: sp("deny")},
	})
	granted := VisiblePaths(eff)
	if !granted["/a"] || granted["/b"] || granted["/c"] {
		t.Fatalf("unexpected visible set: %v", granted)
	}
}

func TestNormalisePath(t *testing.T) {
	cases := map[string]string{
		"docs":     "/docs",
		"/docs/":   "/docs",
		"//docs//": "/docs",
		"/":        "/",
		"":         "/",
		"/a/b/":    "/a/b",
		"a/b":      "/a/b",
	}
	for in, want := range cases {
		if got := NormalisePath(in); got != want {
			t.Errorf("NormalisePath(%q) = %q, want %q", in, got, want)
		}
	}
}

// Mirrors TestResolvePermissionsDetailed::test_shows_all_sources.

func TestResolveDetailedShowsAllSources(t *testing.T) {
	domain := []BoolPerm{{Path: "/docs", Read: true, Write: false}}
	groups := []GroupPerms{{GroupID: 7, GroupName: "editors", Perms: []BoolPerm{{Path: "/docs", Read: true, Write: true}}}}
	user := []TriPerm{{Path: "/docs", Write: sp("deny")}}

	entry := ResolveDetailed(domain, groups, user)["/docs"]
	if entry == nil {
		t.Fatal("missing /docs breakdown")
	}
	if entry.Domain == nil || !entry.Domain.CanRead || entry.Domain.CanWrite {
		t.Fatalf("domain tier wrong: %+v", entry.Domain)
	}
	if len(entry.Groups) != 1 || entry.Groups[0].GroupName != "editors" {
		t.Fatalf("group tier wrong: %+v", entry.Groups)
	}
	if entry.GroupMerged == nil || !entry.GroupMerged.CanWrite {
		t.Fatalf("merged group tier wrong: %+v", entry.GroupMerged)
	}
	if entry.User == nil || entry.User.CanRead != nil || entry.User.CanWrite == nil {
		t.Fatalf("user tier wrong: %+v", entry.User)
	}
	// Effective: read falls through to group allow, write denied by user.
	if !entry.Effective.CanRead || entry.Effective.CanWrite || entry.Effective.Source != "user" {
		t.Fatalf("effective wrong: %+v", entry.Effective)
	}
}

func TestResolveDetailedGroupsAlwaysPresent(t *testing.T) {
	entry := ResolveDetailed([]BoolPerm{{Path: "/docs", Read: true}}, nil, nil)["/docs"]
	if entry.Groups == nil || len(entry.Groups) != 0 {
		t.Fatalf("groups must be an empty (non-nil) slice: %#v", entry.Groups)
	}
	if entry.Effective.Source != "domain" {
		t.Fatalf("effective source = %q, want domain", entry.Effective.Source)
	}
}
