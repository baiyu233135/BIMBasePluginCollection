# -*- coding: utf-8 -*-
"""
紧急修复脚本 - 恢复 board.py 到可启动状态

解决：'CADBoardWindow' object has no attribute '_show_3d_preview'

会自动检测并修复以下情况：
- 如果有3D预览按钮但没有对应方法 → 添加空方法（画板能启动，按钮点着没反应）
- 如果board.py有备份 → 可选择恢复备份

使用方法：
    exec(open(r'C:\ProgramData\PKPM\BIMBase\Plugins\Pro\V1.6\pythonplugin\速构智维\fix_board_emergency.py').read())
"""

import os
import glob


def find_board_py():
    script_dir = os.path.dirname(os.path.abspath(__file__))
    candidates = [
        os.path.join(script_dir, 'board.py'),
        r'C:\ProgramData\PKPM\BIMBase\Plugins\Pro\V1.6\pythonplugin\速构智维\board.py',
    ]
    for p in candidates:
        if os.path.exists(p):
            return p
    # 搜索当前目录
    for root, dirs, files in os.walk(script_dir):
        if 'board.py' in files:
            return os.path.join(root, 'board.py')
    return None


def find_backup(board_path):
    """查找board.py的备份文件"""
    board_dir = os.path.dirname(board_path)
    backups = glob.glob(board_path + '.*bak*')
    # 按修改时间排序
    backups.sort(key=lambda x: os.path.getmtime(x), reverse=True)
    return backups


def fix_board(board_path):
    with open(board_path, 'r', encoding='utf-8') as f:
        content = f.read()
    
    fixes = []
    
    # 检查1：是否有 _show_3d_preview 方法
    has_method = 'def _show_3d_preview(self):' in content
    
    # 检查2：是否有 preview_btn 按钮引用
    has_button = 'preview_btn' in content and '_show_3d_preview' in content
    
    if not has_button:
        print("✅ board.py 没有3D预览按钮，无需修复")
        return True, []
    
    if has_method:
        print("✅ board.py 已有 _show_3d_preview 方法，无需修复")
        return True, []
    
    # 问题确认：有按钮但无方法 → 需要修复
    print("⚠️  发现问题：有3D预览按钮但缺少 _show_3d_preview 方法")
    print()
    
    # 修复方案A：添加一个空的 _show_3d_preview 方法
    # 找到 _create_toolbar_buttons 方法之前的位置插入
    insert_method = '''
    def _show_3d_preview(self):
        """打开3D预览窗口"""
        QMessageBox.information(self, "3D预览",
            "3D预览功能正在开发中。\\n\\n"
            "当前可以通过以下方式查看3D效果:\\n"
            "1. 设置元素的Z高度属性\\n"
            "2. 点击【同步到BIMBase】生成脚本\\n"
            "3. 在VSCode中运行脚本并在BIMBase中放置查看")

'''
    
    # 找到 _create_toolbar_buttons 方法定义的位置，在它前面插入
    target = '    def _create_toolbar_buttons(self):'
    if target in content:
        # 找到最后一个匹配的位置（类方法）
        idx = content.rfind(target)
        if idx > 0:
            # 在前面一个换行处插入
            insert_idx = content.rfind('\n', 0, idx) + 1
            content = content[:insert_idx] + insert_method + content[insert_idx:]
            fixes.append("添加 _show_3d_preview 方法（占位提示）")
    
    # 同时确保 preview_3d 导入存在
    if 'Preview3DWindow = None' not in content and 'preview_3d' not in content:
        if 'import bimbase_sync' in content:
            content = content.replace(
                'import bimbase_sync',
                'import bimbase_sync\n\ntry:\n    from preview_3d import Preview3DWindow\nexcept ImportError:\n    Preview3DWindow = None',
                1
            )
            fixes.append("添加 preview_3d 导入（带异常保护）")
    
    if not fixes:
        print("⚠️  未能应用任何修复")
        return False, []
    
    # 保存
    with open(board_path, 'w', encoding='utf-8') as f:
        f.write(content)
    
    return True, fixes


# ============ 主入口 ============
if __name__ == "__main__":
    print("=" * 60)
    print("CADBoard 紧急修复工具")
    print("=" * 60)
    print()
    
    board_path = find_board_py()
    if not board_path:
        print("❌ 找不到 board.py 文件")
        exit(1)
    
    print(f"📄 board.py: {board_path}")
    print()
    
    # 检查备份
    backups = find_backup(board_path)
    if backups:
        print(f"📋 发现 {len(backups)} 个备份文件:")
        for i, b in enumerate(backups[:5]):
            mtime = os.path.getmtime(b)
            print(f"   {i+1}. {os.path.basename(b)} ({mtime})")
        print()
        print("如果要恢复备份，请手动将备份文件复制覆盖 board.py")
        print()
    
    # 执行修复
    success, fixes = fix_board(board_path)
    
    if success and fixes:
        print("✅ 修复成功！应用的修复:")
        for f in fixes:
            print(f"   - {f}")
        print()
        print("⚠️  请完全退出 BIMBase，重新启动后画板应能正常打开")
        print("   3D预览按钮会显示提示信息（功能开发中）")
    elif success and not fixes:
        print("✅ board.py 状态正常，无需修复")
    else:
        print("❌ 修复失败")
