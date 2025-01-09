from PIL import Image
import os

def convert_to_ico(png_path, ico_path):
    """将PNG图片转换为ICO格式，包含多个尺寸"""
    try:
        # 打开PNG图片
        img = Image.open(png_path)
        print(f"原始图片大小: {img.size}")
        
        # 创建不同尺寸的图标
        sizes = [(16,16), (32,32), (48,48), (256,256)]
        print("\n正在生成多个尺寸的图标...")
        for size in sizes:
            print(f"- 生成 {size[0]}x{size[1]} 像素的图标")
            
        # 保存包含所有尺寸的ICO文件
        img.save(ico_path, format='ICO', sizes=sizes)
        print(f"\n转换成功！ICO文件已保存到: {ico_path}")
        print("该ICO文件包含以下尺寸的图标：")
        for size in sizes:
            print(f"- {size[0]}x{size[1]} 像素")
            
    except Exception as e:
        print(f"转换失败: {str(e)}")

if __name__ == '__main__':
    # 转换图片
    png_path = 'image/app_logo.png'
    ico_path = 'image/app_logo.ico'
    
    if not os.path.exists(png_path):
        print(f"错误：找不到PNG文件: {png_path}")
    else:
        print(f"开始转换 {png_path} 为ICO格式...")
        convert_to_ico(png_path, ico_path) 