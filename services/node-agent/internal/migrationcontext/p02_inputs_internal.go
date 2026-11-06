package migrationcontext

// Already-authenticated prerequisites are hypotheses at this private seam, NOT
// authentication tokens. No port/loader/opaque issuer consumes or creates them.
// Future independently authorized producers must bind exact raw evidence to
// decoded records. Their actual authority and every installation remain HOLD.
type p02Expectation struct {
	present bool
	kind    byte
	literal string
	integer int64
	boolean bool
}
type p02SourceConstants struct {
	k1SourcePinSetSHA256        string
	recipeDefinitionsSHA256     string
	derivedDigestContractSHA256 string
	proofSlotRegistrySHA256     string
	graphSHA256                 string
	nodeKindsSHA256             string
	designRegistrationSHA256    string
}
type p02MemberBinding struct {
	slot              string
	scope             p02NodeScope
	certificateSHA256 string
	caSHA256          string
	sPKISHA256        string
	publicKeyHex      string
}
type p02StepKey struct {
	runID   int64
	jobName string
	number  int64
	name    string
}
type p02PrimaryCI struct {
	runID   int64
	jobID   int64
	jobName string
}
type p02Capsule struct {
	format                   string
	purpose                  string
	selector                 string
	scopeSHA256              string
	generation               string
	keySPKI                  string
	approvedReviewScope      string
	rootApprovalIdentity     string
	rootApprovalPurpose      string
	componentSHA256          string
	expectedRootSHA256       string
	anchorVersion            int64
	keyNotBefore             int64
	keyNotAfter              int64
	expectedUID              int64
	minimumRecordVersion     int64
	primaryCI                p02PrimaryCI
	sourceConstants          p02SourceConstants
	memberBindings           []p02MemberBinding
	sourceParts              map[string]string
	reviewedParts            map[string]map[string]string
	requiredParts            []string
	requiredSteps            []p02StepKey
	optionalSteps            []p02StepKey
	approvedReviewOutcomes   map[string]string
	expectedEffectiveVerdict p02Expectation
}
type p02CoveragePart struct {
	partId             string
	reviewSHA          string
	reviewTargetSHA    string
	reviewedBlobSHA256 string
	currentBlobSHA256  string
	relation           string
}
type p02Effective struct {
	publicationSHA  string
	targetSourceSHA string
	scopeId         string
	verdict         string
}
type p02CoverageStatement struct {
	sourceSHA        string
	sourceTreeSHA256 string
	reviewSetSHA256  string
	effective        p02Effective
	parts            []p02CoveragePart
}
type p02Coverage struct {
	purpose     string
	authorityId string
	rawEvidence []byte
	statement   p02CoverageStatement
}
type p02SourceRecord struct {
	facts p02SourceFacts
}
type p02CIRecord struct {
	runs []p02Run
}
type p02ReviewRecord struct {
	reviews []p02Review
}
type p02Lifecycle struct {
	status                string
	keyStatus             string
	sourceStatus          string
	coverageStatus        string
	receiptStatus         string
	currentRecordIdentity string
	generation            string
	capsuleSHA256         string
	currentVersion        int64
	floor                 int64
	checkedAt             int64
	expiresAt             int64
	reviews               map[string]string
	grants                map[string]string
	certificates          map[string]string
}
type p02Ticket struct {
	purpose               string
	id                    string
	selector              string
	scopeSHA256           string
	capsuleSHA256         string
	generation            string
	currentRecordIdentity string
	issuedAt              int64
	expiresAt             int64
	currentVersion        int64
}
type p02Measurement struct {
	purpose             string
	componentSHA256     string
	executableSHA256    string
	sourceSHA           string
	receiptSHA256       string
	runtimeLockSHA256   string
	linkedClosureSHA256 string
	startGeneration     string
	rootIdentitySHA256  string
	proofNonce          string
	pid                 int64
	uid                 int64
	observedAt          int64
	expiresAt           int64
	rawEvidence         []byte
}
type p02Clock struct {
	lower int64
	upper int64
}
type p02SignatureTuple struct {
	format               string
	purpose              string
	domain               string
	keySPKI              string
	capsuleSHA256        string
	generation           string
	selector             string
	scopeSHA256          string
	requestBindingSHA256 string
	anchorVersion        int64
	recordVersion        int64
	signingInput         []byte
	signature            []byte
}
type p02SnapshotToken struct {
	revision          string
	capsuleSHA256     string
	generation        string
	selector          string
	scopeSHA256       string
	recordIdentity    string
	ticketID          string
	measurementSHA256 string
	recordVersion     int64
}
type p02Inputs struct {
	capsule     *p02Capsule
	capsuleRaw  []byte
	source      *p02SourceRecord
	ci          *p02CIRecord
	reviews     *p02ReviewRecord
	coverage    *p02Coverage
	lifecycle   *p02Lifecycle
	ticket      *p02Ticket
	measurement *p02Measurement
	clock       *p02Clock
	signatures  []p02SignatureTuple
	before      p02SnapshotToken
	after       p02SnapshotToken
}
type p02Budget struct {
	bytes int64
	nodes int64
}

func (b *p02Budget) take(n int64) bool {
	if n < 0 || n > b.bytes || b.nodes <= 0 {
		return false
	}
	b.bytes -= n
	b.nodes--
	return true
}
func p02BudgetString(s string, b *p02Budget) bool { return len(s) <= 65536 && b.take(int64(len(s))) }
func p02BudgetInt64(_ int64, b *p02Budget) bool   { return b.take(8) }
func p02BudgetBool(_ bool, b *p02Budget) bool     { return b.take(1) }
func p02BudgetByte(_ byte, b *p02Budget) bool     { return b.take(1) }
func p02FreezeExpectation(v p02Expectation) p02Expectation {
	out := v
	out.present = v.present
	out.kind = v.kind
	out.literal = v.literal
	out.integer = v.integer
	out.boolean = v.boolean
	return out
}
func p02BudgetExpectation(v p02Expectation, b *p02Budget) bool {
	if !p02BudgetBool(v.present, b) {
		return false
	}
	if !p02BudgetByte(v.kind, b) {
		return false
	}
	if !p02BudgetString(v.literal, b) {
		return false
	}
	if !p02BudgetInt64(v.integer, b) {
		return false
	}
	if !p02BudgetBool(v.boolean, b) {
		return false
	}
	return true
}
func p02FreezeSourceConstants(v p02SourceConstants) p02SourceConstants {
	out := v
	out.k1SourcePinSetSHA256 = v.k1SourcePinSetSHA256
	out.recipeDefinitionsSHA256 = v.recipeDefinitionsSHA256
	out.derivedDigestContractSHA256 = v.derivedDigestContractSHA256
	out.proofSlotRegistrySHA256 = v.proofSlotRegistrySHA256
	out.graphSHA256 = v.graphSHA256
	out.nodeKindsSHA256 = v.nodeKindsSHA256
	out.designRegistrationSHA256 = v.designRegistrationSHA256
	return out
}
func p02BudgetSourceConstants(v p02SourceConstants, b *p02Budget) bool {
	if !p02BudgetString(v.k1SourcePinSetSHA256, b) {
		return false
	}
	if !p02BudgetString(v.recipeDefinitionsSHA256, b) {
		return false
	}
	if !p02BudgetString(v.derivedDigestContractSHA256, b) {
		return false
	}
	if !p02BudgetString(v.proofSlotRegistrySHA256, b) {
		return false
	}
	if !p02BudgetString(v.graphSHA256, b) {
		return false
	}
	if !p02BudgetString(v.nodeKindsSHA256, b) {
		return false
	}
	if !p02BudgetString(v.designRegistrationSHA256, b) {
		return false
	}
	return true
}
func p02FreezeMemberBinding(v p02MemberBinding) p02MemberBinding {
	out := v
	out.slot = v.slot
	out.scope = p02FreezeNodeScope(v.scope)
	out.certificateSHA256 = v.certificateSHA256
	out.caSHA256 = v.caSHA256
	out.sPKISHA256 = v.sPKISHA256
	out.publicKeyHex = v.publicKeyHex
	return out
}
func p02BudgetMemberBinding(v p02MemberBinding, b *p02Budget) bool {
	if !p02BudgetString(v.slot, b) {
		return false
	}
	if !p02BudgetNodeScope(v.scope, b) {
		return false
	}
	if !p02BudgetString(v.certificateSHA256, b) {
		return false
	}
	if !p02BudgetString(v.caSHA256, b) {
		return false
	}
	if !p02BudgetString(v.sPKISHA256, b) {
		return false
	}
	if !p02BudgetString(v.publicKeyHex, b) {
		return false
	}
	return true
}
func p02FreezeStepKey(v p02StepKey) p02StepKey {
	out := v
	out.runID = v.runID
	out.jobName = v.jobName
	out.number = v.number
	out.name = v.name
	return out
}
func p02BudgetStepKey(v p02StepKey, b *p02Budget) bool {
	if !p02BudgetInt64(v.runID, b) {
		return false
	}
	if !p02BudgetString(v.jobName, b) {
		return false
	}
	if !p02BudgetInt64(v.number, b) {
		return false
	}
	if !p02BudgetString(v.name, b) {
		return false
	}
	return true
}
func p02FreezePrimaryCI(v p02PrimaryCI) p02PrimaryCI {
	out := v
	out.runID = v.runID
	out.jobID = v.jobID
	out.jobName = v.jobName
	return out
}
func p02BudgetPrimaryCI(v p02PrimaryCI, b *p02Budget) bool {
	if !p02BudgetInt64(v.runID, b) {
		return false
	}
	if !p02BudgetInt64(v.jobID, b) {
		return false
	}
	if !p02BudgetString(v.jobName, b) {
		return false
	}
	return true
}
func p02FreezeCapsule(v p02Capsule) p02Capsule {
	out := v
	out.format = v.format
	out.purpose = v.purpose
	out.selector = v.selector
	out.scopeSHA256 = v.scopeSHA256
	out.generation = v.generation
	out.keySPKI = v.keySPKI
	out.approvedReviewScope = v.approvedReviewScope
	out.rootApprovalIdentity = v.rootApprovalIdentity
	out.rootApprovalPurpose = v.rootApprovalPurpose
	out.componentSHA256 = v.componentSHA256
	out.expectedRootSHA256 = v.expectedRootSHA256
	out.anchorVersion = v.anchorVersion
	out.keyNotBefore = v.keyNotBefore
	out.keyNotAfter = v.keyNotAfter
	out.expectedUID = v.expectedUID
	out.minimumRecordVersion = v.minimumRecordVersion
	out.primaryCI = p02FreezePrimaryCI(v.primaryCI)
	out.sourceConstants = p02FreezeSourceConstants(v.sourceConstants)
	out.memberBindings = make([]p02MemberBinding, len(v.memberBindings))
	for i, x := range v.memberBindings {
		out.memberBindings[i] = p02FreezeMemberBinding(x)
	}
	out.sourceParts = copyMap(v.sourceParts)
	out.reviewedParts = make(map[string]map[string]string, len(v.reviewedParts))
	for k, x := range v.reviewedParts {
		out.reviewedParts[k] = copyMap(x)
	}
	out.requiredParts = make([]string, len(v.requiredParts))
	for i, x := range v.requiredParts {
		out.requiredParts[i] = x
	}
	out.requiredSteps = make([]p02StepKey, len(v.requiredSteps))
	for i, x := range v.requiredSteps {
		out.requiredSteps[i] = p02FreezeStepKey(x)
	}
	out.optionalSteps = make([]p02StepKey, len(v.optionalSteps))
	for i, x := range v.optionalSteps {
		out.optionalSteps[i] = p02FreezeStepKey(x)
	}
	out.approvedReviewOutcomes = copyMap(v.approvedReviewOutcomes)
	out.expectedEffectiveVerdict = p02FreezeExpectation(v.expectedEffectiveVerdict)
	return out
}
func p02BudgetCapsule(v p02Capsule, b *p02Budget) bool {
	if !p02BudgetString(v.format, b) {
		return false
	}
	if !p02BudgetString(v.purpose, b) {
		return false
	}
	if !p02BudgetString(v.selector, b) {
		return false
	}
	if !p02BudgetString(v.scopeSHA256, b) {
		return false
	}
	if !p02BudgetString(v.generation, b) {
		return false
	}
	if !p02BudgetString(v.keySPKI, b) {
		return false
	}
	if !p02BudgetString(v.approvedReviewScope, b) {
		return false
	}
	if !p02BudgetString(v.rootApprovalIdentity, b) {
		return false
	}
	if !p02BudgetString(v.rootApprovalPurpose, b) {
		return false
	}
	if !p02BudgetString(v.componentSHA256, b) {
		return false
	}
	if !p02BudgetString(v.expectedRootSHA256, b) {
		return false
	}
	if !p02BudgetInt64(v.anchorVersion, b) {
		return false
	}
	if !p02BudgetInt64(v.keyNotBefore, b) {
		return false
	}
	if !p02BudgetInt64(v.keyNotAfter, b) {
		return false
	}
	if !p02BudgetInt64(v.expectedUID, b) {
		return false
	}
	if !p02BudgetInt64(v.minimumRecordVersion, b) {
		return false
	}
	if !p02BudgetPrimaryCI(v.primaryCI, b) {
		return false
	}
	if !p02BudgetSourceConstants(v.sourceConstants, b) {
		return false
	}
	if len(v.memberBindings) > 4096 {
		return false
	}
	for _, x := range v.memberBindings {
		if !p02BudgetMemberBinding(x, b) {
			return false
		}
	}
	if len(v.sourceParts) > 4096 {
		return false
	}
	for k, x := range v.sourceParts {
		if !p02BudgetString(k, b) || !p02BudgetString(x, b) {
			return false
		}
	}
	if len(v.reviewedParts) > 4096 {
		return false
	}
	for k, x := range v.reviewedParts {
		if !p02BudgetString(k, b) || len(x) > 4096 {
			return false
		}
		for a, z := range x {
			if !p02BudgetString(a, b) || !p02BudgetString(z, b) {
				return false
			}
		}
	}
	if len(v.requiredParts) > 4096 {
		return false
	}
	for _, x := range v.requiredParts {
		if !p02BudgetString(x, b) {
			return false
		}
	}
	if len(v.requiredSteps) > 4096 {
		return false
	}
	for _, x := range v.requiredSteps {
		if !p02BudgetStepKey(x, b) {
			return false
		}
	}
	if len(v.optionalSteps) > 4096 {
		return false
	}
	for _, x := range v.optionalSteps {
		if !p02BudgetStepKey(x, b) {
			return false
		}
	}
	if len(v.approvedReviewOutcomes) > 4096 {
		return false
	}
	for k, x := range v.approvedReviewOutcomes {
		if !p02BudgetString(k, b) || !p02BudgetString(x, b) {
			return false
		}
	}
	if !p02BudgetExpectation(v.expectedEffectiveVerdict, b) {
		return false
	}
	return true
}
func p02FreezeCoveragePart(v p02CoveragePart) p02CoveragePart {
	out := v
	out.partId = v.partId
	out.reviewSHA = v.reviewSHA
	out.reviewTargetSHA = v.reviewTargetSHA
	out.reviewedBlobSHA256 = v.reviewedBlobSHA256
	out.currentBlobSHA256 = v.currentBlobSHA256
	out.relation = v.relation
	return out
}
func p02BudgetCoveragePart(v p02CoveragePart, b *p02Budget) bool {
	if !p02BudgetString(v.partId, b) {
		return false
	}
	if !p02BudgetString(v.reviewSHA, b) {
		return false
	}
	if !p02BudgetString(v.reviewTargetSHA, b) {
		return false
	}
	if !p02BudgetString(v.reviewedBlobSHA256, b) {
		return false
	}
	if !p02BudgetString(v.currentBlobSHA256, b) {
		return false
	}
	if !p02BudgetString(v.relation, b) {
		return false
	}
	return true
}
func p02FreezeEffective(v p02Effective) p02Effective {
	out := v
	out.publicationSHA = v.publicationSHA
	out.targetSourceSHA = v.targetSourceSHA
	out.scopeId = v.scopeId
	out.verdict = v.verdict
	return out
}
func p02BudgetEffective(v p02Effective, b *p02Budget) bool {
	if !p02BudgetString(v.publicationSHA, b) {
		return false
	}
	if !p02BudgetString(v.targetSourceSHA, b) {
		return false
	}
	if !p02BudgetString(v.scopeId, b) {
		return false
	}
	if !p02BudgetString(v.verdict, b) {
		return false
	}
	return true
}
func p02FreezeCoverageStatement(v p02CoverageStatement) p02CoverageStatement {
	out := v
	out.sourceSHA = v.sourceSHA
	out.sourceTreeSHA256 = v.sourceTreeSHA256
	out.reviewSetSHA256 = v.reviewSetSHA256
	out.effective = p02FreezeEffective(v.effective)
	out.parts = make([]p02CoveragePart, len(v.parts))
	for i, x := range v.parts {
		out.parts[i] = p02FreezeCoveragePart(x)
	}
	return out
}
func p02BudgetCoverageStatement(v p02CoverageStatement, b *p02Budget) bool {
	if !p02BudgetString(v.sourceSHA, b) {
		return false
	}
	if !p02BudgetString(v.sourceTreeSHA256, b) {
		return false
	}
	if !p02BudgetString(v.reviewSetSHA256, b) {
		return false
	}
	if !p02BudgetEffective(v.effective, b) {
		return false
	}
	if len(v.parts) > 4096 {
		return false
	}
	for _, x := range v.parts {
		if !p02BudgetCoveragePart(x, b) {
			return false
		}
	}
	return true
}
func p02FreezeCoverage(v p02Coverage) p02Coverage {
	out := v
	out.purpose = v.purpose
	out.authorityId = v.authorityId
	out.rawEvidence = copyBytes(v.rawEvidence)
	out.statement = p02FreezeCoverageStatement(v.statement)
	return out
}
func p02BudgetCoverage(v p02Coverage, b *p02Budget) bool {
	if !p02BudgetString(v.purpose, b) {
		return false
	}
	if !p02BudgetString(v.authorityId, b) {
		return false
	}
	if len(v.rawEvidence) > p02PayloadLimit || !b.take(int64(len(v.rawEvidence))) {
		return false
	}
	if !p02BudgetCoverageStatement(v.statement, b) {
		return false
	}
	return true
}
func p02FreezeSourceRecord(v p02SourceRecord) p02SourceRecord {
	out := v
	out.facts = p02FreezeSourceFacts(v.facts)
	return out
}
func p02BudgetSourceRecord(v p02SourceRecord, b *p02Budget) bool {
	if !p02BudgetSourceFacts(v.facts, b) {
		return false
	}
	return true
}
func p02FreezeCIRecord(v p02CIRecord) p02CIRecord {
	out := v
	out.runs = make([]p02Run, len(v.runs))
	for i, x := range v.runs {
		out.runs[i] = p02FreezeRun(x)
	}
	return out
}
func p02BudgetCIRecord(v p02CIRecord, b *p02Budget) bool {
	if len(v.runs) > 4096 {
		return false
	}
	for _, x := range v.runs {
		if !p02BudgetRun(x, b) {
			return false
		}
	}
	return true
}
func p02FreezeReviewRecord(v p02ReviewRecord) p02ReviewRecord {
	out := v
	out.reviews = make([]p02Review, len(v.reviews))
	for i, x := range v.reviews {
		out.reviews[i] = p02FreezeReview(x)
	}
	return out
}
func p02BudgetReviewRecord(v p02ReviewRecord, b *p02Budget) bool {
	if len(v.reviews) > 4096 {
		return false
	}
	for _, x := range v.reviews {
		if !p02BudgetReview(x, b) {
			return false
		}
	}
	return true
}
func p02FreezeLifecycle(v p02Lifecycle) p02Lifecycle {
	out := v
	out.status = v.status
	out.keyStatus = v.keyStatus
	out.sourceStatus = v.sourceStatus
	out.coverageStatus = v.coverageStatus
	out.receiptStatus = v.receiptStatus
	out.currentRecordIdentity = v.currentRecordIdentity
	out.generation = v.generation
	out.capsuleSHA256 = v.capsuleSHA256
	out.currentVersion = v.currentVersion
	out.floor = v.floor
	out.checkedAt = v.checkedAt
	out.expiresAt = v.expiresAt
	out.reviews = copyMap(v.reviews)
	out.grants = copyMap(v.grants)
	out.certificates = copyMap(v.certificates)
	return out
}
func p02BudgetLifecycle(v p02Lifecycle, b *p02Budget) bool {
	if !p02BudgetString(v.status, b) {
		return false
	}
	if !p02BudgetString(v.keyStatus, b) {
		return false
	}
	if !p02BudgetString(v.sourceStatus, b) {
		return false
	}
	if !p02BudgetString(v.coverageStatus, b) {
		return false
	}
	if !p02BudgetString(v.receiptStatus, b) {
		return false
	}
	if !p02BudgetString(v.currentRecordIdentity, b) {
		return false
	}
	if !p02BudgetString(v.generation, b) {
		return false
	}
	if !p02BudgetString(v.capsuleSHA256, b) {
		return false
	}
	if !p02BudgetInt64(v.currentVersion, b) {
		return false
	}
	if !p02BudgetInt64(v.floor, b) {
		return false
	}
	if !p02BudgetInt64(v.checkedAt, b) {
		return false
	}
	if !p02BudgetInt64(v.expiresAt, b) {
		return false
	}
	if len(v.reviews) > 4096 {
		return false
	}
	for k, x := range v.reviews {
		if !p02BudgetString(k, b) || !p02BudgetString(x, b) {
			return false
		}
	}
	if len(v.grants) > 4096 {
		return false
	}
	for k, x := range v.grants {
		if !p02BudgetString(k, b) || !p02BudgetString(x, b) {
			return false
		}
	}
	if len(v.certificates) > 4096 {
		return false
	}
	for k, x := range v.certificates {
		if !p02BudgetString(k, b) || !p02BudgetString(x, b) {
			return false
		}
	}
	return true
}
func p02FreezeTicket(v p02Ticket) p02Ticket {
	out := v
	out.purpose = v.purpose
	out.id = v.id
	out.selector = v.selector
	out.scopeSHA256 = v.scopeSHA256
	out.capsuleSHA256 = v.capsuleSHA256
	out.generation = v.generation
	out.currentRecordIdentity = v.currentRecordIdentity
	out.issuedAt = v.issuedAt
	out.expiresAt = v.expiresAt
	out.currentVersion = v.currentVersion
	return out
}
func p02BudgetTicket(v p02Ticket, b *p02Budget) bool {
	if !p02BudgetString(v.purpose, b) {
		return false
	}
	if !p02BudgetString(v.id, b) {
		return false
	}
	if !p02BudgetString(v.selector, b) {
		return false
	}
	if !p02BudgetString(v.scopeSHA256, b) {
		return false
	}
	if !p02BudgetString(v.capsuleSHA256, b) {
		return false
	}
	if !p02BudgetString(v.generation, b) {
		return false
	}
	if !p02BudgetString(v.currentRecordIdentity, b) {
		return false
	}
	if !p02BudgetInt64(v.issuedAt, b) {
		return false
	}
	if !p02BudgetInt64(v.expiresAt, b) {
		return false
	}
	if !p02BudgetInt64(v.currentVersion, b) {
		return false
	}
	return true
}
func p02FreezeMeasurement(v p02Measurement) p02Measurement {
	out := v
	out.purpose = v.purpose
	out.componentSHA256 = v.componentSHA256
	out.executableSHA256 = v.executableSHA256
	out.sourceSHA = v.sourceSHA
	out.receiptSHA256 = v.receiptSHA256
	out.runtimeLockSHA256 = v.runtimeLockSHA256
	out.linkedClosureSHA256 = v.linkedClosureSHA256
	out.startGeneration = v.startGeneration
	out.rootIdentitySHA256 = v.rootIdentitySHA256
	out.proofNonce = v.proofNonce
	out.pid = v.pid
	out.uid = v.uid
	out.observedAt = v.observedAt
	out.expiresAt = v.expiresAt
	out.rawEvidence = copyBytes(v.rawEvidence)
	return out
}
func p02BudgetMeasurement(v p02Measurement, b *p02Budget) bool {
	if !p02BudgetString(v.purpose, b) {
		return false
	}
	if !p02BudgetString(v.componentSHA256, b) {
		return false
	}
	if !p02BudgetString(v.executableSHA256, b) {
		return false
	}
	if !p02BudgetString(v.sourceSHA, b) {
		return false
	}
	if !p02BudgetString(v.receiptSHA256, b) {
		return false
	}
	if !p02BudgetString(v.runtimeLockSHA256, b) {
		return false
	}
	if !p02BudgetString(v.linkedClosureSHA256, b) {
		return false
	}
	if !p02BudgetString(v.startGeneration, b) {
		return false
	}
	if !p02BudgetString(v.rootIdentitySHA256, b) {
		return false
	}
	if !p02BudgetString(v.proofNonce, b) {
		return false
	}
	if !p02BudgetInt64(v.pid, b) {
		return false
	}
	if !p02BudgetInt64(v.uid, b) {
		return false
	}
	if !p02BudgetInt64(v.observedAt, b) {
		return false
	}
	if !p02BudgetInt64(v.expiresAt, b) {
		return false
	}
	if len(v.rawEvidence) > p02PayloadLimit || !b.take(int64(len(v.rawEvidence))) {
		return false
	}
	return true
}
func p02FreezeClock(v p02Clock) p02Clock {
	out := v
	out.lower = v.lower
	out.upper = v.upper
	return out
}
func p02BudgetClock(v p02Clock, b *p02Budget) bool {
	if !p02BudgetInt64(v.lower, b) {
		return false
	}
	if !p02BudgetInt64(v.upper, b) {
		return false
	}
	return true
}
func p02FreezeSignatureTuple(v p02SignatureTuple) p02SignatureTuple {
	out := v
	out.format = v.format
	out.purpose = v.purpose
	out.domain = v.domain
	out.keySPKI = v.keySPKI
	out.capsuleSHA256 = v.capsuleSHA256
	out.generation = v.generation
	out.selector = v.selector
	out.scopeSHA256 = v.scopeSHA256
	out.requestBindingSHA256 = v.requestBindingSHA256
	out.anchorVersion = v.anchorVersion
	out.recordVersion = v.recordVersion
	out.signingInput = copyBytes(v.signingInput)
	out.signature = copyBytes(v.signature)
	return out
}
func p02BudgetSignatureTuple(v p02SignatureTuple, b *p02Budget) bool {
	if !p02BudgetString(v.format, b) {
		return false
	}
	if !p02BudgetString(v.purpose, b) {
		return false
	}
	if !p02BudgetString(v.domain, b) {
		return false
	}
	if !p02BudgetString(v.keySPKI, b) {
		return false
	}
	if !p02BudgetString(v.capsuleSHA256, b) {
		return false
	}
	if !p02BudgetString(v.generation, b) {
		return false
	}
	if !p02BudgetString(v.selector, b) {
		return false
	}
	if !p02BudgetString(v.scopeSHA256, b) {
		return false
	}
	if !p02BudgetString(v.requestBindingSHA256, b) {
		return false
	}
	if !p02BudgetInt64(v.anchorVersion, b) {
		return false
	}
	if !p02BudgetInt64(v.recordVersion, b) {
		return false
	}
	if len(v.signingInput) > p02PayloadLimit || !b.take(int64(len(v.signingInput))) {
		return false
	}
	if len(v.signature) > p02PayloadLimit || !b.take(int64(len(v.signature))) {
		return false
	}
	return true
}
func p02FreezeSnapshotToken(v p02SnapshotToken) p02SnapshotToken {
	out := v
	out.revision = v.revision
	out.capsuleSHA256 = v.capsuleSHA256
	out.generation = v.generation
	out.selector = v.selector
	out.scopeSHA256 = v.scopeSHA256
	out.recordIdentity = v.recordIdentity
	out.ticketID = v.ticketID
	out.measurementSHA256 = v.measurementSHA256
	out.recordVersion = v.recordVersion
	return out
}
func p02BudgetSnapshotToken(v p02SnapshotToken, b *p02Budget) bool {
	if !p02BudgetString(v.revision, b) {
		return false
	}
	if !p02BudgetString(v.capsuleSHA256, b) {
		return false
	}
	if !p02BudgetString(v.generation, b) {
		return false
	}
	if !p02BudgetString(v.selector, b) {
		return false
	}
	if !p02BudgetString(v.scopeSHA256, b) {
		return false
	}
	if !p02BudgetString(v.recordIdentity, b) {
		return false
	}
	if !p02BudgetString(v.ticketID, b) {
		return false
	}
	if !p02BudgetString(v.measurementSHA256, b) {
		return false
	}
	if !p02BudgetInt64(v.recordVersion, b) {
		return false
	}
	return true
}
func p02FreezeInputs(v p02Inputs) p02Inputs {
	out := v
	if v.capsule != nil {
		x := p02FreezeCapsule(*v.capsule)
		out.capsule = &x
	}
	out.capsuleRaw = copyBytes(v.capsuleRaw)
	if v.source != nil {
		x := p02FreezeSourceRecord(*v.source)
		out.source = &x
	}
	if v.ci != nil {
		x := p02FreezeCIRecord(*v.ci)
		out.ci = &x
	}
	if v.reviews != nil {
		x := p02FreezeReviewRecord(*v.reviews)
		out.reviews = &x
	}
	if v.coverage != nil {
		x := p02FreezeCoverage(*v.coverage)
		out.coverage = &x
	}
	if v.lifecycle != nil {
		x := p02FreezeLifecycle(*v.lifecycle)
		out.lifecycle = &x
	}
	if v.ticket != nil {
		x := p02FreezeTicket(*v.ticket)
		out.ticket = &x
	}
	if v.measurement != nil {
		x := p02FreezeMeasurement(*v.measurement)
		out.measurement = &x
	}
	if v.clock != nil {
		x := p02FreezeClock(*v.clock)
		out.clock = &x
	}
	out.signatures = make([]p02SignatureTuple, len(v.signatures))
	for i, x := range v.signatures {
		out.signatures[i] = p02FreezeSignatureTuple(x)
	}
	out.before = p02FreezeSnapshotToken(v.before)
	out.after = p02FreezeSnapshotToken(v.after)
	return out
}
func p02BudgetInputs(v p02Inputs, b *p02Budget) bool {
	if v.capsule != nil && !p02BudgetCapsule(*v.capsule, b) {
		return false
	}
	if len(v.capsuleRaw) > p02PayloadLimit || !b.take(int64(len(v.capsuleRaw))) {
		return false
	}
	if v.source != nil && !p02BudgetSourceRecord(*v.source, b) {
		return false
	}
	if v.ci != nil && !p02BudgetCIRecord(*v.ci, b) {
		return false
	}
	if v.reviews != nil && !p02BudgetReviewRecord(*v.reviews, b) {
		return false
	}
	if v.coverage != nil && !p02BudgetCoverage(*v.coverage, b) {
		return false
	}
	if v.lifecycle != nil && !p02BudgetLifecycle(*v.lifecycle, b) {
		return false
	}
	if v.ticket != nil && !p02BudgetTicket(*v.ticket, b) {
		return false
	}
	if v.measurement != nil && !p02BudgetMeasurement(*v.measurement, b) {
		return false
	}
	if v.clock != nil && !p02BudgetClock(*v.clock, b) {
		return false
	}
	if len(v.signatures) > 4096 {
		return false
	}
	for _, x := range v.signatures {
		if !p02BudgetSignatureTuple(x, b) {
			return false
		}
	}
	if !p02BudgetSnapshotToken(v.before, b) {
		return false
	}
	if !p02BudgetSnapshotToken(v.after, b) {
		return false
	}
	return true
}
func p02FreezeEnvelope(v p02Envelope) p02Envelope {
	out := v
	out.body = p02FreezeBody(v.body)
	out.signer = p02FreezeSigner(v.signer)
	out.signatureHex = v.signatureHex
	return out
}
func p02BudgetEnvelope(v p02Envelope, b *p02Budget) bool {
	if !p02BudgetBody(v.body, b) {
		return false
	}
	if !p02BudgetSigner(v.signer, b) {
		return false
	}
	if !p02BudgetString(v.signatureHex, b) {
		return false
	}
	return true
}
func p02FreezeBody(v p02Body) p02Body {
	out := v
	out.format = v.format
	out.purpose = v.purpose
	out.selector = v.selector
	out.scopeSHA256 = v.scopeSHA256
	out.capsuleSHA256 = v.capsuleSHA256
	out.provisioningGeneration = v.provisioningGeneration
	out.anchorVersion = v.anchorVersion
	out.recordVersion = v.recordVersion
	out.requestBindingSHA256 = v.requestBindingSHA256
	out.issuedAt = v.issuedAt
	out.validUntil = v.validUntil
	out.facts = p02FreezeFacts(v.facts)
	out.ciRuns = make([]p02Run, len(v.ciRuns))
	for i, x := range v.ciRuns {
		out.ciRuns[i] = p02FreezeRun(x)
	}
	out.reviews = make([]p02Review, len(v.reviews))
	for i, x := range v.reviews {
		out.reviews[i] = p02FreezeReview(x)
	}
	return out
}
func p02BudgetBody(v p02Body, b *p02Budget) bool {
	if !p02BudgetString(v.format, b) {
		return false
	}
	if !p02BudgetString(v.purpose, b) {
		return false
	}
	if !p02BudgetString(v.selector, b) {
		return false
	}
	if !p02BudgetString(v.scopeSHA256, b) {
		return false
	}
	if !p02BudgetString(v.capsuleSHA256, b) {
		return false
	}
	if !p02BudgetString(v.provisioningGeneration, b) {
		return false
	}
	if !p02BudgetInt64(v.anchorVersion, b) {
		return false
	}
	if !p02BudgetInt64(v.recordVersion, b) {
		return false
	}
	if !p02BudgetString(v.requestBindingSHA256, b) {
		return false
	}
	if !p02BudgetInt64(v.issuedAt, b) {
		return false
	}
	if !p02BudgetInt64(v.validUntil, b) {
		return false
	}
	if !p02BudgetFacts(v.facts, b) {
		return false
	}
	if len(v.ciRuns) > 4096 {
		return false
	}
	for _, x := range v.ciRuns {
		if !p02BudgetRun(x, b) {
			return false
		}
	}
	if len(v.reviews) > 4096 {
		return false
	}
	for _, x := range v.reviews {
		if !p02BudgetReview(x, b) {
			return false
		}
	}
	return true
}
func p02FreezeSigner(v p02Signer) p02Signer {
	out := v
	out.keySPKISHA256 = v.keySPKISHA256
	return out
}
func p02BudgetSigner(v p02Signer, b *p02Budget) bool {
	if !p02BudgetString(v.keySPKISHA256, b) {
		return false
	}
	return true
}
func p02FreezeFacts(v p02Facts) p02Facts {
	out := v
	out.artifactZipSHA256 = v.artifactZipSHA256
	out.binarySHA256 = v.binarySHA256
	out.binaryVCSRevision = v.binaryVCSRevision
	out.cohortScopeSHA256 = v.cohortScopeSHA256
	out.contractSetSHA256 = v.contractSetSHA256
	out.designRegistrationSHA256 = v.designRegistrationSHA256
	out.graphSHA256 = v.graphSHA256
	out.helperClosureSHA256 = v.helperClosureSHA256
	out.installationBinarySHA256 = v.installationBinarySHA256
	out.installationReceiptSHA256 = v.installationReceiptSHA256
	out.installationSourceSHA = v.installationSourceSHA
	out.keyGrantsSHA256 = v.keyGrantsSHA256
	out.linkedClosureSHA256 = v.linkedClosureSHA256
	out.moduleClosureSHA256 = v.moduleClosureSHA256
	out.policyPayloadSHA256 = v.policyPayloadSHA256
	out.registryProofSlotsSHA256 = v.registryProofSlotsSHA256
	out.reviewCoverageSHA256 = v.reviewCoverageSHA256
	out.rootChoiceSHA256 = v.rootChoiceSHA256
	out.runningBinarySHA256 = v.runningBinarySHA256
	out.runningLinkedClosureSHA256 = v.runningLinkedClosureSHA256
	out.runningMeasurementSHA256 = v.runningMeasurementSHA256
	out.runningReceiptSHA256 = v.runningReceiptSHA256
	out.runningRuntimeLockSHA256 = v.runningRuntimeLockSHA256
	out.runningSourceSHA = v.runningSourceSHA
	out.runtimeLockSHA256 = v.runtimeLockSHA256
	out.semanticPinsSHA256 = v.semanticPinsSHA256
	out.sourceAcquisitionSHA256 = v.sourceAcquisitionSHA256
	out.sourceEquivalenceSHA256 = v.sourceEquivalenceSHA256
	out.sourcePublicationAnchorSHA256 = v.sourcePublicationAnchorSHA256
	out.sourceSHA = v.sourceSHA
	out.sourceTreeSHA256 = v.sourceTreeSHA256
	out.toolchain = v.toolchain
	out.artifactId = v.artifactId
	out.artifactZipBytes = v.artifactZipBytes
	out.binaryVCSModified = v.binaryVCSModified
	out.effectiveReviewSHA = v.effectiveReviewSHA
	out.effectiveReviewTargetSHA = v.effectiveReviewTargetSHA
	out.effectiveReviewScope = v.effectiveReviewScope
	out.effectiveReviewVerdict = v.effectiveReviewVerdict
	return out
}
func p02BudgetFacts(v p02Facts, b *p02Budget) bool {
	if !p02BudgetString(v.artifactZipSHA256, b) {
		return false
	}
	if !p02BudgetString(v.binarySHA256, b) {
		return false
	}
	if !p02BudgetString(v.binaryVCSRevision, b) {
		return false
	}
	if !p02BudgetString(v.cohortScopeSHA256, b) {
		return false
	}
	if !p02BudgetString(v.contractSetSHA256, b) {
		return false
	}
	if !p02BudgetString(v.designRegistrationSHA256, b) {
		return false
	}
	if !p02BudgetString(v.graphSHA256, b) {
		return false
	}
	if !p02BudgetString(v.helperClosureSHA256, b) {
		return false
	}
	if !p02BudgetString(v.installationBinarySHA256, b) {
		return false
	}
	if !p02BudgetString(v.installationReceiptSHA256, b) {
		return false
	}
	if !p02BudgetString(v.installationSourceSHA, b) {
		return false
	}
	if !p02BudgetString(v.keyGrantsSHA256, b) {
		return false
	}
	if !p02BudgetString(v.linkedClosureSHA256, b) {
		return false
	}
	if !p02BudgetString(v.moduleClosureSHA256, b) {
		return false
	}
	if !p02BudgetString(v.policyPayloadSHA256, b) {
		return false
	}
	if !p02BudgetString(v.registryProofSlotsSHA256, b) {
		return false
	}
	if !p02BudgetString(v.reviewCoverageSHA256, b) {
		return false
	}
	if !p02BudgetString(v.rootChoiceSHA256, b) {
		return false
	}
	if !p02BudgetString(v.runningBinarySHA256, b) {
		return false
	}
	if !p02BudgetString(v.runningLinkedClosureSHA256, b) {
		return false
	}
	if !p02BudgetString(v.runningMeasurementSHA256, b) {
		return false
	}
	if !p02BudgetString(v.runningReceiptSHA256, b) {
		return false
	}
	if !p02BudgetString(v.runningRuntimeLockSHA256, b) {
		return false
	}
	if !p02BudgetString(v.runningSourceSHA, b) {
		return false
	}
	if !p02BudgetString(v.runtimeLockSHA256, b) {
		return false
	}
	if !p02BudgetString(v.semanticPinsSHA256, b) {
		return false
	}
	if !p02BudgetString(v.sourceAcquisitionSHA256, b) {
		return false
	}
	if !p02BudgetString(v.sourceEquivalenceSHA256, b) {
		return false
	}
	if !p02BudgetString(v.sourcePublicationAnchorSHA256, b) {
		return false
	}
	if !p02BudgetString(v.sourceSHA, b) {
		return false
	}
	if !p02BudgetString(v.sourceTreeSHA256, b) {
		return false
	}
	if !p02BudgetString(v.toolchain, b) {
		return false
	}
	if !p02BudgetInt64(v.artifactId, b) {
		return false
	}
	if !p02BudgetInt64(v.artifactZipBytes, b) {
		return false
	}
	if !p02BudgetBool(v.binaryVCSModified, b) {
		return false
	}
	if !p02BudgetString(v.effectiveReviewSHA, b) {
		return false
	}
	if !p02BudgetString(v.effectiveReviewTargetSHA, b) {
		return false
	}
	if !p02BudgetString(v.effectiveReviewScope, b) {
		return false
	}
	if !p02BudgetString(v.effectiveReviewVerdict, b) {
		return false
	}
	return true
}
func p02FreezeRun(v p02Run) p02Run {
	out := v
	out.runId = v.runId
	out.repository = v.repository
	out.headSHA = v.headSHA
	out.ref = v.ref
	out.event = v.event
	out.workflow = v.workflow
	out.correlation = v.correlation
	out.attempt = v.attempt
	out.conclusion = v.conclusion
	out.jobs = make([]p02Job, len(v.jobs))
	for i, x := range v.jobs {
		out.jobs[i] = p02FreezeJob(x)
	}
	return out
}
func p02BudgetRun(v p02Run, b *p02Budget) bool {
	if !p02BudgetInt64(v.runId, b) {
		return false
	}
	if !p02BudgetString(v.repository, b) {
		return false
	}
	if !p02BudgetString(v.headSHA, b) {
		return false
	}
	if !p02BudgetString(v.ref, b) {
		return false
	}
	if !p02BudgetString(v.event, b) {
		return false
	}
	if !p02BudgetString(v.workflow, b) {
		return false
	}
	if !p02BudgetString(v.correlation, b) {
		return false
	}
	if !p02BudgetInt64(v.attempt, b) {
		return false
	}
	if !p02BudgetString(v.conclusion, b) {
		return false
	}
	if len(v.jobs) > 4096 {
		return false
	}
	for _, x := range v.jobs {
		if !p02BudgetJob(x, b) {
			return false
		}
	}
	return true
}
func p02FreezeJob(v p02Job) p02Job {
	out := v
	out.id = v.id
	out.name = v.name
	out.conclusion = v.conclusion
	out.steps = make([]p02Step, len(v.steps))
	for i, x := range v.steps {
		out.steps[i] = p02FreezeStep(x)
	}
	return out
}
func p02BudgetJob(v p02Job, b *p02Budget) bool {
	if !p02BudgetInt64(v.id, b) {
		return false
	}
	if !p02BudgetString(v.name, b) {
		return false
	}
	if !p02BudgetString(v.conclusion, b) {
		return false
	}
	if len(v.steps) > 4096 {
		return false
	}
	for _, x := range v.steps {
		if !p02BudgetStep(x, b) {
			return false
		}
	}
	return true
}
func p02FreezeStep(v p02Step) p02Step {
	out := v
	out.number = v.number
	out.name = v.name
	out.conclusion = v.conclusion
	return out
}
func p02BudgetStep(v p02Step, b *p02Budget) bool {
	if !p02BudgetInt64(v.number, b) {
		return false
	}
	if !p02BudgetString(v.name, b) {
		return false
	}
	if !p02BudgetString(v.conclusion, b) {
		return false
	}
	return true
}
func p02FreezeReview(v p02Review) p02Review {
	out := v
	out.ordinal = v.ordinal
	out.reviewSHA = v.reviewSHA
	out.targetSHA = v.targetSHA
	out.verdict = v.verdict
	out.scopeId = v.scopeId
	out.scopeUTF8Hex = v.scopeUTF8Hex
	out.scopeSHA256 = v.scopeSHA256
	out.reviewerId = v.reviewerId
	out.reviewerSPKISHA256 = v.reviewerSPKISHA256
	out.rawReviewSHA256 = v.rawReviewSHA256
	return out
}
func p02BudgetReview(v p02Review, b *p02Budget) bool {
	if !p02BudgetInt64(v.ordinal, b) {
		return false
	}
	if !p02BudgetString(v.reviewSHA, b) {
		return false
	}
	if !p02BudgetString(v.targetSHA, b) {
		return false
	}
	if !p02BudgetString(v.verdict, b) {
		return false
	}
	if !p02BudgetString(v.scopeId, b) {
		return false
	}
	if !p02BudgetString(v.scopeUTF8Hex, b) {
		return false
	}
	if !p02BudgetString(v.scopeSHA256, b) {
		return false
	}
	if !p02BudgetString(v.reviewerId, b) {
		return false
	}
	if !p02BudgetString(v.reviewerSPKISHA256, b) {
		return false
	}
	if !p02BudgetString(v.rawReviewSHA256, b) {
		return false
	}
	return true
}
func p02FreezePayload(v p02Payload) p02Payload {
	out := v
	out.selector = v.selector
	out.version = v.version
	out.verifier = p02FreezeVerifier(v.verifier)
	out.contractPins = copyMap(v.contractPins)
	out.grants = make([]p02WireGrant, len(v.grants))
	for i, x := range v.grants {
		out.grants[i] = p02FreezeWireGrant(x)
	}
	out.cohortId = v.cohortId
	out.members = make([]p02Member, len(v.members))
	for i, x := range v.members {
		out.members[i] = p02FreezeMember(x)
	}
	out.graphHex = v.graphHex
	out.nodeKinds = copyMap(v.nodeKinds)
	out.proofSlotRegistryHex = v.proofSlotRegistryHex
	out.designRegistrationHex = v.designRegistrationHex
	out.semanticPins = p02FreezeSemanticPins(v.semanticPins)
	return out
}
func p02BudgetPayload(v p02Payload, b *p02Budget) bool {
	if !p02BudgetString(v.selector, b) {
		return false
	}
	if !p02BudgetString(v.version, b) {
		return false
	}
	if !p02BudgetVerifier(v.verifier, b) {
		return false
	}
	if len(v.contractPins) > 4096 {
		return false
	}
	for k, x := range v.contractPins {
		if !p02BudgetString(k, b) || !p02BudgetPin(x, b) {
			return false
		}
	}
	if len(v.grants) > 4096 {
		return false
	}
	for _, x := range v.grants {
		if !p02BudgetWireGrant(x, b) {
			return false
		}
	}
	if !p02BudgetString(v.cohortId, b) {
		return false
	}
	if len(v.members) > 4096 {
		return false
	}
	for _, x := range v.members {
		if !p02BudgetMember(x, b) {
			return false
		}
	}
	if !p02BudgetString(v.graphHex, b) {
		return false
	}
	if len(v.nodeKinds) > 4096 {
		return false
	}
	for k, x := range v.nodeKinds {
		if !p02BudgetString(k, b) || !p02BudgetString(x, b) {
			return false
		}
	}
	if !p02BudgetString(v.proofSlotRegistryHex, b) {
		return false
	}
	if !p02BudgetString(v.designRegistrationHex, b) {
		return false
	}
	if !p02BudgetSemanticPins(v.semanticPins, b) {
		return false
	}
	return true
}
func p02FreezeVerifier(v p02Verifier) p02Verifier {
	out := v
	out.id = v.id
	out.sourceSHA = v.sourceSHA
	out.artifactSHA256 = v.artifactSHA256
	out.reviewSHA = v.reviewSHA
	out.ciRunIDs = make([]int64, len(v.ciRunIDs))
	for i, x := range v.ciRunIDs {
		out.ciRunIDs[i] = x
	}
	return out
}
func p02BudgetVerifier(v p02Verifier, b *p02Budget) bool {
	if !p02BudgetString(v.id, b) {
		return false
	}
	if !p02BudgetString(v.sourceSHA, b) {
		return false
	}
	if !p02BudgetString(v.artifactSHA256, b) {
		return false
	}
	if !p02BudgetString(v.reviewSHA, b) {
		return false
	}
	if len(v.ciRunIDs) > 4096 {
		return false
	}
	for _, x := range v.ciRunIDs {
		if !p02BudgetInt64(x, b) {
			return false
		}
	}
	return true
}
func p02FreezePin(v p02Pin) p02Pin {
	out := v
	out.contractSHA256 = v.contractSHA256
	out.schemaSHA256 = v.schemaSHA256
	out.codec = v.codec
	out.requiredVerifier = v.requiredVerifier
	return out
}
func p02BudgetPin(v p02Pin, b *p02Budget) bool {
	if !p02BudgetString(v.contractSHA256, b) {
		return false
	}
	if !p02BudgetString(v.schemaSHA256, b) {
		return false
	}
	if !p02BudgetString(v.codec, b) {
		return false
	}
	if !p02BudgetString(v.requiredVerifier, b) {
		return false
	}
	return true
}
func p02FreezeWireGrant(v p02WireGrant) p02WireGrant {
	out := v
	out.role = v.role
	out.authorityScopeC2Hex = v.authorityScopeC2Hex
	out.publicKeyHex = v.publicKeyHex
	out.notBefore = v.notBefore
	out.notAfter = v.notAfter
	return out
}
func p02BudgetWireGrant(v p02WireGrant, b *p02Budget) bool {
	if !p02BudgetString(v.role, b) {
		return false
	}
	if !p02BudgetString(v.authorityScopeC2Hex, b) {
		return false
	}
	if !p02BudgetString(v.publicKeyHex, b) {
		return false
	}
	if !p02BudgetInt64(v.notBefore, b) {
		return false
	}
	if !p02BudgetInt64(v.notAfter, b) {
		return false
	}
	return true
}
func p02FreezeMember(v p02Member) p02Member {
	out := v
	out.slot = v.slot
	out.scope = p02FreezeNodeScope(v.scope)
	out.certificateDERHex = v.certificateDERHex
	out.caRootDERHex = v.caRootDERHex
	return out
}
func p02BudgetMember(v p02Member, b *p02Budget) bool {
	if !p02BudgetString(v.slot, b) {
		return false
	}
	if !p02BudgetNodeScope(v.scope, b) {
		return false
	}
	if !p02BudgetString(v.certificateDERHex, b) {
		return false
	}
	if !p02BudgetString(v.caRootDERHex, b) {
		return false
	}
	return true
}
func p02FreezeNodeScope(v p02NodeScope) p02NodeScope {
	out := v
	out.tenantId = v.tenantId
	out.nodeId = v.nodeId
	out.recoveryEpoch = v.recoveryEpoch
	return out
}
func p02BudgetNodeScope(v p02NodeScope, b *p02Budget) bool {
	if !p02BudgetString(v.tenantId, b) {
		return false
	}
	if !p02BudgetString(v.nodeId, b) {
		return false
	}
	if !p02BudgetString(v.recoveryEpoch, b) {
		return false
	}
	return true
}
func p02FreezeSemanticPins(v p02SemanticPins) p02SemanticPins {
	out := v
	out.k1SourcePinSetSHA256 = v.k1SourcePinSetSHA256
	out.recipeDefinitionsSHA256 = v.recipeDefinitionsSHA256
	out.derivedDigestContractSHA256 = v.derivedDigestContractSHA256
	out.proofSlotRegistrySHA256 = v.proofSlotRegistrySHA256
	out.graphSHA256 = v.graphSHA256
	out.nodeKindsSHA256 = v.nodeKindsSHA256
	return out
}
func p02BudgetSemanticPins(v p02SemanticPins, b *p02Budget) bool {
	if !p02BudgetString(v.k1SourcePinSetSHA256, b) {
		return false
	}
	if !p02BudgetString(v.recipeDefinitionsSHA256, b) {
		return false
	}
	if !p02BudgetString(v.derivedDigestContractSHA256, b) {
		return false
	}
	if !p02BudgetString(v.proofSlotRegistrySHA256, b) {
		return false
	}
	if !p02BudgetString(v.graphSHA256, b) {
		return false
	}
	if !p02BudgetString(v.nodeKindsSHA256, b) {
		return false
	}
	return true
}
func p02FreezeSourceFacts(v p02SourceFacts) p02SourceFacts {
	out := v
	out.artifactZipSHA256 = v.artifactZipSHA256
	out.binarySHA256 = v.binarySHA256
	out.binaryVCSRevision = v.binaryVCSRevision
	out.cohortScopeSHA256 = v.cohortScopeSHA256
	out.contractSetSHA256 = v.contractSetSHA256
	out.designRegistrationSHA256 = v.designRegistrationSHA256
	out.graphSHA256 = v.graphSHA256
	out.helperClosureSHA256 = v.helperClosureSHA256
	out.installationBinarySHA256 = v.installationBinarySHA256
	out.installationReceiptSHA256 = v.installationReceiptSHA256
	out.installationSourceSHA = v.installationSourceSHA
	out.keyGrantsSHA256 = v.keyGrantsSHA256
	out.linkedClosureSHA256 = v.linkedClosureSHA256
	out.moduleClosureSHA256 = v.moduleClosureSHA256
	out.policyPayloadSHA256 = v.policyPayloadSHA256
	out.registryProofSlotsSHA256 = v.registryProofSlotsSHA256
	out.reviewCoverageSHA256 = v.reviewCoverageSHA256
	out.rootChoiceSHA256 = v.rootChoiceSHA256
	out.runningBinarySHA256 = v.runningBinarySHA256
	out.runningLinkedClosureSHA256 = v.runningLinkedClosureSHA256
	out.runningReceiptSHA256 = v.runningReceiptSHA256
	out.runningRuntimeLockSHA256 = v.runningRuntimeLockSHA256
	out.runningSourceSHA = v.runningSourceSHA
	out.runtimeLockSHA256 = v.runtimeLockSHA256
	out.semanticPinsSHA256 = v.semanticPinsSHA256
	out.sourceAcquisitionSHA256 = v.sourceAcquisitionSHA256
	out.sourceEquivalenceSHA256 = v.sourceEquivalenceSHA256
	out.sourcePublicationAnchorSHA256 = v.sourcePublicationAnchorSHA256
	out.sourceSHA = v.sourceSHA
	out.sourceTreeSHA256 = v.sourceTreeSHA256
	out.toolchain = v.toolchain
	out.artifactId = v.artifactId
	out.artifactZipBytes = v.artifactZipBytes
	out.binaryVCSModified = v.binaryVCSModified
	out.effectiveReviewSHA = v.effectiveReviewSHA
	out.effectiveReviewTargetSHA = v.effectiveReviewTargetSHA
	out.effectiveReviewScope = v.effectiveReviewScope
	out.effectiveReviewVerdict = v.effectiveReviewVerdict
	return out
}
func p02BudgetSourceFacts(v p02SourceFacts, b *p02Budget) bool {
	if !p02BudgetString(v.artifactZipSHA256, b) {
		return false
	}
	if !p02BudgetString(v.binarySHA256, b) {
		return false
	}
	if !p02BudgetString(v.binaryVCSRevision, b) {
		return false
	}
	if !p02BudgetString(v.cohortScopeSHA256, b) {
		return false
	}
	if !p02BudgetString(v.contractSetSHA256, b) {
		return false
	}
	if !p02BudgetString(v.designRegistrationSHA256, b) {
		return false
	}
	if !p02BudgetString(v.graphSHA256, b) {
		return false
	}
	if !p02BudgetString(v.helperClosureSHA256, b) {
		return false
	}
	if !p02BudgetString(v.installationBinarySHA256, b) {
		return false
	}
	if !p02BudgetString(v.installationReceiptSHA256, b) {
		return false
	}
	if !p02BudgetString(v.installationSourceSHA, b) {
		return false
	}
	if !p02BudgetString(v.keyGrantsSHA256, b) {
		return false
	}
	if !p02BudgetString(v.linkedClosureSHA256, b) {
		return false
	}
	if !p02BudgetString(v.moduleClosureSHA256, b) {
		return false
	}
	if !p02BudgetString(v.policyPayloadSHA256, b) {
		return false
	}
	if !p02BudgetString(v.registryProofSlotsSHA256, b) {
		return false
	}
	if !p02BudgetString(v.reviewCoverageSHA256, b) {
		return false
	}
	if !p02BudgetString(v.rootChoiceSHA256, b) {
		return false
	}
	if !p02BudgetString(v.runningBinarySHA256, b) {
		return false
	}
	if !p02BudgetString(v.runningLinkedClosureSHA256, b) {
		return false
	}
	if !p02BudgetString(v.runningReceiptSHA256, b) {
		return false
	}
	if !p02BudgetString(v.runningRuntimeLockSHA256, b) {
		return false
	}
	if !p02BudgetString(v.runningSourceSHA, b) {
		return false
	}
	if !p02BudgetString(v.runtimeLockSHA256, b) {
		return false
	}
	if !p02BudgetString(v.semanticPinsSHA256, b) {
		return false
	}
	if !p02BudgetString(v.sourceAcquisitionSHA256, b) {
		return false
	}
	if !p02BudgetString(v.sourceEquivalenceSHA256, b) {
		return false
	}
	if !p02BudgetString(v.sourcePublicationAnchorSHA256, b) {
		return false
	}
	if !p02BudgetString(v.sourceSHA, b) {
		return false
	}
	if !p02BudgetString(v.sourceTreeSHA256, b) {
		return false
	}
	if !p02BudgetString(v.toolchain, b) {
		return false
	}
	if !p02BudgetInt64(v.artifactId, b) {
		return false
	}
	if !p02BudgetInt64(v.artifactZipBytes, b) {
		return false
	}
	if !p02BudgetBool(v.binaryVCSModified, b) {
		return false
	}
	if !p02BudgetString(v.effectiveReviewSHA, b) {
		return false
	}
	if !p02BudgetString(v.effectiveReviewTargetSHA, b) {
		return false
	}
	if !p02BudgetString(v.effectiveReviewScope, b) {
		return false
	}
	if !p02BudgetString(v.effectiveReviewVerdict, b) {
		return false
	}
	return true
}
