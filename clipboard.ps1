param(
    [Parameter(Mandatory = $true)]
    [string]$OutFile
)

Add-Type -AssemblyName System.Windows.Forms
Add-Type -AssemblyName System.Drawing

$image = [System.Windows.Forms.Clipboard]::GetImage()
if ($null -eq $image) {
    Write-Error "no image found in clipboard"
    exit 1
}

$image.Save($OutFile, [System.Drawing.Imaging.ImageFormat]::Png)
$image.Dispose()
