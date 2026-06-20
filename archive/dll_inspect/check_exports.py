import os
import sys
import pefile

sys.stdout.reconfigure(encoding='utf-8', errors='replace')

base = r"D:\BIMBASE\BIMBase建模软件 2025\PLATFORM"
files = ['BPPythonBfaAdapter.dll', 'BPGeomBaseTool.dll', 'BimBaseModel.dll', 'BPPrimaryElement.dll', 'BIMBaseNet.Geometries.dll']

for f in files:
    path = os.path.join(base, f)
    try:
        pe = pefile.PE(path)
        exports = []
        if hasattr(pe, 'DIRECTORY_ENTRY_EXPORT') and pe.DIRECTORY_ENTRY_EXPORT:
            for exp in pe.DIRECTORY_ENTRY_EXPORT.symbols:
                if exp.name:
                    n = exp.name.decode('utf-8', errors='replace') if isinstance(exp.name, bytes) else str(exp.name)
                    exports.append(n)
        print(f"{f}: {len(exports)} exports")
        for e in exports[:20]:
            print(f"  {e}")
        if len(exports) > 20:
            print(f"  ... and {len(exports)-20} more")
        # Check for .NET COM descriptor
        is_dotnet = False
        try:
            if hasattr(pe, 'DIRECTORY_ENTRY_COM_DESCRIPTOR') and pe.DIRECTORY_ENTRY_COM_DESCRIPTOR:
                is_dotnet = True
        except:
            pass
        print(f"  Is .NET (COM descriptor): {is_dotnet}")
        pe.close()
    except Exception as e:
        print(f"{f}: ERROR - {e}")
