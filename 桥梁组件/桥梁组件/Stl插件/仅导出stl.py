from pyp3d.tool import *

if __name__ == "__main__":
    try:
        execute_command("ExportFbxAll")
        messages("FBX导出完成。\n请使用左侧的【FBX转STL工具】按钮进行转换。")
    except Exception as e:
        messages(f"导出发生错误: {str(e)}")
        exit()
