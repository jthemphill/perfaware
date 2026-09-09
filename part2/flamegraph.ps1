param(
    [Parameter(Mandatory = $true)][string]$Profiler,
    [Parameter(Mandatory = $true)][string]$ProfilerArguments,
    [Parameter(Mandatory = $true)][string]$OutputFile
)
$ErrorActionPreference = 'Stop'
try {
    Remove-Item Env:HAVERSINE_TRACE -ErrorAction SilentlyContinue
    # Python has quoted this command line using Windows subprocess.list2cmdline.
    $process = Start-Process -FilePath $Profiler -ArgumentList $ProfilerArguments `
        -WorkingDirectory (Split-Path -Parent $OutputFile) `
        -Verb RunAs -WindowStyle Hidden -PassThru
    $process.WaitForExit()
    if ($process.ExitCode -ne 0 -and $null -ne $process.ExitCode) {
        throw "Profiler exited with code $($process.ExitCode)"
    }
    if (!(Test-Path -LiteralPath $OutputFile -PathType Leaf)) {
        throw 'Profiler did not create a flamegraph.'
    }
} catch {
    Write-Error $_
    exit 1
}
