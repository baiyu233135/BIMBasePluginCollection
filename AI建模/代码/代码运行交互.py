import os
import xml.etree.ElementTree as ET
import subprocess

def get_matching_folders(path):
    matching_folders = []
    for folder in os.listdir(path):
        if "BIMBase建模软件" in folder:
            matching_folders.append(folder)
    if(len(matching_folders)==0):
        for folder in os.listdir(path):
            if "BIMBase KIT" in folder:
                matching_folders.append(folder)
    return matching_folders

def get_folder(folders):
    floder_name = folders[0]
    for name in folders:
        if(int(name[-3:])>int(floder_name[-3:])):
            floder_name = name
    return floder_name
# 获取文件夹
path = "C:\ProgramData\BIMBase"
matching_folders = get_matching_folders(path)
floder = get_folder(matching_folders)

# 从文件中读取 XML 内容
install_dir = r'C:\\ProgramData\BIMBase\\{}\\InstDir.xml'.format(floder)
tree = ET.parse(install_dir)
root = tree.getroot()

# 获取 installDir 元素的内容
install_dir = root.text

# 获取当前脚本所在目录
script_dir = os.path.dirname(os.path.abspath(__file__))

# 定义批处理文件路径
bat_file = os.path.join(script_dir, '代码运行交互.bat')


# 启动批处理文件并传递参数
try:
    subprocess.run([bat_file, install_dir], check=True)
    print("Batch script executed successfully.")
except subprocess.CalledProcessError as e:
    print(f"Error executing batch script: {e}")


