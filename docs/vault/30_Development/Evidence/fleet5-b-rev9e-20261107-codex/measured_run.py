"""Own child process measurement. Budget reported, never OS enforced."""
import ctypes,json,os,runpy,sys,time
from ctypes import wintypes
from pathlib import Path
class Memory(ctypes.Structure):
    _fields_=[('cb',wintypes.DWORD),('PageFaultCount',wintypes.DWORD),('PeakWorkingSetSize',ctypes.c_size_t),('WorkingSetSize',ctypes.c_size_t),('QuotaPeakPagedPoolUsage',ctypes.c_size_t),('QuotaPagedPoolUsage',ctypes.c_size_t),('QuotaPeakNonPagedPoolUsage',ctypes.c_size_t),('QuotaNonPagedPoolUsage',ctypes.c_size_t),('PagefileUsage',ctypes.c_size_t),('PeakPagefileUsage',ctypes.c_size_t)]
def main():
    target=sys.argv[1];sys.argv=sys.argv[1:];sys.path.insert(0,str(Path(target).resolve().parent));start=time.monotonic();rc=0
    try:runpy.run_path(target,run_name='__main__')
    except SystemExit as e:rc=e.code if type(e.code) is int else 0 if e.code is None else 1
    finally:
        peak=None
        if os.name=='nt':
            kernel=ctypes.WinDLL('kernel32',use_last_error=True);kernel.GetCurrentProcess.restype=wintypes.HANDLE
            psapi=ctypes.WinDLL('psapi',use_last_error=True);psapi.GetProcessMemoryInfo.argtypes=[wintypes.HANDLE,ctypes.POINTER(Memory),wintypes.DWORD]
            m=Memory();m.cb=ctypes.sizeof(m)
            if psapi.GetProcessMemoryInfo(kernel.GetCurrentProcess(),ctypes.byref(m),m.cb):peak=m.PeakWorkingSetSize
        print(json.dumps({'ownerResourceMeasurement':{'target':target,'peakWorkingSetBytes':peak,'elapsedSeconds':round(time.monotonic()-start,3),'OSMemoryLimitEnforced':False,'serial':True}}),flush=True)
    raise SystemExit(rc)
if __name__=='__main__':main()
