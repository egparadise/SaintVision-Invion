//go:build linux

package recoverycandidate

import ("os"; "path/filepath"; "testing")

func TestFilesystemNumberBound(t *testing.T) {
    for _, v := range []uint64{0, 1<<53-1, 1<<53, 1<<53+1, 1<<63, ^uint64(0)} {
        if supportedFilesystemNumber(v) != (v < 1<<53) { t.Errorf("range check failed for %d",v) }
    }
}

func TestPinnedParentSurvivesRename(t *testing.T) {
    parent:=t.TempDir()
    root:=filepath.Join(parent,"state")
    if err:=os.Mkdir(root,0700); err!=nil { t.Fatal(err) }
    const original="original"
    if err:=os.WriteFile(filepath.Join(root,"floor"),[]byte(original),0600); err!=nil {t.Fatal(err)}
    held,err:=directory(root,false); if err!=nil { t.Fatal(err) }; defer held.Close()
    moved:=filepath.Join(parent,"original")
    if err:=os.Rename(root,moved);err!=nil { t.Fatal(err) }
    foreign:=filepath.Join(parent,"foreign")
    if err:=os.Mkdir(foreign,0700);err!=nil {t.Fatal(err)}
    if err:=os.WriteFile(filepath.Join(foreign,"floor"),[]byte("foreign"),0600);err!=nil {t.Fatal(err)}
    if err:=os.Symlink(foreign,root);err!=nil { t.Fatal(err) }
    if escaped,err:=directory(root,false);err==nil { escaped.Close(); t.Fatal("accepted symlink root") }
    raw,_,err:=readRegular(held,"floor",false)
    if err!=nil || string(raw)!=original { t.Fatal("held directory lost its original file") }
    if err:=durableRecord(held,"proof",[]byte(original));err!=nil {t.Fatal(err)}
    for _,path:=range []string{filepath.Join(moved,"floor"),filepath.Join(moved,"proof")} {
        got,err:=os.ReadFile(path);if err!=nil || string(got)!=original { t.Fatal("original bytes changed") }
    }
    if _,err:=os.Lstat(filepath.Join(foreign,"proof"));!os.IsNotExist(err) { t.Fatal("publication escaped") }
    if got,err:=os.ReadFile(filepath.Join(foreign,"floor"));err!=nil || string(got)!="foreign" {t.Fatal("foreign bytes changed")}
}
