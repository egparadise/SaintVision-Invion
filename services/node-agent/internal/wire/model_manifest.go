package wire

import (
	"encoding/json"
	"errors"

	contracts "github.com/egparadise/SaintVision-Invion/packages/contracts-go"
)

var errModelManifestScope = errors.New("NODE-0070: model manifest scope or authority differs")

// DecodeModelExecutionManifest is the node-agent boundary for the resolver's
// strict observation. It validates the embedded canonical schema before using
// generated Go types and binds the response to the identity and immutable hash
// the caller requested. The observation is availability input only; it never
// authorizes execution and must retain the execution revalidation flag.
func DecodeModelExecutionManifest(
	raw []byte,
	projectID contracts.ProjectId,
	modelID contracts.ModelId,
	version string,
	manifestHash string,
) (contracts.ModelExecutionManifestObservation, error) {
	var result contracts.ModelExecutionManifestObservation
	if err := Validate("ModelExecutionManifestObservation", raw); err != nil {
		return result, err
	}
	if err := json.Unmarshal(raw, &result); err != nil {
		return contracts.ModelExecutionManifestObservation{}, errors.New("NODE-0003: invalid JSON")
	}
	if result.ProjectId != projectID || result.ModelId != modelID ||
		result.Version != version || result.ManifestHash != manifestHash ||
		result.ExecutionAuthorized || !result.RequiresExecutionRevalidation {
		return contracts.ModelExecutionManifestObservation{}, errModelManifestScope
	}
	return result, nil
}
