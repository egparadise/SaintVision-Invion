//go:build linux

package recoverycandidate

import (
    "bytes"
    "fmt"
    "io"
    "os"
    "strconv"
    "strings"
    "runtime"
    "unsafe"
    "syscall"
)

// The standalone helper supports Linux amd64 and arm64 with openat2 (5.6+).
// Unsupported architectures and kernels fail closed; no insecure fallback.
// Both supported Linux syscall ABIs assign openat2 number 437.
func openConfined(dir int, name string, flags int) (int,error) {
    if runtime.GOARCH!="amd64" && runtime.GOARCH!="arm64" { return -1,syscall.ENOSYS }
    path,err:=syscall.BytePtrFromString(name)
    if err!=nil {return -1,err}
    const noCrossMount=0x01
    const noSymlinks=0x04
    const beneath=0x08
    how:=struct{ Flags,Mode,Resolve uint64 }{uint64(flags|syscall.O_CLOEXEC),0,noCrossMount|noSymlinks|beneath}
    fd,_,errno:=syscall.Syscall6(437,uintptr(dir),uintptr(unsafe.Pointer(path)),uintptr(unsafe.Pointer(&how)),unsafe.Sizeof(how),0,0)
    if errno!=0 {return -1,errno}
    return int(fd),nil
}

// mountID reads kernel metadata for an already held FD. It never resolves
// /proc/self/fd/N to obtain filesystem authority.
func mountID(fd int) (uint64, bool) {
    data, err := os.ReadFile(fmt.Sprintf("/proc/self/fdinfo/%d", fd))
    if err != nil { return 0, false }
    for _, line := range strings.Split(string(data), "\n") {
        fields := strings.Fields(line)
        if len(fields) == 2 && fields[0] == "mnt_id:" {
            id, err := strconv.ParseUint(fields[1], 10, 64)
            return id, err == nil && id != 0
        }
    }
    return 0, false
}

// The fixture provisioner bakes this public file into a pinned immutable
// image after CSR collection. A caller-selected file mount has another ID.
func checkProvisionedAuthority(binding Binding, members []any) error {
    hold := refuse("RECOVERY_HOLD_AUTHORITY_BINDING")
    root, err := syscall.Open("/", syscall.O_DIRECTORY|syscall.O_RDONLY|syscall.O_CLOEXEC, 0)
    if err != nil { return hold }
    defer syscall.Close(root)
    fd, err := openConfined(root, "recovery-authority.json", syscall.O_RDONLY|syscall.O_NOFOLLOW|syscall.O_NONBLOCK)
    if err != nil { return hold }
    file := os.NewFile(uintptr(fd), "recovery-authority.json")
    defer file.Close()
    var st syscall.Stat_t
    var fs syscall.Statfs_t
    rootMount, okRoot := mountID(root)
    mount, okFile := mountID(fd)
    if !okRoot || !okFile || rootMount != mount || syscall.Fstatfs(fd, &fs) != nil || fs.Flags&1 == 0 ||
        syscall.Fstat(fd, &st) != nil || st.Mode != syscall.S_IFREG|0444 || st.Uid != 0 || st.Nlink != 1 || st.Size > MaxBytes { return hold }
    raw, err := io.ReadAll(io.LimitReader(file, MaxBytes+1))
    if err != nil || int64(len(raw)) != st.Size { return hold }
    cohort := map[string]any{}
    for _, entry := range members {
        member, ok := entry.(map[string]any)
        if !ok { return hold }
        cohort[Text(member,"nodeId")] = Text(member,"nodeFingerprint")
    }
    expected, err := Canonical(map[string]any{"schema":"sv-recovery-fixture-authority:1","tenant":binding.Tenant,"epoch":binding.Epoch,"nodes":cohort,"authorizerSHA256":binding.AuthorizerHash,"operatorSHA256":binding.OperatorHash})
    if err != nil || !bytes.Equal(expected,raw) { return hold }
    return nil
}
