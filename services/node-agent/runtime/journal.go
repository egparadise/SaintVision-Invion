package runtime

import (
	"encoding/json"
	"errors"
	"fmt"
	contracts "github.com/egparadise/SaintVision-Invion/packages/contracts-go"
	"github.com/egparadise/SaintVision-Invion/services/node-agent/internal/wire"
	"os"
	"path/filepath"
	"reflect"
	goruntime "runtime"
	"strconv"
	"strings"
)

type Record struct {
	Hash         string                     `json:"hash"`
	Claim        contracts.ExecutionClaim   `json:"claim"`
	Allocations  []contracts.NodeAllocation `json:"allocations"`
	Name         string                     `json:"name"`
	NeverStarted bool                       `json:"neverStarted,omitempty"`
}

type Journal struct {
	root string
	lock *os.File
}

func OpenJournal(root string, config Config) (*Journal, error) {
	if goruntime.GOOS != "linux" {
		return nil, errors.New("NODE-0011: Linux runtime required")
	}
	if err := os.MkdirAll(root, 0700); err != nil {
		return nil, errors.New("NODE-0011: journal unavailable")
	}
	info, err := os.Lstat(root)
	if err != nil || !info.IsDir() || info.Mode()&os.ModeSymlink != 0 || info.Mode().Perm()&0077 != 0 {
		return nil, errors.New("NODE-0011: private journal directory required")
	}
	lock, err := lockJournal(filepath.Join(root, ".lock"))
	if err != nil {
		return nil, err
	}
	journal := &Journal{root: root, lock: lock}
	identity := struct{ Tenant, Node, Epoch string }{config.TenantID, config.NodeID, config.Epoch}
	path := filepath.Join(root, "identity.json")
	if _, err = os.Lstat(path); os.IsNotExist(err) {
		err = journal.create(path, identity)
	} else if err == nil {
		var prior struct{ Tenant, Node, Epoch string }
		err = readPrivate(path, &prior)
		if err == nil && prior != identity {
			err = errors.New("NODE-0012: journal identity or epoch requires reconciliation")
		}
	}
	if err != nil {
		_ = journal.Close()
		return nil, err
	}
	return journal, nil
}

func (j *Journal) Close() error { return j.lock.Close() }
func (j *Journal) syncDir() error {
	directory, err := os.Open(j.root)
	if err != nil {
		return err
	}
	defer directory.Close()
	return directory.Sync()
}
func (j *Journal) create(path string, value any) error {
	bytes, err := json.Marshal(value)
	if err != nil {
		return err
	}
	file, err := os.OpenFile(path, os.O_CREATE|os.O_EXCL|os.O_WRONLY, 0600)
	if err != nil {
		return err
	}
	_, writeErr := file.Write(bytes)
	syncErr := file.Sync()
	closeErr := file.Close()
	if writeErr != nil || syncErr != nil || closeErr != nil {
		return errors.New("NODE-0013: durable journal write failed")
	}
	return j.syncDir()
}
func readPrivate(path string, value any) error {
	info, err := os.Lstat(path)
	if err != nil {
		return err
	}
	if !info.Mode().IsRegular() || info.Mode().Perm()&0077 != 0 || info.Size() > 1048576 {
		return errors.New("NODE-0013: unsafe journal entry")
	}
	bytes, err := os.ReadFile(path)
	if err != nil {
		return err
	}
	if err = json.Unmarshal(bytes, value); err != nil {
		return errors.New("NODE-0013: incomplete journal; do not retry execution")
	}
	return nil
}
func (j *Journal) Get(command string) (*Record, *contracts.NodeStopReceipt, error) {
	path := filepath.Join(j.root, command+".intent")
	var record Record
	if err := readPrivate(path, &record); os.IsNotExist(err) {
		return nil, nil, nil
	} else if err != nil {
		return nil, nil, err
	}
	if string(record.Claim.CommandId) != command {
		return nil, nil, errors.New("NODE-0013: journal identity differs")
	}
	var receipt contracts.NodeStopReceipt
	if err := readPrivate(filepath.Join(j.root, command+".receipt"), &receipt); os.IsNotExist(err) {
		return &record, nil, nil
	} else if err != nil {
		return nil, nil, err
	}
	raw, _ := json.Marshal(receipt)
	if wire.Validate("NodeStopReceipt", raw) != nil || receipt.CommandId != record.Claim.CommandId || receipt.ClaimId != record.Claim.ClaimId || receipt.RunId != record.Claim.RunId || receipt.TenantId != record.Claim.TenantId || receipt.ProjectId != record.Claim.ProjectId || receipt.NodeId != record.Claim.NodeId || receipt.RecoveryEpoch != record.Claim.RecoveryEpoch || receipt.PlanDigest != record.Claim.PlanDigest || !reflect.DeepEqual(receipt.Allocations, record.Allocations) {
		return nil, nil, errors.New("NODE-0013: receipt differs from durable intent")
	}
	return &record, &receipt, nil
}
func (j *Journal) Begin(p Permit, name string) (*Record, error) {
	return j.begin(p, name, false)
}

// Reject persists a tombstone under the same command key as Execute. A crash
// before its receipt is saved can only recover this prohibition, never execute.
func (j *Journal) Reject(p Permit) (*Record, error) {
	return j.begin(p, "", true)
}

func (j *Journal) begin(p Permit, name string, neverStarted bool) (*Record, error) {
	record := &Record{Hash: p.Hash, Claim: p.Data.Claim, Allocations: p.Data.Allocations, Name: name, NeverStarted: neverStarted}
	for _, allocation := range record.Allocations {
		lease := allocation.Lease
		parts := strings.Split(lease.FencingToken, ":")
		token, _ := strconv.ParseUint(parts[1], 10, 63)
		path := filepath.Join(j.root, string(lease.LeaseId)+".fence")
		entry := struct {
			Epoch, Command string
			Token          uint64
		}{parts[0], string(record.Claim.CommandId), token}
		var prior struct {
			Epoch, Command string
			Token          uint64
		}
		err := readPrivate(path, &prior)
		if err == nil {
			if prior.Epoch != entry.Epoch || token < prior.Token || (token == prior.Token && prior.Command != entry.Command) {
				return nil, errors.New("NODE-0014: stale allocation fence")
			}
			if prior == entry {
				continue
			}
			// Write/fsync replacement before rename; a crash can only keep the old or new
			// high water mark. No container is created until all entries and intent sync.
			tmp, err := os.CreateTemp(j.root, ".fence-")
			if err != nil {
				return nil, err
			}
			bytes, _ := json.Marshal(entry)
			_, err = tmp.Write(bytes)
			if err == nil {
				err = tmp.Sync()
			}
			name := tmp.Name()
			_ = tmp.Close()
			if err == nil {
				err = os.Rename(name, path)
			}
			if err == nil {
				err = j.syncDir()
			}
			if err != nil {
				return nil, errors.New("NODE-0013: fence persistence failed")
			}
		} else if os.IsNotExist(err) {
			if err = j.create(path, entry); err != nil {
				return nil, err
			}
		} else {
			return nil, err
		}
	}
	if err := j.create(filepath.Join(j.root, string(record.Claim.CommandId)+".intent"), record); err != nil {
		return nil, errors.New("NODE-0013: execution intent persistence failed")
	}
	return record, nil
}
func (j *Journal) Save(receipt contracts.NodeStopReceipt) error {
	return j.create(filepath.Join(j.root, string(receipt.CommandId)+".receipt"), receipt)
}
func (j *Journal) Pending() ([]Record, error) {
	files, err := os.ReadDir(j.root)
	if err != nil {
		return nil, err
	}
	result := []Record{}
	for _, file := range files {
		if !strings.HasSuffix(file.Name(), ".intent") {
			continue
		}
		command := strings.TrimSuffix(file.Name(), ".intent")
		record, receipt, err := j.Get(command)
		if err != nil {
			return nil, fmt.Errorf("NODE-0013: unresolved journal")
		}
		if receipt == nil {
			result = append(result, *record)
		}
	}
	return result, nil
}

// PinPeerPolicy persists an anti-rollback floor separately from allocation fences.
// Caller serializes policy updates; the journal process lock prevents other writers.
func (j *Journal) PinPeerPolicy(version int64, hash string) error {
	if version < 1 || version > 9007199254740991 || !hexID.MatchString(hash) {
		return errors.New("NODE-0041: invalid peer policy floor")
	}
	path := filepath.Join(j.root, ".peer-policy")
	var prior struct {
		Version int64
		Hash    string
	}
	next := struct {
		Version int64
		Hash    string
	}{version, hash}
	err := readPrivate(path, &prior)
	if os.IsNotExist(err) {
		return j.create(path, next)
	}
	if err != nil {
		return errors.New("NODE-0041: peer policy journal unavailable")
	}
	if prior.Version < 1 || !hexID.MatchString(prior.Hash) {
		return errors.New("NODE-0041: corrupt peer policy floor")
	}
	if version < prior.Version || (version == prior.Version && hash != prior.Hash) {
		return errors.New("NODE-0041: peer policy rollback rejected")
	}
	if next == prior {
		return nil
	}
	file, err := os.CreateTemp(j.root, ".peer-policy-")
	if err != nil {
		return err
	}
	raw, _ := json.Marshal(next)
	_, err = file.Write(raw)
	if err == nil {
		err = file.Sync()
	}
	name := file.Name()
	closeErr := file.Close()
	if err == nil {
		err = closeErr
	}
	if err == nil {
		err = os.Rename(name, path)
	}
	if err == nil {
		err = j.syncDir()
	}
	return err
}
