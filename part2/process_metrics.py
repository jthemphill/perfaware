"""End-to-end child-process timing and page faults, without third-party packages.

Unix accounting uses deltas for reaped children: callers must launch/wait for
only one child at a time. Windows reads the child's retained process handle.
"""

import ctypes
import subprocess
import sys
import time


class ProcessMemoryCounters(ctypes.Structure):
    # Windows DWORD is 32 bits; SIZE_T follows the Python process's pointer size.
    _fields_ = [("cb", ctypes.c_uint32), ("PageFaultCount", ctypes.c_uint32)] + [
        (name, ctypes.c_size_t) for name in (
            "PeakWorkingSetSize", "WorkingSetSize", "QuotaPeakPagedPoolUsage",
            "QuotaPagedPoolUsage", "QuotaPeakNonPagedPoolUsage",
            "QuotaNonPagedPoolUsage", "PagefileUsage", "PeakPagefileUsage")]


class WindowsPageFaults:
    def __init__(self):
        self.query = ctypes.WinDLL("psapi", use_last_error=True).GetProcessMemoryInfo
        self.query.argtypes = [ctypes.c_void_p, ctypes.POINTER(ProcessMemoryCounters),
                               ctypes.c_uint32]
        self.query.restype = ctypes.c_int

    def read(self, process):
        counters = ProcessMemoryCounters()
        counters.cb = ctypes.sizeof(counters)
        # CPython retains this native handle after communicate()/wait(). Borrow
        # it while Popen is alive; reopening by PID could race with process exit.
        # https://learn.microsoft.com/windows/win32/api/psapi/nf-psapi-getprocessmemoryinfo
        if not self.query(int(process._handle), ctypes.byref(counters), counters.cb):
            raise ctypes.WinError(ctypes.get_last_error())
        return {"total": counters.PageFaultCount, "minor": None, "major": None}


def page_fault_backend():
    return "GetProcessMemoryInfo" if sys.platform == "win32" else "getrusage(RUSAGE_CHILDREN)"


def run_measured(args, cwd=None, timeout=600):
    """Return (CompletedProcess, elapsed seconds, page-fault counts).

    Counts cover one complete child lifetime, including startup and cleanup.
    Counter initialization and reads are outside the elapsed-time interval.
    Missing counters fail the run instead of silently reporting zero.
    """
    args = [str(arg) for arg in args]
    if sys.platform == "win32":
        windows = WindowsPageFaults()
    else:
        import resource  # Not available on Windows.
        windows = None
        before = resource.getrusage(resource.RUSAGE_CHILDREN)

    start = time.perf_counter()
    with subprocess.Popen(args, cwd=cwd, stdout=subprocess.PIPE,
                          stderr=subprocess.PIPE, text=True) as process:
        try:
            stdout, stderr = process.communicate(timeout=timeout)
        except subprocess.TimeoutExpired as error:
            process.kill()
            error.stdout, error.stderr = process.communicate()
            raise
        except BaseException:
            process.kill()
            process.wait()
            raise
        elapsed = time.perf_counter() - start
        result = subprocess.CompletedProcess(args, process.returncode, stdout, stderr)
        result.check_returncode()
        if windows is not None:
            faults = windows.read(process)
        else:
            after = resource.getrusage(resource.RUSAGE_CHILDREN)
            minor = after.ru_minflt - before.ru_minflt
            major = after.ru_majflt - before.ru_majflt
            faults = {"total": minor + major, "minor": minor, "major": major}
    return result, elapsed, faults
