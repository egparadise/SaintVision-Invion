package runtime

import (
	"encoding/json"
	"errors"
	"os"
	"path/filepath"
	"regexp"
)

// Per-contribution floor in the existing identity/epoch-bound, exclusively
// locked journal. This is local installation evidence, not server acceptance.
type StoragePolicyPin struct {
	ContributionID string `json:"contributionId"`
	RootVersion    int64  `json:"rootVersion"`
	ChannelVersion int64  `json:"channelVersion"`
	RootSHA256     string `json:"rootSha256"`
	ChannelSHA256  string `json:"channelSha256"`
	PolicySHA256   string `json:"policySha256"`
}

var contributionID = regexp.MustCompile(`^stc_[0-9A-HJKMNP-TV-Z]{26}$`)
var storagePolicyRejected = errors.New("NODE-0061: storage policy journal or version rejected")

func (p StoragePolicyPin) valid() bool {
	return contributionID.MatchString(p.ContributionID) && p.RootVersion > 0 && p.RootVersion <= 9007199254740991 && p.ChannelVersion > 0 && p.ChannelVersion <= 9007199254740991 && hexID.MatchString(p.RootSHA256) && hexID.MatchString(p.ChannelSHA256) && hexID.MatchString(p.PolicySHA256)
}

// Startup-only; caller holds the journal process lock. Never erase older
// contribution floors when selecting another approved contribution.
func (j *Journal) PinStoragePolicy(next StoragePolicyPin) error {
	if !next.valid() {
		return storagePolicyRejected
	}
	path := filepath.Join(j.root, ".storage-"+next.ContributionID)
	var prior StoragePolicyPin
	err := readPrivate(path, &prior)
	if os.IsNotExist(err) {
		return j.create(path, next)
	}
	if err != nil || !prior.valid() || prior.ContributionID != next.ContributionID {
		return storagePolicyRejected
	}
	if next.RootVersion < prior.RootVersion || next.ChannelVersion < prior.ChannelVersion ||
		(next.RootVersion == prior.RootVersion && next.RootSHA256 != prior.RootSHA256) ||
		(next.ChannelVersion == prior.ChannelVersion && next.ChannelSHA256 != prior.ChannelSHA256) ||
		(next.RootVersion == prior.RootVersion && next.ChannelVersion == prior.ChannelVersion && next.PolicySHA256 != prior.PolicySHA256) {
		return storagePolicyRejected
	}
	if next == prior {
		return j.syncDir()
	}
	file, err := os.CreateTemp(j.root, ".storage-policy-")
	if err != nil {
		return err
	}
	name := file.Name()
	defer os.Remove(name) // only the temporary file created by this invocation
	raw, err := json.Marshal(next)
	if err == nil {
		_, err = file.Write(raw)
	}
	if err == nil {
		err = file.Sync()
	}
	closed := file.Close()
	if err == nil {
		err = closed
	}
	if err == nil {
		err = os.Rename(name, path)
	}
	if err == nil {
		err = j.syncDir()
	}
	return err
}
