import os
import sys
import io
import subprocess
import traceback

# 强制设置UTF-8编码
sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding='utf-8')
sys.stderr = io.TextIOWrapper(sys.stderr.buffer, encoding='utf-8')

print("开始生成Prisma客户端...")
print(f"当前工作目录: {os.getcwd()}")

# 创建环境变量副本
env = os.environ.copy()

# 设置UTF-8相关环境变量
env['PYTHONUTF8'] = '1'
env['PYTHONIOENCODING'] = 'utf-8'
env['LANG'] = 'en_US.UTF-8'
env['LC_ALL'] = 'en_US.UTF-8'

# 尝试找到npm和prisma命令
npm_path = None
prisma_path = None

# 检查系统路径
paths = os.environ.get('PATH', '').split(os.pathsep)
for path in paths:
    if os.path.exists(os.path.join(path, 'npm.cmd')):
        npm_path = os.path.join(path, 'npm.cmd')
    if os.path.exists(os.path.join(path, 'prisma.cmd')):
        prisma_path = os.path.join(path, 'prisma.cmd')

print(f"找到npm: {npm_path}")
print(f"找到prisma: {prisma_path}")

# 定义命令选项
commands = []

# 尝试使用npx运行prisma generate
commands.append(['npx', 'prisma', 'generate'])

# 尝试使用npm运行prisma generate
if npm_path:
    commands.append([npm_path, 'exec', '--', 'prisma', 'generate'])

# 尝试直接运行prisma命令
if prisma_path:
    commands.append([prisma_path, 'generate'])

# 尝试使用python -m prisma generate
commands.append(['python', '-m', 'prisma', 'generate'])

# 尝试运行命令
for cmd in commands:
    try:
        print(f"\n尝试运行命令: {' '.join(cmd)}")
        
        # 执行命令
        result = subprocess.run(
            cmd,
            env=env,
            capture_output=True,
            text=True,
            cwd=os.path.dirname(os.path.abspath(__file__))
        )
        
        # 输出结果
        if result.stdout:
            print(f"输出:\n{result.stdout}")
        if result.stderr:
            print(f"错误输出:\n{result.stderr}")
        
        if result.returncode == 0:
            print(f"命令执行成功: {' '.join(cmd)}")
            print("Prisma客户端生成成功！")
            # 测试导入Prisma客户端
            try:
                import sys
                sys.path.append('.')
                from prisma import Prisma
                print("成功导入Prisma客户端！")
            except Exception as e:
                print(f"导入Prisma客户端时出错: {e}")
            sys.exit(0)
        else:
            print(f"命令执行失败，退出码: {result.returncode}")
            
    except Exception as e:
        print(f"运行命令 {' '.join(cmd)} 时出错: {e}")
        traceback.print_exc()

# 所有命令都失败了，提供替代解决方案
print("\n所有命令都失败了。请尝试以下手动解决方案：")
print("1. 打开命令提示符")
print("2. 切换到项目目录：cd C:\\Users\\33166\\Desktop\\船舶交通流可视化系统\\backend")
print("3. 激活虚拟环境：venv\\Scripts\\activate")
print("4. 设置编码环境变量：")
print("   set PYTHONUTF8=1")
print("   set PYTHONIOENCODING=utf-8")
print("5. 运行prisma generate命令")
print("\n如果上述方法仍然失败，建议将项目移动到一个不包含中文字符的路径下。")

sys.exit(1)