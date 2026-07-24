package auth

import (
	"net/http"
	"strings"
	"testing"
)

func TestHashAndVerifyPassword(t *testing.T) {
	hash, err := HashPassword("s3cret-pw")
	if err != nil {
		t.Fatal(err)
	}
	if !strings.HasPrefix(hash, "$argon2id$v=19$") {
		t.Fatalf("not an argon2id PHC hash: %s", hash)
	}
	if !VerifyPassword("s3cret-pw", hash) {
		t.Fatal("correct password rejected")
	}
	if VerifyPassword("wrong", hash) {
		t.Fatal("wrong password accepted")
	}
	for _, junk := range []string{"", "not-a-hash", "$argon2id$v=19$m=x$..$..", "$bcrypt$whatever"} {
		if VerifyPassword("s3cret-pw", junk) {
			t.Fatalf("junk hash %q verified", junk)
		}
	}
}

func TestHashPasswordSaltsDiffer(t *testing.T) {
	a, _ := HashPassword("same")
	b, _ := HashPassword("same")
	if a == b {
		t.Fatal("two hashes of the same password must differ (random salt)")
	}
}

func TestNewTokenAndHash(t *testing.T) {
	plain, hash, err := NewToken()
	if err != nil {
		t.Fatal(err)
	}
	if len(plain) < 40 {
		t.Fatalf("token too short: %q", plain)
	}
	if HashToken(plain) != hash {
		t.Fatal("HashToken(plain) must equal the returned hash")
	}
	if plain == hash {
		t.Fatal("stored hash must not equal the plaintext token")
	}

	plain2, hash2, _ := NewToken()
	if plain == plain2 || hash == hash2 {
		t.Fatal("tokens must be unique")
	}
}

func TestTokenFromRequest(t *testing.T) {
	r, _ := http.NewRequest("GET", "/api/v1/files?token=legacyquery", nil)
	r.AddCookie(&http.Cookie{Name: "auth_token", Value: "legacycookie"})
	// Cookies and query parameters are not accepted.
	if got := TokenFromRequest(r); got != "" {
		t.Fatalf("expected empty token, got %q", got)
	}
	r.Header.Set("Authorization", "Bearer frombearer")
	if got := TokenFromRequest(r); got != "frombearer" {
		t.Fatalf("bearer: got %q", got)
	}
}
