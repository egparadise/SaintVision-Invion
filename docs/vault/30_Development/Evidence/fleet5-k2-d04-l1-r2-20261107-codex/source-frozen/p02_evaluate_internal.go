package migrationcontext

import (
	"bytes"
	"encoding/hex"
	"unicode/utf8"
)

// These are consistency results only. No method turns one into InstalledPolicy.
type p02Result struct {
	reason, stage, detail string
	passed                []string
	policy                policyData
	running               runningData
}
type p02Authority struct {
	class, component, cohortID string
	scope                      p02NodeScope
	members                    []p02NodeScope
}
type p02Context struct {
	in                          p02Inputs
	raw, payloadRaw, artifact   []byte
	envelopeValue, payloadValue p02Value
	envelope                    p02Envelope
	payload                     p02Payload
	authorities                 []p02Authority
	result                      p02Result
}

func (r p02Result) publicRefusal() error { return refuse(TrustUnknown) }
func p02Stages() []string {
	return []string{"01_ANCHOR", "02_SOURCES", "03_ENVELOPE", "03_PAYLOAD", "03_C2", "04_SIGNATURE", "04_KEY_INTERVAL", "05_PAYLOAD_JOINS", "05_COMPONENTS", "05_REVIEWS", "05_SOURCE", "05_CI", "05_ARTIFACT", "05_RUNNING", "06_STATUS", "06_VERSION", "06_REPLAY", "06_TIME", "06_READBACK", "07_PROJECTION"}
}
func (c *p02Context) need(ok bool, reason, detail string) bool {
	if !ok {
		c.result.reason = reason
		c.result.detail = detail
	}
	return ok
}

func p02Evaluate(raw, payload, artifact []byte, prerequisites p02Inputs) p02Result {
	// Exclusive ownership is required throughout the budget pass and freeze. This
	// is not malicious same-process or concurrent-mutation isolation.
	if len(prerequisites.signatures) > 16 {
		return p02Result{reason: "OWNERSHIP", stage: "01_ANCHOR", detail: "immutable-signature-table"}
	}
	budget := p02Budget{bytes: 32 << 20, nodes: 100000}
	if !p02BudgetInputs(prerequisites, &budget) {
		return p02Result{reason: "OWNERSHIP", stage: "01_ANCHOR", detail: "bounded-private-snapshots"}
	}
	c := p02Context{in: p02FreezeInputs(prerequisites), raw: raw, payloadRaw: payload, artifact: artifact}
	stages := p02Stages()
	for i, name := range stages {
		ok := false
		switch i {
		case 0:
			ok = c.anchor()
		case 1:
			ok = c.sources()
		case 2:
			ok = c.decodeEnvelope()
		case 3:
			ok = c.decodePayload()
		case 4:
			ok = c.decodeC2()
		case 5:
			ok = c.signature()
		case 6:
			ok = c.keyInterval()
		case 7:
			ok = c.payloadJoins()
		case 8:
			ok = c.components()
		case 9:
			ok = c.reviews()
		case 10:
			ok = c.source()
		case 11:
			ok = c.ci()
		case 12:
			ok = c.archive()
		case 13:
			ok = c.running()
		case 14:
			ok = c.status()
		case 15:
			ok = c.version()
		case 16:
			ok = c.replay()
		case 17:
			ok = c.freshness()
		case 18:
			ok = c.readback()
		case 19:
			ok = c.project()
		}
		if !ok {
			c.result.stage = name
			return c.result
		}
		c.result.passed = append(c.result.passed, name)
	}
	return c.result
}
func (c *p02Context) anchor() bool {
	a := c.in.capsule
	if !c.need(a != nil, "ANCHOR", "capsule-unavailable") {
		return false
	}
	v, ok := p02Decode(c.in.capsuleRaw, 65536, false)
	if !c.need(ok, "ANCHOR", "capsule-unavailable") {
		return false
	}
	expected, ok := p02Encode(p02ValueCapsule(*a), false)
	if !c.need(ok && bytes.Equal(expected, c.in.capsuleRaw) && p02Same(v, p02ValueCapsule(*a)) && a.expectedEffectiveVerdict.present, "ANCHOR", "closed-capsule-descriptor") {
		return false
	}
	return c.need(a.format == p02Format && a.purpose == p02Purpose && a.expectedUID >= 0 && a.expectedUID <= 4294967295, "ANCHOR", "independent-purpose-format-integer-domains")
}
func (c *p02Context) sources() bool {
	a := c.in
	if !c.need(a.source != nil, "PROVENANCE", "independent-source-facts") || !c.need(a.ci != nil, "CI", "independent-ci") || !c.need(a.reviews != nil && a.coverage != nil, "PROVENANCE", "independent-reviews-coverage") {
		return false
	}
	return c.need(a.lifecycle != nil, "STATUS", "independent-lifecycle") && c.need(a.ticket != nil && a.clock != nil, "TIME", "independent-ticket-clock") && c.need(a.measurement != nil, "INSTALLATION", "independent-h5")
}
func (c *p02Context) decodeEnvelope() bool {
	// Budget before copy and tree allocation, at its actual canonical codec stage.
	if !c.need(len(c.raw) > 0 && len(c.raw) <= p02EnvelopeLimit, "FORMAT", "envelope-byte-budget") {
		return false
	}
	c.raw = copyBytes(c.raw)
	v, ok := p02Decode(c.raw, p02EnvelopeLimit, false)
	if !c.need(ok && p02EnvelopeSchema(v), "FORMAT", "closed-envelope-canonical-schema") {
		return false
	}
	c.envelopeValue = v
	c.envelope = p02ReadEnvelope(v)
	b := c.envelope.body
	runs := b.ciRuns
	for i, r := range runs {
		if i > 0 && !c.need(runs[i-1].workflow < r.workflow || runs[i-1].workflow == r.workflow && runs[i-1].runId < r.runId, "FORMAT", "canonical-CI-run-order") {
			return false
		}
		for j := 0; j < i; j++ {
			if !c.need(runs[j].runId != r.runId, "FORMAT", "unique-CI-runs") {
				return false
			}
		}
		for j, job := range r.jobs {
			if j > 0 && !c.need(r.jobs[j-1].name < job.name, "FORMAT", "canonical-unique-jobs") {
				return false
			}
			for k := 0; k < j; k++ {
				if !c.need(r.jobs[k].id != job.id, "FORMAT", "unique-job-ID") {
					return false
				}
			}
			for k, st := range job.steps {
				if k > 0 && !c.need(job.steps[k-1].number < st.number, "FORMAT", "canonical-step-order") {
					return false
				}
				for q := 0; q < k; q++ {
					if !c.need(job.steps[q].name != st.name, "FORMAT", "unique-step-names") {
						return false
					}
				}
			}
		}
	}
	for i, r := range b.reviews {
		if !c.need(r.ordinal == int64(i+1), "FORMAT", "ordered-review-ordinals") {
			return false
		}
		for j := 0; j < i; j++ {
			if !c.need(b.reviews[j].reviewSHA != r.reviewSHA, "FORMAT", "unique-original-reviews") {
				return false
			}
		}
	}
	return true
}
func (c *p02Context) decodePayload() bool {
	if !c.need(len(c.payloadRaw) > 0 && len(c.payloadRaw) <= p02PayloadLimit, "FORMAT", "payload-byte-budget") {
		return false
	}
	c.payloadRaw = copyBytes(c.payloadRaw)
	v, ok := p02Decode(c.payloadRaw, p02PayloadLimit, false)
	if !c.need(ok && p02PayloadSchema(v), "FORMAT", "closed-payload-canonical-schema") {
		return false
	}
	c.payloadValue = v
	c.payload = p02ReadPayload(v)
	return true
}
func p02ReadAuthority(v p02Value) p02Authority {
	out := p02Authority{class: p02Get(v, "class").text, component: p02Get(v, "component").text, cohortID: p02Get(v, "cohortId").text, scope: p02ReadNodeScope(p02Get(v, "scope"))}
	for _, m := range p02Get(v, "members").array {
		out.members = append(out.members, p02ReadNodeScope(m))
	}
	return out
}
func p02AuthorityValue(v p02Authority) p02Value {
	if v.class == "NODE" {
		return p02Object(p02Field{"class", p02String(v.class)}, p02Field{"scope", p02ValueNodeScope(v.scope)})
	}
	if v.class == "COMPONENT" {
		return p02Object(p02Field{"class", p02String(v.class)}, p02Field{"component", p02String(v.component)})
	}
	ms := p02Array(nil)
	for _, m := range v.members {
		ms.array = append(ms.array, p02ValueNodeScope(m))
	}
	return p02Object(p02Field{"class", p02String(v.class)}, p02Field{"cohortId", p02String(v.cohortID)}, p02Field{"members", ms})
}
func p02Unhex(s string) ([]byte, bool) {
	if !p02Hex(s, 0, false) {
		return nil, false
	}
	b, e := hex.DecodeString(s)
	return b, e == nil
}
func (c *p02Context) decodeC2() bool {
	for _, g := range c.payload.grants {
		raw, ok := p02Unhex(g.authorityScopeC2Hex)
		if !c.need(ok && len(raw) <= 65536, "FORMAT", "bounded-C2-hex") {
			return false
		}
		v, ok := p02Decode(raw, 65536, true)
		if !c.need(ok && p02AuthoritySchema(v), "FORMAT", "closed-C2-authority-scope") {
			return false
		}
		c.authorities = append(c.authorities, p02ReadAuthority(v))
	}
	for _, r := range c.envelope.body.reviews {
		raw, ok := p02Unhex(r.scopeUTF8Hex)
		if !c.need(ok && len(raw) > 0 && utf8.ValidString(string(raw)) && hashBytes(raw) == r.scopeSHA256, "FORMAT", "original-review-scope-byte-hash") {
			return false
		}
	}
	return true
}
func (c *p02Context) signingInput() []byte {
	v := p02Object(p02Field{"body", p02Get(c.envelopeValue, "body")}, p02Field{"signer", p02Get(c.envelopeValue, "signer")})
	raw, ok := p02Encode(v, false)
	if !ok {
		return nil
	}
	out := append([]byte(p02Domain), 0)
	return append(out, raw...)
}
func (c *p02Context) signature() bool {
	a := c.in.capsule
	b := c.envelope.body
	e := c.envelope
	if !c.need(b.selector == a.selector && b.scopeSHA256 == a.scopeSHA256 && b.capsuleSHA256 == hashBytes(c.in.capsuleRaw) && b.provisioningGeneration == a.generation && b.anchorVersion == a.anchorVersion, "SCOPE", "exact-independent-capsule-binding") {
		return false
	}
	sig, ok := p02Unhex(e.signatureHex)
	if !c.need(ok && e.signer.keySPKISHA256 == a.keySPKI, "SIGNATURE", "pinned-signature-key") {
		return false
	}
	message := c.signingInput()
	if !c.need(len(message) > len(p02Domain) && len(c.in.signatures) <= 16, "SIGNATURE", "bounded-signature-tuple-table") {
		return false
	}
	for _, t := range c.in.signatures {
		if t.format == b.format && t.purpose == b.purpose && t.domain == p02Domain && t.keySPKI == a.keySPKI && t.capsuleSHA256 == b.capsuleSHA256 && t.generation == a.generation && t.selector == a.selector && t.scopeSHA256 == a.scopeSHA256 && t.anchorVersion == a.anchorVersion && t.recordVersion == b.recordVersion && t.requestBindingSHA256 == b.requestBindingSHA256 && bytes.Equal(t.signingInput, message) && bytes.Equal(t.signature, sig) {
			return true
		}
	}
	return c.need(false, "SIGNATURE", "exact-verified-signature-tuple-membership")
}
func (c *p02Context) keyInterval() bool {
	a := c.in.capsule
	b := c.envelope.body
	k := c.in.clock
	return c.need(a.keyNotBefore <= b.issuedAt && b.issuedAt < a.keyNotAfter && a.keyNotBefore <= k.lower && k.lower <= k.upper && k.upper < a.keyNotAfter, "TIME", "registry-key-issue-and-current-interval")
}
func (c *p02Context) payloadJoins() bool {
	p := c.payload
	b := c.envelope.body
	f := b.facts
	v := p.verifier
	if !c.need(p.selector == b.selector && p.version == p02Decimal(b.recordVersion) && v.sourceSHA == f.sourceSHA && v.artifactSHA256 == f.binarySHA256 && v.reviewSHA == f.effectiveReviewSHA, "PROVENANCE", "payload-selector-version-verifier-joins") {
		return false
	}
	if !c.need(len(v.ciRunIDs) == len(b.ciRuns), "PROVENANCE", "ordered-payload-CI-run-IDs") {
		return false
	}
	for i, id := range v.ciRunIDs {
		if !c.need(id == b.ciRuns[i].runId, "PROVENANCE", "ordered-payload-CI-run-IDs") {
			return false
		}
	}
	return true
}
func p02GrantValue(g p02WireGrant, a p02Authority) p02Value {
	return p02Object(p02Field{"role", p02String(g.role)}, p02Field{"authorityScope", p02AuthorityValue(a)}, p02Field{"publicKeyHex", p02String(g.publicKeyHex)}, p02Field{"notBefore", p02Integer(g.notBefore)}, p02Field{"notAfter", p02Integer(g.notAfter)})
}
func (c *p02Context) components() bool {
	p := c.payload
	f := c.envelope.body.facts
	sc := c.in.capsule.sourceConstants
	graph, ok := p02Unhex(p.graphHex)
	if !c.need(ok, "PROVENANCE", "graph-exact-raw-bytes") {
		return false
	}
	proof, ok := p02Unhex(p.proofSlotRegistryHex)
	if !c.need(ok, "PROVENANCE", "proof-slot-exact-raw-bytes") {
		return false
	}
	reg, ok := p02Unhex(p.designRegistrationHex)
	if !c.need(ok, "PROVENANCE", "registration-exact-raw-bytes") {
		return false
	}
	ms := p02Array(nil)
	for _, m := range p.members {
		ms.array = append(ms.array, p02ValueNodeScope(m.scope))
	}
	cohort := p02Object(p02Field{"class", p02String("COHORT")}, p02Field{"cohortId", p02String(p.cohortId)}, p02Field{"members", ms})
	gs := p02Array(nil)
	for i, g := range p.grants {
		gs.array = append(gs.array, p02GrantValue(g, c.authorities[i]))
	}
	cohortHash := p02CanonicalHash(cohort, true)
	sem := p.semanticPins
	return c.need(hashBytes(c.payloadRaw) == f.policyPayloadSHA256 && hashBytes(graph) == f.graphSHA256 && p02CanonicalHash(p02Get(c.payloadValue, "contractPins"), true) == f.contractSetSHA256 && p02CanonicalHash(p02Get(c.payloadValue, "semanticPins"), true) == f.semanticPinsSHA256 && cohortHash == f.cohortScopeSHA256 && cohortHash == c.envelope.body.scopeSHA256 && p02CanonicalHash(gs, true) == f.keyGrantsSHA256 && hashBytes(proof) == f.registryProofSlotsSHA256 && hashBytes(reg) == f.designRegistrationSHA256, "PROVENANCE", "eight-exact-payload-component-digests") && c.need(sem.k1SourcePinSetSHA256 == sc.k1SourcePinSetSHA256 && sem.recipeDefinitionsSHA256 == sc.recipeDefinitionsSHA256 && sem.derivedDigestContractSHA256 == sc.derivedDigestContractSHA256 && sem.proofSlotRegistrySHA256 == sc.proofSlotRegistrySHA256 && sem.graphSHA256 == sc.graphSHA256 && sem.nodeKindsSHA256 == sc.nodeKindsSHA256 && hashBytes(proof) == sc.proofSlotRegistrySHA256 && hashBytes(graph) == sc.graphSHA256 && p02CanonicalHash(p02Get(c.payloadValue, "nodeKinds"), true) == sc.nodeKindsSHA256 && hashBytes(reg) == sc.designRegistrationSHA256, "PROVENANCE", "independently-installed-source-components")
}
func (c *p02Context) reviews() bool {
	b := c.envelope.body
	f := b.facts
	a := c.in.capsule
	cov := c.in.coverage
	s := cov.statement
	if !c.need(p02Same(p02ValuesReviews(b.reviews), p02ValuesReviews(c.in.reviews.reviews)), "PROVENANCE", "original-authenticated-review-rows") {
		return false
	}
	if !c.need(cov.purpose == a.rootApprovalPurpose && cov.authorityId == a.rootApprovalIdentity, "PROVENANCE", "independent-effective-approval-purpose-origin") {
		return false
	}
	if !c.need(s.sourceSHA == f.sourceSHA && s.sourceTreeSHA256 == f.sourceTreeSHA256 && s.reviewSetSHA256 == p02CanonicalHash(p02ValuesReviews(b.reviews), true), "PROVENANCE", "coverage-current-source-and-original-set") {
		return false
	}
	if !c.need(len(a.approvedReviewOutcomes) == len(b.reviews), "PROVENANCE", "independent-review-outcome-set") {
		return false
	}
	for _, r := range b.reviews {
		expected, exists := a.approvedReviewOutcomes[r.reviewSHA]
		if !c.need(exists && expected == r.verdict, "PROVENANCE", "independent-original-review-verdict") {
			return false
		}
	}
	if !c.need(len(s.parts) == len(a.requiredParts) && len(s.parts) == len(a.sourceParts), "PROVENANCE", "complete-ordered-source-partition") {
		return false
	}
	for i, p := range s.parts {
		if !c.need(p.partId == a.requiredParts[i], "PROVENANCE", "complete-ordered-source-partition") {
			return false
		}
		for j := 0; j < i; j++ {
			if !c.need(s.parts[j].partId != p.partId, "PROVENANCE", "unique-coverage-parts") {
				return false
			}
		}
		found := false
		for _, r := range b.reviews {
			if r.reviewSHA == p.reviewSHA {
				found = true
				if !c.need(p.reviewTargetSHA == r.targetSHA, "PROVENANCE", "preserved-original-review-target") {
					return false
				}
				reviewed, exists := a.reviewedParts[r.reviewSHA][p.partId]
				current, cexists := a.sourceParts[p.partId]
				if !c.need(exists && cexists && reviewed == p.reviewedBlobSHA256 && current == p.currentBlobSHA256 && reviewed == current, "PROVENANCE", "independent-current-reviewed-part-bytes") {
					return false
				}
				if !c.need((p.relation == "DIRECT" || p.relation == "BYTE_IDENTICAL") && (p.relation == "DIRECT") == (r.targetSHA == s.sourceSHA), "PROVENANCE", "explicit-direct-or-inherited-relation") {
					return false
				}
			}
		}
		if !c.need(found, "PROVENANCE", "preserved-original-review-target") {
			return false
		}
	}
	e := s.effective
	if !c.need(e.targetSourceSHA == s.sourceSHA, "PROVENANCE", "effective-approval-current-target") {
		return false
	}
	x := a.expectedEffectiveVerdict
	if !c.need(x.kind == 's' && len(x.literal) > 0 && len(x.literal) <= 128, "PROVENANCE", "closed-independent-effective-verdict-expectation") {
		return false
	}
	if !c.need(e.verdict == x.literal, "PROVENANCE", "independently-approved-effective-verdict") {
		return false
	}
	_, original := a.approvedReviewOutcomes[e.publicationSHA]
	for _, r := range b.reviews {
		if r.reviewSHA == e.publicationSHA {
			original = true
		}
	}
	for _, p := range s.parts {
		if p.reviewSHA == e.publicationSHA {
			original = true
		}
	}
	if !c.need(!original, "PROVENANCE", "effective-publication-distinct-from-every-original-and-part") {
		return false
	}
	if !c.need(e.publicationSHA == f.effectiveReviewSHA && e.targetSourceSHA == f.effectiveReviewTargetSHA && e.scopeId == f.effectiveReviewScope && e.verdict == f.effectiveReviewVerdict, "PROVENANCE", "effective-approval-fact-joins") {
		return false
	}
	parts := p02Array(nil)
	for _, p := range s.parts {
		parts.array = append(parts.array, p02ValueCoveragePart(p))
	}
	return c.need(f.reviewCoverageSHA256 == p02CanonicalHash(p02ValueCoverageStatement(s), true) && f.sourceEquivalenceSHA256 == p02CanonicalHash(parts, true) && len(cov.rawEvidence) > 0 && f.rootChoiceSHA256 == hashBytes(cov.rawEvidence), "PROVENANCE", "Root-coverage-and-exact-raw-evidence-digests")
}
func (c *p02Context) source() bool {
	f := c.envelope.body.facts
	s := c.in.source.facts
	return c.need(p02SourceMatches(f, s), "PROVENANCE", "independent-source-acquisition-facts") && c.need(!s.binaryVCSModified && s.binaryVCSRevision == s.sourceSHA, "PROVENANCE", "source-VCS-join")
}
func p02StepEqual(a, b p02StepKey) bool { return a == b }
func (c *p02Context) ci() bool {
	b := c.envelope.body
	a := c.in.capsule
	if !c.need(p02Same(p02ValuesCI(b.ciRuns), p02ValuesCI(c.in.ci.runs)), "CI", "independently-acquired-CI-records") {
		return false
	}
	if !c.need(len(a.requiredSteps) > 0, "CI", "required-step-policy-missing") {
		return false
	}
	keys := append(append([]p02StepKey(nil), a.requiredSteps...), a.optionalSteps...)
	for i, k := range keys {
		for j := 0; j < i; j++ {
			if !c.need(!p02StepEqual(keys[j], k), "CI", "duplicate-or-overlapping-step-policy") {
				return false
			}
		}
	}
	actual := 0
	for _, r := range b.ciRuns {
		if !c.need(r.headSHA == b.facts.sourceSHA && r.conclusion == "success", "CI", "run-head-conclusion") {
			return false
		}
		for _, job := range r.jobs {
			if !c.need(job.conclusion == "success", "CI", "job-conclusion") {
				return false
			}
			for _, st := range job.steps {
				actual++
				key := p02StepKey{runID: r.runId, jobName: job.name, number: st.number, name: st.name}
				found := false
				for _, req := range a.requiredSteps {
					if req == key {
						found = true
						if !c.need(st.conclusion == "success", "CI", "every-required-step-success") {
							return false
						}
					}
				}
				for _, opt := range a.optionalSteps {
					if opt == key {
						found = true
						if !c.need(st.conclusion == "success" || st.conclusion == "skipped", "CI", "optional-step-conclusion") {
							return false
						}
					}
				}
				if !c.need(found, "CI", "exact-required-optional-step-policy") {
					return false
				}
			}
		}
	}
	return c.need(actual == len(keys), "CI", "complete-required-optional-step-policy")
}
func (c *p02Context) archive() bool {
	f := c.envelope.body.facts
	if !c.need(len(c.artifact) > 0 && len(c.artifact) <= p02ArtifactLimit && int64(len(c.artifact)) == f.artifactZipBytes, "ARTIFACT", "archive-byte-budget-size") {
		return false
	}
	c.artifact = copyBytes(c.artifact)
	return c.need(hashBytes(c.artifact) == f.artifactZipSHA256, "ARTIFACT", "exact-downloaded-archive-digest")
}
func (c *p02Context) running() bool {
	h := c.in.measurement
	a := c.in.capsule
	s := c.in.source.facts
	raw, ok := p02Encode(p02ValueMeasurement(*h), false)
	if !c.need(ok && len(h.rawEvidence) > 0 && bytes.Equal(raw, h.rawEvidence), "INSTALLATION", "exact-authenticated-H5-record-bytes") {
		return false
	}
	if !c.need(h.purpose == "running-integration-measurement" && h.componentSHA256 == a.componentSHA256 && h.pid > 0 && len(h.startGeneration) > 0 && h.uid == a.expectedUID && h.rootIdentitySHA256 == a.expectedRootSHA256, "INSTALLATION", "actual-component-process-generation-root-UID") {
		return false
	}
	if !c.need(h.executableSHA256 == s.binarySHA256, "INSTALLATION", "independent-H5-executableSHA256") || !c.need(h.sourceSHA == s.sourceSHA, "INSTALLATION", "independent-H5-sourceSHA") || !c.need(h.receiptSHA256 == s.installationReceiptSHA256, "INSTALLATION", "independent-H5-receiptSHA256") || !c.need(h.runtimeLockSHA256 == s.runtimeLockSHA256, "INSTALLATION", "independent-H5-runtimeLockSHA256") || !c.need(h.linkedClosureSHA256 == s.linkedClosureSHA256, "INSTALLATION", "independent-H5-linkedClosureSHA256") {
		return false
	}
	return c.need(s.binarySHA256 == s.installationBinarySHA256 && s.binarySHA256 == s.runningBinarySHA256 && s.sourceSHA == s.installationSourceSHA && s.sourceSHA == s.runningSourceSHA && s.installationReceiptSHA256 == s.runningReceiptSHA256 && s.runtimeLockSHA256 == s.runningRuntimeLockSHA256 && s.linkedClosureSHA256 == s.runningLinkedClosureSHA256, "INSTALLATION", "approved-versus-installation-closure")
}
func (c *p02Context) status() bool {
	l := c.in.lifecycle
	if !c.need(l.status == "ACTIVE" && l.keyStatus == "ACTIVE" && l.sourceStatus == "ACTIVE" && l.coverageStatus == "ACTIVE" && l.receiptStatus == "ACTIVE", "STATUS", "independent-current-status") {
		return false
	}
	for _, r := range c.envelope.body.reviews {
		if !c.need(l.reviews[r.reviewSHA] == "ACTIVE", "STATUS", "current-review-registration") {
			return false
		}
	}
	for i, g := range c.payload.grants {
		if !c.need(l.grants[p02CanonicalHash(p02GrantValue(g, c.authorities[i]), true)] == "ACTIVE", "STATUS", "current-independent-grant-registration") {
			return false
		}
	}
	for _, m := range c.payload.members {
		der, ok := p02Unhex(m.certificateDERHex)
		if !c.need(ok && l.certificates[hashBytes(der)] == "ACTIVE", "STATUS", "current-independent-certificate-registration") {
			return false
		}
	}
	return true
}
func p02RecordIdentity(v p02Value) string {
	b := p02Get(v, "body")
	stable := p02Object()
	for _, name := range []string{"format", "purpose", "selector", "scopeSHA256", "capsuleSHA256", "provisioningGeneration", "anchorVersion", "recordVersion", "facts", "ciRuns", "reviews"} {
		x := p02Get(b, name)
		if name == "facts" {
			fs := p02Object()
			for _, f := range x.object {
				if f.key != "runningMeasurementSHA256" {
					fs.object = append(fs.object, f)
				}
			}
			x = fs
		}
		stable.object = append(stable.object, p02Field{name, x})
	}
	return p02CanonicalHash(stable, false)
}
func (c *p02Context) version() bool {
	l := c.in.lifecycle
	a := c.in.capsule
	b := c.envelope.body
	return c.need(l.generation == a.generation && l.capsuleSHA256 == hashBytes(c.in.capsuleRaw), "VERSION", "current-installation-generation") && c.need(b.recordVersion == l.currentVersion && b.recordVersion >= a.minimumRecordVersion && b.recordVersion >= l.floor && l.floor > 0 && l.currentRecordIdentity == p02RecordIdentity(c.envelopeValue), "VERSION", "current-stable-record-protected-floor")
}
func (c *p02Context) requestProjection() p02Value {
	a := c.in.capsule
	l := c.in.lifecycle
	t := c.in.ticket
	return p02Object(p02Field{"format", p02String(p02Format)}, p02Field{"purpose", p02String(p02Purpose)}, p02Field{"capsuleSHA256", p02String(hashBytes(c.in.capsuleRaw))}, p02Field{"provisioningGeneration", p02String(a.generation)}, p02Field{"selector", p02String(a.selector)}, p02Field{"scopeSHA256", p02String(a.scopeSHA256)}, p02Field{"recordVersion", p02Integer(l.currentVersion)}, p02Field{"currentRecordIdentity", p02String(l.currentRecordIdentity)}, p02Field{"componentSHA256", p02String(a.componentSHA256)}, p02Field{"ticketId", p02String(t.id)}, p02Field{"ticketIssuedAt", p02Integer(t.issuedAt)}, p02Field{"ticketExpiresAt", p02Integer(t.expiresAt)}, p02Field{"h5EvidenceSHA256", p02String(hashBytes(c.in.measurement.rawEvidence))})
}
func (c *p02Context) replay() bool {
	t := c.in.ticket
	a := c.in.capsule
	l := c.in.lifecycle
	b := c.envelope.body
	return c.need(t.purpose == "p02-read-ticket-candidate:2" && len(t.id) > 0 && t.selector == a.selector && t.scopeSHA256 == a.scopeSHA256 && t.capsuleSHA256 == hashBytes(c.in.capsuleRaw) && t.generation == a.generation && t.currentVersion == l.currentVersion && t.currentRecordIdentity == l.currentRecordIdentity, "REPLAY", "independent-ticket-scope-current-binding") && c.need(b.requestBindingSHA256 == p02CanonicalHash(c.requestProjection(), true) && b.facts.runningMeasurementSHA256 == hashBytes(c.in.measurement.rawEvidence), "REPLAY", "zero-weight-H5-echo-bound-through-client-request")
}
func p02Epoch(n int64) bool { return n >= 0 && n <= p02MaxEpoch }
func (c *p02Context) freshness() bool {
	k := c.in.clock
	l := c.in.lifecycle
	t := c.in.ticket
	b := c.envelope.body
	h := c.in.measurement
	if !c.need(p02Epoch(k.lower) && p02Epoch(k.upper) && k.lower <= k.upper && k.upper-k.lower <= 1, "TIME", "whole-authenticated-clock-interval") {
		return false
	}
	if !c.need(p02Epoch(l.checkedAt) && p02Epoch(l.expiresAt) && l.checkedAt <= k.lower && k.upper < l.expiresAt && k.upper-l.checkedAt <= 120, "TIME", "current-status-freshness") {
		return false
	}
	if !c.need(p02Epoch(t.issuedAt) && p02Epoch(t.expiresAt) && t.issuedAt <= b.issuedAt && b.issuedAt <= k.lower && k.upper < t.expiresAt && k.upper < b.validUntil && k.upper-b.issuedAt <= 120, "TIME", "response-ticket-freshness") {
		return false
	}
	return c.need(p02Epoch(h.observedAt) && p02Epoch(h.expiresAt) && h.observedAt <= k.lower && k.upper < h.expiresAt && k.upper-h.observedAt <= 120, "TIME", "independent-H5-freshness")
}
func (c *p02Context) readback() bool {
	x := c.in.before
	y := c.in.after
	a := c.in.capsule
	l := c.in.lifecycle
	return c.need(len(x.revision) > 0 && x == y && x.capsuleSHA256 == hashBytes(c.in.capsuleRaw) && x.generation == a.generation && x.selector == a.selector && x.scopeSHA256 == a.scopeSHA256 && x.recordIdentity == l.currentRecordIdentity && x.recordVersion == l.currentVersion && x.ticketID == c.in.ticket.id && x.measurementSHA256 == hashBytes(c.in.measurement.rawEvidence), "READBACK", "mandatory-exact-bound-final-readback")
}
