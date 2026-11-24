import pymupdf
import os
import subprocess
import json

doc = pymupdf.open('D:/UserData/Downloads/Synthetic_Portfolio_Training_Report.pdf')
page = doc[0]

# Render page at 300 DPI (scale = 300 / 72 = 4.1667)
zoom = 300 / 72
mat = pymupdf.Matrix(zoom, zoom)
pix = page.get_pixmap(matrix=mat, alpha=False)
img_path = 'D:/zz/UBP_Extraction_App/backend/page_1_render.png'
pix.save(img_path)
print(f"Rendered Page 1: {pix.width}x{pix.height} at 300 DPI")

# Run Windows Media OCR on page_1_render.png
ps_script = f"""
Add-Type -AssemblyName System.Runtime.WindowsRuntime
$null = [Windows.Media.Ocr.OcrEngine, Windows.Foundation.Diagnostics, ContentType = WindowsRuntime]
$null = [Windows.Graphics.Imaging.BitmapDecoder, Windows.Foundation.Diagnostics, ContentType = WindowsRuntime]
$null = [Windows.Storage.StorageFile, Windows.Foundation.Diagnostics, ContentType = WindowsRuntime]

function Run-Ocr {{
    param($imgPath)
    $file = [Windows.Storage.StorageFile]::GetFileFromPathAsync($imgPath).GetAwaiter().GetResult()
    $stream = $file.OpenAsync([Windows.Storage.FileAccessMode]::Read).GetAwaiter().GetResult()
    $decoder = [Windows.Graphics.Imaging.BitmapDecoder]::CreateAsync($stream).GetAwaiter().GetResult()
    $bitmap = $decoder.GetSoftwareBitmapAsync().GetAwaiter().GetResult()
    $engine = [Windows.Media.Ocr.OcrEngine]::TryCreateFromUserProfileLanguages()
    if ($engine -eq $null) {{
        $engine = [Windows.Media.Ocr.OcrEngine]::TryCreateFromLanguage([Windows.Globalization.Language]::new('en-US'))
    }}
    $result = $engine.RecognizeAsync($bitmap).GetAwaiter().GetResult()
    
    $lines = @()
    foreach ($line in $result.Lines) {{
        $words = @()
        foreach ($w in $line.Words) {{
            $words += @{{
                Text = $w.Text
                X = $w.BoundingRect.X
                Y = $w.BoundingRect.Y
                Width = $w.BoundingRect.Width
                Height = $w.BoundingRect.Height
            }}
        }}
        $lines += @{{
            Text = $line.Text
            Words = $words
        }}
    }}
    return @{{
        Text = $result.Text
        Lines = $lines
    }} | ConvertTo-Json -Depth 5
}}

Run-Ocr '{img_path.replace("/", "\\")}'
"""

res = subprocess.run(["powershell", "-NoProfile", "-Command", ps_script], capture_output=True, text=True)
print("STDOUT:", res.stdout)
print("STDERR:", res.stderr)

