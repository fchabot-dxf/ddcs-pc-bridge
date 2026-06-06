# tts-speak.ps1 - dot-source to get Invoke-Tts.
# Speaks via Piper (EN=Norman / FR=Gilles, auto-routed); UTF-8 piped so accents (cedille, etc.)
# pronounce correctly. Falls back to Windows SAPI if Piper/model missing.
# 100% ASCII source (PS 5.1 ANSI-safe): accents detected by code-point, not literal chars.
$script:PiperDir = Join-Path $env:USERPROFILE ".claude\piper"

function Get-TtsLang([string]$text) {
    # accented Latin letters live at code points 192..591; count them, plus FR function words
    $accents = 0
    foreach ($ch in $text.ToCharArray()) {
        $code = [int][char]$ch
        if ($code -ge 192 -and $code -le 591) { $accents++ }
    }
    $fr = ([regex]::Matches($text, '(?i)\b(le|la|les|un|une|des|du|est|et|ou|pour|avec|vous|je|tu|nous|ne|pas|que|qui|dans|sur|ce|cette|mais|donc|alors|merci|oui|non|bonjour|salut|sont|fait|peux|voix|ca)\b')).Count
    $en = ([regex]::Matches($text, '(?i)\b(the|is|are|and|or|for|with|you|we|not|that|which|this|but|so|thanks|yes|no|hello|of|to|it|on)\b')).Count
    if (($accents -ge 1) -or ($fr -gt $en)) { return "fr" } else { return "en" }
}

function Invoke-Tts([string]$msg) {
    if (-not $msg) { return }
    $msg = $msg.Trim()
    if (-not $msg) { return }
    $exe  = Join-Path $script:PiperDir "piper\piper.exe"
    $lang = Get-TtsLang $msg
    $model = if ($lang -eq "fr") { Join-Path $script:PiperDir "fr_FR-gilles-low.onnx" }
             else { Join-Path $script:PiperDir "en_US-norman-medium.onnx" }
    if ((Test-Path $exe) -and (Test-Path $model)) {
        $wav = Join-Path $env:TEMP ("claude_tts_" + $lang + ".wav")
        $txt = Join-Path $env:TEMP ("claude_tts_" + $lang + ".txt")
        # PS 5.1's native pipe drops multibyte UTF-8 (accents) even with $OutputEncoding set.
        # Write the text as UTF-8 (no BOM) and feed Piper via cmd's < redirection (keeps accents).
        [System.IO.File]::WriteAllText($txt, $msg, (New-Object System.Text.UTF8Encoding($false)))
        if (Test-Path $wav) { Remove-Item $wav -Force -ErrorAction SilentlyContinue }
        cmd /c ('"' + $exe + '" -m "' + $model + '" -f "' + $wav + '" < "' + $txt + '"') 2>$null
        if (Test-Path $wav) { (New-Object System.Media.SoundPlayer $wav).PlaySync(); return }
    }
    try {
        Add-Type -AssemblyName System.Speech
        $sp = New-Object System.Speech.Synthesis.SpeechSynthesizer
        try { $sp.SelectVoiceByHints([System.Speech.Synthesis.VoiceGender]::Male) } catch {}
        $sp.Speak($msg)
    } catch {}
}
