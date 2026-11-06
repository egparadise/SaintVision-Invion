package migrationcontext

// Exact typed-to-codec projections only; no arbitrary struct/custom marshaler.
func p02StringMap(v map[string]string) p02Value {
	out := p02Object()
	for k, x := range v {
		out.object = append(out.object, p02Field{k, p02String(x)})
	}
	return out
}
func p02ExpectedValue(v p02Expectation) p02Value {
	switch v.kind {
	case 's':
		return p02String(v.literal)
	case 'i':
		return p02Integer(v.integer)
	case 'b':
		return p02Boolean(v.boolean)
	case 'n':
		return p02Value{kind: 'n'}
	case 'a':
		return p02Array(nil)
	case 'o':
		return p02Object()
	}
	return p02Value{}
}
func p02StepValue(v p02StepKey) p02Value {
	return p02Array([]p02Value{p02Integer(v.runID), p02String(v.jobName), p02Integer(v.number), p02String(v.name)})
}
func p02ValueSourceConstants(v p02SourceConstants) p02Value {
	out := p02Object()
	out.object = append(out.object, p02Field{"k1SourcePinSetSHA256", p02String(v.k1SourcePinSetSHA256)})
	out.object = append(out.object, p02Field{"recipeDefinitionsSHA256", p02String(v.recipeDefinitionsSHA256)})
	out.object = append(out.object, p02Field{"derivedDigestContractSHA256", p02String(v.derivedDigestContractSHA256)})
	out.object = append(out.object, p02Field{"proofSlotRegistrySHA256", p02String(v.proofSlotRegistrySHA256)})
	out.object = append(out.object, p02Field{"graphSHA256", p02String(v.graphSHA256)})
	out.object = append(out.object, p02Field{"nodeKindsSHA256", p02String(v.nodeKindsSHA256)})
	out.object = append(out.object, p02Field{"designRegistrationSHA256", p02String(v.designRegistrationSHA256)})
	return out
}
func p02ValueMemberBinding(v p02MemberBinding) p02Value {
	out := p02Object()
	out.object = append(out.object, p02Field{"slot", p02String(v.slot)})
	out.object = append(out.object, p02Field{"scope", p02ValueNodeScope(v.scope)})
	out.object = append(out.object, p02Field{"certificateSHA256", p02String(v.certificateSHA256)})
	out.object = append(out.object, p02Field{"caSHA256", p02String(v.caSHA256)})
	out.object = append(out.object, p02Field{"SPKISHA256", p02String(v.sPKISHA256)})
	out.object = append(out.object, p02Field{"publicKeyHex", p02String(v.publicKeyHex)})
	return out
}
func p02ValuePrimaryCI(v p02PrimaryCI) p02Value {
	out := p02Object()
	out.object = append(out.object, p02Field{"runId", p02Integer(v.runID)})
	out.object = append(out.object, p02Field{"jobId", p02Integer(v.jobID)})
	out.object = append(out.object, p02Field{"jobName", p02String(v.jobName)})
	return out
}
func p02ValueCapsule(v p02Capsule) p02Value {
	out := p02Object()
	out.object = append(out.object, p02Field{"format", p02String(v.format)})
	out.object = append(out.object, p02Field{"purpose", p02String(v.purpose)})
	out.object = append(out.object, p02Field{"selector", p02String(v.selector)})
	out.object = append(out.object, p02Field{"scopeSHA256", p02String(v.scopeSHA256)})
	out.object = append(out.object, p02Field{"generation", p02String(v.generation)})
	out.object = append(out.object, p02Field{"keySPKI", p02String(v.keySPKI)})
	out.object = append(out.object, p02Field{"approvedReviewScope", p02String(v.approvedReviewScope)})
	out.object = append(out.object, p02Field{"rootApprovalIdentity", p02String(v.rootApprovalIdentity)})
	out.object = append(out.object, p02Field{"rootApprovalPurpose", p02String(v.rootApprovalPurpose)})
	out.object = append(out.object, p02Field{"componentSHA256", p02String(v.componentSHA256)})
	out.object = append(out.object, p02Field{"expectedRootSHA256", p02String(v.expectedRootSHA256)})
	out.object = append(out.object, p02Field{"anchorVersion", p02Integer(v.anchorVersion)})
	out.object = append(out.object, p02Field{"keyNotBefore", p02Integer(v.keyNotBefore)})
	out.object = append(out.object, p02Field{"keyNotAfter", p02Integer(v.keyNotAfter)})
	out.object = append(out.object, p02Field{"expectedUID", p02Integer(v.expectedUID)})
	out.object = append(out.object, p02Field{"minimumRecordVersion", p02Integer(v.minimumRecordVersion)})
	out.object = append(out.object, p02Field{"primaryCI", p02ValuePrimaryCI(v.primaryCI)})
	out.object = append(out.object, p02Field{"sourceConstants", p02ValueSourceConstants(v.sourceConstants)})
	xmemberBindings := p02Array(nil)
	for _, x := range v.memberBindings {
		xmemberBindings.array = append(xmemberBindings.array, p02ValueMemberBinding(x))
	}
	out.object = append(out.object, p02Field{"memberBindings", xmemberBindings})
	out.object = append(out.object, p02Field{"sourceParts", p02StringMap(v.sourceParts)})
	xreviewedParts := p02Object()
	for k, x := range v.reviewedParts {
		xreviewedParts.object = append(xreviewedParts.object, p02Field{k, p02StringMap(x)})
	}
	out.object = append(out.object, p02Field{"reviewedParts", xreviewedParts})
	xrequiredParts := p02Array(nil)
	for _, x := range v.requiredParts {
		xrequiredParts.array = append(xrequiredParts.array, p02String(x))
	}
	out.object = append(out.object, p02Field{"requiredParts", xrequiredParts})
	xrequiredSteps := p02Array(nil)
	for _, x := range v.requiredSteps {
		xrequiredSteps.array = append(xrequiredSteps.array, p02StepValue(x))
	}
	out.object = append(out.object, p02Field{"requiredSteps", xrequiredSteps})
	xoptionalSteps := p02Array(nil)
	for _, x := range v.optionalSteps {
		xoptionalSteps.array = append(xoptionalSteps.array, p02StepValue(x))
	}
	out.object = append(out.object, p02Field{"optionalSteps", xoptionalSteps})
	out.object = append(out.object, p02Field{"approvedReviewOutcomes", p02StringMap(v.approvedReviewOutcomes)})
	if v.expectedEffectiveVerdict.present {
		out.object = append(out.object, p02Field{"expectedEffectiveVerdict", p02ExpectedValue(v.expectedEffectiveVerdict)})
	}
	return out
}
func p02ValueCoveragePart(v p02CoveragePart) p02Value {
	out := p02Object()
	out.object = append(out.object, p02Field{"partId", p02String(v.partId)})
	out.object = append(out.object, p02Field{"reviewSHA", p02String(v.reviewSHA)})
	out.object = append(out.object, p02Field{"reviewTargetSHA", p02String(v.reviewTargetSHA)})
	out.object = append(out.object, p02Field{"reviewedBlobSHA256", p02String(v.reviewedBlobSHA256)})
	out.object = append(out.object, p02Field{"currentBlobSHA256", p02String(v.currentBlobSHA256)})
	out.object = append(out.object, p02Field{"relation", p02String(v.relation)})
	return out
}
func p02ValueEffective(v p02Effective) p02Value {
	out := p02Object()
	out.object = append(out.object, p02Field{"publicationSHA", p02String(v.publicationSHA)})
	out.object = append(out.object, p02Field{"targetSourceSHA", p02String(v.targetSourceSHA)})
	out.object = append(out.object, p02Field{"scopeId", p02String(v.scopeId)})
	out.object = append(out.object, p02Field{"verdict", p02String(v.verdict)})
	return out
}
func p02ValueCoverageStatement(v p02CoverageStatement) p02Value {
	out := p02Object()
	out.object = append(out.object, p02Field{"sourceSHA", p02String(v.sourceSHA)})
	out.object = append(out.object, p02Field{"sourceTreeSHA256", p02String(v.sourceTreeSHA256)})
	out.object = append(out.object, p02Field{"reviewSetSHA256", p02String(v.reviewSetSHA256)})
	out.object = append(out.object, p02Field{"effective", p02ValueEffective(v.effective)})
	xparts := p02Array(nil)
	for _, x := range v.parts {
		xparts.array = append(xparts.array, p02ValueCoveragePart(x))
	}
	out.object = append(out.object, p02Field{"parts", xparts})
	return out
}
func p02ValueTicket(v p02Ticket) p02Value {
	out := p02Object()
	out.object = append(out.object, p02Field{"purpose", p02String(v.purpose)})
	out.object = append(out.object, p02Field{"id", p02String(v.id)})
	out.object = append(out.object, p02Field{"selector", p02String(v.selector)})
	out.object = append(out.object, p02Field{"scopeSHA256", p02String(v.scopeSHA256)})
	out.object = append(out.object, p02Field{"capsuleSHA256", p02String(v.capsuleSHA256)})
	out.object = append(out.object, p02Field{"generation", p02String(v.generation)})
	out.object = append(out.object, p02Field{"currentRecordIdentity", p02String(v.currentRecordIdentity)})
	out.object = append(out.object, p02Field{"issuedAt", p02Integer(v.issuedAt)})
	out.object = append(out.object, p02Field{"expiresAt", p02Integer(v.expiresAt)})
	out.object = append(out.object, p02Field{"currentVersion", p02Integer(v.currentVersion)})
	return out
}
func p02ValueMeasurement(v p02Measurement) p02Value {
	out := p02Object()
	out.object = append(out.object, p02Field{"purpose", p02String(v.purpose)})
	out.object = append(out.object, p02Field{"componentSHA256", p02String(v.componentSHA256)})
	out.object = append(out.object, p02Field{"executableSHA256", p02String(v.executableSHA256)})
	out.object = append(out.object, p02Field{"sourceSHA", p02String(v.sourceSHA)})
	out.object = append(out.object, p02Field{"receiptSHA256", p02String(v.receiptSHA256)})
	out.object = append(out.object, p02Field{"runtimeLockSHA256", p02String(v.runtimeLockSHA256)})
	out.object = append(out.object, p02Field{"linkedClosureSHA256", p02String(v.linkedClosureSHA256)})
	out.object = append(out.object, p02Field{"startGeneration", p02String(v.startGeneration)})
	out.object = append(out.object, p02Field{"rootIdentitySHA256", p02String(v.rootIdentitySHA256)})
	out.object = append(out.object, p02Field{"proofNonce", p02String(v.proofNonce)})
	out.object = append(out.object, p02Field{"pid", p02Integer(v.pid)})
	out.object = append(out.object, p02Field{"uid", p02Integer(v.uid)})
	out.object = append(out.object, p02Field{"observedAt", p02Integer(v.observedAt)})
	out.object = append(out.object, p02Field{"expiresAt", p02Integer(v.expiresAt)})
	return out
}
func p02ValueClock(v p02Clock) p02Value {
	out := p02Object()
	out.object = append(out.object, p02Field{"lower", p02Integer(v.lower)})
	out.object = append(out.object, p02Field{"upper", p02Integer(v.upper)})
	return out
}
func p02ValuesReviews(v []p02Review) p02Value {
	out := p02Array(nil)
	for _, x := range v {
		out.array = append(out.array, p02ValueReview(x))
	}
	return out
}
func p02ValuesCI(v []p02Run) p02Value {
	out := p02Array(nil)
	for _, x := range v {
		out.array = append(out.array, p02ValueRun(x))
	}
	return out
}
func p02CanonicalHash(v p02Value, c2 bool) string {
	b, ok := p02Encode(v, c2)
	if !ok {
		return ""
	}
	return hashBytes(b)
}
