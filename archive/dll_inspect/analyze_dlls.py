import os
import sys
import pefile

sys.stdout.reconfigure(encoding='utf-8', errors='replace')

dirs = [
    r"D:\BIMBASE\BIMBase建模软件 2025\PLATFORM",
    r"D:\BIMBASE\BIMBase建模软件 2025\BIMBase",
]

print("Scanning for .NET assemblies and native exports...\n")

for d in dirs:
    if not os.path.isdir(d):
        continue
    print(f"Directory: {d}")
    for f in sorted(os.listdir(d)):
        if not f.lower().endswith(".dll"):
            continue
        path = os.path.join(d, f)
        try:
            pe = pefile.PE(path, fast_load=True)
        except Exception as e:
            print(f"  {f}: ERROR reading PE - {e}")
            continue
        
        is_dotnet = False
        if hasattr(pe, 'DIRECTORY_ENTRY_COM_DESCRIPTOR') and pe.DIRECTORY_ENTRY_COM_DESCRIPTOR:
            is_dotnet = True
        
        exports = []
        if hasattr(pe, 'DIRECTORY_ENTRY_EXPORT') and pe.DIRECTORY_ENTRY_EXPORT:
            try:
                for exp in pe.DIRECTORY_ENTRY_EXPORT.symbols:
                    if exp.name:
                        name = exp.name.decode('utf-8', errors='replace') if isinstance(exp.name, bytes) else str(exp.name)
                        exports.append(name)
            except Exception as e:
                exports.append(f"(error reading exports: {e})")
        
        if is_dotnet:
            print(f"  {f}: .NET assembly")
        elif exports:
            print(f"  {f}: Native / C++ DLL, {len(exports)} exports")
            # Print first 20 exports
            for e in exports[:20]:
                print(f"      {e}")
            if len(exports) > 20:
                print(f"      ... and {len(exports)-20} more exports")
        else:
            print(f"  {f}: Native / C++ DLL, no exports or export table unreadable")
        pe.close()
    print()
