param([string]$ImagePath)

Add-Type -AssemblyName System.Runtime.WindowsRuntime
$null = [Windows.Media.Ocr.OcrEngine, Windows.Foundation.Diagnostics, ContentType = WindowsRuntime]
$null = [Windows.Graphics.Imaging.BitmapDecoder, Windows.Foundation.Diagnostics, ContentType = WindowsRuntime]
$null = [Windows.Storage.StorageFile, Windows.Foundation.Diagnostics, ContentType = WindowsRuntime]
$null = [Windows.Globalization.Language, Windows.Foundation.Diagnostics, ContentType = WindowsRuntime]

$asTaskGeneric = ([System.WindowsRuntimeSystemExtensions].GetMethods() | Where-Object { $_.Name -eq 'AsTask' -and $_.GetParameters().Count -eq 1 -and $_.GetParameters()[0].ParameterType.Name -eq 'IAsyncOperation`1' })[0]

function Await($asyncOp, $type) {
    $m = $asTaskGeneric.MakeGenericMethod($type)
    $task = $m.Invoke($null, @($asyncOp))
    $task.Wait()
    return $task.Result
}

$file = Await ([Windows.Storage.StorageFile]::GetFileFromPathAsync($ImagePath)) ([Windows.Storage.StorageFile])
$stream = Await ($file.OpenAsync([Windows.Storage.FileAccessMode]::Read)) ([Windows.Storage.Streams.IRandomAccessStream])
$decoder = Await ([Windows.Graphics.Imaging.BitmapDecoder]::CreateAsync($stream)) ([Windows.Graphics.Imaging.BitmapDecoder])
$bitmap = Await ($decoder.GetSoftwareBitmapAsync()) ([Windows.Graphics.Imaging.SoftwareBitmap])

$lang = [Windows.Globalization.Language]::new("en-US")
$engine = [Windows.Media.Ocr.OcrEngine]::TryCreateFromLanguage($lang)
if ($engine -eq $null) {
    $engine = [Windows.Media.Ocr.OcrEngine]::TryCreateFromUserProfileLanguages()
}

$asTaskNoGeneric = ([System.WindowsRuntimeSystemExtensions].GetMethods() | Where-Object { $_.Name -eq 'AsTask' -and $_.GetParameters().Count -eq 1 -and $_.GetParameters()[0].ParameterType.Name -eq 'IAsyncOperation`1' })[0]
$m = $asTaskNoGeneric.MakeGenericMethod([Windows.Media.Ocr.OcrResult])
$task = $m.Invoke($null, @($engine.RecognizeAsync($bitmap)))
$task.Wait()
$result = $task.Result

$lines = @()
foreach ($line in $result.Lines) {
    $words = @()
    foreach ($w in $line.Words) {
        $words += @{
            text = $w.Text
            x = $w.BoundingRect.X
            y = $w.BoundingRect.Y
            width = $w.BoundingRect.Width
            height = $w.BoundingRect.Height
        }
    }
    $lines += @{
        text = $line.Text
        words = $words
    }
}

@{
    text = $result.Text
    lines = $lines
} | ConvertTo-Json -Depth 6
