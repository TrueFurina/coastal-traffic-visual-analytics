import os
import sys
import traceback
from pathlib import Path
from prisma.generator.generator import Generator

# 设置必要的环境变量
os.environ['PRISMA_GENERATOR_INVOCATION'] = '1'

# 获取schema.prisma文件路径
schema_path = Path(__file__).parent / 'prisma' / 'schema.prisma'

# 确保schema路径是绝对路径
os.environ['PRISMA_GENERATOR_SCHEMA_PATH'] = str(schema_path.resolve())

# 创建并运行生成器
try:
    generator = Generator()
    print("开始生成Prisma客户端...")
    generator.run()
    print("Prisma客户端生成成功!")
    # 检查生成的客户端文件
    client_path = Path(__file__).parent / 'venv' / 'Lib' / 'site-packages' / 'prisma' / 'client.py'
    if client_path.exists():
        print(f"客户端文件已生成: {client_path}")
    else:
        print("客户端文件未找到，生成可能失败。")

except Exception as e:
    print(f"生成客户端时出错: {e}")
    traceback.print_exc()
    sys.exit(1)