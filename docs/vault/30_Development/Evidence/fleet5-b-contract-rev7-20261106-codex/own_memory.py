"""Read this Python process's peak only; no OS/settings/process-control changes."""
def measure():
    import ctypes,os
    result={'scope':'this process only','enforcedOSRAMLimit':None,'OSChanges':False}
    if os.name=='nt':
        class PMC(ctypes.Structure):
            _fields_=[('cb',ctypes.c_ulong),('PageFaultCount',ctypes.c_ulong)]+[(n,ctypes.c_size_t) for n in ('PeakWorkingSetSize','WorkingSetSize','QuotaPeakPagedPoolUsage','QuotaPagedPoolUsage','QuotaPeakNonPagedPoolUsage','QuotaNonPagedPoolUsage','PagefileUsage','PeakPagefileUsage')]
        p=PMC();p.cb=ctypes.sizeof(p);f=ctypes.windll.psapi.GetProcessMemoryInfo;f.argtypes=[ctypes.c_void_p,ctypes.c_void_p,ctypes.c_ulong]
        if f(ctypes.c_void_p(-1),ctypes.byref(p),p.cb):result.update(peakWorkingSetBytes=p.PeakWorkingSetSize,workingSetBytes=p.WorkingSetSize)
    return result
