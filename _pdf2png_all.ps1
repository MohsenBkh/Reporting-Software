# WinRT PDF -> PNG renderer for ALL pages (for OCR transcription)
param([string]$PdfPath, [string]$OutDir, [string]$Prefix = "ref", [int]$Dpi = 200)
$ErrorActionPreference = "Stop"

Add-Type -AssemblyName System.Runtime.WindowsRuntime

$null = [Windows.Data.Pdf.PdfDocument, Windows.Data.Pdf, ContentType = WindowsRuntime]
$null = [Windows.Storage.StorageFile, Windows.Storage, ContentType = WindowsRuntime]
$null = [Windows.Storage.Streams.IRandomAccessStream, Windows.Storage.Streams, ContentType = WindowsRuntime]

$asTaskGeneric = ([System.WindowsRuntimeSystemExtensions].GetMethods() | Where-Object {
    $_.Name -eq 'AsTask' -and $_.GetParameters().Count -eq 1 -and
    $_.GetParameters()[0].ParameterType.Name -eq 'IAsyncOperation`1'
})[0]

function Await($WinRtTask, $ResultType) {
    $asTask = $asTaskGeneric.MakeGenericMethod($ResultType)
    $netTask = $asTask.Invoke($null, @($WinRtTask))
    $netTask.Wait(-1) | Out-Null
    $netTask.Result
}

$asTaskAction = ([System.WindowsRuntimeSystemExtensions].GetMethods() | Where-Object {
    $_.Name -eq 'AsTask' -and $_.GetParameters().Count -eq 1 -and
    $_.GetParameters()[0].ParameterType.Name -eq 'IAsyncAction'
})[0]

function AwaitAction($WinRtAction) {
    $netTask = $asTaskAction.Invoke($null, @($WinRtAction))
    $netTask.Wait(-1) | Out-Null
}

New-Item -ItemType Directory -Force -Path $OutDir | Out-Null

$file = Await ([Windows.Storage.StorageFile]::GetFileFromPathAsync($PdfPath)) ([Windows.Storage.StorageFile])
$pdf = Await ([Windows.Data.Pdf.PdfDocument]::LoadFromFileAsync($file)) ([Windows.Data.Pdf.PdfDocument])
$outFolder = Await ([Windows.Storage.StorageFolder]::GetFolderFromPathAsync($OutDir)) ([Windows.Storage.StorageFolder])

for ($i = 0; $i -lt $pdf.PageCount; $i++) {
    $page = $pdf.GetPage([uint32]$i)
    $leaf = "{0}_p{1}.png" -f $Prefix, ($i + 1)
    $outFile = Await ($outFolder.CreateFileAsync($leaf, [Windows.Storage.CreationCollisionOption]::ReplaceExisting)) ([Windows.Storage.StorageFile])
    $stream = Await ($outFile.OpenAsync([Windows.Storage.FileAccessMode]::ReadWrite)) ([Windows.Storage.Streams.IRandomAccessStream])
    $renderOpts = New-Object Windows.Data.Pdf.PdfPageRenderOptions
    $scale = $Dpi / 96.0
    $renderOpts.DestinationWidth = [uint32]([math]::Round($page.Size.Width * $scale))
    $renderOpts.DestinationHeight = [uint32]([math]::Round($page.Size.Height * $scale))
    AwaitAction ($page.RenderToStreamAsync($stream, $renderOpts)) | Out-Null
    $stream.Dispose()
    $page.Dispose()
    Write-Host ("saved " + (Join-Path $OutDir $leaf))
}
Write-Host ("pages total: " + $pdf.PageCount)
