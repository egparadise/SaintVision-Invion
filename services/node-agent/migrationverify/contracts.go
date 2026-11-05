package migrationverify

import (
	"encoding/json"
	"errors"
	"fmt"

	"github.com/santhosh-tekuri/jsonschema/v6"
)

type proofSlot struct {
	SlotID           string  `json:"slotId"`
	Artifact         string  `json:"artifact"`
	Method           *string `json:"method"`
	FieldPath        string  `json:"fieldPath"`
	ContractID       string  `json:"contractId"`
	Domain           string  `json:"signatureDomainASCII"`
	Producer         string  `json:"producerRole"`
	Role             string  `json:"signerRole"`
	RequiredVerifier string  `json:"requiredVerifier"`
	Freshness        struct {
		Mode string `json:"mode"`
	} `json:"freshness"`
}
type proofContract struct {
	id, domain, producer, role, codec, mode, hash, schemaHash, verifier, kind string
	schema                                                                    *jsonschema.Schema
	subjectSchema                                                             *jsonschema.Schema
}
type contracts struct {
	slots   map[string]proofSlot
	byID    map[string]*proofContract
	recipes map[string]any
}

func loadContracts() (*contracts, error) {
	c := &contracts{slots: map[string]proofSlot{}, byID: map[string]*proofContract{}}
	raw, e := resources.ReadFile("resources/proof-slot-registry.json")
	if e != nil {
		return nil, e
	}
	var sr struct {
		Entries []proofSlot `json:"entries"`
	}
	if e = json.Unmarshal(raw, &sr); e != nil {
		return nil, e
	}
	for _, s := range sr.Entries {
		if _, ok := c.slots[s.SlotID]; ok {
			return nil, errors.New("duplicate fixed proof slot")
		}
		c.slots[s.SlotID] = s
	}
	if len(c.slots) != 77 {
		return nil, errors.New("incomplete fixed slot registry")
	}
	raw, e = resources.ReadFile("resources/recipe-definitions.json")
	if e != nil {
		return nil, e
	}
	rv, e := ParseJSON(raw)
	if e != nil {
		return nil, e
	}
	rm, e := object(rv)
	if e != nil {
		return nil, e
	}
	c.recipes, e = object(rm["recipes"])
	if e != nil {
		return nil, e
	}
	raw, e = resources.ReadFile("resources/proposed-contracts/index.json")
	if e != nil {
		return nil, e
	}
	var idx struct {
		Contracts []struct {
			ID         string `json:"contractId"`
			File       string `json:"file"`
			Hash       string `json:"rawSHA256"`
			SchemaHash string `json:"schemaSHA256"`
		} `json:"contracts"`
	}
	if e = json.Unmarshal(raw, &idx); e != nil {
		return nil, e
	}
	for _, p := range idx.Contracts {
		b, e := resources.ReadFile("resources/proposed-contracts/" + p.File)
		if e != nil {
			return nil, e
		}
		if shaHex(b) != p.Hash {
			return nil, errors.New("proposal contract pin mismatch")
		}
		v, e := ParseJSON(b)
		if e != nil {
			return nil, e
		}
		m, e := object(v)
		if e != nil {
			return nil, e
		}
		get := func(k string) string { s, _ := m[k].(string); return s }
		pc := &proofContract{id: get("contractId"), domain: get("signatureDomainASCII"), producer: get("producerRole"), role: get("signerRole"), codec: get("codec"), mode: get("freshness"), verifier: get("requiredVerifier"), hash: p.Hash, schemaHash: p.SchemaHash}
		if pc.id != p.ID || pc.codec != "normalized-proof-v1" && pc.codec != "native-m2-v2" {
			return nil, errors.New("invalid fixed codec")
		}
		ss, e := object(m["subjectSchema"])
		if e != nil {
			return nil, e
		}
		pp, e := object(ss["properties"])
		if e != nil {
			return nil, e
		}
		kk, e := object(pp["kind"])
		if e != nil {
			return nil, e
		}
		pc.kind, e = text(kk["const"])
		if e != nil {
			return nil, e
		}
		if (pc.kind == "node-floor-v2") != (pc.codec == "native-m2-v2") {
			return nil, errors.New("cross-codec registration")
		}
		b, e = resources.ReadFile("resources/proposed-contracts/" + get("schemaFile"))
		if e != nil {
			return nil, e
		}
		if shaHex(b) != pc.schemaHash {
			return nil, errors.New("proposal schema pin mismatch")
		}
		sv, e := ParseJSON(b)
		if e != nil {
			return nil, e
		}
		compiler := jsonschema.NewCompiler()
		compiler.DefaultDraft(jsonschema.Draft2020)
		compiler.UseLoader(noResolution{})
		compiler.UseRegexpEngine(pinnedRegexp)
		compiler.AssertFormat()
		id := "https://fleet5-k1-proposal.invalid/" + pc.kind + ".schema.json"
		if e = compiler.AddResource(id, sv); e != nil {
			return nil, e
		}
		pc.schema, e = compiler.Compile(id)
		if e != nil {
			return nil, e
		}
		subID := "https://fleet5-k1-proposal.invalid/" + pc.kind + ".subject.json"
		if e = compiler.AddResource(subID, ss); e != nil {
			return nil, e
		}
		pc.subjectSchema, e = compiler.Compile(subID)
		if e != nil {
			return nil, e
		}
		if _, ok := c.byID[pc.id]; ok {
			return nil, errors.New("duplicate contract")
		}
		c.byID[pc.id] = pc
	}
	if len(c.byID) != 28 {
		return nil, errors.New("incomplete fixed proof contracts")
	}
	for _, s := range c.slots {
		p := c.byID[s.ContractID]
		if p == nil || p.domain != s.Domain || p.producer != s.Producer || p.role != s.Role || p.mode != s.Freshness.Mode || p.verifier != s.RequiredVerifier {
			return nil, fmt.Errorf("slot/contract mismatch %s", s.SlotID)
		}
	}
	return c, nil
}
