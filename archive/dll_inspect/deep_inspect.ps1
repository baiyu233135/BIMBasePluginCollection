param([string]$DllPath, [string]$OutPath)

$asm = $null
try {
    $asm = [System.Reflection.Assembly]::ReflectionOnlyLoadFrom($DllPath)
} catch {
    try {
        $asm = [System.Reflection.Assembly]::LoadFrom($DllPath)
    } catch {
        [System.IO.File]::WriteAllText($OutPath, "FAILED: $($_.Exception.Message)")
        exit 1
    }
}

$sb = New-Object System.Text.StringBuilder
function AppendLine($text) { [void]$sb.AppendLine($text) }

AppendLine "Assembly: $($asm.FullName)"

$types = @()
try {
    $types = $asm.GetTypes()
} catch [System.Reflection.ReflectionTypeLoadException] {
    $types = $_.Exception.Types | Where-Object { $_ -ne $null }
    AppendLine "ReflectionTypeLoadException; loaded $($types.Count) types."
} catch {
    AppendLine "GetTypes failed: $($_.Exception.Message)"
    [System.IO.File]::WriteAllText($OutPath, $sb.ToString())
    exit 1
}

$publicTypes = $types | Where-Object { $_.IsPublic } | Sort-Object FullName
AppendLine "Public types: $($publicTypes.Count)"
AppendLine ""

foreach ($t in $publicTypes) {
    $kind = if($t.IsInterface){'Interface'}elseif($t.IsClass){'Class'}elseif($t.IsEnum){'Enum'}elseif($t.IsValueType){'Struct'}else{'Other'}
    $base = if($t.BaseType){$t.BaseType.FullName}else{'none'}
    AppendLine "$($t.FullName) [$kind] Base: $base"
}

AppendLine ""
AppendLine "=== All public methods on all types ==="
foreach ($t in ($publicTypes | Sort-Object FullName)) {
    AppendLine ""
    AppendLine "-- $($t.FullName) --"
    $methods = $t.GetMethods() | Where-Object { $_.IsPublic -and -not $_.IsSpecialName } | Sort-Object Name
    foreach ($m in $methods) {
        $params = ""
        try { $params = ($m.GetParameters() | ForEach-Object { "$($_.ParameterType.FullName) $($_.Name)" }) -join ", " } catch { $params = "(error)" }
        AppendLine "  $($m.ReturnType.FullName) $($m.Name)($params)"
    }
    $ctors = $t.GetConstructors() | Where-Object { $_.IsPublic }
    if ($ctors) {
        AppendLine "  Constructors:"
        foreach ($c in $ctors) {
            $params = ""
            try { $params = ($c.GetParameters() | ForEach-Object { "$($_.ParameterType.FullName) $($_.Name)" }) -join ", " } catch { $params = "(error)" }
            AppendLine "    .ctor($params)"
        }
    }
}

[System.IO.File]::WriteAllText($OutPath, $sb.ToString(), [System.Text.Encoding]::UTF8)
