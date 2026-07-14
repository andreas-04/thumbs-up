package httpapi

import (
	"encoding/json"
	"io"
	"net/http"

	"google.golang.org/protobuf/encoding/protojson"
	"google.golang.org/protobuf/proto"

	pb "github.com/andreas-04/terra-crate/backend/gen/terracrate/v1"
)

// marshalOpts renders responses with the standard proto3 JSON mapping;
// EmitUnpopulated keeps response shapes stable (zero scalars, empty lists,
// and null message fields are always present).
var marshalOpts = protojson.MarshalOptions{EmitUnpopulated: true}

func writeProto(w http.ResponseWriter, status int, m proto.Message) {
	body, err := marshalOpts.Marshal(m)
	if err != nil {
		http.Error(w, `{"error":"Internal serialization error","code":"INTERNAL_ERROR"}`, http.StatusInternalServerError)
		return
	}
	w.Header().Set("Content-Type", "application/json")
	w.WriteHeader(status)
	w.Write(body)
}

func writeError(w http.ResponseWriter, status int, message, code string) {
	writeProto(w, status, &pb.ErrorResponse{Error: message, Code: code})
}

func writeSuccess(w http.ResponseWriter) {
	writeProto(w, http.StatusOK, &pb.SuccessResponse{Success: true})
}

const maxJSONBody = 1 << 20 // JSON request bodies are small; uploads bypass this.

// readBody returns the raw top-level JSON object, or nil when the body is
// missing or not a JSON object.
func readBody(r *http.Request) map[string]json.RawMessage {
	data, err := io.ReadAll(io.LimitReader(r.Body, maxJSONBody))
	if err != nil || len(data) == 0 {
		return nil
	}
	var raw map[string]json.RawMessage
	if err := json.Unmarshal(data, &raw); err != nil {
		return nil
	}
	return raw
}

// decodeProto decodes raw JSON into a request proto; protojson accepts both
// camelCase and snake_case keys and null for optionals.
func decodeProto(raw map[string]json.RawMessage, m proto.Message) error {
	data, err := json.Marshal(raw)
	if err != nil {
		return err
	}
	return protojson.UnmarshalOptions{DiscardUnknown: true}.Unmarshal(data, m)
}

// bodyInto combines readBody + decodeProto; the map is returned for key
// presence checks. ok is false when the body is absent/invalid.
func bodyInto(r *http.Request, m proto.Message) (map[string]json.RawMessage, bool) {
	raw := readBody(r)
	if raw == nil {
		return nil, false
	}
	if err := decodeProto(raw, m); err != nil {
		return nil, false
	}
	return raw, true
}
