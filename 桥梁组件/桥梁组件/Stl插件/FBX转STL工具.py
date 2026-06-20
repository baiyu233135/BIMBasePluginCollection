#!/usr/bin/env python3
# -*- coding: utf-8 -*-
import os
import sys
import tempfile
import shutil
import tkinter as tk
from tkinter import filedialog, messagebox

def convert_fbx_to_stl(fbx_path, stl_path):
    import pymeshlab
    ms = pymeshlab.MeshSet()
    ms.load_new_mesh(fbx_path)
    
    # pymeshlab 的 save_current_mesh 对中文路径支持有问题，
    # 先保存到临时英文路径，再移动到目标位置
    temp_dir = tempfile.mkdtemp(prefix="fbx2stl_")
    temp_stl = os.path.join(temp_dir, "output.stl")
    ms.save_current_mesh(temp_stl)
    shutil.move(temp_stl, stl_path)
    os.rmdir(temp_dir)

def gui_mode():
    root = tk.Tk()
    root.title("FBX 转 STL 工具")
    root.geometry("520x200")
    root.resizable(False, False)
    
    root.update_idletasks()
    x = (root.winfo_screenwidth() // 2) - (520 // 2)
    y = (root.winfo_screenheight() // 2) - (200 // 2)
    root.geometry(f"+{x}+{y}")
    
    fbx_path_var = tk.StringVar()
    stl_path_var = tk.StringVar()
    
    def select_fbx():
        path = filedialog.askopenfilename(
            title="选择 FBX 文件",
            filetypes=[("FBX 文件", "*.fbx"), ("所有文件", "*.*")]
        )
        if path:
            fbx_path_var.set(path)
            base, _ = os.path.splitext(path)
            stl_path_var.set(base + ".stl")
    
    def select_stl():
        path = filedialog.asksaveasfilename(
            title="保存 STL 文件",
            defaultextension=".stl",
            filetypes=[("STL 文件", "*.stl"), ("所有文件", "*.*")]
        )
        if path:
            stl_path_var.set(path)
    
    def do_convert():
        fbx_path = fbx_path_var.get().strip()
        stl_path = stl_path_var.get().strip()
        
        if not fbx_path or not os.path.exists(fbx_path):
            messagebox.showwarning("提示", "请先选择有效的 FBX 文件")
            return
        if not stl_path:
            messagebox.showwarning("提示", "请设置 STL 保存路径")
            return
        
        convert_btn.config(state="disabled")
        status_var.set("正在转换...")
        root.update()
        
        try:
            convert_fbx_to_stl(fbx_path, stl_path)
            status_var.set("转换成功")
            if messagebox.askyesno("完成", f"STL 已保存到:\n{stl_path}\n\n是否打开所在文件夹？"):
                os.system(f'explorer /select,"{stl_path}"')
        except Exception as e:
            status_var.set("转换失败")
            messagebox.showerror("错误", f"转换失败:\n{str(e)}")
        finally:
            convert_btn.config(state="normal")
            root.update()
    
    tk.Label(root, text="FBX 转 STL 转换工具", font=("微软雅黑", 14, "bold")).pack(pady=(15, 10))
    
    fbx_frame = tk.Frame(root)
    fbx_frame.pack(fill="x", padx=20, pady=5)
    tk.Label(fbx_frame, text="FBX文件:").pack(side="left")
    tk.Entry(fbx_frame, textvariable=fbx_path_var, width=40).pack(side="left", padx=5, fill="x", expand=True)
    tk.Button(fbx_frame, text="浏览...", command=select_fbx, width=8).pack(side="left")
    
    stl_frame = tk.Frame(root)
    stl_frame.pack(fill="x", padx=20, pady=5)
    tk.Label(stl_frame, text="STL保存:").pack(side="left")
    tk.Entry(stl_frame, textvariable=stl_path_var, width=40).pack(side="left", padx=5, fill="x", expand=True)
    tk.Button(stl_frame, text="浏览...", command=select_stl, width=8).pack(side="left")
    
    status_var = tk.StringVar(value="就绪")
    tk.Label(root, textvariable=status_var, fg="gray").pack(pady=5)
    
    convert_btn = tk.Button(root, text="开始转换", command=do_convert, width=20, height=1, font=("微软雅黑", 10))
    convert_btn.pack(pady=10)
    
    root.mainloop()

if __name__ == "__main__":
    gui_mode()
