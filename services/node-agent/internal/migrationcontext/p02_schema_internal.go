package migrationcontext

// Generated ONLY from the three immutable accepted Rev2 schemas at84ee base.
// Fixed functions, not a runtime schema loader, regex engine or callback dispatch.
func p02Pattern(id int, s string) bool {
	switch id {
	case 0:
		return validSelector(s)
	case 1:
		return p02Hex(s, 64, false)
	case 2:
		return p02Hex(s, 40, false)
	case 3:
		return len(s) > 0 && p02ASCII(s)
	case 4:
		return p02Hex(s, 0, false)
	case 5:
		return p02Hex(s, 128, false)
	case 6:
		if len(s) < 1 || len(s) > 16 || s[0] < '1' || s[0] > '9' {
			return false
		}
		for j := 1; j < len(s); j++ {
			if p02Digit(s[j]) < 0 {
				return false
			}
		}
		return true
	}
	return false
}
func p02Schema2(v p02Value) bool {
	if v.kind != 's' || v.text != "fleet5-p02-registry-candidate:2" {
		return false
	}
	return true
}

func p02Schema3(v p02Value) bool {
	if v.kind != 's' || v.text != "installed-policy-registry" {
		return false
	}
	return true
}

func p02Schema4(v p02Value) bool {
	if v.kind != 's' {
		return false
	}
	if !p02Pattern(0, v.text) {
		return false
	}
	return true
}

func p02Schema5(v p02Value) bool {
	if v.kind != 's' {
		return false
	}
	if !p02Pattern(1, v.text) {
		return false
	}
	nonzero := false
	for i := 0; i < len(v.text); i++ {
		if v.text[i] != '0' {
			nonzero = true
		}
	}
	if !nonzero {
		return false
	}
	return true
}

func p02Schema6(v p02Value) bool {
	if v.kind != 'i' {
		return false
	}
	if v.integer < 1 {
		return false
	}
	if v.integer > 9007199254740991 {
		return false
	}
	return true
}

func p02Schema8(v p02Value) bool {
	if v.kind != 's' {
		return false
	}
	if !p02Pattern(2, v.text) {
		return false
	}
	nonzero := false
	for i := 0; i < len(v.text); i++ {
		if v.text[i] != '0' {
			nonzero = true
		}
	}
	if !nonzero {
		return false
	}
	return true
}

func p02Schema9(v p02Value) bool {
	if v.kind != 's' {
		return false
	}
	if len(v.text) < 1 {
		return false
	}
	if len(v.text) > 256 {
		return false
	}
	if !p02Pattern(3, v.text) {
		return false
	}
	return true
}

func p02Schema10(v p02Value) bool {
	if v.kind != 'b' {
		return false
	}
	return true
}

func p02Schema7(v p02Value) bool {
	if v.kind != 'o' {
		return false
	}
	if len(v.object) != 39 {
		return false
	}
	if p02Get(v, "artifactZipSHA256").kind == 0 {
		return false
	}
	if p02Get(v, "binarySHA256").kind == 0 {
		return false
	}
	if p02Get(v, "binaryVCSRevision").kind == 0 {
		return false
	}
	if p02Get(v, "cohortScopeSHA256").kind == 0 {
		return false
	}
	if p02Get(v, "contractSetSHA256").kind == 0 {
		return false
	}
	if p02Get(v, "designRegistrationSHA256").kind == 0 {
		return false
	}
	if p02Get(v, "graphSHA256").kind == 0 {
		return false
	}
	if p02Get(v, "helperClosureSHA256").kind == 0 {
		return false
	}
	if p02Get(v, "installationBinarySHA256").kind == 0 {
		return false
	}
	if p02Get(v, "installationReceiptSHA256").kind == 0 {
		return false
	}
	if p02Get(v, "installationSourceSHA").kind == 0 {
		return false
	}
	if p02Get(v, "keyGrantsSHA256").kind == 0 {
		return false
	}
	if p02Get(v, "linkedClosureSHA256").kind == 0 {
		return false
	}
	if p02Get(v, "moduleClosureSHA256").kind == 0 {
		return false
	}
	if p02Get(v, "policyPayloadSHA256").kind == 0 {
		return false
	}
	if p02Get(v, "registryProofSlotsSHA256").kind == 0 {
		return false
	}
	if p02Get(v, "reviewCoverageSHA256").kind == 0 {
		return false
	}
	if p02Get(v, "rootChoiceSHA256").kind == 0 {
		return false
	}
	if p02Get(v, "runningBinarySHA256").kind == 0 {
		return false
	}
	if p02Get(v, "runningLinkedClosureSHA256").kind == 0 {
		return false
	}
	if p02Get(v, "runningMeasurementSHA256").kind == 0 {
		return false
	}
	if p02Get(v, "runningReceiptSHA256").kind == 0 {
		return false
	}
	if p02Get(v, "runningRuntimeLockSHA256").kind == 0 {
		return false
	}
	if p02Get(v, "runningSourceSHA").kind == 0 {
		return false
	}
	if p02Get(v, "runtimeLockSHA256").kind == 0 {
		return false
	}
	if p02Get(v, "semanticPinsSHA256").kind == 0 {
		return false
	}
	if p02Get(v, "sourceAcquisitionSHA256").kind == 0 {
		return false
	}
	if p02Get(v, "sourceEquivalenceSHA256").kind == 0 {
		return false
	}
	if p02Get(v, "sourcePublicationAnchorSHA256").kind == 0 {
		return false
	}
	if p02Get(v, "sourceSHA").kind == 0 {
		return false
	}
	if p02Get(v, "sourceTreeSHA256").kind == 0 {
		return false
	}
	if p02Get(v, "toolchain").kind == 0 {
		return false
	}
	if p02Get(v, "artifactId").kind == 0 {
		return false
	}
	if p02Get(v, "artifactZipBytes").kind == 0 {
		return false
	}
	if p02Get(v, "binaryVCSModified").kind == 0 {
		return false
	}
	if p02Get(v, "effectiveReviewSHA").kind == 0 {
		return false
	}
	if p02Get(v, "effectiveReviewTargetSHA").kind == 0 {
		return false
	}
	if p02Get(v, "effectiveReviewScope").kind == 0 {
		return false
	}
	if p02Get(v, "effectiveReviewVerdict").kind == 0 {
		return false
	}
	for _, field := range v.object {
		switch field.key {
		case "artifactZipSHA256":
			if !p02Schema5(field.value) {
				return false
			}
		case "binarySHA256":
			if !p02Schema5(field.value) {
				return false
			}
		case "binaryVCSRevision":
			if !p02Schema8(field.value) {
				return false
			}
		case "cohortScopeSHA256":
			if !p02Schema5(field.value) {
				return false
			}
		case "contractSetSHA256":
			if !p02Schema5(field.value) {
				return false
			}
		case "designRegistrationSHA256":
			if !p02Schema5(field.value) {
				return false
			}
		case "graphSHA256":
			if !p02Schema5(field.value) {
				return false
			}
		case "helperClosureSHA256":
			if !p02Schema5(field.value) {
				return false
			}
		case "installationBinarySHA256":
			if !p02Schema5(field.value) {
				return false
			}
		case "installationReceiptSHA256":
			if !p02Schema5(field.value) {
				return false
			}
		case "installationSourceSHA":
			if !p02Schema8(field.value) {
				return false
			}
		case "keyGrantsSHA256":
			if !p02Schema5(field.value) {
				return false
			}
		case "linkedClosureSHA256":
			if !p02Schema5(field.value) {
				return false
			}
		case "moduleClosureSHA256":
			if !p02Schema5(field.value) {
				return false
			}
		case "policyPayloadSHA256":
			if !p02Schema5(field.value) {
				return false
			}
		case "registryProofSlotsSHA256":
			if !p02Schema5(field.value) {
				return false
			}
		case "reviewCoverageSHA256":
			if !p02Schema5(field.value) {
				return false
			}
		case "rootChoiceSHA256":
			if !p02Schema5(field.value) {
				return false
			}
		case "runningBinarySHA256":
			if !p02Schema5(field.value) {
				return false
			}
		case "runningLinkedClosureSHA256":
			if !p02Schema5(field.value) {
				return false
			}
		case "runningMeasurementSHA256":
			if !p02Schema5(field.value) {
				return false
			}
		case "runningReceiptSHA256":
			if !p02Schema5(field.value) {
				return false
			}
		case "runningRuntimeLockSHA256":
			if !p02Schema5(field.value) {
				return false
			}
		case "runningSourceSHA":
			if !p02Schema8(field.value) {
				return false
			}
		case "runtimeLockSHA256":
			if !p02Schema5(field.value) {
				return false
			}
		case "semanticPinsSHA256":
			if !p02Schema5(field.value) {
				return false
			}
		case "sourceAcquisitionSHA256":
			if !p02Schema5(field.value) {
				return false
			}
		case "sourceEquivalenceSHA256":
			if !p02Schema5(field.value) {
				return false
			}
		case "sourcePublicationAnchorSHA256":
			if !p02Schema5(field.value) {
				return false
			}
		case "sourceSHA":
			if !p02Schema8(field.value) {
				return false
			}
		case "sourceTreeSHA256":
			if !p02Schema5(field.value) {
				return false
			}
		case "toolchain":
			if !p02Schema9(field.value) {
				return false
			}
		case "artifactId":
			if !p02Schema6(field.value) {
				return false
			}
		case "artifactZipBytes":
			if !p02Schema6(field.value) {
				return false
			}
		case "binaryVCSModified":
			if !p02Schema10(field.value) {
				return false
			}
		case "effectiveReviewSHA":
			if !p02Schema8(field.value) {
				return false
			}
		case "effectiveReviewTargetSHA":
			if !p02Schema8(field.value) {
				return false
			}
		case "effectiveReviewScope":
			if !p02Schema9(field.value) {
				return false
			}
		case "effectiveReviewVerdict":
			if !p02Schema9(field.value) {
				return false
			}
		default:
			return false
		}
	}
	return true
}

func p02Schema15(v p02Value) bool {
	if v.kind != 's' {
		return false
	}
	if len(v.text) < 1 {
		return false
	}
	if len(v.text) > 128 {
		return false
	}
	if !p02Pattern(3, v.text) {
		return false
	}
	return true
}

func p02Schema17(v p02Value) bool {
	if v.kind != 'o' {
		return false
	}
	if len(v.object) != 3 {
		return false
	}
	if p02Get(v, "number").kind == 0 {
		return false
	}
	if p02Get(v, "name").kind == 0 {
		return false
	}
	if p02Get(v, "conclusion").kind == 0 {
		return false
	}
	for _, field := range v.object {
		switch field.key {
		case "number":
			if !p02Schema6(field.value) {
				return false
			}
		case "name":
			if !p02Schema9(field.value) {
				return false
			}
		case "conclusion":
			if !p02Schema9(field.value) {
				return false
			}
		default:
			return false
		}
	}
	return true
}

func p02Schema16(v p02Value) bool {
	if v.kind != 'a' {
		return false
	}
	if len(v.array) < 1 {
		return false
	}
	if len(v.array) > 128 {
		return false
	}
	for i, child := range v.array {
		_ = i
		if !p02Schema17(child) {
			return false
		}
	}
	return true
}

func p02Schema14(v p02Value) bool {
	if v.kind != 'o' {
		return false
	}
	if len(v.object) != 4 {
		return false
	}
	if p02Get(v, "id").kind == 0 {
		return false
	}
	if p02Get(v, "name").kind == 0 {
		return false
	}
	if p02Get(v, "conclusion").kind == 0 {
		return false
	}
	if p02Get(v, "steps").kind == 0 {
		return false
	}
	for _, field := range v.object {
		switch field.key {
		case "id":
			if !p02Schema6(field.value) {
				return false
			}
		case "name":
			if !p02Schema15(field.value) {
				return false
			}
		case "conclusion":
			if !p02Schema9(field.value) {
				return false
			}
		case "steps":
			if !p02Schema16(field.value) {
				return false
			}
		default:
			return false
		}
	}
	return true
}

func p02Schema13(v p02Value) bool {
	if v.kind != 'a' {
		return false
	}
	if len(v.array) < 1 {
		return false
	}
	if len(v.array) > 8 {
		return false
	}
	for i, child := range v.array {
		_ = i
		if !p02Schema14(child) {
			return false
		}
	}
	return true
}

func p02Schema12(v p02Value) bool {
	if v.kind != 'o' {
		return false
	}
	if len(v.object) != 10 {
		return false
	}
	if p02Get(v, "runId").kind == 0 {
		return false
	}
	if p02Get(v, "repository").kind == 0 {
		return false
	}
	if p02Get(v, "headSHA").kind == 0 {
		return false
	}
	if p02Get(v, "ref").kind == 0 {
		return false
	}
	if p02Get(v, "event").kind == 0 {
		return false
	}
	if p02Get(v, "workflow").kind == 0 {
		return false
	}
	if p02Get(v, "correlation").kind == 0 {
		return false
	}
	if p02Get(v, "attempt").kind == 0 {
		return false
	}
	if p02Get(v, "conclusion").kind == 0 {
		return false
	}
	if p02Get(v, "jobs").kind == 0 {
		return false
	}
	for _, field := range v.object {
		switch field.key {
		case "runId":
			if !p02Schema6(field.value) {
				return false
			}
		case "repository":
			if !p02Schema9(field.value) {
				return false
			}
		case "headSHA":
			if !p02Schema8(field.value) {
				return false
			}
		case "ref":
			if !p02Schema9(field.value) {
				return false
			}
		case "event":
			if !p02Schema9(field.value) {
				return false
			}
		case "workflow":
			if !p02Schema9(field.value) {
				return false
			}
		case "correlation":
			if !p02Schema9(field.value) {
				return false
			}
		case "attempt":
			if !p02Schema6(field.value) {
				return false
			}
		case "conclusion":
			if !p02Schema9(field.value) {
				return false
			}
		case "jobs":
			if !p02Schema13(field.value) {
				return false
			}
		default:
			return false
		}
	}
	return true
}

func p02Schema11(v p02Value) bool {
	if v.kind != 'a' {
		return false
	}
	if len(v.array) < 1 {
		return false
	}
	if len(v.array) > 8 {
		return false
	}
	for i, child := range v.array {
		_ = i
		if !p02Schema12(child) {
			return false
		}
	}
	return true
}

func p02Schema20(v p02Value) bool {
	if v.kind != 's' {
		return false
	}
	if len(v.text) < 40 {
		return false
	}
	if len(v.text) > 40 {
		return false
	}
	if !p02Pattern(2, v.text) {
		return false
	}
	if v.text == "0000000000000000000000000000000000000000" {
		return false
	}
	return true
}

func p02Schema21(v p02Value) bool {
	if v.kind != 's' {
		return false
	}
	if len(v.text) < 2 {
		return false
	}
	if len(v.text) > 32768 {
		return false
	}
	if !p02Pattern(4, v.text) {
		return false
	}
	return true
}

func p02Schema22(v p02Value) bool {
	if v.kind != 's' {
		return false
	}
	if len(v.text) < 64 {
		return false
	}
	if len(v.text) > 64 {
		return false
	}
	if !p02Pattern(1, v.text) {
		return false
	}
	if v.text == "0000000000000000000000000000000000000000000000000000000000000000" {
		return false
	}
	return true
}

func p02Schema19(v p02Value) bool {
	if v.kind != 'o' {
		return false
	}
	if len(v.object) != 10 {
		return false
	}
	if p02Get(v, "ordinal").kind == 0 {
		return false
	}
	if p02Get(v, "reviewSHA").kind == 0 {
		return false
	}
	if p02Get(v, "targetSHA").kind == 0 {
		return false
	}
	if p02Get(v, "verdict").kind == 0 {
		return false
	}
	if p02Get(v, "scopeId").kind == 0 {
		return false
	}
	if p02Get(v, "scopeUTF8Hex").kind == 0 {
		return false
	}
	if p02Get(v, "scopeSHA256").kind == 0 {
		return false
	}
	if p02Get(v, "reviewerId").kind == 0 {
		return false
	}
	if p02Get(v, "reviewerSPKISHA256").kind == 0 {
		return false
	}
	if p02Get(v, "rawReviewSHA256").kind == 0 {
		return false
	}
	for _, field := range v.object {
		switch field.key {
		case "ordinal":
			if !p02Schema6(field.value) {
				return false
			}
		case "reviewSHA":
			if !p02Schema20(field.value) {
				return false
			}
		case "targetSHA":
			if !p02Schema20(field.value) {
				return false
			}
		case "verdict":
			if !p02Schema9(field.value) {
				return false
			}
		case "scopeId":
			if !p02Schema9(field.value) {
				return false
			}
		case "scopeUTF8Hex":
			if !p02Schema21(field.value) {
				return false
			}
		case "scopeSHA256":
			if !p02Schema22(field.value) {
				return false
			}
		case "reviewerId":
			if !p02Schema9(field.value) {
				return false
			}
		case "reviewerSPKISHA256":
			if !p02Schema22(field.value) {
				return false
			}
		case "rawReviewSHA256":
			if !p02Schema22(field.value) {
				return false
			}
		default:
			return false
		}
	}
	return true
}

func p02Schema18(v p02Value) bool {
	if v.kind != 'a' {
		return false
	}
	if len(v.array) < 1 {
		return false
	}
	if len(v.array) > 16 {
		return false
	}
	for i, child := range v.array {
		_ = i
		if !p02Schema19(child) {
			return false
		}
	}
	return true
}

func p02Schema1(v p02Value) bool {
	if v.kind != 'o' {
		return false
	}
	if len(v.object) != 14 {
		return false
	}
	if p02Get(v, "format").kind == 0 {
		return false
	}
	if p02Get(v, "purpose").kind == 0 {
		return false
	}
	if p02Get(v, "selector").kind == 0 {
		return false
	}
	if p02Get(v, "scopeSHA256").kind == 0 {
		return false
	}
	if p02Get(v, "capsuleSHA256").kind == 0 {
		return false
	}
	if p02Get(v, "provisioningGeneration").kind == 0 {
		return false
	}
	if p02Get(v, "anchorVersion").kind == 0 {
		return false
	}
	if p02Get(v, "recordVersion").kind == 0 {
		return false
	}
	if p02Get(v, "requestBindingSHA256").kind == 0 {
		return false
	}
	if p02Get(v, "issuedAt").kind == 0 {
		return false
	}
	if p02Get(v, "validUntil").kind == 0 {
		return false
	}
	if p02Get(v, "facts").kind == 0 {
		return false
	}
	if p02Get(v, "ciRuns").kind == 0 {
		return false
	}
	if p02Get(v, "reviews").kind == 0 {
		return false
	}
	for _, field := range v.object {
		switch field.key {
		case "format":
			if !p02Schema2(field.value) {
				return false
			}
		case "purpose":
			if !p02Schema3(field.value) {
				return false
			}
		case "selector":
			if !p02Schema4(field.value) {
				return false
			}
		case "scopeSHA256":
			if !p02Schema5(field.value) {
				return false
			}
		case "capsuleSHA256":
			if !p02Schema5(field.value) {
				return false
			}
		case "provisioningGeneration":
			if !p02Schema4(field.value) {
				return false
			}
		case "anchorVersion":
			if !p02Schema6(field.value) {
				return false
			}
		case "recordVersion":
			if !p02Schema6(field.value) {
				return false
			}
		case "requestBindingSHA256":
			if !p02Schema5(field.value) {
				return false
			}
		case "issuedAt":
			if !p02Schema6(field.value) {
				return false
			}
		case "validUntil":
			if !p02Schema6(field.value) {
				return false
			}
		case "facts":
			if !p02Schema7(field.value) {
				return false
			}
		case "ciRuns":
			if !p02Schema11(field.value) {
				return false
			}
		case "reviews":
			if !p02Schema18(field.value) {
				return false
			}
		default:
			return false
		}
	}
	return true
}

func p02Schema23(v p02Value) bool {
	if v.kind != 'o' {
		return false
	}
	if len(v.object) != 1 {
		return false
	}
	if p02Get(v, "keySPKISHA256").kind == 0 {
		return false
	}
	for _, field := range v.object {
		switch field.key {
		case "keySPKISHA256":
			if !p02Schema5(field.value) {
				return false
			}
		default:
			return false
		}
	}
	return true
}

func p02Schema24(v p02Value) bool {
	if v.kind != 's' {
		return false
	}
	if !p02Pattern(5, v.text) {
		return false
	}
	nonzero := false
	for i := 0; i < len(v.text); i++ {
		if v.text[i] != '0' {
			nonzero = true
		}
	}
	if !nonzero {
		return false
	}
	return true
}

func p02Schema0(v p02Value) bool {
	if v.kind != 'o' {
		return false
	}
	if len(v.object) != 3 {
		return false
	}
	if p02Get(v, "body").kind == 0 {
		return false
	}
	if p02Get(v, "signer").kind == 0 {
		return false
	}
	if p02Get(v, "signatureHex").kind == 0 {
		return false
	}
	for _, field := range v.object {
		switch field.key {
		case "body":
			if !p02Schema1(field.value) {
				return false
			}
		case "signer":
			if !p02Schema23(field.value) {
				return false
			}
		case "signatureHex":
			if !p02Schema24(field.value) {
				return false
			}
		default:
			return false
		}
	}
	return true
}

func p02Schema26(v p02Value) bool {
	if v.kind != 's' {
		return false
	}
	if len(v.text) < 1 {
		return false
	}
	if len(v.text) > 16 {
		return false
	}
	if !p02Pattern(6, v.text) {
		return false
	}
	return true
}

func p02Schema28(v p02Value) bool {
	if v.kind != 's' || v.text != "saintvision-migrationverify-k1:1" {
		return false
	}
	return true
}

func p02Schema29(v p02Value) bool {
	if v.kind != 'a' {
		return false
	}
	if len(v.array) < 1 {
		return false
	}
	if len(v.array) > 8 {
		return false
	}
	for i, child := range v.array {
		_ = i
		if !p02Schema6(child) {
			return false
		}
	}
	for i := range v.array {
		for j := 0; j < i; j++ {
			if p02Same(v.array[i], v.array[j]) {
				return false
			}
		}
	}
	return true
}

func p02Schema27(v p02Value) bool {
	if v.kind != 'o' {
		return false
	}
	if len(v.object) != 5 {
		return false
	}
	if p02Get(v, "id").kind == 0 {
		return false
	}
	if p02Get(v, "sourceSHA").kind == 0 {
		return false
	}
	if p02Get(v, "artifactSHA256").kind == 0 {
		return false
	}
	if p02Get(v, "reviewSHA").kind == 0 {
		return false
	}
	if p02Get(v, "ciRunIDs").kind == 0 {
		return false
	}
	for _, field := range v.object {
		switch field.key {
		case "id":
			if !p02Schema28(field.value) {
				return false
			}
		case "sourceSHA":
			if !p02Schema8(field.value) {
				return false
			}
		case "artifactSHA256":
			if !p02Schema5(field.value) {
				return false
			}
		case "reviewSHA":
			if !p02Schema8(field.value) {
				return false
			}
		case "ciRunIDs":
			if !p02Schema29(field.value) {
				return false
			}
		default:
			return false
		}
	}
	return true
}

func p02Schema32(v p02Value) bool {
	if v.kind != 's' || v.text != "57169c1e179332aeb41fd9c50ba9abaa01cc816564eb134eec6aeeb59a146793" {
		return false
	}
	return true
}

func p02Schema33(v p02Value) bool {
	if v.kind != 's' || v.text != "ec75c0fa90cf6ee3d5f32f591aca3042e67a5e10989f5968b106517d8e70cba4" {
		return false
	}
	return true
}

func p02Schema34(v p02Value) bool {
	if v.kind != 's' || v.text != "normalized-proof-v1" {
		return false
	}
	return true
}

func p02Schema35(v p02Value) bool {
	if v.kind != 's' || v.text != "pretrusted:build-provenance:1" {
		return false
	}
	return true
}

func p02Schema31(v p02Value) bool {
	if v.kind != 'o' {
		return false
	}
	if len(v.object) != 4 {
		return false
	}
	if p02Get(v, "contractSHA256").kind == 0 {
		return false
	}
	if p02Get(v, "schemaSHA256").kind == 0 {
		return false
	}
	if p02Get(v, "codec").kind == 0 {
		return false
	}
	if p02Get(v, "requiredVerifier").kind == 0 {
		return false
	}
	for _, field := range v.object {
		switch field.key {
		case "contractSHA256":
			if !p02Schema32(field.value) {
				return false
			}
		case "schemaSHA256":
			if !p02Schema33(field.value) {
				return false
			}
		case "codec":
			if !p02Schema34(field.value) {
				return false
			}
		case "requiredVerifier":
			if !p02Schema35(field.value) {
				return false
			}
		default:
			return false
		}
	}
	return true
}

func p02Schema37(v p02Value) bool {
	if v.kind != 's' || v.text != "6b1058699c5b2f9e57c69e4a53372dac19ca3fee6b407f9ee58f08de3f80a0bc" {
		return false
	}
	return true
}

func p02Schema38(v p02Value) bool {
	if v.kind != 's' || v.text != "9ef78efbf72c62356c3cd254c1e6fba5dbf63e3bad2bc77578365d934a09ebf1" {
		return false
	}
	return true
}

func p02Schema39(v p02Value) bool {
	if v.kind != 's' || v.text != "pretrusted:ci-attestation:1" {
		return false
	}
	return true
}

func p02Schema36(v p02Value) bool {
	if v.kind != 'o' {
		return false
	}
	if len(v.object) != 4 {
		return false
	}
	if p02Get(v, "contractSHA256").kind == 0 {
		return false
	}
	if p02Get(v, "schemaSHA256").kind == 0 {
		return false
	}
	if p02Get(v, "codec").kind == 0 {
		return false
	}
	if p02Get(v, "requiredVerifier").kind == 0 {
		return false
	}
	for _, field := range v.object {
		switch field.key {
		case "contractSHA256":
			if !p02Schema37(field.value) {
				return false
			}
		case "schemaSHA256":
			if !p02Schema38(field.value) {
				return false
			}
		case "codec":
			if !p02Schema34(field.value) {
				return false
			}
		case "requiredVerifier":
			if !p02Schema39(field.value) {
				return false
			}
		default:
			return false
		}
	}
	return true
}

func p02Schema41(v p02Value) bool {
	if v.kind != 's' || v.text != "08bdfb17d2adc7189bacf5964a27fd71e423ab3782d92a6eafd3e53b6e90c1cc" {
		return false
	}
	return true
}

func p02Schema42(v p02Value) bool {
	if v.kind != 's' || v.text != "d662dc3e3381a787f28714423dc975b21ad8a90907b137dfd8439e9467f88413" {
		return false
	}
	return true
}

func p02Schema43(v p02Value) bool {
	if v.kind != 's' || v.text != "pretrusted:descendant-quiescence:1" {
		return false
	}
	return true
}

func p02Schema40(v p02Value) bool {
	if v.kind != 'o' {
		return false
	}
	if len(v.object) != 4 {
		return false
	}
	if p02Get(v, "contractSHA256").kind == 0 {
		return false
	}
	if p02Get(v, "schemaSHA256").kind == 0 {
		return false
	}
	if p02Get(v, "codec").kind == 0 {
		return false
	}
	if p02Get(v, "requiredVerifier").kind == 0 {
		return false
	}
	for _, field := range v.object {
		switch field.key {
		case "contractSHA256":
			if !p02Schema41(field.value) {
				return false
			}
		case "schemaSHA256":
			if !p02Schema42(field.value) {
				return false
			}
		case "codec":
			if !p02Schema34(field.value) {
				return false
			}
		case "requiredVerifier":
			if !p02Schema43(field.value) {
				return false
			}
		default:
			return false
		}
	}
	return true
}

func p02Schema45(v p02Value) bool {
	if v.kind != 's' || v.text != "6c3007fe677038fc878ee1180337c72a09f99961702b7b0cb934972999c560cd" {
		return false
	}
	return true
}

func p02Schema46(v p02Value) bool {
	if v.kind != 's' || v.text != "650e913892cb3b501e387fd0461cd4db51a8711c34c799babc025b9cc6123d8b" {
		return false
	}
	return true
}

func p02Schema47(v p02Value) bool {
	if v.kind != 's' || v.text != "pretrusted:g2-planning-policy:1" {
		return false
	}
	return true
}

func p02Schema44(v p02Value) bool {
	if v.kind != 'o' {
		return false
	}
	if len(v.object) != 4 {
		return false
	}
	if p02Get(v, "contractSHA256").kind == 0 {
		return false
	}
	if p02Get(v, "schemaSHA256").kind == 0 {
		return false
	}
	if p02Get(v, "codec").kind == 0 {
		return false
	}
	if p02Get(v, "requiredVerifier").kind == 0 {
		return false
	}
	for _, field := range v.object {
		switch field.key {
		case "contractSHA256":
			if !p02Schema45(field.value) {
				return false
			}
		case "schemaSHA256":
			if !p02Schema46(field.value) {
				return false
			}
		case "codec":
			if !p02Schema34(field.value) {
				return false
			}
		case "requiredVerifier":
			if !p02Schema47(field.value) {
				return false
			}
		default:
			return false
		}
	}
	return true
}

func p02Schema49(v p02Value) bool {
	if v.kind != 's' || v.text != "39c1a706ccf54187e9182eea0f19cead9b3959902442e8d73443ed4d5dd6d974" {
		return false
	}
	return true
}

func p02Schema50(v p02Value) bool {
	if v.kind != 's' || v.text != "f59b10102399f8b3c5f91d1d61f84fb5e4372920811dbe6da3cda9cc275215c8" {
		return false
	}
	return true
}

func p02Schema51(v p02Value) bool {
	if v.kind != 's' || v.text != "pretrusted:image-distribution:1" {
		return false
	}
	return true
}

func p02Schema48(v p02Value) bool {
	if v.kind != 'o' {
		return false
	}
	if len(v.object) != 4 {
		return false
	}
	if p02Get(v, "contractSHA256").kind == 0 {
		return false
	}
	if p02Get(v, "schemaSHA256").kind == 0 {
		return false
	}
	if p02Get(v, "codec").kind == 0 {
		return false
	}
	if p02Get(v, "requiredVerifier").kind == 0 {
		return false
	}
	for _, field := range v.object {
		switch field.key {
		case "contractSHA256":
			if !p02Schema49(field.value) {
				return false
			}
		case "schemaSHA256":
			if !p02Schema50(field.value) {
				return false
			}
		case "codec":
			if !p02Schema34(field.value) {
				return false
			}
		case "requiredVerifier":
			if !p02Schema51(field.value) {
				return false
			}
		default:
			return false
		}
	}
	return true
}

func p02Schema53(v p02Value) bool {
	if v.kind != 's' || v.text != "ad81f205d924cfb93aa2f95a8f698818878adc44ce869421335b720b8861136c" {
		return false
	}
	return true
}

func p02Schema54(v p02Value) bool {
	if v.kind != 's' || v.text != "54394f4b3b8ceee9fcffb3111eb565a9ad452d19e01c4eac9e5a30f6a8847a89" {
		return false
	}
	return true
}

func p02Schema55(v p02Value) bool {
	if v.kind != 's' || v.text != "pretrusted:independent-code-review:1" {
		return false
	}
	return true
}

func p02Schema52(v p02Value) bool {
	if v.kind != 'o' {
		return false
	}
	if len(v.object) != 4 {
		return false
	}
	if p02Get(v, "contractSHA256").kind == 0 {
		return false
	}
	if p02Get(v, "schemaSHA256").kind == 0 {
		return false
	}
	if p02Get(v, "codec").kind == 0 {
		return false
	}
	if p02Get(v, "requiredVerifier").kind == 0 {
		return false
	}
	for _, field := range v.object {
		switch field.key {
		case "contractSHA256":
			if !p02Schema53(field.value) {
				return false
			}
		case "schemaSHA256":
			if !p02Schema54(field.value) {
				return false
			}
		case "codec":
			if !p02Schema34(field.value) {
				return false
			}
		case "requiredVerifier":
			if !p02Schema55(field.value) {
				return false
			}
		default:
			return false
		}
	}
	return true
}

func p02Schema57(v p02Value) bool {
	if v.kind != 's' || v.text != "c4a2ccd10b8e7e4f8aad7e18803d7d1049cbffdfcaa56ea33c711799fdd605ba" {
		return false
	}
	return true
}

func p02Schema58(v p02Value) bool {
	if v.kind != 's' || v.text != "f3bffb3e70b853236dd973550af2ff38aa5acff2593d1bb757ad3eb92c705f4f" {
		return false
	}
	return true
}

func p02Schema59(v p02Value) bool {
	if v.kind != 's' || v.text != "pretrusted:independent-plan-review:1" {
		return false
	}
	return true
}

func p02Schema56(v p02Value) bool {
	if v.kind != 'o' {
		return false
	}
	if len(v.object) != 4 {
		return false
	}
	if p02Get(v, "contractSHA256").kind == 0 {
		return false
	}
	if p02Get(v, "schemaSHA256").kind == 0 {
		return false
	}
	if p02Get(v, "codec").kind == 0 {
		return false
	}
	if p02Get(v, "requiredVerifier").kind == 0 {
		return false
	}
	for _, field := range v.object {
		switch field.key {
		case "contractSHA256":
			if !p02Schema57(field.value) {
				return false
			}
		case "schemaSHA256":
			if !p02Schema58(field.value) {
				return false
			}
		case "codec":
			if !p02Schema34(field.value) {
				return false
			}
		case "requiredVerifier":
			if !p02Schema59(field.value) {
				return false
			}
		default:
			return false
		}
	}
	return true
}

func p02Schema61(v p02Value) bool {
	if v.kind != 's' || v.text != "d31962924a87403f6117cadbd1ff29569c7181b8c63f12965c88f6d17337af79" {
		return false
	}
	return true
}

func p02Schema62(v p02Value) bool {
	if v.kind != 's' || v.text != "01e115e8f9b7268ca412cfd8a33fdf93d29c9255ff761ac81e5b6bcd87066614" {
		return false
	}
	return true
}

func p02Schema63(v p02Value) bool {
	if v.kind != 's' || v.text != "pretrusted:inventory-head-readback:1" {
		return false
	}
	return true
}

func p02Schema60(v p02Value) bool {
	if v.kind != 'o' {
		return false
	}
	if len(v.object) != 4 {
		return false
	}
	if p02Get(v, "contractSHA256").kind == 0 {
		return false
	}
	if p02Get(v, "schemaSHA256").kind == 0 {
		return false
	}
	if p02Get(v, "codec").kind == 0 {
		return false
	}
	if p02Get(v, "requiredVerifier").kind == 0 {
		return false
	}
	for _, field := range v.object {
		switch field.key {
		case "contractSHA256":
			if !p02Schema61(field.value) {
				return false
			}
		case "schemaSHA256":
			if !p02Schema62(field.value) {
				return false
			}
		case "codec":
			if !p02Schema34(field.value) {
				return false
			}
		case "requiredVerifier":
			if !p02Schema63(field.value) {
				return false
			}
		default:
			return false
		}
	}
	return true
}

func p02Schema65(v p02Value) bool {
	if v.kind != 's' || v.text != "e5fadf62766737cddc44ba463ad0f4935eaee752e55beaa9d4bae77e7c089117" {
		return false
	}
	return true
}

func p02Schema66(v p02Value) bool {
	if v.kind != 's' || v.text != "7adedccf531968117bc985819a0d621ea5ea286a7cabbe04f6233c1a4aabb8e0" {
		return false
	}
	return true
}

func p02Schema67(v p02Value) bool {
	if v.kind != 's' || v.text != "pretrusted:launch-surface-inventory:1" {
		return false
	}
	return true
}

func p02Schema64(v p02Value) bool {
	if v.kind != 'o' {
		return false
	}
	if len(v.object) != 4 {
		return false
	}
	if p02Get(v, "contractSHA256").kind == 0 {
		return false
	}
	if p02Get(v, "schemaSHA256").kind == 0 {
		return false
	}
	if p02Get(v, "codec").kind == 0 {
		return false
	}
	if p02Get(v, "requiredVerifier").kind == 0 {
		return false
	}
	for _, field := range v.object {
		switch field.key {
		case "contractSHA256":
			if !p02Schema65(field.value) {
				return false
			}
		case "schemaSHA256":
			if !p02Schema66(field.value) {
				return false
			}
		case "codec":
			if !p02Schema34(field.value) {
				return false
			}
		case "requiredVerifier":
			if !p02Schema67(field.value) {
				return false
			}
		default:
			return false
		}
	}
	return true
}

func p02Schema69(v p02Value) bool {
	if v.kind != 's' || v.text != "9ae795c1f5962c54eeafd0feb8beabdba8d6362921d994aee66489919d7ba748" {
		return false
	}
	return true
}

func p02Schema70(v p02Value) bool {
	if v.kind != 's' || v.text != "57c5db5e2533244c3ad8dd5e47c639626616b50e48ffbd32513f2c9a6d4fcfbd" {
		return false
	}
	return true
}

func p02Schema71(v p02Value) bool {
	if v.kind != 's' || v.text != "pretrusted:m2-capability:1" {
		return false
	}
	return true
}

func p02Schema68(v p02Value) bool {
	if v.kind != 'o' {
		return false
	}
	if len(v.object) != 4 {
		return false
	}
	if p02Get(v, "contractSHA256").kind == 0 {
		return false
	}
	if p02Get(v, "schemaSHA256").kind == 0 {
		return false
	}
	if p02Get(v, "codec").kind == 0 {
		return false
	}
	if p02Get(v, "requiredVerifier").kind == 0 {
		return false
	}
	for _, field := range v.object {
		switch field.key {
		case "contractSHA256":
			if !p02Schema69(field.value) {
				return false
			}
		case "schemaSHA256":
			if !p02Schema70(field.value) {
				return false
			}
		case "codec":
			if !p02Schema34(field.value) {
				return false
			}
		case "requiredVerifier":
			if !p02Schema71(field.value) {
				return false
			}
		default:
			return false
		}
	}
	return true
}

func p02Schema73(v p02Value) bool {
	if v.kind != 's' || v.text != "f801a27df679b2c78c22d5135cb951c28ba3f82f1ab7e3e02fbd02a4042e154d" {
		return false
	}
	return true
}

func p02Schema74(v p02Value) bool {
	if v.kind != 's' || v.text != "8170de0758758dc5fe5be046ff923dbb72023b58a5b5f0bf59a381c33efba29d" {
		return false
	}
	return true
}

func p02Schema75(v p02Value) bool {
	if v.kind != 's' || v.text != "pretrusted:member-progress-evidence:1" {
		return false
	}
	return true
}

func p02Schema72(v p02Value) bool {
	if v.kind != 'o' {
		return false
	}
	if len(v.object) != 4 {
		return false
	}
	if p02Get(v, "contractSHA256").kind == 0 {
		return false
	}
	if p02Get(v, "schemaSHA256").kind == 0 {
		return false
	}
	if p02Get(v, "codec").kind == 0 {
		return false
	}
	if p02Get(v, "requiredVerifier").kind == 0 {
		return false
	}
	for _, field := range v.object {
		switch field.key {
		case "contractSHA256":
			if !p02Schema73(field.value) {
				return false
			}
		case "schemaSHA256":
			if !p02Schema74(field.value) {
				return false
			}
		case "codec":
			if !p02Schema34(field.value) {
				return false
			}
		case "requiredVerifier":
			if !p02Schema75(field.value) {
				return false
			}
		default:
			return false
		}
	}
	return true
}

func p02Schema77(v p02Value) bool {
	if v.kind != 's' || v.text != "c6dcd04184732881856f2e5e2bf8e32770b3419395fef08d04f350e9c5462e86" {
		return false
	}
	return true
}

func p02Schema78(v p02Value) bool {
	if v.kind != 's' || v.text != "d5d08bd89b26749fd8d07a099a6ba7f7daa31f9a3c057c4b39a1ed90c98eee16" {
		return false
	}
	return true
}

func p02Schema79(v p02Value) bool {
	if v.kind != 's' || v.text != "pretrusted:migration-effect-readback:1" {
		return false
	}
	return true
}

func p02Schema76(v p02Value) bool {
	if v.kind != 'o' {
		return false
	}
	if len(v.object) != 4 {
		return false
	}
	if p02Get(v, "contractSHA256").kind == 0 {
		return false
	}
	if p02Get(v, "schemaSHA256").kind == 0 {
		return false
	}
	if p02Get(v, "codec").kind == 0 {
		return false
	}
	if p02Get(v, "requiredVerifier").kind == 0 {
		return false
	}
	for _, field := range v.object {
		switch field.key {
		case "contractSHA256":
			if !p02Schema77(field.value) {
				return false
			}
		case "schemaSHA256":
			if !p02Schema78(field.value) {
				return false
			}
		case "codec":
			if !p02Schema34(field.value) {
				return false
			}
		case "requiredVerifier":
			if !p02Schema79(field.value) {
				return false
			}
		default:
			return false
		}
	}
	return true
}

func p02Schema81(v p02Value) bool {
	if v.kind != 's' || v.text != "7ad54c7fc2380880ca62e9a8ba3b745dc64daecca71ca2b6ed29ff5d145f5615" {
		return false
	}
	return true
}

func p02Schema82(v p02Value) bool {
	if v.kind != 's' || v.text != "345256de3a239204fb61b4b9381bb1b30b16d99f0346e3c59481e66c4e2fb9bc" {
		return false
	}
	return true
}

func p02Schema83(v p02Value) bool {
	if v.kind != 's' || v.text != "pretrusted:migration-event-evidence:1" {
		return false
	}
	return true
}

func p02Schema80(v p02Value) bool {
	if v.kind != 'o' {
		return false
	}
	if len(v.object) != 4 {
		return false
	}
	if p02Get(v, "contractSHA256").kind == 0 {
		return false
	}
	if p02Get(v, "schemaSHA256").kind == 0 {
		return false
	}
	if p02Get(v, "codec").kind == 0 {
		return false
	}
	if p02Get(v, "requiredVerifier").kind == 0 {
		return false
	}
	for _, field := range v.object {
		switch field.key {
		case "contractSHA256":
			if !p02Schema81(field.value) {
				return false
			}
		case "schemaSHA256":
			if !p02Schema82(field.value) {
				return false
			}
		case "codec":
			if !p02Schema34(field.value) {
				return false
			}
		case "requiredVerifier":
			if !p02Schema83(field.value) {
				return false
			}
		default:
			return false
		}
	}
	return true
}

func p02Schema85(v p02Value) bool {
	if v.kind != 's' || v.text != "10ecd7182b813d5e2f64e91c585b0507091b6efe8c3acf2465e87e13d3d1eb3d" {
		return false
	}
	return true
}

func p02Schema86(v p02Value) bool {
	if v.kind != 's' || v.text != "e46e56d2fee968e83940b106e5a211f4f705e875258668c4af52927182143c7c" {
		return false
	}
	return true
}

func p02Schema87(v p02Value) bool {
	if v.kind != 's' || v.text != "pretrusted:native-two-cycle:1" {
		return false
	}
	return true
}

func p02Schema84(v p02Value) bool {
	if v.kind != 'o' {
		return false
	}
	if len(v.object) != 4 {
		return false
	}
	if p02Get(v, "contractSHA256").kind == 0 {
		return false
	}
	if p02Get(v, "schemaSHA256").kind == 0 {
		return false
	}
	if p02Get(v, "codec").kind == 0 {
		return false
	}
	if p02Get(v, "requiredVerifier").kind == 0 {
		return false
	}
	for _, field := range v.object {
		switch field.key {
		case "contractSHA256":
			if !p02Schema85(field.value) {
				return false
			}
		case "schemaSHA256":
			if !p02Schema86(field.value) {
				return false
			}
		case "codec":
			if !p02Schema34(field.value) {
				return false
			}
		case "requiredVerifier":
			if !p02Schema87(field.value) {
				return false
			}
		default:
			return false
		}
	}
	return true
}

func p02Schema89(v p02Value) bool {
	if v.kind != 's' || v.text != "09a5bdcb43d5d23bca789aeb10a400f6902efb72cf0ecbc10fb61f8b7d4ac68e" {
		return false
	}
	return true
}

func p02Schema90(v p02Value) bool {
	if v.kind != 's' || v.text != "3153c18ab404681bbfb218e72d0dbdfe671f5d30fdf9fea0f611c176f628db1d" {
		return false
	}
	return true
}

func p02Schema91(v p02Value) bool {
	if v.kind != 's' || v.text != "pretrusted:no-overlap:1" {
		return false
	}
	return true
}

func p02Schema88(v p02Value) bool {
	if v.kind != 'o' {
		return false
	}
	if len(v.object) != 4 {
		return false
	}
	if p02Get(v, "contractSHA256").kind == 0 {
		return false
	}
	if p02Get(v, "schemaSHA256").kind == 0 {
		return false
	}
	if p02Get(v, "codec").kind == 0 {
		return false
	}
	if p02Get(v, "requiredVerifier").kind == 0 {
		return false
	}
	for _, field := range v.object {
		switch field.key {
		case "contractSHA256":
			if !p02Schema89(field.value) {
				return false
			}
		case "schemaSHA256":
			if !p02Schema90(field.value) {
				return false
			}
		case "codec":
			if !p02Schema34(field.value) {
				return false
			}
		case "requiredVerifier":
			if !p02Schema91(field.value) {
				return false
			}
		default:
			return false
		}
	}
	return true
}

func p02Schema93(v p02Value) bool {
	if v.kind != 's' || v.text != "ef03e4c2a035672a829d81d43c0d09be0483c196dda4b3664451ecd3b607e4fa" {
		return false
	}
	return true
}

func p02Schema94(v p02Value) bool {
	if v.kind != 's' || v.text != "14f09f682837e8abfd84cfafc6acde88734e0d6480fec4098c0c4a60230fbf01" {
		return false
	}
	return true
}

func p02Schema95(v p02Value) bool {
	if v.kind != 's' || v.text != "native-m2-v2" {
		return false
	}
	return true
}

func p02Schema96(v p02Value) bool {
	if v.kind != 's' || v.text != "pretrusted:node-floor-v2:1" {
		return false
	}
	return true
}

func p02Schema92(v p02Value) bool {
	if v.kind != 'o' {
		return false
	}
	if len(v.object) != 4 {
		return false
	}
	if p02Get(v, "contractSHA256").kind == 0 {
		return false
	}
	if p02Get(v, "schemaSHA256").kind == 0 {
		return false
	}
	if p02Get(v, "codec").kind == 0 {
		return false
	}
	if p02Get(v, "requiredVerifier").kind == 0 {
		return false
	}
	for _, field := range v.object {
		switch field.key {
		case "contractSHA256":
			if !p02Schema93(field.value) {
				return false
			}
		case "schemaSHA256":
			if !p02Schema94(field.value) {
				return false
			}
		case "codec":
			if !p02Schema95(field.value) {
				return false
			}
		case "requiredVerifier":
			if !p02Schema96(field.value) {
				return false
			}
		default:
			return false
		}
	}
	return true
}

func p02Schema98(v p02Value) bool {
	if v.kind != 's' || v.text != "9719c303f4c31c7e0683e46a97d5405ec5d99c413351c8c3e85db3e2cc026c73" {
		return false
	}
	return true
}

func p02Schema99(v p02Value) bool {
	if v.kind != 's' || v.text != "37b7d1ca5893e70b863eac650074358df3d1151871afe487ec84a87ded902aa6" {
		return false
	}
	return true
}

func p02Schema100(v p02Value) bool {
	if v.kind != 's' || v.text != "pretrusted:old-new-no-write:1" {
		return false
	}
	return true
}

func p02Schema97(v p02Value) bool {
	if v.kind != 'o' {
		return false
	}
	if len(v.object) != 4 {
		return false
	}
	if p02Get(v, "contractSHA256").kind == 0 {
		return false
	}
	if p02Get(v, "schemaSHA256").kind == 0 {
		return false
	}
	if p02Get(v, "codec").kind == 0 {
		return false
	}
	if p02Get(v, "requiredVerifier").kind == 0 {
		return false
	}
	for _, field := range v.object {
		switch field.key {
		case "contractSHA256":
			if !p02Schema98(field.value) {
				return false
			}
		case "schemaSHA256":
			if !p02Schema99(field.value) {
				return false
			}
		case "codec":
			if !p02Schema34(field.value) {
				return false
			}
		case "requiredVerifier":
			if !p02Schema100(field.value) {
				return false
			}
		default:
			return false
		}
	}
	return true
}

func p02Schema102(v p02Value) bool {
	if v.kind != 's' || v.text != "b234a4dadeb31df06540e04d0af353a92ba05d43c42cbbafd04ed5812c3679b4" {
		return false
	}
	return true
}

func p02Schema103(v p02Value) bool {
	if v.kind != 's' || v.text != "4b521aaee09f39b4daf74448c696f24768003d9262e653fbc338561ea5a84119" {
		return false
	}
	return true
}

func p02Schema104(v p02Value) bool {
	if v.kind != 's' || v.text != "pretrusted:owned-engine-exec:1" {
		return false
	}
	return true
}

func p02Schema101(v p02Value) bool {
	if v.kind != 'o' {
		return false
	}
	if len(v.object) != 4 {
		return false
	}
	if p02Get(v, "contractSHA256").kind == 0 {
		return false
	}
	if p02Get(v, "schemaSHA256").kind == 0 {
		return false
	}
	if p02Get(v, "codec").kind == 0 {
		return false
	}
	if p02Get(v, "requiredVerifier").kind == 0 {
		return false
	}
	for _, field := range v.object {
		switch field.key {
		case "contractSHA256":
			if !p02Schema102(field.value) {
				return false
			}
		case "schemaSHA256":
			if !p02Schema103(field.value) {
				return false
			}
		case "codec":
			if !p02Schema34(field.value) {
				return false
			}
		case "requiredVerifier":
			if !p02Schema104(field.value) {
				return false
			}
		default:
			return false
		}
	}
	return true
}

func p02Schema106(v p02Value) bool {
	if v.kind != 's' || v.text != "2267728118b38c039d9dc21fe85adf8346ac38508feda76f079f59ce36126776" {
		return false
	}
	return true
}

func p02Schema107(v p02Value) bool {
	if v.kind != 's' || v.text != "6be629f142a908f8a92e68a571fe2eab72a2134ccfb1c7a23a5e92d2fe6a173a" {
		return false
	}
	return true
}

func p02Schema108(v p02Value) bool {
	if v.kind != 's' || v.text != "pretrusted:process-quiescence:1" {
		return false
	}
	return true
}

func p02Schema105(v p02Value) bool {
	if v.kind != 'o' {
		return false
	}
	if len(v.object) != 4 {
		return false
	}
	if p02Get(v, "contractSHA256").kind == 0 {
		return false
	}
	if p02Get(v, "schemaSHA256").kind == 0 {
		return false
	}
	if p02Get(v, "codec").kind == 0 {
		return false
	}
	if p02Get(v, "requiredVerifier").kind == 0 {
		return false
	}
	for _, field := range v.object {
		switch field.key {
		case "contractSHA256":
			if !p02Schema106(field.value) {
				return false
			}
		case "schemaSHA256":
			if !p02Schema107(field.value) {
				return false
			}
		case "codec":
			if !p02Schema34(field.value) {
				return false
			}
		case "requiredVerifier":
			if !p02Schema108(field.value) {
				return false
			}
		default:
			return false
		}
	}
	return true
}

func p02Schema110(v p02Value) bool {
	if v.kind != 's' || v.text != "405a06f1e7d3b3855a7920f1c5f2a14c88121854d64f4d70fd035e1221f4d9f3" {
		return false
	}
	return true
}

func p02Schema111(v p02Value) bool {
	if v.kind != 's' || v.text != "87f30c0d14e5dd738cc6c55f6108cdfbf0af56ee178f85d3a99887f32567914a" {
		return false
	}
	return true
}

func p02Schema112(v p02Value) bool {
	if v.kind != 's' || v.text != "pretrusted:protected-tree-equality:1" {
		return false
	}
	return true
}

func p02Schema109(v p02Value) bool {
	if v.kind != 'o' {
		return false
	}
	if len(v.object) != 4 {
		return false
	}
	if p02Get(v, "contractSHA256").kind == 0 {
		return false
	}
	if p02Get(v, "schemaSHA256").kind == 0 {
		return false
	}
	if p02Get(v, "codec").kind == 0 {
		return false
	}
	if p02Get(v, "requiredVerifier").kind == 0 {
		return false
	}
	for _, field := range v.object {
		switch field.key {
		case "contractSHA256":
			if !p02Schema110(field.value) {
				return false
			}
		case "schemaSHA256":
			if !p02Schema111(field.value) {
				return false
			}
		case "codec":
			if !p02Schema34(field.value) {
				return false
			}
		case "requiredVerifier":
			if !p02Schema112(field.value) {
				return false
			}
		default:
			return false
		}
	}
	return true
}

func p02Schema114(v p02Value) bool {
	if v.kind != 's' || v.text != "4e88dfd58f1e564beb6c0459d43641ec2fe903772e259c3541b546cfd9b0fb25" {
		return false
	}
	return true
}

func p02Schema115(v p02Value) bool {
	if v.kind != 's' || v.text != "1e48a65750575b9013bf6c1f4a2c7a755d02a89ec80abe2ed895b00b878c6423" {
		return false
	}
	return true
}

func p02Schema116(v p02Value) bool {
	if v.kind != 's' || v.text != "pretrusted:root-execution-decision:1" {
		return false
	}
	return true
}

func p02Schema113(v p02Value) bool {
	if v.kind != 'o' {
		return false
	}
	if len(v.object) != 4 {
		return false
	}
	if p02Get(v, "contractSHA256").kind == 0 {
		return false
	}
	if p02Get(v, "schemaSHA256").kind == 0 {
		return false
	}
	if p02Get(v, "codec").kind == 0 {
		return false
	}
	if p02Get(v, "requiredVerifier").kind == 0 {
		return false
	}
	for _, field := range v.object {
		switch field.key {
		case "contractSHA256":
			if !p02Schema114(field.value) {
				return false
			}
		case "schemaSHA256":
			if !p02Schema115(field.value) {
				return false
			}
		case "codec":
			if !p02Schema34(field.value) {
				return false
			}
		case "requiredVerifier":
			if !p02Schema116(field.value) {
				return false
			}
		default:
			return false
		}
	}
	return true
}

func p02Schema118(v p02Value) bool {
	if v.kind != 's' || v.text != "3716b51a60a37beef9939bba50e9c398cdb008f50aee41e48799d675b7054d68" {
		return false
	}
	return true
}

func p02Schema119(v p02Value) bool {
	if v.kind != 's' || v.text != "09c7a38c987ed058d7738349eac50d07b8e47c16f8dc5e68adf75633ee542ef7" {
		return false
	}
	return true
}

func p02Schema120(v p02Value) bool {
	if v.kind != 's' || v.text != "pretrusted:root-publication-intent:1" {
		return false
	}
	return true
}

func p02Schema117(v p02Value) bool {
	if v.kind != 'o' {
		return false
	}
	if len(v.object) != 4 {
		return false
	}
	if p02Get(v, "contractSHA256").kind == 0 {
		return false
	}
	if p02Get(v, "schemaSHA256").kind == 0 {
		return false
	}
	if p02Get(v, "codec").kind == 0 {
		return false
	}
	if p02Get(v, "requiredVerifier").kind == 0 {
		return false
	}
	for _, field := range v.object {
		switch field.key {
		case "contractSHA256":
			if !p02Schema118(field.value) {
				return false
			}
		case "schemaSHA256":
			if !p02Schema119(field.value) {
				return false
			}
		case "codec":
			if !p02Schema34(field.value) {
				return false
			}
		case "requiredVerifier":
			if !p02Schema120(field.value) {
				return false
			}
		default:
			return false
		}
	}
	return true
}

func p02Schema122(v p02Value) bool {
	if v.kind != 's' || v.text != "a55312190de97c423055b80e61c104ffb73b91cd0dd50fb3865bf5b67c274626" {
		return false
	}
	return true
}

func p02Schema123(v p02Value) bool {
	if v.kind != 's' || v.text != "87d1e23248113b03453cfccfdd91495d1e5090ac913202f908c88b0b0851e3ed" {
		return false
	}
	return true
}

func p02Schema124(v p02Value) bool {
	if v.kind != 's' || v.text != "pretrusted:root-restart-restore:1" {
		return false
	}
	return true
}

func p02Schema121(v p02Value) bool {
	if v.kind != 'o' {
		return false
	}
	if len(v.object) != 4 {
		return false
	}
	if p02Get(v, "contractSHA256").kind == 0 {
		return false
	}
	if p02Get(v, "schemaSHA256").kind == 0 {
		return false
	}
	if p02Get(v, "codec").kind == 0 {
		return false
	}
	if p02Get(v, "requiredVerifier").kind == 0 {
		return false
	}
	for _, field := range v.object {
		switch field.key {
		case "contractSHA256":
			if !p02Schema122(field.value) {
				return false
			}
		case "schemaSHA256":
			if !p02Schema123(field.value) {
				return false
			}
		case "codec":
			if !p02Schema34(field.value) {
				return false
			}
		case "requiredVerifier":
			if !p02Schema124(field.value) {
				return false
			}
		default:
			return false
		}
	}
	return true
}

func p02Schema126(v p02Value) bool {
	if v.kind != 's' || v.text != "a70bb825aaed6301f730f33261e3c648b94d51975d6ac5a499fab9b9175f0bef" {
		return false
	}
	return true
}

func p02Schema127(v p02Value) bool {
	if v.kind != 's' || v.text != "2d277069f0d6ef238d496b03c15b5b2ab8a37c16dbad15a00a2afcffa9466acf" {
		return false
	}
	return true
}

func p02Schema128(v p02Value) bool {
	if v.kind != 's' || v.text != "pretrusted:root-seal-decision:1" {
		return false
	}
	return true
}

func p02Schema125(v p02Value) bool {
	if v.kind != 'o' {
		return false
	}
	if len(v.object) != 4 {
		return false
	}
	if p02Get(v, "contractSHA256").kind == 0 {
		return false
	}
	if p02Get(v, "schemaSHA256").kind == 0 {
		return false
	}
	if p02Get(v, "codec").kind == 0 {
		return false
	}
	if p02Get(v, "requiredVerifier").kind == 0 {
		return false
	}
	for _, field := range v.object {
		switch field.key {
		case "contractSHA256":
			if !p02Schema126(field.value) {
				return false
			}
		case "schemaSHA256":
			if !p02Schema127(field.value) {
				return false
			}
		case "codec":
			if !p02Schema34(field.value) {
				return false
			}
		case "requiredVerifier":
			if !p02Schema128(field.value) {
				return false
			}
		default:
			return false
		}
	}
	return true
}

func p02Schema130(v p02Value) bool {
	if v.kind != 's' || v.text != "d9b8b80b0e660e6925bb1ab2ddb1b3fcf9eeb537fca381a7074cefdd199cbfa6" {
		return false
	}
	return true
}

func p02Schema131(v p02Value) bool {
	if v.kind != 's' || v.text != "560bf6179890ebef3e02aa1220c8115cc7eadeba8f9d1e2600bd020d96655e2a" {
		return false
	}
	return true
}

func p02Schema132(v p02Value) bool {
	if v.kind != 's' || v.text != "pretrusted:runtime-inspection-after:1" {
		return false
	}
	return true
}

func p02Schema129(v p02Value) bool {
	if v.kind != 'o' {
		return false
	}
	if len(v.object) != 4 {
		return false
	}
	if p02Get(v, "contractSHA256").kind == 0 {
		return false
	}
	if p02Get(v, "schemaSHA256").kind == 0 {
		return false
	}
	if p02Get(v, "codec").kind == 0 {
		return false
	}
	if p02Get(v, "requiredVerifier").kind == 0 {
		return false
	}
	for _, field := range v.object {
		switch field.key {
		case "contractSHA256":
			if !p02Schema130(field.value) {
				return false
			}
		case "schemaSHA256":
			if !p02Schema131(field.value) {
				return false
			}
		case "codec":
			if !p02Schema34(field.value) {
				return false
			}
		case "requiredVerifier":
			if !p02Schema132(field.value) {
				return false
			}
		default:
			return false
		}
	}
	return true
}

func p02Schema134(v p02Value) bool {
	if v.kind != 's' || v.text != "4f43ed65324d3aff28e21e1b1a9c15b0799596e8ff6fda0728ae26f108f6c6e7" {
		return false
	}
	return true
}

func p02Schema135(v p02Value) bool {
	if v.kind != 's' || v.text != "d8be7a9531caef138086db9e85a5d8733e0fa3e9d56b4ae4c69ccfafc13bf90d" {
		return false
	}
	return true
}

func p02Schema136(v p02Value) bool {
	if v.kind != 's' || v.text != "pretrusted:runtime-inspection-before:1" {
		return false
	}
	return true
}

func p02Schema133(v p02Value) bool {
	if v.kind != 'o' {
		return false
	}
	if len(v.object) != 4 {
		return false
	}
	if p02Get(v, "contractSHA256").kind == 0 {
		return false
	}
	if p02Get(v, "schemaSHA256").kind == 0 {
		return false
	}
	if p02Get(v, "codec").kind == 0 {
		return false
	}
	if p02Get(v, "requiredVerifier").kind == 0 {
		return false
	}
	for _, field := range v.object {
		switch field.key {
		case "contractSHA256":
			if !p02Schema134(field.value) {
				return false
			}
		case "schemaSHA256":
			if !p02Schema135(field.value) {
				return false
			}
		case "codec":
			if !p02Schema34(field.value) {
				return false
			}
		case "requiredVerifier":
			if !p02Schema136(field.value) {
				return false
			}
		default:
			return false
		}
	}
	return true
}

func p02Schema138(v p02Value) bool {
	if v.kind != 's' || v.text != "39c6b61caa9ecb86b1c5792cb0c63c2f492b6e04606e70803025ebb6d8cc7994" {
		return false
	}
	return true
}

func p02Schema139(v p02Value) bool {
	if v.kind != 's' || v.text != "8d4c081260c8c715f5ff48ca35e2aba7436fdaac090d3d8624fe418134d846d0" {
		return false
	}
	return true
}

func p02Schema140(v p02Value) bool {
	if v.kind != 's' || v.text != "pretrusted:schedule-disabled-readback:1" {
		return false
	}
	return true
}

func p02Schema137(v p02Value) bool {
	if v.kind != 'o' {
		return false
	}
	if len(v.object) != 4 {
		return false
	}
	if p02Get(v, "contractSHA256").kind == 0 {
		return false
	}
	if p02Get(v, "schemaSHA256").kind == 0 {
		return false
	}
	if p02Get(v, "codec").kind == 0 {
		return false
	}
	if p02Get(v, "requiredVerifier").kind == 0 {
		return false
	}
	for _, field := range v.object {
		switch field.key {
		case "contractSHA256":
			if !p02Schema138(field.value) {
				return false
			}
		case "schemaSHA256":
			if !p02Schema139(field.value) {
				return false
			}
		case "codec":
			if !p02Schema34(field.value) {
				return false
			}
		case "requiredVerifier":
			if !p02Schema140(field.value) {
				return false
			}
		default:
			return false
		}
	}
	return true
}

func p02Schema142(v p02Value) bool {
	if v.kind != 's' || v.text != "1f26d116a9e1b6baa3730f6c0bcdf8cec19ee9cec6d0c834b58b558c1f967dec" {
		return false
	}
	return true
}

func p02Schema143(v p02Value) bool {
	if v.kind != 's' || v.text != "48df9c31a686880e3e268046cd5248f45c202231da9c88cc9d3f10de2af6365f" {
		return false
	}
	return true
}

func p02Schema144(v p02Value) bool {
	if v.kind != 's' || v.text != "pretrusted:unchanged-mtls:1" {
		return false
	}
	return true
}

func p02Schema141(v p02Value) bool {
	if v.kind != 'o' {
		return false
	}
	if len(v.object) != 4 {
		return false
	}
	if p02Get(v, "contractSHA256").kind == 0 {
		return false
	}
	if p02Get(v, "schemaSHA256").kind == 0 {
		return false
	}
	if p02Get(v, "codec").kind == 0 {
		return false
	}
	if p02Get(v, "requiredVerifier").kind == 0 {
		return false
	}
	for _, field := range v.object {
		switch field.key {
		case "contractSHA256":
			if !p02Schema142(field.value) {
				return false
			}
		case "schemaSHA256":
			if !p02Schema143(field.value) {
				return false
			}
		case "codec":
			if !p02Schema34(field.value) {
				return false
			}
		case "requiredVerifier":
			if !p02Schema144(field.value) {
				return false
			}
		default:
			return false
		}
	}
	return true
}

func p02Schema30(v p02Value) bool {
	if v.kind != 'o' {
		return false
	}
	if len(v.object) != 28 {
		return false
	}
	if p02Get(v, "saintvision-proof-build-provenance:1").kind == 0 {
		return false
	}
	if p02Get(v, "saintvision-proof-ci-attestation:1").kind == 0 {
		return false
	}
	if p02Get(v, "saintvision-proof-descendant-quiescence:1").kind == 0 {
		return false
	}
	if p02Get(v, "saintvision-proof-g2-planning-policy:1").kind == 0 {
		return false
	}
	if p02Get(v, "saintvision-proof-image-distribution:1").kind == 0 {
		return false
	}
	if p02Get(v, "saintvision-proof-independent-code-review:1").kind == 0 {
		return false
	}
	if p02Get(v, "saintvision-proof-independent-plan-review:1").kind == 0 {
		return false
	}
	if p02Get(v, "saintvision-proof-inventory-head-readback:1").kind == 0 {
		return false
	}
	if p02Get(v, "saintvision-proof-launch-surface-inventory:1").kind == 0 {
		return false
	}
	if p02Get(v, "saintvision-proof-m2-capability:1").kind == 0 {
		return false
	}
	if p02Get(v, "saintvision-proof-member-progress-evidence:1").kind == 0 {
		return false
	}
	if p02Get(v, "saintvision-proof-migration-effect-readback:1").kind == 0 {
		return false
	}
	if p02Get(v, "saintvision-proof-migration-event-evidence:1").kind == 0 {
		return false
	}
	if p02Get(v, "saintvision-proof-native-two-cycle:1").kind == 0 {
		return false
	}
	if p02Get(v, "saintvision-proof-no-overlap:1").kind == 0 {
		return false
	}
	if p02Get(v, "saintvision-proof-node-floor-v2:1").kind == 0 {
		return false
	}
	if p02Get(v, "saintvision-proof-old-new-no-write:1").kind == 0 {
		return false
	}
	if p02Get(v, "saintvision-proof-owned-engine-exec:1").kind == 0 {
		return false
	}
	if p02Get(v, "saintvision-proof-process-quiescence:1").kind == 0 {
		return false
	}
	if p02Get(v, "saintvision-proof-protected-tree-equality:1").kind == 0 {
		return false
	}
	if p02Get(v, "saintvision-proof-root-execution-decision:1").kind == 0 {
		return false
	}
	if p02Get(v, "saintvision-proof-root-publication-intent:1").kind == 0 {
		return false
	}
	if p02Get(v, "saintvision-proof-root-restart-restore:1").kind == 0 {
		return false
	}
	if p02Get(v, "saintvision-proof-root-seal-decision:1").kind == 0 {
		return false
	}
	if p02Get(v, "saintvision-proof-runtime-inspection-after:1").kind == 0 {
		return false
	}
	if p02Get(v, "saintvision-proof-runtime-inspection-before:1").kind == 0 {
		return false
	}
	if p02Get(v, "saintvision-proof-schedule-disabled-readback:1").kind == 0 {
		return false
	}
	if p02Get(v, "saintvision-proof-unchanged-mtls:1").kind == 0 {
		return false
	}
	for _, field := range v.object {
		switch field.key {
		case "saintvision-proof-build-provenance:1":
			if !p02Schema31(field.value) {
				return false
			}
		case "saintvision-proof-ci-attestation:1":
			if !p02Schema36(field.value) {
				return false
			}
		case "saintvision-proof-descendant-quiescence:1":
			if !p02Schema40(field.value) {
				return false
			}
		case "saintvision-proof-g2-planning-policy:1":
			if !p02Schema44(field.value) {
				return false
			}
		case "saintvision-proof-image-distribution:1":
			if !p02Schema48(field.value) {
				return false
			}
		case "saintvision-proof-independent-code-review:1":
			if !p02Schema52(field.value) {
				return false
			}
		case "saintvision-proof-independent-plan-review:1":
			if !p02Schema56(field.value) {
				return false
			}
		case "saintvision-proof-inventory-head-readback:1":
			if !p02Schema60(field.value) {
				return false
			}
		case "saintvision-proof-launch-surface-inventory:1":
			if !p02Schema64(field.value) {
				return false
			}
		case "saintvision-proof-m2-capability:1":
			if !p02Schema68(field.value) {
				return false
			}
		case "saintvision-proof-member-progress-evidence:1":
			if !p02Schema72(field.value) {
				return false
			}
		case "saintvision-proof-migration-effect-readback:1":
			if !p02Schema76(field.value) {
				return false
			}
		case "saintvision-proof-migration-event-evidence:1":
			if !p02Schema80(field.value) {
				return false
			}
		case "saintvision-proof-native-two-cycle:1":
			if !p02Schema84(field.value) {
				return false
			}
		case "saintvision-proof-no-overlap:1":
			if !p02Schema88(field.value) {
				return false
			}
		case "saintvision-proof-node-floor-v2:1":
			if !p02Schema92(field.value) {
				return false
			}
		case "saintvision-proof-old-new-no-write:1":
			if !p02Schema97(field.value) {
				return false
			}
		case "saintvision-proof-owned-engine-exec:1":
			if !p02Schema101(field.value) {
				return false
			}
		case "saintvision-proof-process-quiescence:1":
			if !p02Schema105(field.value) {
				return false
			}
		case "saintvision-proof-protected-tree-equality:1":
			if !p02Schema109(field.value) {
				return false
			}
		case "saintvision-proof-root-execution-decision:1":
			if !p02Schema113(field.value) {
				return false
			}
		case "saintvision-proof-root-publication-intent:1":
			if !p02Schema117(field.value) {
				return false
			}
		case "saintvision-proof-root-restart-restore:1":
			if !p02Schema121(field.value) {
				return false
			}
		case "saintvision-proof-root-seal-decision:1":
			if !p02Schema125(field.value) {
				return false
			}
		case "saintvision-proof-runtime-inspection-after:1":
			if !p02Schema129(field.value) {
				return false
			}
		case "saintvision-proof-runtime-inspection-before:1":
			if !p02Schema133(field.value) {
				return false
			}
		case "saintvision-proof-schedule-disabled-readback:1":
			if !p02Schema137(field.value) {
				return false
			}
		case "saintvision-proof-unchanged-mtls:1":
			if !p02Schema141(field.value) {
				return false
			}
		default:
			return false
		}
	}
	return true
}

func p02Schema147(v p02Value) bool {
	if v.kind != 's' {
		return false
	}
	if len(v.text) < 2 {
		return false
	}
	if len(v.text) > 131072 {
		return false
	}
	if !p02Pattern(4, v.text) {
		return false
	}
	return true
}

func p02Schema148(v p02Value) bool {
	if v.kind != 'i' {
		return false
	}
	if v.integer < 0 {
		return false
	}
	if v.integer > 253402300799 {
		return false
	}
	return true
}

func p02Schema146(v p02Value) bool {
	if v.kind != 'o' {
		return false
	}
	if len(v.object) != 5 {
		return false
	}
	if p02Get(v, "role").kind == 0 {
		return false
	}
	if p02Get(v, "authorityScopeC2Hex").kind == 0 {
		return false
	}
	if p02Get(v, "publicKeyHex").kind == 0 {
		return false
	}
	if p02Get(v, "notBefore").kind == 0 {
		return false
	}
	if p02Get(v, "notAfter").kind == 0 {
		return false
	}
	for _, field := range v.object {
		switch field.key {
		case "role":
			if !p02Schema15(field.value) {
				return false
			}
		case "authorityScopeC2Hex":
			if !p02Schema147(field.value) {
				return false
			}
		case "publicKeyHex":
			if !p02Schema5(field.value) {
				return false
			}
		case "notBefore":
			if !p02Schema148(field.value) {
				return false
			}
		case "notAfter":
			if !p02Schema148(field.value) {
				return false
			}
		default:
			return false
		}
	}
	return true
}

func p02Schema145(v p02Value) bool {
	if v.kind != 'a' {
		return false
	}
	if len(v.array) < 1 {
		return false
	}
	if len(v.array) > 512 {
		return false
	}
	for i, child := range v.array {
		_ = i
		if !p02Schema146(child) {
			return false
		}
	}
	return true
}

func p02Schema151(v p02Value) bool {
	if v.kind != 's' || v.text != "PC2" {
		return false
	}
	return true
}

func p02Schema152(v p02Value) bool {
	if v.kind != 'o' {
		return false
	}
	if len(v.object) != 3 {
		return false
	}
	if p02Get(v, "tenantId").kind == 0 {
		return false
	}
	if p02Get(v, "nodeId").kind == 0 {
		return false
	}
	if p02Get(v, "recoveryEpoch").kind == 0 {
		return false
	}
	for _, field := range v.object {
		switch field.key {
		case "tenantId":
			if !p02Schema15(field.value) {
				return false
			}
		case "nodeId":
			if !p02Schema15(field.value) {
				return false
			}
		case "recoveryEpoch":
			if !p02Schema15(field.value) {
				return false
			}
		default:
			return false
		}
	}
	return true
}

func p02Schema150(v p02Value) bool {
	if v.kind != 'o' {
		return false
	}
	if len(v.object) != 4 {
		return false
	}
	if p02Get(v, "slot").kind == 0 {
		return false
	}
	if p02Get(v, "scope").kind == 0 {
		return false
	}
	if p02Get(v, "certificateDERHex").kind == 0 {
		return false
	}
	if p02Get(v, "caRootDERHex").kind == 0 {
		return false
	}
	for _, field := range v.object {
		switch field.key {
		case "slot":
			if !p02Schema151(field.value) {
				return false
			}
		case "scope":
			if !p02Schema152(field.value) {
				return false
			}
		case "certificateDERHex":
			if !p02Schema147(field.value) {
				return false
			}
		case "caRootDERHex":
			if !p02Schema147(field.value) {
				return false
			}
		default:
			return false
		}
	}
	return true
}

func p02Schema154(v p02Value) bool {
	if v.kind != 's' || v.text != "PC4" {
		return false
	}
	return true
}

func p02Schema153(v p02Value) bool {
	if v.kind != 'o' {
		return false
	}
	if len(v.object) != 4 {
		return false
	}
	if p02Get(v, "slot").kind == 0 {
		return false
	}
	if p02Get(v, "scope").kind == 0 {
		return false
	}
	if p02Get(v, "certificateDERHex").kind == 0 {
		return false
	}
	if p02Get(v, "caRootDERHex").kind == 0 {
		return false
	}
	for _, field := range v.object {
		switch field.key {
		case "slot":
			if !p02Schema154(field.value) {
				return false
			}
		case "scope":
			if !p02Schema152(field.value) {
				return false
			}
		case "certificateDERHex":
			if !p02Schema147(field.value) {
				return false
			}
		case "caRootDERHex":
			if !p02Schema147(field.value) {
				return false
			}
		default:
			return false
		}
	}
	return true
}

func p02Schema149(v p02Value) bool {
	if v.kind != 'a' {
		return false
	}
	if len(v.array) < 2 {
		return false
	}
	if len(v.array) > 2 {
		return false
	}
	for i, child := range v.array {
		_ = i
		switch i {
		case 0:
			if !p02Schema150(child) {
				return false
			}
		case 1:
			if !p02Schema153(child) {
				return false
			}
		default:
			return false
		}
	}
	return true
}

func p02Schema155(v p02Value) bool {
	if v.kind != 's' {
		return false
	}
	if len(v.text) < 2 {
		return false
	}
	if len(v.text) > 12582912 {
		return false
	}
	if !p02Pattern(4, v.text) {
		return false
	}
	return true
}

func p02Schema156(v p02Value) bool {
	if v.kind != 'o' {
		return false
	}
	if len(v.object) < 1 {
		return false
	}
	if len(v.object) > 4096 {
		return false
	}
	for _, field := range v.object {
		if !p02Schema9(p02String(field.key)) {
			return false
		}
		if !p02Schema15(field.value) {
			return false
		}
	}
	return true
}

func p02Schema157(v p02Value) bool {
	if v.kind != 's' {
		return false
	}
	if len(v.text) < 2 {
		return false
	}
	if len(v.text) > 4194304 {
		return false
	}
	if !p02Pattern(4, v.text) {
		return false
	}
	return true
}

func p02Schema158(v p02Value) bool {
	if v.kind != 's' {
		return false
	}
	if len(v.text) < 2 {
		return false
	}
	if len(v.text) > 2097152 {
		return false
	}
	if !p02Pattern(4, v.text) {
		return false
	}
	return true
}

func p02Schema159(v p02Value) bool {
	if v.kind != 'o' {
		return false
	}
	if len(v.object) != 6 {
		return false
	}
	if p02Get(v, "k1SourcePinSetSHA256").kind == 0 {
		return false
	}
	if p02Get(v, "recipeDefinitionsSHA256").kind == 0 {
		return false
	}
	if p02Get(v, "derivedDigestContractSHA256").kind == 0 {
		return false
	}
	if p02Get(v, "proofSlotRegistrySHA256").kind == 0 {
		return false
	}
	if p02Get(v, "graphSHA256").kind == 0 {
		return false
	}
	if p02Get(v, "nodeKindsSHA256").kind == 0 {
		return false
	}
	for _, field := range v.object {
		switch field.key {
		case "k1SourcePinSetSHA256":
			if !p02Schema22(field.value) {
				return false
			}
		case "recipeDefinitionsSHA256":
			if !p02Schema22(field.value) {
				return false
			}
		case "derivedDigestContractSHA256":
			if !p02Schema22(field.value) {
				return false
			}
		case "proofSlotRegistrySHA256":
			if !p02Schema22(field.value) {
				return false
			}
		case "graphSHA256":
			if !p02Schema22(field.value) {
				return false
			}
		case "nodeKindsSHA256":
			if !p02Schema22(field.value) {
				return false
			}
		default:
			return false
		}
	}
	return true
}

func p02Schema25(v p02Value) bool {
	if v.kind != 'o' {
		return false
	}
	if len(v.object) != 12 {
		return false
	}
	if p02Get(v, "selector").kind == 0 {
		return false
	}
	if p02Get(v, "version").kind == 0 {
		return false
	}
	if p02Get(v, "verifier").kind == 0 {
		return false
	}
	if p02Get(v, "contractPins").kind == 0 {
		return false
	}
	if p02Get(v, "grants").kind == 0 {
		return false
	}
	if p02Get(v, "cohortId").kind == 0 {
		return false
	}
	if p02Get(v, "members").kind == 0 {
		return false
	}
	if p02Get(v, "graphHex").kind == 0 {
		return false
	}
	if p02Get(v, "nodeKinds").kind == 0 {
		return false
	}
	if p02Get(v, "proofSlotRegistryHex").kind == 0 {
		return false
	}
	if p02Get(v, "designRegistrationHex").kind == 0 {
		return false
	}
	if p02Get(v, "semanticPins").kind == 0 {
		return false
	}
	for _, field := range v.object {
		switch field.key {
		case "selector":
			if !p02Schema4(field.value) {
				return false
			}
		case "version":
			if !p02Schema26(field.value) {
				return false
			}
		case "verifier":
			if !p02Schema27(field.value) {
				return false
			}
		case "contractPins":
			if !p02Schema30(field.value) {
				return false
			}
		case "grants":
			if !p02Schema145(field.value) {
				return false
			}
		case "cohortId":
			if !p02Schema15(field.value) {
				return false
			}
		case "members":
			if !p02Schema149(field.value) {
				return false
			}
		case "graphHex":
			if !p02Schema155(field.value) {
				return false
			}
		case "nodeKinds":
			if !p02Schema156(field.value) {
				return false
			}
		case "proofSlotRegistryHex":
			if !p02Schema157(field.value) {
				return false
			}
		case "designRegistrationHex":
			if !p02Schema158(field.value) {
				return false
			}
		case "semanticPins":
			if !p02Schema159(field.value) {
				return false
			}
		default:
			return false
		}
	}
	return true
}

func p02Schema162(v p02Value) bool {
	if v.kind != 's' || v.text != "NODE" {
		return false
	}
	return true
}

func p02Schema161(v p02Value) bool {
	if v.kind != 'o' {
		return false
	}
	if len(v.object) != 2 {
		return false
	}
	if p02Get(v, "class").kind == 0 {
		return false
	}
	if p02Get(v, "scope").kind == 0 {
		return false
	}
	for _, field := range v.object {
		switch field.key {
		case "class":
			if !p02Schema162(field.value) {
				return false
			}
		case "scope":
			if !p02Schema152(field.value) {
				return false
			}
		default:
			return false
		}
	}
	return true
}

func p02Schema164(v p02Value) bool {
	if v.kind != 's' || v.text != "COHORT" {
		return false
	}
	return true
}

func p02Schema165(v p02Value) bool {
	if v.kind != 'a' {
		return false
	}
	if len(v.array) < 2 {
		return false
	}
	if len(v.array) > 2 {
		return false
	}
	for i, child := range v.array {
		_ = i
		if !p02Schema152(child) {
			return false
		}
	}
	return true
}

func p02Schema163(v p02Value) bool {
	if v.kind != 'o' {
		return false
	}
	if len(v.object) != 3 {
		return false
	}
	if p02Get(v, "class").kind == 0 {
		return false
	}
	if p02Get(v, "cohortId").kind == 0 {
		return false
	}
	if p02Get(v, "members").kind == 0 {
		return false
	}
	for _, field := range v.object {
		switch field.key {
		case "class":
			if !p02Schema164(field.value) {
				return false
			}
		case "cohortId":
			if !p02Schema15(field.value) {
				return false
			}
		case "members":
			if !p02Schema165(field.value) {
				return false
			}
		default:
			return false
		}
	}
	return true
}

func p02Schema167(v p02Value) bool {
	if v.kind != 's' || v.text != "COMPONENT" {
		return false
	}
	return true
}

func p02Schema166(v p02Value) bool {
	if v.kind != 'o' {
		return false
	}
	if len(v.object) != 2 {
		return false
	}
	if p02Get(v, "class").kind == 0 {
		return false
	}
	if p02Get(v, "component").kind == 0 {
		return false
	}
	for _, field := range v.object {
		switch field.key {
		case "class":
			if !p02Schema167(field.value) {
				return false
			}
		case "component":
			if !p02Schema9(field.value) {
				return false
			}
		default:
			return false
		}
	}
	return true
}

func p02Schema160(v p02Value) bool {
	matches := 0
	if p02Schema161(v) {
		matches++
	}
	if p02Schema163(v) {
		matches++
	}
	if p02Schema166(v) {
		matches++
	}
	return matches == 1
}

func p02EnvelopeSchema(v p02Value) bool  { return p02Schema0(v) }
func p02PayloadSchema(v p02Value) bool   { return p02Schema25(v) }
func p02AuthoritySchema(v p02Value) bool { return p02Schema160(v) }
