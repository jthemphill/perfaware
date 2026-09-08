param(
    [Parameter(Mandatory = $true)][string]$Profiler,
    [Parameter(Mandatory = $true)][string]$Program,
    [Parameter(Mandatory = $true)][string]$InputFile,
    [Parameter(Mandatory = $true)][string]$OutputFile
)
$ErrorActionPreference = 'Stop'
try {
    Remove-Item Env:HAVERSINE_TRACE -ErrorAction SilentlyContinue
    # Start-Process joins ArgumentList into a command line; quote each file path.
    $profilerArguments = '-o "{0}" -- "{1}" "{2}"' -f $OutputFile, $Program, $InputFile
    $process = Start-Process -FilePath $Profiler -ArgumentList $profilerArguments `
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
