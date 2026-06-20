
$dllPaths = Get-Content -Path "dlls.txt" -Encoding UTF8
$outPath = "output.txt"
$sb = New-Object System.Text.StringBuilder

function AppendLine($text) {
    [void]$sb.AppendLine($text)
}

foreach ($dllPath in $dllPaths) {
    AppendLine "========== INSPECTING: $dllPath =========="
    if (-not (Test-Path $dllPath)) {
        AppendLine "NOT FOUND"
        continue
    }
    $asm = $null
    try {
        $asm = [System.Reflection.Assembly]::ReflectionOnlyLoadFrom($dllPath)
    } catch [System.BadImageFormatException] {
        AppendLine "BadImageFormatException: likely native/C++ DLL."
        continue
    } catch {
        AppendLine "ReflectionOnlyLoadFrom failed: $($_.Exception.GetType().FullName) : $($_.Exception.Message)"
        try {
            $asm = [System.Reflection.Assembly]::LoadFrom($dllPath)
            AppendLine "LoadFrom succeeded."
        } catch {
            AppendLine "LoadFrom also failed: $($_.Exception.GetType().FullName) : $($_.Exception.Message)"
            continue
        }
    }
    AppendLine "FullName: $($asm.FullName)"
    $attrs = $asm.GetCustomAttributesData()
    $comVis = $attrs | Where-Object { $_.AttributeType.FullName -eq "System.Runtime.InteropServices.ComVisibleAttribute" } | Select-Object -First 1
    $guidAttr = $attrs | Where-Object { $_.AttributeType.FullName -eq "System.Runtime.InteropServices.GuidAttribute" } | Select-Object -First 1
    if ($comVis) { AppendLine "Assembly ComVisible: $($comVis.ConstructorArguments[0].Value)" } else { AppendLine "Assembly ComVisible: (not set)" }
    if ($guidAttr) { AppendLine "Assembly Guid: $($guidAttr.ConstructorArguments[0].Value)" }
    $types = @()
    try {
        $types = $asm.GetTypes()
    } catch [System.Reflection.ReflectionTypeLoadException] {
        $types = $_.Exception.Types | Where-Object { $_ -ne $null }
        AppendLine "ReflectionTypeLoadException; loaded $($types.Count) types."
    } catch {
        AppendLine "GetTypes() failed: $($_.Exception.Message)"
    }
    $publicTypes = $types | Where-Object { $_.IsPublic }
    AppendLine "Public types count: $($publicTypes.Count)"
    $nsList = $publicTypes | Select-Object -ExpandProperty Namespace -Unique | Sort-Object
    AppendLine "Namespaces: $($nsList -join ', ')"
    $comTypes = $publicTypes | Where-Object {
        $attrs = $_.GetCustomAttributesData()
        $hasCom = $attrs | Where-Object { $_.AttributeType.FullName -eq "System.Runtime.InteropServices.ComVisibleAttribute" -and $_.ConstructorArguments[0].Value -eq $true }
        $hasGuid = $attrs | Where-Object { $_.AttributeType.FullName -eq "System.Runtime.InteropServices.GuidAttribute" }
        $hasCom -or $hasGuid
    } | Sort-Object FullName
    if ($comTypes) {
        AppendLine "--- COM-visible / Guid-attributed types ---"
        foreach ($t in $comTypes) {
            $attrs = $t.GetCustomAttributesData()
            $cv = $attrs | Where-Object { $_.AttributeType.FullName -eq "System.Runtime.InteropServices.ComVisibleAttribute" } | Select-Object -First 1
            $g = $attrs | Where-Object { $_.AttributeType.FullName -eq "System.Runtime.InteropServices.GuidAttribute" } | Select-Object -First 1
            $cvVal = if ($cv) { $cv.ConstructorArguments[0].Value } else { "-" }
            $gVal = if ($g) { $g.ConstructorArguments[0].Value } else { "-" }
            AppendLine "$($t.FullName) [$(if($t.IsInterface){'I'}elseif($t.IsClass){'C'}else{'?'})] ComVisible=$cvVal Guid=$gVal"
        }
    } else {
        AppendLine "No explicitly COM-visible types."
    }
    $keywords = @("Model", "Document", "Entity", "Geometry", "Create", "Shape", "Solid", "Mesh", "Point", "Line", "Curve", "Surface", "Body", "Part", "Component", "Element", "Node", "Edge", "Face", "Vertex", "Polyline", "Circle", "Arc", "Box", "Cylinder", "Sphere", "Extrude", "Revolve", "Loft", "Boolean", "Transform", "Matrix", "Vector", "Coordinate")
    $matched = $publicTypes | Where-Object { $n = $_.Name; $keywords | Where-Object { $n -like "*$_*" } } | Sort-Object FullName
    if ($matched) {
        AppendLine "--- Geometry/Model-related types (first 30) ---"
        foreach ($t in ($matched | Select-Object -First 30)) {
            AppendLine ">>> $($t.FullName) [$(if($t.IsClass){'Class'}elseif($t.IsInterface){'Interface'}elseif($t.IsEnum){'Enum'}elseif($t.IsValueType){'Struct'}else{'Other'})] Base: $($t.BaseType)"
            $methods = @()
            try { $methods = $t.GetMethods() | Where-Object { $_.IsPublic -and -not $_.IsSpecialName } | Sort-Object Name } catch {}
            foreach ($m in ($methods | Select-Object -First 10)) {
                $params = ""
                try { $params = ($m.GetParameters() | ForEach-Object { "$($_.ParameterType.Name) $($_.Name)" }) -join ", " } catch { $params = "(error)" }
                AppendLine "  $($m.ReturnType.Name) $($m.Name)($params)"
            }
            if ($methods.Count -gt 10) { AppendLine "  ... and $($methods.Count - 10) more methods" }
            $ctors = @()
            try { $ctors = $t.GetConstructors() | Where-Object { $_.IsPublic } } catch {}
            if ($ctors) {
                foreach ($c in ($ctors | Select-Object -First 2)) {
                    $params = ""
                    try { $params = ($c.GetParameters() | ForEach-Object { "$($_.ParameterType.Name) $($_.Name)" }) -join ", " } catch { $params = "(error)" }
                    AppendLine "  .ctor($params)"
                }
                if ($ctors.Count -gt 2) { AppendLine "  ... and $($ctors.Count - 2) more constructors" }
            }
        }
        if (($matched | Measure-Object).Count -gt 30) {
            AppendLine "... and $(($matched | Measure-Object).Count - 30) more matched types."
        }
    } else {
        AppendLine "No keyword-matched types."
    }
    AppendLine "---------- END ----------"
}

[System.IO.File]::WriteAllText($outPath, $sb.ToString(), [System.Text.Encoding]::UTF8)
