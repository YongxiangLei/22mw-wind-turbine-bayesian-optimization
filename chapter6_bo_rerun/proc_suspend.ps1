# Suspend / resume whole processes via ntdll (NtSuspendProcess / NtResumeProcess).
# Dot-source after env_d.ps1 (Add-Type compiles into $env:TEMP, which env_d.ps1 points to D:).
if (-not ([System.Management.Automation.PSTypeName]'ProcCtl').Type) {
    Add-Type -TypeDefinition @"
using System; using System.Runtime.InteropServices;
public static class ProcCtl {
  [DllImport("ntdll.dll")] static extern int NtSuspendProcess(IntPtr h);
  [DllImport("ntdll.dll")] static extern int NtResumeProcess(IntPtr h);
  [DllImport("kernel32.dll")] static extern IntPtr OpenProcess(uint a, bool i, int pid);
  [DllImport("kernel32.dll")] static extern bool CloseHandle(IntPtr h);
  const uint PROCESS_SUSPEND_RESUME = 0x0800;
  public static int Suspend(int pid){ IntPtr h=OpenProcess(PROCESS_SUSPEND_RESUME,false,pid); if(h==IntPtr.Zero) return -1; int r=NtSuspendProcess(h); CloseHandle(h); return r; }
  public static int Resume(int pid){ IntPtr h=OpenProcess(PROCESS_SUSPEND_RESUME,false,pid); if(h==IntPtr.Zero) return -1; int r=NtResumeProcess(h); CloseHandle(h); return r; }
}
"@
}

function Get-RunProcesses {
    Get-CimInstance Win32_Process | Where-Object { $_.ExecutablePath -like "$env:MAMBA_ROOT_PREFIX*" }
}

function Test-RunSuspended {
    # true if every thread of every openfast process is in Suspended wait state
    $of = @(Get-Process openfast -ErrorAction SilentlyContinue | Where-Object { $_.Path -like "$env:MAMBA_ROOT_PREFIX*" })
    if ($of.Count -eq 0) { return $false }
    foreach ($p in $of) {
        foreach ($t in $p.Threads) { if ($t.WaitReason -ne 'Suspended') { return $false } }
    }
    return $true
}
