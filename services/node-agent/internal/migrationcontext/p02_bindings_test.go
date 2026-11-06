package migrationcontext

import (
	"bytes"
	"reflect"
	"testing"
)

func TestP02InternalOriginalSetAndPartition(t *testing.T) {
	t.Run("unused-original", func(t *testing.T) {
		tc := p02BenignFixture()
		e, p := p02TestWire(t, tc)
		r := e.body.reviews[0]
		r.ordinal = 3
		r.reviewSHA = "c2c2c2c2c2c2c2c2c2c2c2c2c2c2c2c2c2c2c2c2"
		r.targetSHA = "c1c1c1c1c1c1c1c1c1c1c1c1c1c1c1c1c1c1c1c1"
		r.verdict = "SYNTHETIC_UNUSED_SCOPE_ACCEPT"
		e.body.reviews = append(e.body.reviews, r)
		tc.in.reviews.reviews = append(tc.in.reviews.reviews, r)
		tc.in.capsule.approvedReviewOutcomes[r.reviewSHA] = r.verdict
		tc.in.coverage.statement.reviewSetSHA256 = p02CanonicalHash(p02ValuesReviews(e.body.reviews), true)
		tc.in.coverage.statement.effective.publicationSHA = r.reviewSHA
		e.body.facts.effectiveReviewSHA = r.reviewSHA
		p.verifier.reviewSHA = r.reviewSHA
		tc.in.source.facts.effectiveReviewSHA = r.reviewSHA
		tc = p02TestRebind(t, tc, e, p)
		p02TestBound(t, "unused-original-alias", tc, "PROVENANCE", "05_REVIEWS", "effective-publication-distinct-from-every-original-and-part")
		// Causal control: same expanded original set and a distinct publication. H4
		// has no current registration for the extra review; no fabricated status.
		e, p = p02TestWire(t, tc)
		pub := "e2e2e2e2e2e2e2e2e2e2e2e2e2e2e2e2e2e2e2e2"
		tc.in.coverage.statement.effective.publicationSHA = pub
		e.body.facts.effectiveReviewSHA = pub
		p.verifier.reviewSHA = pub
		tc.in.source.facts.effectiveReviewSHA = pub
		tc = p02TestRebind(t, tc, e, p)
		p02TestBound(t, "unused-original-control-H4-unknown", tc, "STATUS", "06_STATUS", "current-review-registration")
	})
	t.Run("shrunk-independent-originals", func(t *testing.T) {
		tc := p02BenignFixture()
		e, p := p02TestWire(t, tc)
		e.body.reviews = e.body.reviews[1:]
		e.body.reviews[0].ordinal = 1
		tc.in.reviews.reviews = append([]p02Review(nil), e.body.reviews...)
		tc.in.coverage.statement.reviewSetSHA256 = p02CanonicalHash(p02ValuesReviews(e.body.reviews), true)
		tc = p02TestRebind(t, tc, e, p)
		p02TestBound(t, "shrunk-originals", tc, "PROVENANCE", "05_REVIEWS", "independent-review-outcome-set")
	})
	t.Run("shrunk-partition", func(t *testing.T) {
		tc := p02BenignFixture()
		e, p := p02TestWire(t, tc)
		tc.in.coverage.statement.parts = tc.in.coverage.statement.parts[1:]
		tc = p02TestRebind(t, tc, e, p)
		p02TestBound(t, "shrunk-partition", tc, "PROVENANCE", "05_REVIEWS", "complete-ordered-source-partition")
	})
}
func TestP02InternalExactVerifiedTupleTable(t *testing.T) {
	cases := []string{"format", "purpose", "domain", "keySPKI", "capsule", "generation", "selector", "scope", "anchor", "recordVersion", "request", "body-only", "digest-only", "signature", "empty"}
	for _, name := range cases {
		t.Run(name, func(t *testing.T) {
			tc := p02BenignFixture()
			x := &tc.in.signatures[0]
			switch name {
			case "format":
				x.format = "other"
			case "purpose":
				x.purpose = "other"
			case "domain":
				x.domain = "other"
			case "keySPKI":
				x.keySPKI = "other"
			case "capsule":
				x.capsuleSHA256 = "other"
			case "generation":
				x.generation = "other"
			case "selector":
				x.selector = "other"
			case "scope":
				x.scopeSHA256 = "other"
			case "anchor":
				x.anchorVersion++
			case "recordVersion":
				x.recordVersion++
			case "request":
				x.requestBindingSHA256 = "other"
			case "body-only":
				v, ok := p02Decode(tc.raw, p02EnvelopeLimit, false)
				if !ok {
					t.Fatal("setup")
				}
				x.signingInput = p02TestEncode(t, p02Get(v, "body"), false)
			case "digest-only":
				x.signingInput = []byte(hashBytes(x.signingInput))
			case "signature":
				x.signature[0] ^= 1
			case "empty":
				tc.in.signatures = nil
			}
			p02TestCheck(t, "tuple-"+name, tc, "SIGNATURE", "04_SIGNATURE", "", false)
		})
	}
	t.Run("old-context-cannot-replay", func(t *testing.T) {
		tc := p02BenignFixture()
		e, p := p02TestWire(t, tc)
		old := p02FreezeInputs(tc.in).signatures
		tc.in.ticket.id = "NEW_SYNTHETIC_TICKET"
		tc.in.measurement.proofNonce = "NEW_SYNTHETIC_PROOF"
		tc = p02TestRebind(t, tc, e, p)
		tc.in.signatures = old
		p02TestCheck(t, "old-tuple-new-request", tc, "SIGNATURE", "04_SIGNATURE", "exact-verified-signature-tuple-membership", false)
	})
}
func TestP02InternalH3H5BindingsAndSnapshots(t *testing.T) {
	for _, side := range []string{"H3", "H5"} {
		for _, field := range []string{"receipt", "lock", "link", "executable", "source"} {
			t.Run(side+"-"+field, func(t *testing.T) {
				tc := p02BenignFixture()
				e, p := p02TestWire(t, tc)
				bad := string(bytes.Repeat([]byte("af"), 32))
				key := ""
				if field == "source" {
					bad = string(bytes.Repeat([]byte("af"), 20))
				}
				if side == "H3" {
					switch field {
					case "receipt":
						e.body.facts.installationReceiptSHA256 = bad
						tc.in.source.facts.installationReceiptSHA256 = bad
						key = "receiptSHA256"
					case "lock":
						e.body.facts.runtimeLockSHA256 = bad
						tc.in.source.facts.runtimeLockSHA256 = bad
						key = "runtimeLockSHA256"
					case "link":
						e.body.facts.linkedClosureSHA256 = bad
						tc.in.source.facts.linkedClosureSHA256 = bad
						key = "linkedClosureSHA256"
					case "executable":
						e.body.facts.binarySHA256 = bad
						tc.in.source.facts.binarySHA256 = bad
						p.verifier.artifactSHA256 = bad
						key = "executableSHA256"
					case "source":
						e.body.facts.sourceSHA = bad
						tc.in.source.facts.sourceSHA = bad
						p.verifier.sourceSHA = bad
						key = "sourceSHA"
					}
				} else {
					switch field {
					case "receipt":
						tc.in.measurement.receiptSHA256 = bad
						key = "receiptSHA256"
					case "lock":
						tc.in.measurement.runtimeLockSHA256 = bad
						key = "runtimeLockSHA256"
					case "link":
						tc.in.measurement.linkedClosureSHA256 = bad
						key = "linkedClosureSHA256"
					case "executable":
						tc.in.measurement.executableSHA256 = bad
						key = "executableSHA256"
					case "source":
						tc.in.measurement.sourceSHA = bad
						key = "sourceSHA"
					}
				}
				tc = p02TestRebind(t, tc, e, p)
				if side == "H3" && field == "source" {
					p02TestBound(t, side+"-"+field, tc, "PROVENANCE", "05_REVIEWS", "coverage-current-source-and-original-set")
				} else {
					p02TestBound(t, side+"-"+field, tc, "INSTALLATION", "05_RUNNING", "independent-H5-"+key)
				}
			})
		}
	}
	for _, name := range []string{"floor", "fork", "replay", "expired-H5", "expired-response", "changed-readback", "status-revoked", "raw-approval-digest"} {
		t.Run(name, func(t *testing.T) {
			tc := p02BenignFixture()
			e, p := p02TestWire(t, tc)
			reason, stage := "", ""
			detail := ""
			switch name {
			case "floor":
				tc.in.lifecycle.floor = 8
				reason, stage = "VERSION", "06_VERSION"
			case "fork":
				tc.in.lifecycle.currentRecordIdentity = "SYNTHETIC_FOREIGN_HEAD"
				tc.in.ticket.currentRecordIdentity = tc.in.lifecycle.currentRecordIdentity
				reason, stage = "VERSION", "06_VERSION"
			case "replay":
				tc.in.ticket.id = "NEW_SYNTHETIC_TICKET"
				reason, stage = "REPLAY", "06_REPLAY"
			case "expired-H5":
				tc.in.measurement.expiresAt = 1001
				tc = p02TestRebind(t, tc, e, p)
				reason, stage = "TIME", "06_TIME"
				detail = "independent-H5-freshness"
			case "expired-response":
				e.body.validUntil = 1001
				tc = p02TestRebind(t, tc, e, p)
				reason, stage = "TIME", "06_TIME"
				detail = "response-ticket-freshness"
			case "changed-readback":
				tc.in.after.revision = "CHANGED"
				reason, stage = "READBACK", "06_READBACK"
			case "status-revoked":
				tc.in.lifecycle.coverageStatus = "REVOKED"
				reason, stage = "STATUS", "06_STATUS"
			case "raw-approval-digest":
				tc.in.coverage.rawEvidence = append(tc.in.coverage.rawEvidence, '!')
				reason, stage = "PROVENANCE", "05_REVIEWS"
				detail = "Root-coverage-and-exact-raw-evidence-digests"
			}
			p02TestBound(t, name, tc, reason, stage, detail)
		})
	}
}
func p02LastK1Comparison(p policyData, h runningData) bool {
	v := p.Verifier
	pr := p.Provenance
	return h.ExecutableSHA256 == v.ArtifactSHA256 && pr.RunningExecutableSHA256 == h.ExecutableSHA256 && h.SourceSHA == v.SourceSHA && h.InstallationReceiptSHA256 == pr.InstallationReceiptSHA256 && h.RuntimeLockSHA256 == pr.RuntimeLockSHA256 && h.LinkedClosureSHA256 == pr.LinkedClosureSHA256
}
func TestP02InternalProjectionEveryFieldAndOwnership(t *testing.T) {
	tc := p02BenignFixture()
	r := p02TestBound(t, "projection-control", tc, "", "", "")
	e, p := p02TestWire(t, tc)
	out := r.policy
	s := tc.in.source.facts
	h := *tc.in.measurement
	cap := tc.in.capsule
	if out.Selector != cap.selector || out.Version != "7" || out.RegistrySHA256 != hashBytes(tc.payload) || out.CohortID != p.cohortId || out.GraphSHA256 != hashBytes(out.GraphBytes) || out.GraphSHA256 != cap.sourceConstants.graphSHA256 || !reflect.DeepEqual(out.NodeKinds, p.nodeKinds) {
		t.Fatal("seven top-level policy leaves")
	}
	if out.Verifier.ID != p.verifier.id || out.Verifier.SourceSHA != s.sourceSHA || out.Verifier.ArtifactSHA256 != s.binarySHA256 || out.Verifier.ReviewSHA != tc.in.coverage.statement.effective.publicationSHA || !reflect.DeepEqual(out.Verifier.CIRunIDs, []string{"101", "102"}) {
		t.Fatal("five publication leaves")
	}
	if len(out.ContractPins) != 28 {
		t.Fatal("contract28")
	}
	for id, w := range p.contractPins {
		got := out.ContractPins[id]
		if got.ContractSHA256 != w.contractSHA256 || got.SchemaSHA256 != w.schemaSHA256 || got.Codec != w.codec || got.RequiredVerifier != w.requiredVerifier {
			t.Fatal("four contractPin leaves", id)
		}
	}
	if len(out.Grants) != len(p.grants) {
		t.Fatal("grants")
	}
	for i, g := range out.Grants {
		w := p.grants[i]
		sc, _ := p02Unhex(w.authorityScopeC2Hex)
		canonical, err := canonicalValue(g.AuthorityScope)
		if err != nil || !bytes.Equal(canonical, sc) || g.Role != w.role || g.PublicKeyHex != w.publicKeyHex || g.NotBefore.Unix() != w.notBefore || g.NotAfter.Unix() != w.notAfter || g.NotBefore.Location().String() != "UTC" || g.NotAfter.Location().String() != "UTC" || g.Status != "ACTIVE" {
			t.Fatal("six grant leaves", i)
		}
	}
	for i, m := range out.Members {
		w := p.members[i]
		der, _ := p02Unhex(w.certificateDERHex)
		ca, _ := p02Unhex(w.caRootDERHex)
		if m.Slot != w.slot || !reflect.DeepEqual(m.Scope, p02NodeScopeValue(cap.memberBindings[i].scope)) || !bytes.Equal(m.CertificateDER, der) || !bytes.Equal(m.CARootDER, ca) {
			t.Fatal("four member leaves", i)
		}
	}
	pr := out.Provenance
	primary := e.body.ciRuns[1]
	want := provenance{ReviewTargetSHA: tc.in.coverage.statement.effective.targetSourceSHA, ReviewScope: tc.in.coverage.statement.effective.scopeId, ApprovedReviewScope: cap.approvedReviewScope, BinaryVCS: s.binaryVCSRevision, RuntimeLockSHA256: s.runtimeLockSHA256, CIHeadSHA: primary.headSHA, CIRef: primary.ref, CIWorkflow: primary.workflow, CIRunID: "102", CIAttempt: "2", CIJobID: "202", ArtifactDigest: s.artifactZipSHA256, InstallationReceiptSHA256: s.installationReceiptSHA256, RunningExecutableSHA256: h.executableSHA256, LinkedClosureSHA256: s.linkedClosureSHA256}
	if pr != want || pr.ArtifactDigest == out.Verifier.ArtifactSHA256 {
		t.Fatal("fifteen Provenance leaves/archive vs executable")
	}
	if r.running != (runningData{ExecutableSHA256: h.executableSHA256, InstallationReceiptSHA256: h.receiptSHA256, SourceSHA: h.sourceSHA, RuntimeLockSHA256: h.runtimeLockSHA256, LinkedClosureSHA256: h.linkedClosureSHA256}) || !p02LastK1Comparison(out, r.running) {
		t.Fatal("five measured leaves and independent expected counterparts")
	}
	before, err := policyDigest(out)
	if err != nil {
		t.Fatal(err)
	}
	tc.raw[0] = '!'
	tc.payload[0] = '!'
	tc.artifact[0] = '!'
	tc.in.capsule.sourceParts["k1-core"] = "changed"
	tc.in.capsule.memberBindings[0].scope.nodeId = "changed"
	tc.in.ci.runs[0].jobs[0].steps[0].name = "changed"
	tc.in.measurement.receiptSHA256 = "changed"
	tc.in.source.facts.installationReceiptSHA256 = "changed"
	tc.in.signatures[0].signature[0] ^= 1
	after, err := policyDigest(r.policy)
	if err != nil || before != after {
		t.Fatal("post-return original mutation reached policy projection")
	}
	// Output itself owns map/slice/byte/JSON storage. This promises no concurrent
	// mutation isolation or malicious same-process authority boundary.
}
func TestP02InternalTwoSourceProjectionMutants(t *testing.T) {
	tc := p02BenignFixture()
	p02TestBound(t, "isolated-prerequisite-control", tc, "", "", "")
	for _, field := range []string{"receipt", "lock", "link", "executable", "source"} {
		for _, side := range []string{"H3", "H5"} {
			if side == "H3" && (field == "executable" || field == "source") {
				continue
			}
			t.Run(side+"-"+field, func(t *testing.T) {
				s := tc.in.source.facts
				h := *tc.in.measurement
				bad := "SYNTHETIC_DIFFERENT_" + field
				if side == "H3" {
					switch field {
					case "receipt":
						s.installationReceiptSHA256 = bad
					case "lock":
						s.runtimeLockSHA256 = bad
					case "link":
						s.linkedClosureSHA256 = bad
					}
				} else {
					switch field {
					case "receipt":
						h.receiptSHA256 = bad
					case "lock":
						h.runtimeLockSHA256 = bad
					case "link":
						h.linkedClosureSHA256 = bad
					case "executable":
						h.executableSHA256 = bad
					case "source":
						h.sourceSHA = bad
					}
				}
				// Isolated DTO only, not an accepted policy or K1/crypto execution.
				p := policyData{Verifier: publication{ArtifactSHA256: s.binarySHA256, SourceSHA: s.sourceSHA}, Provenance: p02InstallationProvenance(s, h)}
				measured := p02MeasuredProjection(h)
				if p02LastK1Comparison(p, measured) {
					t.Fatal("isolated independent counterpart became vacuous")
				}
				if field == "receipt" || field == "lock" || field == "link" {
					mutant := p
					mutant.Provenance.InstallationReceiptSHA256 = h.receiptSHA256
					mutant.Provenance.RuntimeLockSHA256 = h.runtimeLockSHA256
					mutant.Provenance.LinkedClosureSHA256 = h.linkedClosureSHA256
					if !p02LastK1Comparison(mutant, measured) {
						t.Fatal("regressed H5-to-both-sides causal mutant setup")
					}
				}
				t.Logf("P02_ISOLATED id=%s-%s comparison=false acceptedPolicy=false actualAuth=false", side, field)
			})
		}
	}
	// Actual helper projection's sources are separately inspected by the complete
	// field test; no unsafe-positive use is inferred from an isolated DTO.
}
func TestP02InternalCauseOrderAndNullRefusal(t *testing.T) {
	tc := p02BenignFixture()
	tc.in.lifecycle.coverageStatus = "REVOKED"
	tc.in.after.revision = "changed"
	p02TestBound(t, "status-before-readback", tc, "STATUS", "06_STATUS", "independent-current-status")
	tc = p02BenignFixture()
	tc.in.clock.upper = 1002
	tc.in.after.revision = "changed"
	p02TestBound(t, "time-before-readback", tc, "TIME", "06_TIME", "whole-authenticated-clock-interval")
	tc = p02BenignFixture()
	tc.in.capsule.expectedEffectiveVerdict.literal = "other"
	e, p := p02TestWire(t, tc)
	tc = p02TestRebind(t, tc, e, p)
	tc.in.lifecycle.status = "REVOKED"
	p02TestBound(t, "reviews-before-status", tc, "PROVENANCE", "05_REVIEWS", "independently-approved-effective-verdict")
	zero := p02Evaluate(nil, nil, nil, p02Inputs{})
	if zero.reason != "ANCHOR" || zero.publicRefusal().(*Refusal).Code() != TrustUnknown {
		t.Fatal("null internal context refuses")
	}
}
