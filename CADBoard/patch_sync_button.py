# -*- coding: utf-8 -*-
"""
补丁脚本2 - 修改 board.py 的同步按钮行为
将"同步到BIMBase"改为安全的"导出脚本"模式，避免闪退

运行方式：
    exec(open(r'C:\ProgramData\PKPM\BIMBase\Plugins\Pro\V1.6\pythonplugin\CADBoard\patch_sync_button.py').read())

功能：
    - 替换 _sync_to_bimbase 方法为安全模式（生成脚本文件）
    - 保留 _sync_from_bimbase 方法
"""

import os


def find_board_py():
    script_dir = os.path.dirname(os.path.abspath(__file__))
    board_path = os.path.join(script_dir, 'board.py')
    if os.path.exists(board_path):
        return board_path
    candidates = [
        r'C:\ProgramData\PKPM\BIMBase\Plugins\Pro\V1.6\pythonplugin\CADBoard\board.py',
    ]
    for p in candidates:
        if os.path.exists(p):
            return p
    return None


def patch_sync_method(board_path):
    with open(board_path, 'r', encoding='utf-8') as f:
        content = f.read()
    
    # 检查是否已经打过补丁
    if 'export_script' in content:
        print("✅ 同步按钮已经打过补丁（安全模式），无需重复操作")
        return True
    
    # 替换 _sync_to_bimbase 方法
    old_sync = '''    def _sync_to_bimbase(self):
        if not bimbase_sync.is_bimbase_available():
            QMessageBox.warning(self, "同步失败",
                "未在BIMBase环境中运行，无法同步。\\n请在BIMBase软件中运行插件。")
            return
        if not self.elements:
            QMessageBox.information(self, "同步", "画板为空，没有可同步的内容。")
            return
        count, errors = bimbase_sync.sync_to_bimbase(self.elements)
        msg = f"同步到BIMBase完成: {count} 个元素成功"
        if errors:
            msg += f"\\n错误: {len(errors)} 个"
            for e in errors[:5]:
                msg += f"\\n- {e}"
        QMessageBox.information(self, "同步结果", msg)
        self.status_bar.showMessage(f"已同步 {count} 个元素到BIMBase")'''
    
    new_sync = '''    def _sync_to_bimbase(self):
        """同步到BIMBase - 安全模式（生成脚本文件）"""
        if not self.elements:
            QMessageBox.information(self, "同步", "画板为空，没有可同步的内容。")
            return
        try:
            from bimbase_sync import BIMBaseSync
            sync = BIMBaseSync(self.elements)
            success, msg, path = sync.export_script()
            if success:
                QMessageBox.information(self, "同步脚本已生成", msg)
                self.status_bar.showMessage(f"同步脚本已生成: {path}")
            else:
                QMessageBox.warning(self, "同步失败", msg)
        except Exception as e:
            import traceback
            traceback.print_exc()
            QMessageBox.warning(self, "同步错误", f"同步失败: {str(e)}")'''
    
    if old_sync in content:
        content = content.replace(old_sync, new_sync, 1)
        patches = "替换 _sync_to_bimbase 为安全模式（导出脚本）"
    else:
        # 尝试查找简化的 _sync_to_bimbase
        if 'def _sync_to_bimbase(self):' in content:
            # 找到方法开始的位置，替换整个方法体
            start_idx = content.find('def _sync_to_bimbase(self):')
            # 找到下一个方法定义
            next_def_idx = content.find('\n    def ', start_idx + 1)
            if next_def_idx == -1:
                next_def_idx = len(content)
            
            old_method = content[start_idx:next_def_idx]
            content = content[:start_idx] + new_sync + '\n\n' + content[next_def_idx:]
            patches = "替换 _sync_to_bimbase 为安全模式（模糊匹配）"
        else:
            print("❌ 在 board.py 中找不到 _sync_to_bimbase 方法")
            return False
    
    # 保存
    backup_path = board_path + '.sync_bak'
    if not os.path.exists(backup_path):
        with open(backup_path, 'w', encoding='utf-8') as f:
            f.write(open(board_path, 'r', encoding='utf-8').read())
    
    with open(board_path, 'w', encoding='utf-8') as f:
        f.write(content)
    
    print(f"✅ 同步按钮补丁应用成功！")
    print(f"   {patches}")
    return True


# ============ 主入口 ============
if __name__ == "__main__":
    print("=" * 50)
    print("同步按钮安全模式补丁")
    print("=" * 50)
    
    board_path = find_board_py()
    if board_path is None:
        print("❌ 找不到 board.py")
        exit(1)
    
    print(f"📄 目标: {board_path}")
    success = patch_sync_method(board_path)
    
    if success:
        print("\n⚠️  请重启 BIMBase 后生效")
        print("   点击【同步到BIMBase】将生成脚本文件而非直接调用place()")
