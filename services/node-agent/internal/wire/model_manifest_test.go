package wire

import (
	"encoding/json"
	"os"
	"path/filepath"
	"testing"

	contracts "github.com/egparadise/SaintVision-Invion/packages/contracts-go"
)

func modelManifestFixture(t *testing.T) []byte {
	t.Helper()
	raw, err := os.ReadFile(filepath.Join(
		"..", "..", "..", "..", "contracts", "fixtures",
		"model-execution-manifest-observation.json",
	))
	if err != nil {
		t.Fatal(err)
	}
	return raw
}

func TestDecodeModelExecutionManifestConsumesResolverWireContract(t *testing.T) {
	raw := modelManifestFixture(t)
	result, err := DecodeModelExecutionManifest(
		raw,
		contracts.ProjectId("prj_01ARZ3NDEKTSV4RRFFQ69G5FAV"),
		contracts.ModelId("mdl_01ARZ3NDEKTSV4RRFFQ69G5FAV"),
		"1.0.0",
		"1111111111111111111111111111111111111111111111111111111111111111",
	)
	if err != nil {
		t.Fatal(err)
	}
	if result.ManifestHash != "1111111111111111111111111111111111111111111111111111111111111111" {
		t.Fatal("manifest hash changed across the resolver/node-agent boundary")
	}
	if len(result.Shards) != 1 || len(result.ShardLocations) != 1 ||
		len(result.ShardLocations[0].ReadyNodes) != 1 || !result.Materialisable {
		t.Fatal("strict shard/location readiness projection was not consumed")
	}
	if result.ExecutionAuthorized || !result.RequiresExecutionRevalidation {
		t.Fatal("resolver observation was promoted to execution authority")
	}
}

func TestDecodeModelExecutionManifestRejectsScopeAndAuthorityDrift(t *testing.T) {
	raw := modelManifestFixture(t)
	if _, err := DecodeModelExecutionManifest(
		raw,
		contracts.ProjectId("prj_01ARZ3NDEKTSV4RRFFQ69G5FAA"),
		contracts.ModelId("mdl_01ARZ3NDEKTSV4RRFFQ69G5FAV"),
		"1.0.0",
		"1111111111111111111111111111111111111111111111111111111111111111",
	); err == nil {
		t.Fatal("project identity drift was accepted")
	}
	if _, err := DecodeModelExecutionManifest(
		raw,
		contracts.ProjectId("prj_01ARZ3NDEKTSV4RRFFQ69G5FAV"),
		contracts.ModelId("mdl_01ARZ3NDEKTSV4RRFFQ69G5FAV"),
		"1.0.0",
		"3333333333333333333333333333333333333333333333333333333333333333",
	); err == nil {
		t.Fatal("manifest hash drift was accepted")
	}

	var changed map[string]any
	if err := json.Unmarshal(raw, &changed); err != nil {
		t.Fatal(err)
	}
	changed["executionAuthorized"] = true
	corrupt, err := json.Marshal(changed)
	if err != nil {
		t.Fatal(err)
	}
	if _, err := DecodeModelExecutionManifest(
		corrupt,
		contracts.ProjectId("prj_01ARZ3NDEKTSV4RRFFQ69G5FAV"),
		contracts.ModelId("mdl_01ARZ3NDEKTSV4RRFFQ69G5FAV"),
		"1.0.0",
		"1111111111111111111111111111111111111111111111111111111111111111",
	); err == nil {
		t.Fatal("execution authority drift was accepted")
	}
}
