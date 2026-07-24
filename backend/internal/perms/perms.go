// Package perms is the layered folder-permission resolver. Three tiers
// merge into an effective set:
//
//  1. Domain defaults  – from the user's email domain config
//  2. Group permissions – OR across the user's groups; overrides domain
//  3. User overrides   – tri-state per flag: "allow"/"deny" override the
//     lower tiers, nil defers to them
//
// Permissions are additive: with no configuration a user has no access.
// Admins bypass the resolver entirely (checked by callers).
package perms

import "strings"

// BoolPerm is a boolean folder grant (domain or group tier).
type BoolPerm struct {
	Path  string
	Read  bool
	Write bool
}

// GroupPerms is one group's grants, tagged for source attribution.
type GroupPerms struct {
	GroupID   int
	GroupName string
	Perms     []BoolPerm
}

// TriPerm is a user-tier override; nil flags defer to lower tiers.
type TriPerm struct {
	Path  string
	Read  *string // "allow", "deny", or nil
	Write *string
}

// Effective is the resolved outcome at one path.
type Effective struct {
	CanRead  bool
	CanWrite bool
	Source   string // "domain", "group", "user", or "none"
}

// NormalisePath ensures a leading '/' and no trailing slash ("/" stays "/").
func NormalisePath(path string) string {
	n := "/" + strings.Trim(path, "/")
	return n
}

func triToBool(v *string, fallback bool) bool {
	switch {
	case v == nil:
		return fallback
	case *v == "allow":
		return true
	case *v == "deny":
		return false
	default:
		return fallback
	}
}

// Resolve merges the three tiers into a map keyed by normalised path. An
// empty map means nothing is configured at any tier.
func Resolve(domain []BoolPerm, groups []GroupPerms, user []TriPerm) map[string]Effective {
	effective := map[string]Effective{}

	// Tier 1: domain defaults.
	for _, dp := range domain {
		p := NormalisePath(dp.Path)
		effective[p] = Effective{CanRead: dp.Read, CanWrite: dp.Write, Source: "domain"}
	}

	// Tier 2: OR across groups, then override domain at the same path.
	merged := map[string]BoolPerm{}
	for _, grp := range groups {
		for _, gp := range grp.Perms {
			p := NormalisePath(gp.Path)
			m := merged[p]
			m.Read = m.Read || gp.Read
			m.Write = m.Write || gp.Write
			merged[p] = m
		}
	}
	for p, flags := range merged {
		effective[p] = Effective{CanRead: flags.Read, CanWrite: flags.Write, Source: "group"}
	}

	// Tier 3: user tri-state overrides with fall-through on nil.
	for _, up := range user {
		p := NormalisePath(up.Path)
		base, ok := effective[p]
		if !ok {
			base = Effective{Source: "none"}
		}
		source := base.Source
		if up.Read != nil || up.Write != nil {
			source = "user"
		}
		effective[p] = Effective{
			CanRead:  triToBool(up.Read, base.CanRead),
			CanWrite: triToBool(up.Write, base.CanWrite),
			Source:   source,
		}
	}

	return effective
}

// CheckAccess reports whether the effective set grants access to folderPath.
// A grant on /docs covers /docs and all of its children; the most specific
// (longest) covering path wins.
func CheckAccess(effective map[string]Effective, folderPath string, requireWrite bool) bool {
	if len(effective) == 0 {
		return false
	}
	normalised := NormalisePath(folderPath)

	bestLen := -1
	var best Effective
	for permPath, entry := range effective {
		if normalised == permPath || strings.HasPrefix(normalised, permPath+"/") {
			if len(permPath) > bestLen {
				bestLen = len(permPath)
				best = entry
			}
		}
	}
	if bestLen < 0 {
		return false
	}
	if requireWrite {
		return best.CanWrite
	}
	return best.CanRead
}

// VisiblePaths returns the set of paths with read access.
func VisiblePaths(effective map[string]Effective) map[string]bool {
	granted := map[string]bool{}
	for p, e := range effective {
		if e.CanRead {
			granted[p] = true
		}
	}
	return granted
}

// IsItemVisible decides whether a directory entry shows up in a listing:
// items inside a granted folder are visible, and folders on the path toward
// a granted folder are visible so the user can navigate there.
func IsItemVisible(itemPath string, itemIsFolder bool, granted map[string]bool) bool {
	for gp := range granted {
		if itemPath == gp || strings.HasPrefix(itemPath, gp+"/") {
			return true
		}
		if itemIsFolder && strings.HasPrefix(gp, itemPath+"/") {
			return true
		}
	}
	return false
}

// -- Detailed breakdown for the admin UI --------------------------------------

// TierFlags is a resolved (boolean) tier entry.
type TierFlags struct {
	CanRead  bool
	CanWrite bool
}

// GroupTierEntry is one group's contribution at a path.
type GroupTierEntry struct {
	GroupID   int
	GroupName string
	CanRead   bool
	CanWrite  bool
}

// UserTierFlags carries the raw tri-state strings.
type UserTierFlags struct {
	CanRead  *string
	CanWrite *string
}

// DetailedEntry is the per-path breakdown with source attribution.
type DetailedEntry struct {
	Domain      *TierFlags
	Groups      []GroupTierEntry
	GroupMerged *TierFlags
	User        *UserTierFlags
	Effective   Effective
}

// ResolveDetailed returns the per-path tier breakdown used by
// GET /users/{id}/effective-permissions.
func ResolveDetailed(domain []BoolPerm, groups []GroupPerms, user []TriPerm) map[string]*DetailedEntry {
	domainMap := map[string]*TierFlags{}
	groupsMap := map[string][]GroupTierEntry{}
	groupMergedMap := map[string]*TierFlags{}
	userMap := map[string]*UserTierFlags{}
	allPaths := map[string]bool{}

	for _, dp := range domain {
		p := NormalisePath(dp.Path)
		allPaths[p] = true
		domainMap[p] = &TierFlags{CanRead: dp.Read, CanWrite: dp.Write}
	}
	for _, grp := range groups {
		for _, gp := range grp.Perms {
			p := NormalisePath(gp.Path)
			allPaths[p] = true
			groupsMap[p] = append(groupsMap[p], GroupTierEntry{
				GroupID:   grp.GroupID,
				GroupName: grp.GroupName,
				CanRead:   gp.Read,
				CanWrite:  gp.Write,
			})
		}
	}
	for p, entries := range groupsMap {
		m := &TierFlags{}
		for _, g := range entries {
			m.CanRead = m.CanRead || g.CanRead
			m.CanWrite = m.CanWrite || g.CanWrite
		}
		groupMergedMap[p] = m
	}
	for _, up := range user {
		p := NormalisePath(up.Path)
		allPaths[p] = true
		userMap[p] = &UserTierFlags{CanRead: up.Read, CanWrite: up.Write}
	}

	result := map[string]*DetailedEntry{}
	for p := range allPaths {
		var eff Effective
		switch {
		case userMap[p] != nil:
			var baseRead, baseWrite bool
			if gm := groupMergedMap[p]; gm != nil {
				baseRead, baseWrite = gm.CanRead, gm.CanWrite
			} else if dm := domainMap[p]; dm != nil {
				baseRead, baseWrite = dm.CanRead, dm.CanWrite
			}
			source := "none"
			if userMap[p].CanRead != nil || userMap[p].CanWrite != nil {
				source = "user"
			} else if groupMergedMap[p] != nil {
				source = "group"
			} else if domainMap[p] != nil {
				source = "domain"
			}
			eff = Effective{
				CanRead:  triToBool(userMap[p].CanRead, baseRead),
				CanWrite: triToBool(userMap[p].CanWrite, baseWrite),
				Source:   source,
			}
		case groupMergedMap[p] != nil:
			eff = Effective{CanRead: groupMergedMap[p].CanRead, CanWrite: groupMergedMap[p].CanWrite, Source: "group"}
		case domainMap[p] != nil:
			eff = Effective{CanRead: domainMap[p].CanRead, CanWrite: domainMap[p].CanWrite, Source: "domain"}
		default:
			eff = Effective{Source: "none"}
		}

		groupEntries := groupsMap[p]
		if groupEntries == nil {
			groupEntries = []GroupTierEntry{}
		}
		result[p] = &DetailedEntry{
			Domain:      domainMap[p],
			Groups:      groupEntries,
			GroupMerged: groupMergedMap[p],
			User:        userMap[p],
			Effective:   eff,
		}
	}
	return result
}
