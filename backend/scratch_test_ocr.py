import subprocess

ps_code = """
Add-Type -AssemblyName System.Runtime.WindowsRuntime
$null = [Windows.Media.Ocr.OcrEngine, Windows.Foundation.Diagnostics, ContentType = WindowsRuntime]
$langs = [Windows.Media.Ocr.OcrEngine]::AvailableRecognizerLanguages
Write-Output "LANG_COUNT: $($langs.Count)"
foreach ($l in $langs) {
    Write-Output "LANG: $($l.LanguageTag)"
}
"""

res = subprocess.run(["powershell", "-NoProfile", "-Command", ps_code], capture_output=True, text=True)
print("STDOUT:", res.stdout)
print("STDERR:", res.stderr)
