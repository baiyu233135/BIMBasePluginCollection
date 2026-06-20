# -*- coding: utf-8 -*-
"""点命令 - PO"""
from PyQt5.QtGui import QPen, QColor

from commands.base_command import BaseCommand, CommandState
from geometry.elements import PointElement
class PointCommand(BaseCommand):
    name = "点"
    shortcut = "PO"
    description = "绘制点"

    def on_activate(self):
        self.board.status_bar.showMessage(self.get_prompt())

    def on_mouse_press(self, world_x, world_y, button, modifiers):
        if button == 1:
            pt = PointElement(world_x, world_y)
            self.board.apply_current_layer_style(pt)
            self.board.add_element(pt)
            self.board.viewport.update()
            return True
        elif button == 2:
            self.cancel()
            self.board.set_default_command()
            return True
        return False

    def on_mouse_move(self, world_x, world_y, modifiers):
        self.board.status_bar.showMessage(f"点: ({world_x:.2f}, {world_y:.2f})")
        return False

    def get_prompt(self):
        return "点: 点击放置 (右键取消)"

    def draw_preview(self, painter, coord_system):
        return False
