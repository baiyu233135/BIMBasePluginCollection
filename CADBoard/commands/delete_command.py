# -*- coding: utf-8 -*-
"""删除命令 - E"""
from commands.base_command import BaseCommand, CommandState
class DeleteCommand(BaseCommand):
    name = "删除"
    shortcut = "E"
    description = "删除选中的元素"
    is_modify_command = True

    def __init__(self, board):
        super().__init__(board)
        self._confirmed = False

    def on_activate(self):
        self._confirmed = False
        selected = self._get_selected_elements()
        if selected:
            self._confirmed = True
            self._execute_delete()
        else:
            self.board.status_bar.showMessage("删除: 点击选择要删除的对象 (右键取消)")

    def on_mouse_press(self, world_x, world_y, button, modifiers):
        if button == 1:
            if not self._confirmed:
                self._try_select_at(world_x, world_y)
                selected = self._get_selected_elements()
                if selected:
                    self._execute_delete()
                self.board.viewport.update()
                return True
        elif button == 2:
            self.cancel()
            self.board.set_default_command()
            return True
        return False

    def _execute_delete(self):
        selected = self._get_selected_elements()
        for e in selected:
            if e in self.board.elements:
                self.board.elements.remove(e)
        self._clear_selection()
        self.board.status_bar.showMessage(f"已删除 {len(selected)} 个元素")
        self.cancel()
        self.board.set_default_command()

    def on_mouse_move(self, world_x, world_y, modifiers):
        return False

    def get_prompt(self):
        return "删除: 选择对象删除"

    def draw_preview(self, painter, coord_system):
        return False
