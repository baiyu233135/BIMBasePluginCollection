# -*- coding: utf-8 -*-
"""
自动补丁脚本 - 给 board.py 添加3D预览按钮

使用方法：
    1. 将此文件放到 CADBoard 插件目录（与 board.py 同级）
    2. 在 BIMBase 命令栏输入：
       exec(open(r'C:\ProgramData\PKPM\BIMBase\Plugins\Pro\V1.6\pythonplugin\速构智维\auto_patch_board.py').read())
    3. 或在 VSCode 中按 F5 运行此脚本
    4. 重启 BIMBase，画板中就会出现"3D预览"按钮

功能：
    - 自动检测 board.py 路径
    - 自动添加 preview_3d 导入
    - 自动在工具栏添加"3D预览"按钮
    - 自动添加 _show_3d_preview 方法
    - 已打过补丁的不会重复添加
"""

import os
import sys


def find_board_py():
    """自动查找 board.py 路径"""
    # 方案1：从当前脚本位置推导
    script_dir = os.path.dirname(os.path.abspath(__file__))
    board_path = os.path.join(script_dir, 'board.py')
    if os.path.exists(board_path):
        return board_path
    
    # 方案2：常见安装路径
    candidates = [
        r'C:\ProgramData\PKPM\BIMBase\Plugins\Pro\V1.6\pythonplugin\速构智维\board.py',
        r'D:\ProgramData\PKPM\BIMBase\Plugins\Pro\V1.6\pythonplugin\速构智维\board.py',
    ]
    for p in candidates:
        if os.path.exists(p):
            return p
    
    return None


def patch_board_py(board_path):
    """给 board.py 打补丁"""
    
    with open(board_path, 'r', encoding='utf-8') as f:
        content = f.read()
    
    # 检查是否已经打过补丁
    if 'preview_3d' in content or '_show_3d_preview' in content:
        print("✅ board.py 已经打过3D预览补丁，无需重复操作")
        print("   如果3D预览按钮仍未显示，请检查 preview_3d.py 是否在同目录")
        return True
    
    patches_applied = []
    
    # ========== 补丁1：添加 import ==========
    # 找到 board.py 中 import bimbase_sync 的那一行，在其前面添加 preview_3d 导入
    if 'import bimbase_sync' in content:
        content = content.replace(
            'import bimbase_sync',
            'import bimbase_sync\n\n# 3D预览窗口导入\ntry:\n    from preview_3d import Preview3DWindow\nexcept ImportError:\n    Preview3DWindow = None',
            1
        )
        patches_applied.append("添加 preview_3d 导入")
    
    # ========== 补丁2：在 __init__ 中添加 preview_3d_window 属性 ==========
    # 找到 self.elements = [] 这一行，在其后面添加
    if 'self.elements = []' in content and 'self.preview_3d_window' not in content:
        content = content.replace(
            'self.elements = []',
            'self.elements = []\n        self.preview_3d_window = None  # 3D预览窗口引用',
            1
        )
        patches_applied.append("添加 preview_3d_window 属性")
    
    # ========== 补丁3：在工具栏添加"3D预览"按钮 ==========
    # 找到 "从BIMBase更新" 按钮的代码块，在其后面添加3D预览按钮
    if 'pull_btn = QPushButton("从BIMBase更新")' in content:
        # 找到 pull_btn 的完整代码块
        old_code = '''        pull_btn = QPushButton("从BIMBase更新")
        pull_btn.setToolTip("从BIMBase读取参数更新画板")
        pull_btn.setMinimumWidth(80)
        pull_btn.setStyleSheet("QPushButton { background-color: #1565C0; color: white; }")
        pull_btn.clicked.connect(self._sync_from_bimbase)
        self.toolbar.addWidget(pull_btn)'''
        
        new_code = '''        pull_btn = QPushButton("从BIMBase更新")
        pull_btn.setToolTip("从BIMBase读取参数更新画板")
        pull_btn.setMinimumWidth(80)
        pull_btn.setStyleSheet("QPushButton { background-color: #1565C0; color: white; }")
        pull_btn.clicked.connect(self._sync_from_bimbase)
        self.toolbar.addWidget(pull_btn)

        # ===== 3D预览按钮 =====
        preview_btn = QPushButton("3D预览")
        preview_btn.setToolTip("打开3D预览窗口（独立窗口，支持旋转/缩放/平移）")
        preview_btn.setMinimumWidth(80)
        preview_btn.setStyleSheet("QPushButton { background-color: #2E7D32; color: white; }")
        preview_btn.clicked.connect(self._show_3d_preview)
        self.toolbar.addWidget(preview_btn)'''
        
        if old_code in content:
            content = content.replace(old_code, new_code, 1)
            patches_applied.append("添加3D预览工具栏按钮")
        else:
            # 尝试简化匹配
            content = content.replace(
                'self.toolbar.addWidget(pull_btn)',
                'self.toolbar.addWidget(pull_btn)\n\n        # ===== 3D预览按钮 =====\n        preview_btn = QPushButton("3D预览")\n        preview_btn.setToolTip("打开3D预览窗口（独立窗口，支持旋转/缩放/平移）")\n        preview_btn.setMinimumWidth(80)\n        preview_btn.setStyleSheet("QPushButton { background-color: #2E7D32; color: white; }")\n        preview_btn.clicked.connect(self._show_3d_preview)\n        self.toolbar.addWidget(preview_btn)',
                1
            )
            patches_applied.append("添加3D预览工具栏按钮（简化模式）")
    
    # ========== 补丁4：添加 _show_3d_preview 方法 ==========
    if '_show_3d_preview' not in content:
        # 找到 _sync_from_bimbase 方法，在其前面添加
        preview_method = '''
    # ---------- 3D预览 ----------

    def _show_3d_preview(self):
        """打开3D预览窗口"""
        try:
            from preview_3d import Preview3DWindow

            # 创建或显示窗口
            if self.preview_3d_window is None:
                self.preview_3d_window = Preview3DWindow(
                    canvas_widget=self.viewport,
                    parent=self
                )

            # 刷新数据
            try:
                elements = self.viewport.elements if hasattr(self.viewport, 'elements') else []
                sel_ids = []
                if hasattr(self.viewport, 'selected_elements'):
                    sel_ids = [e.id for e in self.viewport.selected_elements if hasattr(e, 'id')]
                self.preview_3d_window.refresh_from_canvas(elements, sel_ids)
            except Exception as refresh_err:
                print(f"3D预览刷新数据警告: {refresh_err}")

            self.preview_3d_window.show()
            self.preview_3d_window.raise_()
            self.preview_3d_window.activateWindow()
            self.status_bar.showMessage("3D预览窗口已打开 - 左键旋转/滚轮缩放/中键平移")

        except ImportError:
            QMessageBox.warning(self, "3D预览",
                "未找到 preview_3d.py 文件。\\n\\n"
                "请确保 preview_3d.py 与 board.py 在同一目录。")
        except Exception as e:
            import traceback
            traceback.print_exc()
            QMessageBox.warning(self, "3D预览错误",
                f"无法打开3D预览窗口:\\n{str(e)}")

'''
        if 'def _sync_from_bimbase(self):' in content:
            content = content.replace(
                '    def _sync_from_bimbase(self):',
                preview_method + '    def _sync_from_bimbase(self):',
                1
            )
            patches_applied.append("添加 _show_3d_preview 方法")
    
    # ========== 保存 ==========
    if patches_applied:
        # 备份原文件
        backup_path = board_path + '.bak'
        if not os.path.exists(backup_path):
            with open(backup_path, 'w', encoding='utf-8') as f:
                f.write(open(board_path, 'r', encoding='utf-8').read())
            print(f"✅ 已备份原文件: {backup_path}")
        
        # 写入补丁后文件
        with open(board_path, 'w', encoding='utf-8') as f:
            f.write(content)
        
        print(f"\n✅ board.py 补丁应用成功！")
        print(f"   文件路径: {board_path}")
        print(f"\n应用的补丁:")
        for i, p in enumerate(patches_applied, 1):
            print(f"   {i}. {p}")
        print(f"\n⚠️  请重启 BIMBase，然后打开 CADBoard 画板")
        print(f"   工具栏中会出现绿色的【3D预览】按钮")
        return True
    else:
        print("⚠️ 未能应用任何补丁，可能 board.py 格式与预期不符")
        return False


# ============ 主入口 ============
if __name__ == "__main__":
    print("=" * 60)
    print("CADBoard 3D预览自动补丁工具")
    print("=" * 60)
    print()
    
    board_path = find_board_py()
    
    if board_path is None:
        print("❌ 无法自动找到 board.py 文件")
        print()
        print("请手动指定 board.py 的完整路径，")
        print("修改脚本中的 board_path 变量后重新运行。")
        sys.exit(1)
    
    print(f"📄 找到 board.py: {board_path}")
    print()
    
    success = patch_board_py(board_path)
    
    if success:
        print()
        print("=" * 60)
        print("补丁完成！请按以下步骤操作：")
        print("=" * 60)
        print("1. 关闭 BIMBase（完全退出）")
        print("2. 重新启动 BIMBase")
        print("3. 点击【CAD画板】按钮打开画板")
        print("4. 在工具栏中找到绿色的【3D预览】按钮")
        print()
        print("如果补丁有问题，备份文件在：")
        print(f"   {board_path}.bak")
    else:
        print("\n❌ 补丁失败")
        sys.exit(1)
