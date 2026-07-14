package httpapi

import (
	"net/http"
	"net/http/httptest"
	"regexp"
	"strings"
	"testing"

	"google.golang.org/genproto/googleapis/api/annotations"
	"google.golang.org/protobuf/proto"
	"google.golang.org/protobuf/reflect/protoreflect"
	"google.golang.org/protobuf/reflect/protoregistry"

	_ "github.com/andreas-04/terra-crate/backend/gen/terracrate/v1"
)

var pathParamRe = regexp.MustCompile(`\{[^}]+\}`)

// TestEveryProtoRouteIsServed walks the google.api.http annotations in the
// terracrate.v1 service definitions (the API's source of truth) and verifies
// the mux actually serves each method+path. This pins the hand-written route
// table to the protos.
func TestEveryProtoRouteIsServed(t *testing.T) {
	srv := newTestServer(t)
	handler := srv.Handler()

	type route struct{ method, path, rpc string }
	var routes []route

	protoregistry.GlobalFiles.RangeFiles(func(fd protoreflect.FileDescriptor) bool {
		if fd.Package() != "terracrate.v1" {
			return true
		}
		for i := 0; i < fd.Services().Len(); i++ {
			svc := fd.Services().Get(i)
			for j := 0; j < svc.Methods().Len(); j++ {
				m := svc.Methods().Get(j)
				rule, ok := proto.GetExtension(m.Options(), annotations.E_Http).(*annotations.HttpRule)
				if !ok || rule == nil {
					continue
				}
				var method, path string
				switch p := rule.Pattern.(type) {
				case *annotations.HttpRule_Get:
					method, path = http.MethodGet, p.Get
				case *annotations.HttpRule_Post:
					method, path = http.MethodPost, p.Post
				case *annotations.HttpRule_Put:
					method, path = http.MethodPut, p.Put
				case *annotations.HttpRule_Delete:
					method, path = http.MethodDelete, p.Delete
				case *annotations.HttpRule_Patch:
					method, path = http.MethodPatch, p.Patch
				}
				if path != "" {
					routes = append(routes, route{method, path, string(m.FullName())})
				}
			}
		}
		return true
	})

	if len(routes) < 40 {
		t.Fatalf("expected the full API surface (>=40 annotated RPCs), found %d", len(routes))
	}

	for _, rt := range routes {
		concrete := pathParamRe.ReplaceAllString(rt.path, "1")
		req := httptest.NewRequest(rt.method, concrete, strings.NewReader("{}"))
		rec := httptest.NewRecorder()
		handler.ServeHTTP(rec, req)

		// The mux default handlers answer 404 "page not found" / 405; any
		// registered handler produces a JSON API response instead.
		if rec.Code == http.StatusMethodNotAllowed ||
			(rec.Code == http.StatusNotFound && !strings.Contains(rec.Header().Get("Content-Type"), "json")) {
			t.Errorf("%s: %s %s is not served by the mux (status %d)", rt.rpc, rt.method, rt.path, rec.Code)
		}
	}
}
