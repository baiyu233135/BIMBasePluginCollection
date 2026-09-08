# -*- coding: utf-8 -*-
"""
board.py 修改补丁 - 集成3D预览和修正后的BIMBase同步

使用方法：
1. 将本文件中所有方法添加到 board.py 的 CADBoardWindow 类中
2. 按下面的说明修改 _create_toolbar_buttons 方法
3. 修改 _sync_to_bimbase 方法
4. 添加 preview_3d 模块导入

需要添加的导入（放在board.py顶部import区域）：
    from preview_3d import Preview3DWindow

需要在 __init__ 中添加（约第xxx行，CADBoardWindow.__init__中）：
    self.preview_3d_window = None  # 3D预览窗口引用
"""

# ===== 以下方法需要添加到 CADBoardWindow 类中 =====

def _create_toolbar_buttons_patched(self):
    """
    替换原有的 _create_toolbar_buttons 方法
    在"同步到BIMBase"按钮后面添加"3D预览"按钮
    """
    self.toolbar.addWidget(QLabel("<b>文件</b>"))

    import_btn = QPushButton("导入DWG")
    import_btn.setToolTip("导入DWG/DXF文件")
    import_btn.setMinimumWidth(80)
    import_btn.clicked.connect(self._import_dwg)
    self.toolbar.addWidget(import_btn)

    export_btn = QPushButton("导出DWG")
    export_btn.setToolTip("导出为DXF/DWG文件")
    export_btn.setMinimumWidth(80)
    export_btn.clicked.connect(self._export_dwg)
    self.toolbar.addWidget(export_btn)

    sync_btn = QPushButton("同步到BIMBase")
    sync_btn.setToolTip("将当前画板内容同步为BIMBase参数化组件(手动place放置)")
    sync_btn.setMinimumWidth(80)
    sync_btn.setStyleSheet("QPushButton { background-color: #1565C0; color: white; }")
    sync_btn.clicked.connect(self._sync_to_bimbase)
    self.toolbar.addWidget(sync_btn)

    pull_btn = QPushButton("从BIMBase更新")
    pull_btn.setToolTip("从BIMBase手动刷新(有限支持)")
    pull_btn.setMinimumWidth(80)
    pull_btn.setStyleSheet("QPushButton { background-color: #1565C0; color: white; }")
    pull_btn.clicked.connect(self._sync_from_bimbase)
    self.toolbar.addWidget(pull_btn)

    # ===== 新增：3D预览按钮 =====
    preview_btn = QPushButton("3D预览")
    preview_btn.setToolTip("打开3D预览窗口(独立窗口，支持旋转/缩放/平移)")
    preview_btn.setMinimumWidth(80)
    preview_btn.setStyleSheet("QPushButton { background-color: #2E7D32; color: white; }")
    preview_btn.clicked.connect(self._show_3d_preview)
    self.toolbar.addWidget(preview_btn)
    # ===== 新增结束 =====

    self.toolbar.addSeparator()

    self.toolbar.addWidget(QLabel("<b>绘图</b>"))
    # ... 其余按钮保持不变 ...


def _show_3d_preview(self):
    """
    新增方法：显示3D预览窗口
    """
    try:
        from preview_3d import Preview3DWindow

        # 创建或显示窗口
        if self.preview_3d_window is None:
            self.preview_3d_window = Preview3DWindow(
                canvas_widget=self.viewport,
                parent=self
            )

        # 刷新数据
        self.preview_3d_window.refresh_from_canvas(
            self.viewport.elements,
            [e.id for e in self.viewport.selected_elements if hasattr(e, 'id')]
        )

        self.preview_3d_window.show()
        self.preview_3d_window.raise_()
        self.preview_3d_window.activateWindow()
        self.status_bar.showMessage("3D预览窗口已打开")

    except Exception as e:
        import traceback
        traceback.print_exc()
        QMessageBox.warning(self, "3D预览错误",
            f"无法打开3D预览窗口:\n{str(e)}\n\n请确保 preview_3d.py 文件存在于插件目录中。")


def _sync_to_bimbase_patched(self):
    """
    替换原有的 _sync_to_bimbase 方法
    使用修正后的 bimbase_sync API
    """
    try:
        # 尝试导入新的同步模块
        from bimbase_sync import BIMBaseSync
        use_new_api = True
    except ImportError:
        use_new_api = False

    if use_new_api:
        # 使用新的API
        try:
            from pyp3d import place, Component
        except ImportError:
            QMessageBox.warning(self, "同步失败",
                "未在BIMBase环境中运行，无法同步。\n请在BIMBase软件中运行插件。")
            return
    else:
        # 回退到旧API
        if not bimbase_sync.is_bimbase_available():
            QMessageBox.warning(self, "同步失败",
                "未在BIMBase环境中运行，无法同步。\n请在BIMBase软件中运行插件。")
            return

    if not self.elements:
        QMessageBox.information(self, "同步", "画板为空，没有可同步的内容。")
        return

    if use_new_api:
        # 使用新API：为每个元素创建Component并手动place
        sync = BIMBaseSync(self.elements)
        results = sync.sync_all()
        status = sync.get_status()
        count = status['synced']
        error_count = status['errors']

        msg = f"同步到BIMBase完成: {count} 个元素已启动place"
        if error_count > 0:
            msg += f"\n错误: {error_count} 个"
            for r in results:
                if r.startswith("错误:"):
                    msg += f"\n- {r}"
                    if msg.count("\n") > 8:
                        msg += "\n..."
                        break

        QMessageBox.information(self, "同步结果", msg)
        self.status_bar.showMessage(f"已同步 {count} 个元素到BIMBase (请逐个点击放置位置)")
    else:
        # 旧API
        count, errors, replaced, manual = bimbase_sync.sync_to_bimbase(self.elements)
        msg = f"同步到BIMBase完成: {count} 个元素成功"
        if manual:
            msg += f"\n手动放置: {len(manual)} 个"
        if errors:
            msg += f"\n错误: {len(errors)} 个"
            for e in errors[:5]:
                msg += f"\n- {e}"
        QMessageBox.information(self, "同步结果", msg)
        self.status_bar.showMessage(f"已同步 {count} 个元素到BIMBase")
