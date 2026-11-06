package migrationcontext

import "time"

func p02NodeScopeValue(v p02NodeScope) any {
	// Only concrete validated strings enter this required legacy policyData algebra.
	return map[string]any{"tenantId": v.tenantId, "nodeId": v.nodeId, "recoveryEpoch": v.recoveryEpoch}
}
func p02AuthorityProjection(v p02Authority) any {
	switch v.class {
	case "NODE":
		return map[string]any{"class": "NODE", "scope": p02NodeScopeValue(v.scope)}
	case "COMPONENT":
		return map[string]any{"class": "COMPONENT", "component": v.component}
	case "COHORT":
		members := make([]any, len(v.members))
		for i, m := range v.members {
			members[i] = p02NodeScopeValue(m)
		}
		return map[string]any{"class": "COHORT", "cohortId": v.cohortID, "members": members}
	}
	return nil
}
func p02InstallationProvenance(s p02SourceFacts, h p02Measurement) provenance {
	return provenance{RuntimeLockSHA256: s.runtimeLockSHA256, InstallationReceiptSHA256: s.installationReceiptSHA256, LinkedClosureSHA256: s.linkedClosureSHA256, RunningExecutableSHA256: h.executableSHA256}
}
func p02MeasuredProjection(h p02Measurement) runningData {
	return runningData{ExecutableSHA256: h.executableSHA256, InstallationReceiptSHA256: h.receiptSHA256, SourceSHA: h.sourceSHA, RuntimeLockSHA256: h.runtimeLockSHA256, LinkedClosureSHA256: h.linkedClosureSHA256}
}

type p02GrantKey struct{ role, scopeHash, publicKey string }

func (c *p02Context) project() bool {
	p := c.payload
	a := c.in.capsule
	s := c.in.source.facts
	h := *c.in.measurement
	cov := c.in.coverage.statement
	l := c.in.lifecycle
	primary := a.primaryCI
	if !c.need(primary.runID > 0 && primary.runID <= p02SafeInteger && primary.jobID > 0 && primary.jobID <= p02SafeInteger && len(primary.jobName) > 0, "CI", "provisioned-primary-CI-tuple") {
		return false
	}
	run := p02Run{}
	found := 0
	for _, r := range c.envelope.body.ciRuns {
		if r.runId == primary.runID {
			run = r
			found++
		}
	}
	if !c.need(found == 1, "CI", "provisioned-primary-run-not-first-green") {
		return false
	}
	found = 0
	for _, j := range run.jobs {
		if j.id == primary.jobID && j.name == primary.jobName {
			found++
		}
	}
	if !c.need(found == 1, "CI", "provisioned-primary-job-not-first-green") {
		return false
	}
	pr := p02InstallationProvenance(s, h)
	pr.ReviewTargetSHA = cov.effective.targetSourceSHA
	pr.ReviewScope = cov.effective.scopeId
	pr.ApprovedReviewScope = a.approvedReviewScope
	pr.BinaryVCS = s.binaryVCSRevision
	pr.CIHeadSHA = run.headSHA
	pr.CIRef = run.ref
	pr.CIWorkflow = run.workflow
	pr.CIRunID = p02Decimal(run.runId)
	pr.CIAttempt = p02Decimal(run.attempt)
	pr.CIJobID = p02Decimal(primary.jobID)
	pr.ArtifactDigest = s.artifactZipSHA256
	v := publication{ID: p.verifier.id, SourceSHA: s.sourceSHA, ArtifactSHA256: s.binarySHA256, ReviewSHA: cov.effective.publicationSHA}
	for _, id := range p.verifier.ciRunIDs {
		v.CIRunIDs = append(v.CIRunIDs, p02Decimal(id))
	}
	hasPrimary := false
	for _, id := range v.CIRunIDs {
		if id == pr.CIRunID {
			hasPrimary = true
		}
	}
	if !c.need(pr.ReviewTargetSHA == v.SourceSHA && pr.ReviewScope == pr.ApprovedReviewScope && pr.CIHeadSHA == v.SourceSHA && pr.BinaryVCS == v.SourceSHA && hasPrimary, "PROVENANCE", "independent-review-scope-and-primary-provenance-joins") {
		return false
	}
	graph, ok := p02Unhex(p.graphHex)
	if !c.need(ok, "PROVENANCE", "projection-graph-raw") {
		return false
	}
	out := policyData{Selector: a.selector, Version: p.version, RegistrySHA256: hashBytes(c.payloadRaw), Verifier: v, ContractPins: make(map[string]contractPin), CohortID: p.cohortId, GraphBytes: graph, GraphSHA256: hashBytes(graph), NodeKinds: copyMap(p.nodeKinds), Provenance: pr}
	for k, pin := range p.contractPins {
		out.ContractPins[k] = contractPin{ContractSHA256: pin.contractSHA256, SchemaSHA256: pin.schemaSHA256, Codec: pin.codec, RequiredVerifier: pin.requiredVerifier}
	}
	used := make(map[p02GrantKey]bool)
	for i, g := range p.grants {
		if !c.need(p02Epoch(g.notBefore) && p02Epoch(g.notAfter) && g.notBefore < g.notAfter, "PROVENANCE", "original-grant-interval-order-domain") {
			return false
		}
		key := p02GrantKey{g.role, p02CanonicalHash(p02AuthorityValue(c.authorities[i]), true), g.publicKeyHex}
		if !c.need(!used[key], "PROVENANCE", "unique-role-scope-public-key-grants") {
			return false
		}
		used[key] = true
		reg := p02CanonicalHash(p02GrantValue(g, c.authorities[i]), true)
		out.Grants = append(out.Grants, grant{Role: g.role, AuthorityScope: p02AuthorityProjection(c.authorities[i]), PublicKeyHex: g.publicKeyHex, NotBefore: time.Unix(g.notBefore, 0).UTC(), NotAfter: time.Unix(g.notAfter, 0).UTC(), Status: l.grants[reg]})
	}
	if !c.need(len(p.members) == 2 && len(a.memberBindings) == 2, "PROVENANCE", "ordered-legacy-members") {
		return false
	}
	for i, m := range p.members {
		b := a.memberBindings[i]
		der, dok := p02Unhex(m.certificateDERHex)
		ca, cok := p02Unhex(m.caRootDERHex)
		if !c.need(dok && cok && m.slot == b.slot && m.scope == b.scope && hashBytes(der) == b.certificateSHA256 && hashBytes(ca) == b.caSHA256, "PROVENANCE", "independent-DER-CA-scope-bindings") {
			return false
		}
		nodeGrant := false
		for j, g := range p.grants {
			sc := c.authorities[j]
			if g.role == "node-leaf" && g.publicKeyHex == b.publicKeyHex && sc.class == "NODE" && sc.scope == m.scope {
				nodeGrant = true
			}
		}
		if !c.need(nodeGrant, "PROVENANCE", "node-leaf-grant-scope-public-key-binding") {
			return false
		}
		out.Members = append(out.Members, member{Slot: m.slot, Scope: p02NodeScopeValue(m.scope), CertificateDER: der, CARootDER: ca})
	}
	if !c.need(out.Members[0].Slot == "PC2" && out.Members[1].Slot == "PC4" && p.members[0].scope != p.members[1].scope && p.members[0].certificateDERHex != p.members[1].certificateDERHex && a.memberBindings[0].sPKISHA256 != a.memberBindings[1].sPKISHA256, "PROVENANCE", "distinct-ordered-member-scope-DER-SPKI") {
		return false
	}
	frozen, e := freezePolicy(out)
	if !c.need(e == nil, "PROVENANCE", "closed-owned-policy-projection") {
		return false
	}
	c.result.policy = frozen
	c.result.running = p02MeasuredProjection(h)
	// Necessary consistency only. The future granted factory must still call
	// unchanged checkPolicyBindings before K1. This seam never calls/constructs K1,
	// authenticates X509/Ed25519, or issues an InstalledPolicy/History binding.
	return true
}
