$dllPaths = @(
    "D:\BIMBASE\BIMBase建模软件 2025\PLATFORM\BIMBaseNet.dll",
    "D:\BIMBASE\BIMBase建模软件 2025\PLATFORM\BIMBaseNet.BIMCore.dll",
    "D:\BIMBASE\BIMBase建模软件 2025\PLATFORM\BIMBaseNet.Geometries.dll",
    "D:\BIMBASE\BIMBase建模软件 2025\PLATFORM\BPPythonBfaAdapter.dll",
    "D:\BIMBASE\BIMBase建模软件 2025\PLATFORM\BPGeomBaseTool.dll",
    "D:\BIMBASE\BIMBase建模软件 2025\BIMBase\BimBaseModel.dll",
    "D:\BIMBASE\BIMBase建模软件 2025\PLATFORM\BPPrimaryElement.dll"
)

$baseDir = "D:\BIMBASE\BIMBase建模软件 2025"

$onResolve = [System.ResolveEventHandler] {
    param($sender, $e)
    $name = New-Object System.Reflection.AssemblyName($e.Name)
    $paths = @(
        (Join-Path $baseDir "PLATFORM" ($name.Name + ".dll")),
        (Join-Path $baseDir "BIMBase" ($name.Name + ".dll")),
        (Join-Path $baseDir "DwgAndT" ($name.Name + ".dll")),
        (Join-Path $baseDir ($name.Name + ".dll"))
    )
    foreach ($p in $paths) {
        if (Test-Path $p) {
            try { return [System.Reflection.Assembly]::LoadFrom($p) } catch { }
        }
    }
    return $null
}
[System.AppDomain]::CurrentDomain.add_AssemblyResolve($onResolve)

$keywords = @("Model", "Document", "Entity", "Geometry", "Create", "Shape", "Solid", "Mesh", "Point", "Line", "Curve", "Surface", "Body", "Part", "Component", "Element", "Node", "Edge", "Face", "Vertex", "Polyline", "Circle", "Arc", "Box", "Cylinder", "Sphere", "Extrude", "Revolve", "Loft", "Boolean", "Transform", "Matrix", "Vector", "Coordinate")

foreach ($dllPath in $dllPaths) {
    if (-not (Test-Path $dllPath)) {
        Write-Host "`n========== SKIPPING (not found): $dllPath =========="
        continue
    }
    Write-Host "`n========== INSPECTING: $dllPath =========="
    
    $asm = $null
    try {
        $asm = [System.Reflection.Assembly]::LoadFrom($dllPath)
    } catch {
        Write-Host "LoadFrom failed: $($_.Exception.Message)"
        try {
            $asm = [System.Reflection.Assembly]::ReflectionOnlyLoadFrom($dllPath)
            Write-Host "Loaded via ReflectionOnlyLoadFrom."
        } catch {
            Write-Host "ReflectionOnlyLoadFrom also failed: $($_.Exception.Message)"
            continue
        }
    }
    
    Write-Host "FullName: $($asm.FullName)"
    $attrs = $asm.GetCustomAttributes($true)
    $comVis = $attrs | Where-Object { $_ -is [System.Runtime.InteropServices.ComVisibleAttribute] } | Select-Object -First 1
    $guidAttr = $attrs | Where-Object { $_ -is [System.Runtime.InteropServices.GuidAttribute] } | Select-Object -First 1
    Write-Host "Assembly ComVisible: $(if($comVis){$comVis.Value}else{'(not set)'})"
    Write-Host "Assembly Guid: $(if($guidAttr){$guidAttr.Value}else{'(not set)'})"
    
    $publicTypes = @()
    try {
        $publicTypes = $asm.GetTypes() | Where-Object { $_.IsPublic }
    } catch {
        Write-Host "GetTypes() failed: $($_.Exception.Message)"
        continue
    }
    
    Write-Host "Public types count: $($publicTypes.Count)"
    
    $nsList = $publicTypes | Select-Object -ExpandProperty Namespace -Unique | Sort-Object
    Write-Host "Namespaces: $($nsList -join ', ')"
    
    # COM types
    $comTypes = $publicTypes | Where-Object {
        $cv = $_.GetCustomAttributes([System.Runtime.InteropServices.ComVisibleAttribute], $true)
        $g = $_.GetCustomAttributes([System.Runtime.InteropServices.GuidAttribute], $false)
        ($cv -and ($cv | Where-Object { $_.Value -eq $true })) -or $g
    } | Sort-Object FullName
    
    if ($comTypes) {
        Write-Host "`n--- COM-visible / Guid-attributed types ---"
        foreach ($t in $comTypes) {
            $cv = $t.GetCustomAttributes([System.Runtime.InteropServices.ComVisibleAttribute], $true) | Select-Object -First 1
            $g = $t.GetCustomAttributes([System.Runtime.InteropServices.GuidAttribute], $false) | Select-Object -First 1
            Write-Host "$($t.FullName) [Kind:$(if($t.IsInterface){'Interface'}elseif($t.IsClass){'Class'}else{'Other'})] [ComVisible:$(if($cv){$cv.Value}else{'-'})] [Guid:$(if($g){$g.Value}else{'-'})]"
        }
    } else {
        Write-Host "No explicitly COM-visible types found."
    }
    
    # Keyword types
    $matched = $publicTypes | Where-Object {
        $n = $_.Name
        $keywords | Where-Object { $n -like "*$_*" }
    } | Sort-Object FullName
    
    if ($matched) {
        Write-Host "`n--- Geometry/Model-related types ---"
        foreach ($t in $matched) {
            Write-Host "`n>> $($t.FullName) [$(if($t.IsClass){'Class'}elseif($t.IsInterface){'Interface'}elseif($t.IsEnum){'Enum'}else{'Other'})] [Base: $($t.BaseType)]"
            
            # Methods
            $methods = $t.GetMethods([System.Reflection.BindingFlags]::Public -bor [System.Reflection.BindingFlags]::Instance -bor [System.Reflection.BindingFlags]::Static) | Where-Object { $_.IsPublic -and -not $_.IsSpecialName } | Sort-Object Name
            foreach ($m in ($methods | Select-Object -First 20)) {
                $params = ($m.GetParameters() | ForEach-Object { "$($_.ParameterType.Name) $($_.Name)" }) -join ", "
                Write-Host "  $($m.ReturnType.Name) $($m.Name)($params)"
            }
            if ($methods.Count -gt 20) { Write-Host "  ... and $($methods.Count - 20) more methods" }
            
            # Constructors
            $ctors = $t.GetConstructors([System.Reflection.BindingFlags]::Public -bor [System.Reflection.BindingFlags]::Instance) | Where-Object { $_.IsPublic }
            if ($ctors) {
                Write-Host "  Constructors:"
                foreach ($c in ($ctors | Select-Object -First 5)) {
                    $params = ($c.GetParameters() | ForEach-Object { "$($_.ParameterType.Name) $($_.Name)" }) -join ", "
                    Write-Host "    .ctor($params)"
                }
                if ($ctors.Count -gt 5) { Write-Host "    ... and $($ctors.Count - 5) more constructors" }
            }
        }
    } else {
        Write-Host "No keyword-matched types."
    }
    
    Write-Host "`n---------- END $($asm.GetName().Name) ----------"
}
