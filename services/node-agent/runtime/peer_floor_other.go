//go:build !linux

package runtime

import "errors"

func ServingExecutableSHA256(pid int, uid uint32) (string, error) {
	return "", errors.New("NODE-0041: Linux serving executable observation required")
}

const MaxPeerPolicyVersion int64 = 9007199254740991

type PeerPolicyFloorObservation struct {
	Version                                  int64
	Hash, FloorSHA256, JournalIdentitySHA256 string
	JournalUID                               uint32
}

func ReadPeerPolicyFloor(state, policyPath string, config Config) (PeerPolicyFloorObservation, error) {
	return PeerPolicyFloorObservation{}, errors.New("NODE-0041: Linux actual peer policy floor observation required")
}
func PeerFloorServingProcess(pid int, state, policy string, config Config, uid uint32) (string, error) {
	return "", errors.New("NODE-0041: Linux serving process observation required")
}
