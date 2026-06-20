import os
import sys
import pefile

sys.stdout.reconfigure(encoding='utf-8', errors='replace')

dirs = [
    r"D:\BIMBASE\BIMBase建模软件 2025\PLATFORM",
    r"D:\BIMBASE\BIMBase建模软件 2025\BIMBase",
]

for d in dirs:
    if not os.path.isdir(d):
        continue
    print(f"\nDirectory: {d}")
    for f in sorted(os.listdir(d)):
        if not f.lower().endswith(".dll"):
            continue
        path = os.path.join(d, f)
        try:
            pe = pefile.PE(path)
        except Exception as e:
            print(f"  {f}: ERROR reading PE - {e}")
            continue
        
        is_dotnet = False
        try:
            if hasattr(pe, 'DIRECTORY_ENTRY_COM_DESCRIPTOR') and pe.DIRECTORY_ENTRY_COM_DESCRIPTOR:
                is_dotnet = True
        except:
            pass
        
        exports = []
        try:
            if hasattr(pe, 'DIRECTORY_ENTRY_EXPORT') and pe.DIRECTORY_ENTRY_EXPORT:
                for exp in pe.DIRECTORY_ENTRY_EXPORT.symbols:
                    if exp.name:
                        name = exp.name.decode('utf-8', errors='replace') if isinstance(exp.name, bytes) else str(exp.name)
                        exports.append(name)
        except Exception as e:
            exports.append(f"(error: {e})")
        
        if is_dotnet:
            print(f"  {f}: .NET assembly ({len(exports)} exports)")
        elif exports:
            print(f"  {f}: Native DLL, {len(exports)} exports")
            for e in exports[:10]:
                print(f"      {e}")
            if len(exports) > 10:
                print(f"      ... and {len(exports)-10} more")
        else:
            print(f"  {f}: DLL, no exports")
        pe.close()
