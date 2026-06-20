$dllPaths = @(
    "D:\BIMBASE\BIMBase建模软件 2025\PLATFORM\BIMBaseNet.dll",
    "D:\BIMBASE\BIMBase建模软件 2025\PLATFORM\BIMBaseNet.BIMCore.dll",
    "D:\BIMBASE\BIMBase建模软件 2025\PLATFORM\BIMBaseNet.Geometries.dll",
    "D:\BIMBASE\BIMBase建模软件 2025\PLATFORM\BPPythonBfaAdapter.dll",
    "D:\BIMBASE\BIMBase建模软件 2025\PLATFORM\BPGeomBaseTool.dll",
    "D:\BIMBASE\BIMBase建模软件 2025\BIMBase\BimBaseModel.dll",
    "D:\BIMBASE\BIMBase建模软件 2025\PLATFORM\BPPrimaryElement.dll"
)

$keywords = @("Model", "Document", "Entity", "Geometry", "Create", "Shape", "Solid", "Mesh", "Point", "Line", "Curve", "Surface", "Body", "Part", "Component", "Element", "Node", "Edge", "Face", "Vertex", "Polyline", "Circle", "Arc", "Box", "Cylinder", "Sphere", "Extrude", "Revolve", "Loft", "Boolean", "Transform", "Matrix", "Vector", "Coordinate")

foreach ($dllPath in $dllPaths) {
    if (-not (Test-Path $dllPath)) {
        Write-Host "`n========== NOT FOUND: $dllPath =========="
        continue
    }
    Write-Host "`n========== INSPECTING: $dllPath =========="
    
    $asm = $null
    try {
        $asm = [System.Reflection.Assembly]::ReflectionOnlyLoadFrom($dllPath)
    } catch {
        Write-Host "ReflectionOnlyLoadFrom failed: $($_.Exception.Message)"
        continue
    }
    
    Write-Host "FullName: $($asm.FullName)"
    
    $comVis = $asm.GetCustomAttributesData() | Where-Object { $_.AttributeType.FullName -eq "System.Runtime.InteropServices.ComVisibleAttribute" } | Select-Object -First 1
    $guidAttr = $asm.GetCustomAttributesData() | Where-Object { $_.AttributeType.FullName -eq "System.Runtime.InteropServices.GuidAttribute" } | Select-Object -First 1
    
    if ($comVis) {
        $val = $comVis.ConstructorArguments[0].Value
        Write-Host "Assembly ComVisible: $val"
    } else {
        Write-Host "Assembly ComVisible: (not set)"
    }
    if ($guidAttr) { Write-Host "Assembly Guid: $($guidAttr.ConstructorArguments[0].Value)" }
    
    $types = @()
    try {
        $types = $asm.GetTypes()
    } catch [System.Reflection.ReflectionTypeLoadException] {
        $types = $_.Exception.Types | Where-Object { $_ -ne $null }
        Write-Host "ReflectionTypeLoadException caught; loaded $($types.Count) types."
    } catch {
        Write-Host "GetTypes() failed: $($_.Exception.Message)"
        continue
    }
    
    $publicTypes = $types | Where-Object { $_.IsPublic }
    Write-Host "Public types count: $($publicTypes.Count)"
    
    $nsList = $publicTypes | Select-Object -ExpandProperty Namespace -Unique | Sort-Object
    Write-Host "Namespaces: $($nsList -join ', ')"
    
    # COM-visible / Guid types
    $comTypes = $publicTypes | Where-Object {
        $attrs = $_.GetCustomAttributesData()
        $hasCom = $attrs | Where-Object { $_.AttributeType.FullName -eq "System.Runtime.InteropServices.ComVisibleAttribute" -and $_.ConstructorArguments[0].Value -eq $true }
        $hasGuid = $attrs | Where-Object { $_.AttributeType.FullName -eq "System.Runtime.InteropServices.GuidAttribute" }
        $hasCom -or $hasGuid
    } | Sort-Object FullName
    
    if ($comTypes) {
        Write-Host "`n--- COM-visible / Guid-attributed types ---"
        foreach ($t in $comTypes) {
            $attrs = $t.GetCustomAttributesData()
            $cv = $attrs | Where-Object { $_.AttributeType.FullName -eq "System.Runtime.InteropServices.ComVisibleAttribute" } | Select-Object -First 1
            $g = $attrs | Where-Object { $_.AttributeType.FullName -eq "System.Runtime.InteropServices.GuidAttribute" } | Select-Object -First 1
            $cvVal = if ($cv) { $cv.ConstructorArguments[0].Value } else { "-" }
            $gVal = if ($g) { $g.ConstructorArguments[0].Value } else { "-" }
            Write-Host "$($t.FullName) [$(if($t.IsInterface){'I'}elseif($t.IsClass){'C'}else{'?'})] ComVisible=$cvVal Guid=$gVal"
        }
    } else {
        Write-Host "No explicitly COM-visible types."
    }
    
    # Keyword matched types
    $matched = $publicTypes | Where-Object {
        $n = $_.Name
        $keywords | Where-Object { $n -like "*$_*" }
    } | Sort-Object FullName
    
    if ($matched) {
        Write-Host "`n--- Geometry/Model-related types ---"
        foreach ($t in ($matched | Select-Object -First 40)) {
            Write-Host "`n>> $($t.FullName) [$(if($t.IsClass){'Class'}elseif($t.IsInterface){'Interface'}elseif($t.IsEnum){'Enum'}elseif($t.IsValueType){'Struct'}else{'Other'})] Base: $($t.BaseType)"
            
            $methods = @()
            try {
                $methods = $t.GetMethods() | Where-Object { $_.IsPublic -and -not $_.IsSpecialName } | Sort-Object Name
            } catch { }
            
            foreach ($m in ($methods | Select-Object -First 15)) {
                $params = ""
                try {
                    $params = ($m.GetParameters() | ForEach-Object { "$($_.ParameterType.Name) $($_.Name)" }) -join ", "
                } catch { $params = "(error)" }
                Write-Host "  $($m.ReturnType.Name) $($m.Name)($params)"
            }
            if ($methods.Count -gt 15) { Write-Host "  ... and $($methods.Count - 15) more methods" }
            
            $ctors = @()
            try {
                $ctors = $t.GetConstructors() | Where-Object { $_.IsPublic }
            } catch { }
            if ($ctors) {
                foreach ($c in ($ctors | Select-Object -First 3)) {
                    $params = ""
                    try {
                        $params = ($c.GetParameters() | ForEach-Object { "$($_.ParameterType.Name) $($_.Name)" }) -join ", "
                    } catch { $params = "(error)" }
                    Write-Host "  .ctor($params)"
                }
                if ($ctors.Count -gt 3) { Write-Host "  ... and $($ctors.Count - 3) more constructors" }
            }
        }
        if (($matched | Measure-Object).Count -gt 40) {
            Write-Host "`n... and $(($matched | Measure-Object).Count - 40) more matched types."
        }
    } else {
        Write-Host "No keyword-matched types."
    }
    
    Write-Host "`n---------- END ----------"
}
