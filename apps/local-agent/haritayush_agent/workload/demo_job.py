from __future__ import annotations

import multiprocessing
import os
import platform
import threading
import time


def _burn(stop: multiprocessing.synchronize.Event) -> None:
    # A small, fixed worker pool creates a repeatable load; Job Object limits it.
    while not stop.is_set():
        _ = time.perf_counter() * time.perf_counter()


class WindowsJob:
    """Windows Job Object wrapper. The CPU limit applies only to this child process."""
    def __init__(self, worker_count: int) -> None:
        if platform.system() != "Windows":
            raise OSError("The demo job and CPU cap require Windows 10/11")
        import ctypes
        from ctypes import wintypes
        self.ctypes, self.wintypes = ctypes, wintypes
        self.kernel32 = ctypes.WinDLL("kernel32", use_last_error=True)
        self.kernel32.CreateJobObjectW.restype = wintypes.HANDLE
        self.kernel32.CreateJobObjectW.argtypes = [wintypes.LPVOID, wintypes.LPCWSTR]
        self.kernel32.OpenProcess.restype = wintypes.HANDLE
        self.kernel32.OpenProcess.argtypes = [wintypes.DWORD, wintypes.BOOL, wintypes.DWORD]
        self.kernel32.SetInformationJobObject.restype = wintypes.BOOL
        self.kernel32.SetInformationJobObject.argtypes = [wintypes.HANDLE, ctypes.c_int, wintypes.LPVOID, wintypes.DWORD]
        self.kernel32.AssignProcessToJobObject.restype = wintypes.BOOL
        self.kernel32.AssignProcessToJobObject.argtypes = [wintypes.HANDLE, wintypes.HANDLE]
        self.kernel32.TerminateJobObject.restype = wintypes.BOOL
        self.kernel32.TerminateJobObject.argtypes = [wintypes.HANDLE, wintypes.UINT]
        self.kernel32.CloseHandle.restype = wintypes.BOOL
        self.kernel32.CloseHandle.argtypes = [wintypes.HANDLE]
        self.handle = self.kernel32.CreateJobObjectW(None, None)
        if not self.handle:
            raise ctypes.WinError(ctypes.get_last_error())
        self.process_handles = {}
        self.worker_count = worker_count
        try:
            self._enable_kill_on_close()
            self._set_limit(100)
        except Exception:
            self.kernel32.CloseHandle(self.handle)
            self.handle = None
            raise

    def _enable_kill_on_close(self) -> None:
        class BasicLimitInformation(self.ctypes.Structure):
            _fields_ = [
                ("PerProcessUserTimeLimit", self.ctypes.c_longlong),
                ("PerJobUserTimeLimit", self.ctypes.c_longlong),
                ("LimitFlags", self.wintypes.DWORD),
                ("MinimumWorkingSetSize", self.ctypes.c_size_t),
                ("MaximumWorkingSetSize", self.ctypes.c_size_t),
                ("ActiveProcessLimit", self.wintypes.DWORD),
                ("Affinity", self.ctypes.c_size_t),
                ("PriorityClass", self.wintypes.DWORD),
                ("SchedulingClass", self.wintypes.DWORD),
            ]
        class IoCounters(self.ctypes.Structure):
            _fields_ = [(name, self.ctypes.c_ulonglong) for name in
                        ("ReadOperationCount", "WriteOperationCount", "OtherOperationCount",
                         "ReadTransferCount", "WriteTransferCount", "OtherTransferCount")]
        class ExtendedLimitInformation(self.ctypes.Structure):
            _fields_ = [
                ("BasicLimitInformation", BasicLimitInformation), ("IoInfo", IoCounters),
                ("ProcessMemoryLimit", self.ctypes.c_size_t), ("JobMemoryLimit", self.ctypes.c_size_t),
                ("PeakProcessMemoryUsed", self.ctypes.c_size_t), ("PeakJobMemoryUsed", self.ctypes.c_size_t),
            ]
        info = ExtendedLimitInformation()
        info.BasicLimitInformation.LimitFlags = 0x2000  # JOB_OBJECT_LIMIT_KILL_ON_JOB_CLOSE
        if not self.kernel32.SetInformationJobObject(self.handle, 9, self.ctypes.byref(info), self.ctypes.sizeof(info)):
            raise self.ctypes.WinError(self.ctypes.get_last_error())

    def assign(self, pid: int) -> None:
        PROCESS_SET_QUOTA, PROCESS_TERMINATE, PROCESS_QUERY_LIMITED_INFORMATION = 0x0100, 0x0001, 0x1000
        handle = self.kernel32.OpenProcess(PROCESS_SET_QUOTA | PROCESS_TERMINATE | PROCESS_QUERY_LIMITED_INFORMATION, False, pid)
        if not handle:
            raise self.ctypes.WinError(self.ctypes.get_last_error())
        if not self.kernel32.AssignProcessToJobObject(self.handle, handle):
            self.kernel32.CloseHandle(handle)
            raise self.ctypes.WinError(self.ctypes.get_last_error())
        self.process_handles[pid] = handle

    def owns_processes(self, process_ids: set[int]) -> bool:
        self.kernel32.IsProcessInJob.restype = self.wintypes.BOOL
        self.kernel32.IsProcessInJob.argtypes = [self.wintypes.HANDLE, self.wintypes.HANDLE,
                                                  self.ctypes.POINTER(self.wintypes.BOOL)]
        if set(self.process_handles) != process_ids:
            return False
        for handle in self.process_handles.values():
            in_job = self.wintypes.BOOL(False)
            if not self.kernel32.IsProcessInJob(handle, self.handle, self.ctypes.byref(in_job)) or not in_job.value:
                return False
            # Handles correspond to the child list assigned by DemoJob in order.
        return True

    def _set_limit(self, pct: int) -> None:
        # Job Object rates are a share of the whole machine. Scale the requested
        # fraction of this bounded worker pool by the logical processor count.
        class CpuRateControl(self.ctypes.Structure):
            _fields_ = [("ControlFlags", self.wintypes.DWORD), ("CpuRate", self.wintypes.DWORD)]
        logical_cpus = max(1, os.cpu_count() or 1)
        rate = max(1, min(10000, round(pct * 100 * self.worker_count / logical_cpus)))
        info = CpuRateControl(0x1 | 0x4, rate)
        if not self.kernel32.SetInformationJobObject(self.handle, 15, self.ctypes.byref(info), self.ctypes.sizeof(info)):
            raise self.ctypes.WinError(self.ctypes.get_last_error())

    def cap(self, pct: int) -> None:
        self._set_limit(pct)

    def close(self) -> None:
        if self.handle:
            self.kernel32.TerminateJobObject(self.handle, 0)
            for process_handle in self.process_handles.values():
                self.kernel32.CloseHandle(process_handle)
            self.process_handles.clear()
            self.kernel32.CloseHandle(self.handle)
            self.handle = None


class DemoJob:
    is_simulated = False

    def __init__(self) -> None:
        self.processes: list[multiprocessing.Process] = []
        self.stop_event: multiprocessing.Event | None = None
        self.job: WindowsJob | None = None
        self.cap_pct = 100
        self._lock = threading.RLock()

    @property
    def running(self) -> bool:
        return any(process.is_alive() for process in self.processes)

    @property
    def owns_target(self) -> bool:
        ids = self.owned_pids
        return (self.running and self.job is not None and bool(ids)
                and os.getpid() not in ids and len(ids) == len(self.processes)
                and self.job.owns_processes(ids))

    @property
    def owned_pids(self) -> set[int]:
        return {process.pid for process in self.processes if process.pid is not None}

    def start(self) -> None:
        with self._lock:
            if self.running:
                return
            if self.job is not None or self.processes:
                self.stop()
            if platform.system() != "Windows":
                raise OSError("The demo job is supported on Windows 10/11 only")
            context = multiprocessing.get_context("spawn")
            self.stop_event = context.Event()
            worker_count = min(2, max(1, os.cpu_count() or 1))
            self.processes = [context.Process(target=_burn, args=(self.stop_event,),
                                              name=f"HaritAyushDemoJob-{index + 1}", daemon=False)
                              for index in range(worker_count)]
            try:
                self.job = WindowsJob(worker_count)
                for process in self.processes:
                    process.start()
                    self.job.assign(process.pid)
                self.cap_pct = 100
            except Exception:
                self.stop()
                raise

    def apply_cap(self, pct: int) -> None:
        with self._lock:
            if not self.running or self.job is None:
                raise RuntimeError("demo job is not running")
            self.job.cap(pct)
            self.cap_pct = pct

    def remove_cap(self) -> None:
        with self._lock:
            if self.running and self.job is not None:
                self.job.cap(100)
            self.cap_pct = 100

    def stop(self) -> None:
        with self._lock:
            self.remove_cap()
            if self.stop_event is not None:
                self.stop_event.set()
            for process in self.processes:
                if process.pid is None:
                    continue
                process.join(timeout=3)
                if process.is_alive():
                    process.terminate()
                    process.join(timeout=2)
            if self.job is not None:
                self.job.close()
            self.processes, self.stop_event, self.job = [], None, None
            self.cap_pct = 100


class SimulatedDemoJob:
    """DEV ONLY: state-only workload; never creates processes or applies an OS cap."""

    is_simulated = True

    def __init__(self) -> None:
        self.running = False
        self.cap_pct = 100
        self._lock = threading.RLock()

    @property
    def owns_target(self) -> bool:
        return self.running

    @property
    def owned_pids(self) -> set[int]:
        return set()

    def start(self) -> None:
        with self._lock:
            self.running = True
            self.cap_pct = 100

    def apply_cap(self, pct: int) -> None:
        with self._lock:
            if not self.running:
                raise RuntimeError("simulated demo workload is not running")
            self.cap_pct = pct

    def remove_cap(self) -> None:
        with self._lock:
            self.cap_pct = 100

    def stop(self) -> None:
        with self._lock:
            self.cap_pct = 100
            self.running = False

