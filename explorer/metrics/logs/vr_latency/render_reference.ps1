$ErrorActionPreference = 'Stop'
$taskRoot = 'C:\Users\25298\Desktop\FPGA'
$sourceDoc = Join-Path $taskRoot '01_文档\探路者_竞赛技术文档V1.5_数据更新参考稿.docx'
$reviewDir = Join-Path $taskRoot '07_实验记录\VR时延清洗_20261103\render_review'
New-Item -ItemType Directory -Force -Path $reviewDir | Out-Null
$pdfFile = Join-Path $reviewDir 'reference.pdf'
$wordApp = $null
$reviewDoc = $null
try {
    $wordApp = New-Object -ComObject Word.Application
    $wordApp.Visible = $false
    $wordApp.DisplayAlerts = 0
    $reviewDoc = $wordApp.Documents.Open($sourceDoc, $false, $false)
    $reviewDoc.Repaginate()
    foreach ($toc in $reviewDoc.TablesOfContents) { $toc.UpdatePageNumbers() }
    $reviewDoc.Repaginate()
    $reviewDoc.Save()
    $reviewDoc.ExportAsFixedFormat($pdfFile, 17)
    Write-Output "PDF_READY $pdfFile"
    Write-Output "PAGES $($reviewDoc.ComputeStatistics(2))"
} finally {
    if ($null -ne $reviewDoc) { $reviewDoc.Close(0) }
    if ($null -ne $wordApp) { $wordApp.Quit(0) }
}
