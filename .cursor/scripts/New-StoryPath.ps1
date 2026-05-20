# Returns story_cursor filename path: YYMMDD_HHMM_shorttitle.md
param(
    [Parameter(Mandatory = $true)]
    [string]$ShortTitle
)

$MaxTitleLen = 50
$slug = $ShortTitle.ToLower() -replace '[^a-z0-9]+', '_'
$slug = $slug.Trim('_')
if ($slug.Length -gt $MaxTitleLen) {
    $slug = $slug.Substring(0, $MaxTitleLen).TrimEnd('_')
}
if (-not $slug) {
    $slug = 'task'
}

$dt = Get-Date -Format 'yyMMdd_HHmm'
$projectRoot = Resolve-Path (Join-Path $PSScriptRoot '..\..')
$dir = Join-Path $projectRoot 'story_cursor'
if (-not (Test-Path $dir)) {
    New-Item -ItemType Directory -Path $dir -Force | Out-Null
}

$fileName = "${dt}_${slug}.md"
Join-Path $dir $fileName
