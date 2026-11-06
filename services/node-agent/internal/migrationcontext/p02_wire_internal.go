package migrationcontext

// Closed typed records; decoding is called only after canonical/schema checks.
type p02Envelope struct {
	body         p02Body
	signer       p02Signer
	signatureHex string
}

func p02ReadEnvelope(v p02Value) p02Envelope {
	out := p02Envelope{}
	out.body = p02ReadBody(p02Get(v, "body"))
	out.signer = p02ReadSigner(p02Get(v, "signer"))
	out.signatureHex = p02Get(v, "signatureHex").text
	return out
}
func p02ValueEnvelope(v p02Envelope) p02Value {
	out := p02Object()

	out.object = append(out.object, p02Field{"body", p02ValueBody(v.body)})

	out.object = append(out.object, p02Field{"signer", p02ValueSigner(v.signer)})

	out.object = append(out.object, p02Field{"signatureHex", p02String(v.signatureHex)})
	return out
}

type p02Body struct {
	format                 string
	purpose                string
	selector               string
	scopeSHA256            string
	capsuleSHA256          string
	provisioningGeneration string
	anchorVersion          int64
	recordVersion          int64
	requestBindingSHA256   string
	issuedAt               int64
	validUntil             int64
	facts                  p02Facts
	ciRuns                 []p02Run
	reviews                []p02Review
}

func p02ReadBody(v p02Value) p02Body {
	out := p02Body{}
	out.format = p02Get(v, "format").text
	out.purpose = p02Get(v, "purpose").text
	out.selector = p02Get(v, "selector").text
	out.scopeSHA256 = p02Get(v, "scopeSHA256").text
	out.capsuleSHA256 = p02Get(v, "capsuleSHA256").text
	out.provisioningGeneration = p02Get(v, "provisioningGeneration").text
	out.anchorVersion = p02Get(v, "anchorVersion").integer
	out.recordVersion = p02Get(v, "recordVersion").integer
	out.requestBindingSHA256 = p02Get(v, "requestBindingSHA256").text
	out.issuedAt = p02Get(v, "issuedAt").integer
	out.validUntil = p02Get(v, "validUntil").integer
	out.facts = p02ReadFacts(p02Get(v, "facts"))
	for _, child := range p02Get(v, "ciRuns").array {
		out.ciRuns = append(out.ciRuns, p02ReadRun(child))
	}
	for _, child := range p02Get(v, "reviews").array {
		out.reviews = append(out.reviews, p02ReadReview(child))
	}
	return out
}
func p02ValueBody(v p02Body) p02Value {
	out := p02Object()

	out.object = append(out.object, p02Field{"format", p02String(v.format)})

	out.object = append(out.object, p02Field{"purpose", p02String(v.purpose)})

	out.object = append(out.object, p02Field{"selector", p02String(v.selector)})

	out.object = append(out.object, p02Field{"scopeSHA256", p02String(v.scopeSHA256)})

	out.object = append(out.object, p02Field{"capsuleSHA256", p02String(v.capsuleSHA256)})

	out.object = append(out.object, p02Field{"provisioningGeneration", p02String(v.provisioningGeneration)})

	out.object = append(out.object, p02Field{"anchorVersion", p02Integer(v.anchorVersion)})

	out.object = append(out.object, p02Field{"recordVersion", p02Integer(v.recordVersion)})

	out.object = append(out.object, p02Field{"requestBindingSHA256", p02String(v.requestBindingSHA256)})

	out.object = append(out.object, p02Field{"issuedAt", p02Integer(v.issuedAt)})

	out.object = append(out.object, p02Field{"validUntil", p02Integer(v.validUntil)})

	out.object = append(out.object, p02Field{"facts", p02ValueFacts(v.facts)})
	xciRuns := p02Array(nil)
	for _, child := range v.ciRuns {
		xciRuns.array = append(xciRuns.array, p02ValueRun(child))
	}
	out.object = append(out.object, p02Field{"ciRuns", xciRuns})
	xreviews := p02Array(nil)
	for _, child := range v.reviews {
		xreviews.array = append(xreviews.array, p02ValueReview(child))
	}
	out.object = append(out.object, p02Field{"reviews", xreviews})
	return out
}

type p02Signer struct {
	keySPKISHA256 string
}

func p02ReadSigner(v p02Value) p02Signer {
	out := p02Signer{}
	out.keySPKISHA256 = p02Get(v, "keySPKISHA256").text
	return out
}
func p02ValueSigner(v p02Signer) p02Value {
	out := p02Object()

	out.object = append(out.object, p02Field{"keySPKISHA256", p02String(v.keySPKISHA256)})
	return out
}

type p02Facts struct {
	artifactZipSHA256             string
	binarySHA256                  string
	binaryVCSRevision             string
	cohortScopeSHA256             string
	contractSetSHA256             string
	designRegistrationSHA256      string
	graphSHA256                   string
	helperClosureSHA256           string
	installationBinarySHA256      string
	installationReceiptSHA256     string
	installationSourceSHA         string
	keyGrantsSHA256               string
	linkedClosureSHA256           string
	moduleClosureSHA256           string
	policyPayloadSHA256           string
	registryProofSlotsSHA256      string
	reviewCoverageSHA256          string
	rootChoiceSHA256              string
	runningBinarySHA256           string
	runningLinkedClosureSHA256    string
	runningMeasurementSHA256      string
	runningReceiptSHA256          string
	runningRuntimeLockSHA256      string
	runningSourceSHA              string
	runtimeLockSHA256             string
	semanticPinsSHA256            string
	sourceAcquisitionSHA256       string
	sourceEquivalenceSHA256       string
	sourcePublicationAnchorSHA256 string
	sourceSHA                     string
	sourceTreeSHA256              string
	toolchain                     string
	artifactId                    int64
	artifactZipBytes              int64
	binaryVCSModified             bool
	effectiveReviewSHA            string
	effectiveReviewTargetSHA      string
	effectiveReviewScope          string
	effectiveReviewVerdict        string
}

func p02ReadFacts(v p02Value) p02Facts {
	out := p02Facts{}
	out.artifactZipSHA256 = p02Get(v, "artifactZipSHA256").text
	out.binarySHA256 = p02Get(v, "binarySHA256").text
	out.binaryVCSRevision = p02Get(v, "binaryVCSRevision").text
	out.cohortScopeSHA256 = p02Get(v, "cohortScopeSHA256").text
	out.contractSetSHA256 = p02Get(v, "contractSetSHA256").text
	out.designRegistrationSHA256 = p02Get(v, "designRegistrationSHA256").text
	out.graphSHA256 = p02Get(v, "graphSHA256").text
	out.helperClosureSHA256 = p02Get(v, "helperClosureSHA256").text
	out.installationBinarySHA256 = p02Get(v, "installationBinarySHA256").text
	out.installationReceiptSHA256 = p02Get(v, "installationReceiptSHA256").text
	out.installationSourceSHA = p02Get(v, "installationSourceSHA").text
	out.keyGrantsSHA256 = p02Get(v, "keyGrantsSHA256").text
	out.linkedClosureSHA256 = p02Get(v, "linkedClosureSHA256").text
	out.moduleClosureSHA256 = p02Get(v, "moduleClosureSHA256").text
	out.policyPayloadSHA256 = p02Get(v, "policyPayloadSHA256").text
	out.registryProofSlotsSHA256 = p02Get(v, "registryProofSlotsSHA256").text
	out.reviewCoverageSHA256 = p02Get(v, "reviewCoverageSHA256").text
	out.rootChoiceSHA256 = p02Get(v, "rootChoiceSHA256").text
	out.runningBinarySHA256 = p02Get(v, "runningBinarySHA256").text
	out.runningLinkedClosureSHA256 = p02Get(v, "runningLinkedClosureSHA256").text
	out.runningMeasurementSHA256 = p02Get(v, "runningMeasurementSHA256").text
	out.runningReceiptSHA256 = p02Get(v, "runningReceiptSHA256").text
	out.runningRuntimeLockSHA256 = p02Get(v, "runningRuntimeLockSHA256").text
	out.runningSourceSHA = p02Get(v, "runningSourceSHA").text
	out.runtimeLockSHA256 = p02Get(v, "runtimeLockSHA256").text
	out.semanticPinsSHA256 = p02Get(v, "semanticPinsSHA256").text
	out.sourceAcquisitionSHA256 = p02Get(v, "sourceAcquisitionSHA256").text
	out.sourceEquivalenceSHA256 = p02Get(v, "sourceEquivalenceSHA256").text
	out.sourcePublicationAnchorSHA256 = p02Get(v, "sourcePublicationAnchorSHA256").text
	out.sourceSHA = p02Get(v, "sourceSHA").text
	out.sourceTreeSHA256 = p02Get(v, "sourceTreeSHA256").text
	out.toolchain = p02Get(v, "toolchain").text
	out.artifactId = p02Get(v, "artifactId").integer
	out.artifactZipBytes = p02Get(v, "artifactZipBytes").integer
	out.binaryVCSModified = p02Get(v, "binaryVCSModified").boolean
	out.effectiveReviewSHA = p02Get(v, "effectiveReviewSHA").text
	out.effectiveReviewTargetSHA = p02Get(v, "effectiveReviewTargetSHA").text
	out.effectiveReviewScope = p02Get(v, "effectiveReviewScope").text
	out.effectiveReviewVerdict = p02Get(v, "effectiveReviewVerdict").text
	return out
}
func p02ValueFacts(v p02Facts) p02Value {
	out := p02Object()

	out.object = append(out.object, p02Field{"artifactZipSHA256", p02String(v.artifactZipSHA256)})

	out.object = append(out.object, p02Field{"binarySHA256", p02String(v.binarySHA256)})

	out.object = append(out.object, p02Field{"binaryVCSRevision", p02String(v.binaryVCSRevision)})

	out.object = append(out.object, p02Field{"cohortScopeSHA256", p02String(v.cohortScopeSHA256)})

	out.object = append(out.object, p02Field{"contractSetSHA256", p02String(v.contractSetSHA256)})

	out.object = append(out.object, p02Field{"designRegistrationSHA256", p02String(v.designRegistrationSHA256)})

	out.object = append(out.object, p02Field{"graphSHA256", p02String(v.graphSHA256)})

	out.object = append(out.object, p02Field{"helperClosureSHA256", p02String(v.helperClosureSHA256)})

	out.object = append(out.object, p02Field{"installationBinarySHA256", p02String(v.installationBinarySHA256)})

	out.object = append(out.object, p02Field{"installationReceiptSHA256", p02String(v.installationReceiptSHA256)})

	out.object = append(out.object, p02Field{"installationSourceSHA", p02String(v.installationSourceSHA)})

	out.object = append(out.object, p02Field{"keyGrantsSHA256", p02String(v.keyGrantsSHA256)})

	out.object = append(out.object, p02Field{"linkedClosureSHA256", p02String(v.linkedClosureSHA256)})

	out.object = append(out.object, p02Field{"moduleClosureSHA256", p02String(v.moduleClosureSHA256)})

	out.object = append(out.object, p02Field{"policyPayloadSHA256", p02String(v.policyPayloadSHA256)})

	out.object = append(out.object, p02Field{"registryProofSlotsSHA256", p02String(v.registryProofSlotsSHA256)})

	out.object = append(out.object, p02Field{"reviewCoverageSHA256", p02String(v.reviewCoverageSHA256)})

	out.object = append(out.object, p02Field{"rootChoiceSHA256", p02String(v.rootChoiceSHA256)})

	out.object = append(out.object, p02Field{"runningBinarySHA256", p02String(v.runningBinarySHA256)})

	out.object = append(out.object, p02Field{"runningLinkedClosureSHA256", p02String(v.runningLinkedClosureSHA256)})

	out.object = append(out.object, p02Field{"runningMeasurementSHA256", p02String(v.runningMeasurementSHA256)})

	out.object = append(out.object, p02Field{"runningReceiptSHA256", p02String(v.runningReceiptSHA256)})

	out.object = append(out.object, p02Field{"runningRuntimeLockSHA256", p02String(v.runningRuntimeLockSHA256)})

	out.object = append(out.object, p02Field{"runningSourceSHA", p02String(v.runningSourceSHA)})

	out.object = append(out.object, p02Field{"runtimeLockSHA256", p02String(v.runtimeLockSHA256)})

	out.object = append(out.object, p02Field{"semanticPinsSHA256", p02String(v.semanticPinsSHA256)})

	out.object = append(out.object, p02Field{"sourceAcquisitionSHA256", p02String(v.sourceAcquisitionSHA256)})

	out.object = append(out.object, p02Field{"sourceEquivalenceSHA256", p02String(v.sourceEquivalenceSHA256)})

	out.object = append(out.object, p02Field{"sourcePublicationAnchorSHA256", p02String(v.sourcePublicationAnchorSHA256)})

	out.object = append(out.object, p02Field{"sourceSHA", p02String(v.sourceSHA)})

	out.object = append(out.object, p02Field{"sourceTreeSHA256", p02String(v.sourceTreeSHA256)})

	out.object = append(out.object, p02Field{"toolchain", p02String(v.toolchain)})

	out.object = append(out.object, p02Field{"artifactId", p02Integer(v.artifactId)})

	out.object = append(out.object, p02Field{"artifactZipBytes", p02Integer(v.artifactZipBytes)})

	out.object = append(out.object, p02Field{"binaryVCSModified", p02Boolean(v.binaryVCSModified)})

	out.object = append(out.object, p02Field{"effectiveReviewSHA", p02String(v.effectiveReviewSHA)})

	out.object = append(out.object, p02Field{"effectiveReviewTargetSHA", p02String(v.effectiveReviewTargetSHA)})

	out.object = append(out.object, p02Field{"effectiveReviewScope", p02String(v.effectiveReviewScope)})

	out.object = append(out.object, p02Field{"effectiveReviewVerdict", p02String(v.effectiveReviewVerdict)})
	return out
}

type p02Run struct {
	runId       int64
	repository  string
	headSHA     string
	ref         string
	event       string
	workflow    string
	correlation string
	attempt     int64
	conclusion  string
	jobs        []p02Job
}

func p02ReadRun(v p02Value) p02Run {
	out := p02Run{}
	out.runId = p02Get(v, "runId").integer
	out.repository = p02Get(v, "repository").text
	out.headSHA = p02Get(v, "headSHA").text
	out.ref = p02Get(v, "ref").text
	out.event = p02Get(v, "event").text
	out.workflow = p02Get(v, "workflow").text
	out.correlation = p02Get(v, "correlation").text
	out.attempt = p02Get(v, "attempt").integer
	out.conclusion = p02Get(v, "conclusion").text
	for _, child := range p02Get(v, "jobs").array {
		out.jobs = append(out.jobs, p02ReadJob(child))
	}
	return out
}
func p02ValueRun(v p02Run) p02Value {
	out := p02Object()

	out.object = append(out.object, p02Field{"runId", p02Integer(v.runId)})

	out.object = append(out.object, p02Field{"repository", p02String(v.repository)})

	out.object = append(out.object, p02Field{"headSHA", p02String(v.headSHA)})

	out.object = append(out.object, p02Field{"ref", p02String(v.ref)})

	out.object = append(out.object, p02Field{"event", p02String(v.event)})

	out.object = append(out.object, p02Field{"workflow", p02String(v.workflow)})

	out.object = append(out.object, p02Field{"correlation", p02String(v.correlation)})

	out.object = append(out.object, p02Field{"attempt", p02Integer(v.attempt)})

	out.object = append(out.object, p02Field{"conclusion", p02String(v.conclusion)})
	xjobs := p02Array(nil)
	for _, child := range v.jobs {
		xjobs.array = append(xjobs.array, p02ValueJob(child))
	}
	out.object = append(out.object, p02Field{"jobs", xjobs})
	return out
}

type p02Job struct {
	id         int64
	name       string
	conclusion string
	steps      []p02Step
}

func p02ReadJob(v p02Value) p02Job {
	out := p02Job{}
	out.id = p02Get(v, "id").integer
	out.name = p02Get(v, "name").text
	out.conclusion = p02Get(v, "conclusion").text
	for _, child := range p02Get(v, "steps").array {
		out.steps = append(out.steps, p02ReadStep(child))
	}
	return out
}
func p02ValueJob(v p02Job) p02Value {
	out := p02Object()

	out.object = append(out.object, p02Field{"id", p02Integer(v.id)})

	out.object = append(out.object, p02Field{"name", p02String(v.name)})

	out.object = append(out.object, p02Field{"conclusion", p02String(v.conclusion)})
	xsteps := p02Array(nil)
	for _, child := range v.steps {
		xsteps.array = append(xsteps.array, p02ValueStep(child))
	}
	out.object = append(out.object, p02Field{"steps", xsteps})
	return out
}

type p02Step struct {
	number     int64
	name       string
	conclusion string
}

func p02ReadStep(v p02Value) p02Step {
	out := p02Step{}
	out.number = p02Get(v, "number").integer
	out.name = p02Get(v, "name").text
	out.conclusion = p02Get(v, "conclusion").text
	return out
}
func p02ValueStep(v p02Step) p02Value {
	out := p02Object()

	out.object = append(out.object, p02Field{"number", p02Integer(v.number)})

	out.object = append(out.object, p02Field{"name", p02String(v.name)})

	out.object = append(out.object, p02Field{"conclusion", p02String(v.conclusion)})
	return out
}

type p02Review struct {
	ordinal            int64
	reviewSHA          string
	targetSHA          string
	verdict            string
	scopeId            string
	scopeUTF8Hex       string
	scopeSHA256        string
	reviewerId         string
	reviewerSPKISHA256 string
	rawReviewSHA256    string
}

func p02ReadReview(v p02Value) p02Review {
	out := p02Review{}
	out.ordinal = p02Get(v, "ordinal").integer
	out.reviewSHA = p02Get(v, "reviewSHA").text
	out.targetSHA = p02Get(v, "targetSHA").text
	out.verdict = p02Get(v, "verdict").text
	out.scopeId = p02Get(v, "scopeId").text
	out.scopeUTF8Hex = p02Get(v, "scopeUTF8Hex").text
	out.scopeSHA256 = p02Get(v, "scopeSHA256").text
	out.reviewerId = p02Get(v, "reviewerId").text
	out.reviewerSPKISHA256 = p02Get(v, "reviewerSPKISHA256").text
	out.rawReviewSHA256 = p02Get(v, "rawReviewSHA256").text
	return out
}
func p02ValueReview(v p02Review) p02Value {
	out := p02Object()

	out.object = append(out.object, p02Field{"ordinal", p02Integer(v.ordinal)})

	out.object = append(out.object, p02Field{"reviewSHA", p02String(v.reviewSHA)})

	out.object = append(out.object, p02Field{"targetSHA", p02String(v.targetSHA)})

	out.object = append(out.object, p02Field{"verdict", p02String(v.verdict)})

	out.object = append(out.object, p02Field{"scopeId", p02String(v.scopeId)})

	out.object = append(out.object, p02Field{"scopeUTF8Hex", p02String(v.scopeUTF8Hex)})

	out.object = append(out.object, p02Field{"scopeSHA256", p02String(v.scopeSHA256)})

	out.object = append(out.object, p02Field{"reviewerId", p02String(v.reviewerId)})

	out.object = append(out.object, p02Field{"reviewerSPKISHA256", p02String(v.reviewerSPKISHA256)})

	out.object = append(out.object, p02Field{"rawReviewSHA256", p02String(v.rawReviewSHA256)})
	return out
}

type p02Payload struct {
	selector              string
	version               string
	verifier              p02Verifier
	contractPins          map[string]p02Pin
	grants                []p02WireGrant
	cohortId              string
	members               []p02Member
	graphHex              string
	nodeKinds             map[string]string
	proofSlotRegistryHex  string
	designRegistrationHex string
	semanticPins          p02SemanticPins
}

func p02ReadPayload(v p02Value) p02Payload {
	out := p02Payload{}
	out.selector = p02Get(v, "selector").text
	out.version = p02Get(v, "version").text
	out.verifier = p02ReadVerifier(p02Get(v, "verifier"))
	out.contractPins = make(map[string]p02Pin)
	for _, f := range p02Get(v, "contractPins").object {
		out.contractPins[f.key] = p02ReadPin(f.value)
	}
	for _, child := range p02Get(v, "grants").array {
		out.grants = append(out.grants, p02ReadWireGrant(child))
	}
	out.cohortId = p02Get(v, "cohortId").text
	for _, child := range p02Get(v, "members").array {
		out.members = append(out.members, p02ReadMember(child))
	}
	out.graphHex = p02Get(v, "graphHex").text
	out.nodeKinds = make(map[string]string)
	for _, f := range p02Get(v, "nodeKinds").object {
		out.nodeKinds[f.key] = f.value.text
	}
	out.proofSlotRegistryHex = p02Get(v, "proofSlotRegistryHex").text
	out.designRegistrationHex = p02Get(v, "designRegistrationHex").text
	out.semanticPins = p02ReadSemanticPins(p02Get(v, "semanticPins"))
	return out
}
func p02ValuePayload(v p02Payload) p02Value {
	out := p02Object()

	out.object = append(out.object, p02Field{"selector", p02String(v.selector)})

	out.object = append(out.object, p02Field{"version", p02String(v.version)})

	out.object = append(out.object, p02Field{"verifier", p02ValueVerifier(v.verifier)})
	xcontractPins := p02Object()
	for k, x := range v.contractPins {
		xcontractPins.object = append(xcontractPins.object, p02Field{k, p02ValuePin(x)})
	}
	out.object = append(out.object, p02Field{"contractPins", xcontractPins})
	xgrants := p02Array(nil)
	for _, child := range v.grants {
		xgrants.array = append(xgrants.array, p02ValueWireGrant(child))
	}
	out.object = append(out.object, p02Field{"grants", xgrants})

	out.object = append(out.object, p02Field{"cohortId", p02String(v.cohortId)})
	xmembers := p02Array(nil)
	for _, child := range v.members {
		xmembers.array = append(xmembers.array, p02ValueMember(child))
	}
	out.object = append(out.object, p02Field{"members", xmembers})

	out.object = append(out.object, p02Field{"graphHex", p02String(v.graphHex)})
	xnodeKinds := p02Object()
	for k, x := range v.nodeKinds {
		xnodeKinds.object = append(xnodeKinds.object, p02Field{k, p02String(x)})
	}
	out.object = append(out.object, p02Field{"nodeKinds", xnodeKinds})

	out.object = append(out.object, p02Field{"proofSlotRegistryHex", p02String(v.proofSlotRegistryHex)})

	out.object = append(out.object, p02Field{"designRegistrationHex", p02String(v.designRegistrationHex)})

	out.object = append(out.object, p02Field{"semanticPins", p02ValueSemanticPins(v.semanticPins)})
	return out
}

type p02Verifier struct {
	id             string
	sourceSHA      string
	artifactSHA256 string
	reviewSHA      string
	ciRunIDs       []int64
}

func p02ReadVerifier(v p02Value) p02Verifier {
	out := p02Verifier{}
	out.id = p02Get(v, "id").text
	out.sourceSHA = p02Get(v, "sourceSHA").text
	out.artifactSHA256 = p02Get(v, "artifactSHA256").text
	out.reviewSHA = p02Get(v, "reviewSHA").text
	for _, child := range p02Get(v, "ciRunIDs").array {
		out.ciRunIDs = append(out.ciRunIDs, child.integer)
	}
	return out
}
func p02ValueVerifier(v p02Verifier) p02Value {
	out := p02Object()

	out.object = append(out.object, p02Field{"id", p02String(v.id)})

	out.object = append(out.object, p02Field{"sourceSHA", p02String(v.sourceSHA)})

	out.object = append(out.object, p02Field{"artifactSHA256", p02String(v.artifactSHA256)})

	out.object = append(out.object, p02Field{"reviewSHA", p02String(v.reviewSHA)})
	xciRunIDs := p02Array(nil)
	for _, child := range v.ciRunIDs {
		xciRunIDs.array = append(xciRunIDs.array, p02Integer(child))
	}
	out.object = append(out.object, p02Field{"ciRunIDs", xciRunIDs})
	return out
}

type p02Pin struct {
	contractSHA256   string
	schemaSHA256     string
	codec            string
	requiredVerifier string
}

func p02ReadPin(v p02Value) p02Pin {
	out := p02Pin{}
	out.contractSHA256 = p02Get(v, "contractSHA256").text
	out.schemaSHA256 = p02Get(v, "schemaSHA256").text
	out.codec = p02Get(v, "codec").text
	out.requiredVerifier = p02Get(v, "requiredVerifier").text
	return out
}
func p02ValuePin(v p02Pin) p02Value {
	out := p02Object()

	out.object = append(out.object, p02Field{"contractSHA256", p02String(v.contractSHA256)})

	out.object = append(out.object, p02Field{"schemaSHA256", p02String(v.schemaSHA256)})

	out.object = append(out.object, p02Field{"codec", p02String(v.codec)})

	out.object = append(out.object, p02Field{"requiredVerifier", p02String(v.requiredVerifier)})
	return out
}

type p02WireGrant struct {
	role                string
	authorityScopeC2Hex string
	publicKeyHex        string
	notBefore           int64
	notAfter            int64
}

func p02ReadWireGrant(v p02Value) p02WireGrant {
	out := p02WireGrant{}
	out.role = p02Get(v, "role").text
	out.authorityScopeC2Hex = p02Get(v, "authorityScopeC2Hex").text
	out.publicKeyHex = p02Get(v, "publicKeyHex").text
	out.notBefore = p02Get(v, "notBefore").integer
	out.notAfter = p02Get(v, "notAfter").integer
	return out
}
func p02ValueWireGrant(v p02WireGrant) p02Value {
	out := p02Object()

	out.object = append(out.object, p02Field{"role", p02String(v.role)})

	out.object = append(out.object, p02Field{"authorityScopeC2Hex", p02String(v.authorityScopeC2Hex)})

	out.object = append(out.object, p02Field{"publicKeyHex", p02String(v.publicKeyHex)})

	out.object = append(out.object, p02Field{"notBefore", p02Integer(v.notBefore)})

	out.object = append(out.object, p02Field{"notAfter", p02Integer(v.notAfter)})
	return out
}

type p02Member struct {
	slot              string
	scope             p02NodeScope
	certificateDERHex string
	caRootDERHex      string
}

func p02ReadMember(v p02Value) p02Member {
	out := p02Member{}
	out.slot = p02Get(v, "slot").text
	out.scope = p02ReadNodeScope(p02Get(v, "scope"))
	out.certificateDERHex = p02Get(v, "certificateDERHex").text
	out.caRootDERHex = p02Get(v, "caRootDERHex").text
	return out
}
func p02ValueMember(v p02Member) p02Value {
	out := p02Object()

	out.object = append(out.object, p02Field{"slot", p02String(v.slot)})

	out.object = append(out.object, p02Field{"scope", p02ValueNodeScope(v.scope)})

	out.object = append(out.object, p02Field{"certificateDERHex", p02String(v.certificateDERHex)})

	out.object = append(out.object, p02Field{"caRootDERHex", p02String(v.caRootDERHex)})
	return out
}

type p02NodeScope struct {
	tenantId      string
	nodeId        string
	recoveryEpoch string
}

func p02ReadNodeScope(v p02Value) p02NodeScope {
	out := p02NodeScope{}
	out.tenantId = p02Get(v, "tenantId").text
	out.nodeId = p02Get(v, "nodeId").text
	out.recoveryEpoch = p02Get(v, "recoveryEpoch").text
	return out
}
func p02ValueNodeScope(v p02NodeScope) p02Value {
	out := p02Object()

	out.object = append(out.object, p02Field{"tenantId", p02String(v.tenantId)})

	out.object = append(out.object, p02Field{"nodeId", p02String(v.nodeId)})

	out.object = append(out.object, p02Field{"recoveryEpoch", p02String(v.recoveryEpoch)})
	return out
}

type p02SemanticPins struct {
	k1SourcePinSetSHA256        string
	recipeDefinitionsSHA256     string
	derivedDigestContractSHA256 string
	proofSlotRegistrySHA256     string
	graphSHA256                 string
	nodeKindsSHA256             string
}

func p02ReadSemanticPins(v p02Value) p02SemanticPins {
	out := p02SemanticPins{}
	out.k1SourcePinSetSHA256 = p02Get(v, "k1SourcePinSetSHA256").text
	out.recipeDefinitionsSHA256 = p02Get(v, "recipeDefinitionsSHA256").text
	out.derivedDigestContractSHA256 = p02Get(v, "derivedDigestContractSHA256").text
	out.proofSlotRegistrySHA256 = p02Get(v, "proofSlotRegistrySHA256").text
	out.graphSHA256 = p02Get(v, "graphSHA256").text
	out.nodeKindsSHA256 = p02Get(v, "nodeKindsSHA256").text
	return out
}
func p02ValueSemanticPins(v p02SemanticPins) p02Value {
	out := p02Object()

	out.object = append(out.object, p02Field{"k1SourcePinSetSHA256", p02String(v.k1SourcePinSetSHA256)})

	out.object = append(out.object, p02Field{"recipeDefinitionsSHA256", p02String(v.recipeDefinitionsSHA256)})

	out.object = append(out.object, p02Field{"derivedDigestContractSHA256", p02String(v.derivedDigestContractSHA256)})

	out.object = append(out.object, p02Field{"proofSlotRegistrySHA256", p02String(v.proofSlotRegistrySHA256)})

	out.object = append(out.object, p02Field{"graphSHA256", p02String(v.graphSHA256)})

	out.object = append(out.object, p02Field{"nodeKindsSHA256", p02String(v.nodeKindsSHA256)})
	return out
}

type p02SourceFacts struct {
	artifactZipSHA256             string
	binarySHA256                  string
	binaryVCSRevision             string
	cohortScopeSHA256             string
	contractSetSHA256             string
	designRegistrationSHA256      string
	graphSHA256                   string
	helperClosureSHA256           string
	installationBinarySHA256      string
	installationReceiptSHA256     string
	installationSourceSHA         string
	keyGrantsSHA256               string
	linkedClosureSHA256           string
	moduleClosureSHA256           string
	policyPayloadSHA256           string
	registryProofSlotsSHA256      string
	reviewCoverageSHA256          string
	rootChoiceSHA256              string
	runningBinarySHA256           string
	runningLinkedClosureSHA256    string
	runningReceiptSHA256          string
	runningRuntimeLockSHA256      string
	runningSourceSHA              string
	runtimeLockSHA256             string
	semanticPinsSHA256            string
	sourceAcquisitionSHA256       string
	sourceEquivalenceSHA256       string
	sourcePublicationAnchorSHA256 string
	sourceSHA                     string
	sourceTreeSHA256              string
	toolchain                     string
	artifactId                    int64
	artifactZipBytes              int64
	binaryVCSModified             bool
	effectiveReviewSHA            string
	effectiveReviewTargetSHA      string
	effectiveReviewScope          string
	effectiveReviewVerdict        string
}

func p02SourceMatches(f p02Facts, s p02SourceFacts) bool {
	return f.artifactZipSHA256 == s.artifactZipSHA256 && f.binarySHA256 == s.binarySHA256 && f.binaryVCSRevision == s.binaryVCSRevision && f.cohortScopeSHA256 == s.cohortScopeSHA256 && f.contractSetSHA256 == s.contractSetSHA256 && f.designRegistrationSHA256 == s.designRegistrationSHA256 && f.graphSHA256 == s.graphSHA256 && f.helperClosureSHA256 == s.helperClosureSHA256 && f.installationBinarySHA256 == s.installationBinarySHA256 && f.installationReceiptSHA256 == s.installationReceiptSHA256 && f.installationSourceSHA == s.installationSourceSHA && f.keyGrantsSHA256 == s.keyGrantsSHA256 && f.linkedClosureSHA256 == s.linkedClosureSHA256 && f.moduleClosureSHA256 == s.moduleClosureSHA256 && f.policyPayloadSHA256 == s.policyPayloadSHA256 && f.registryProofSlotsSHA256 == s.registryProofSlotsSHA256 && f.reviewCoverageSHA256 == s.reviewCoverageSHA256 && f.rootChoiceSHA256 == s.rootChoiceSHA256 && f.runningBinarySHA256 == s.runningBinarySHA256 && f.runningLinkedClosureSHA256 == s.runningLinkedClosureSHA256 && f.runningReceiptSHA256 == s.runningReceiptSHA256 && f.runningRuntimeLockSHA256 == s.runningRuntimeLockSHA256 && f.runningSourceSHA == s.runningSourceSHA && f.runtimeLockSHA256 == s.runtimeLockSHA256 && f.semanticPinsSHA256 == s.semanticPinsSHA256 && f.sourceAcquisitionSHA256 == s.sourceAcquisitionSHA256 && f.sourceEquivalenceSHA256 == s.sourceEquivalenceSHA256 && f.sourcePublicationAnchorSHA256 == s.sourcePublicationAnchorSHA256 && f.sourceSHA == s.sourceSHA && f.sourceTreeSHA256 == s.sourceTreeSHA256 && f.toolchain == s.toolchain && f.artifactId == s.artifactId && f.artifactZipBytes == s.artifactZipBytes && f.binaryVCSModified == s.binaryVCSModified && f.effectiveReviewSHA == s.effectiveReviewSHA && f.effectiveReviewTargetSHA == s.effectiveReviewTargetSHA && f.effectiveReviewScope == s.effectiveReviewScope && f.effectiveReviewVerdict == s.effectiveReviewVerdict
}
