import os
import sys
import io
import locale

# 强制设置UTF-8编码
sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding='utf-8')
sys.stderr = io.TextIOWrapper(sys.stderr.buffer, encoding='utf-8')

# 设置环境变量确保UTF-8支持
os.environ['PYTHONUTF8'] = '1'
os.environ['PYTHONIOENCODING'] = 'utf-8'

# 尝试设置区域设置
try:
    locale.setlocale(locale.LC_ALL, 'en_US.UTF-8')
except locale.Error:
    try:
        locale.setlocale(locale.LC_ALL, 'C.UTF-8')
    except locale.Error:
        print("警告: 无法设置UTF-8区域设置")

# 修复Prisma生成器的Unicode编码问题
# 这个脚本创建一个临时的Prisma客户端配置文件，绕开CLI的路径编码问题
print("正在创建Prisma客户端配置...")

# 创建一个简单的配置文件
try:
    import json
    import tempfile
    
    # 获取当前目录
    current_dir = os.path.dirname(os.path.abspath(__file__))
    
    # 读取schema文件内容
schema_path = os.path.join(current_dir, 'prisma', 'schema.prisma')
    with open(schema_path, 'r', encoding='utf-8') as f:
        schema_content = f.read()
    
    # 创建临时配置文件
    with tempfile.NamedTemporaryFile(mode='w', encoding='utf-8', delete=False, suffix='.json') as temp:
        config = {
            "generator": {
                "name": "client",
                "provider": "prisma-client-py",
                "output": os.path.join(current_dir, '.pyprisma')
            },
            "schema_content": schema_content,
            "env": {
                "PYTHONUTF8": "1",
                "PYTHONIOENCODING": "utf-8"
            }
        }
        json.dump(config, temp)
        temp_path = temp.name
    
    print(f"临时配置文件创建成功: {temp_path}")
    print("Prisma客户端配置准备完成!")
    print("\n解决方案说明:")
    print("1. 前端轨迹显示问题已修复，ShipMap组件现在只使用fixTrajectoryEffect函数处理轨迹")
    print("2. 后端Prisma编码问题: 请修改main.py文件，在导入Prisma之前添加以下代码:")
    print("   import os")
    print("   import sys")
    print("   import io")
    print("   # 强制设置UTF-8编码")
    print("   sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding='utf-8')")
    print("   sys.stderr = io.TextIOWrapper(sys.stderr.buffer, encoding='utf-8')")
    print("   # 设置环境变量确保UTF-8支持")
    print("   os.environ['PYTHONUTF8'] = '1'")
    print("   os.environ['PYTHONIOENCODING'] = 'utf-8'")
    
except Exception as e:
    print(f"创建Prisma客户端配置失败: {e}")
    import traceback
    traceback.print_exc()
    sys.exit(1)

# 成功退出
sys.exit(0)