import os
import sys
import subprocess
import io
import locale

# 重新设置标准输出编码以支持UTF-8
sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding='utf-8')
sys.stderr = io.TextIOWrapper(sys.stderr.buffer, encoding='utf-8')

# 确保环境变量正确设置
os.environ['PYTHONUTF8'] = '1'

# 检查虚拟环境路径
current_dir = os.path.dirname(os.path.abspath(__file__))
venv_dir = os.path.join(current_dir, 'venv')

# 保存原始的LC_CTYPE
original_lc_ctype = os.environ.get('LC_CTYPE')

# 设置LC_CTYPE为UTF-8
try:
    os.environ['LC_CTYPE'] = 'C.UTF-8'
    
    # 检测操作系统并使用适当的命令运行prisma
    if os.name == 'nt':  # Windows
        # 尝试使用npm运行prisma
        result = subprocess.run(
            ['npm', 'run', 'prisma', 'generate'],
            cwd=current_dir,
            capture_output=True,
            text=True,
            encoding='utf-8'
        )
    else:
        # 非Windows系统
        result = subprocess.run(
            ['npx', 'prisma', 'generate'],
            cwd=current_dir,
            capture_output=True,
            text=True,
            encoding='utf-8'
        )
    
    # 输出结果
    if result.stdout:
        print(f"\nPrisma generate output:\n{result.stdout}")
    if result.stderr:
        print(f"\nPrisma generate errors:\n{result.stderr}")
        
    print(f"\nPrisma generate completed with exit code: {result.returncode}")
    
    # 如果npm方式失败，尝试直接调用虚拟环境中的prisma
    if result.returncode != 0:
        print("\n尝试使用虚拟环境中的prisma命令...")
        
        # 构造虚拟环境中的prisma路径
        if os.name == 'nt':
            prisma_cmd = os.path.join(venv_dir, 'Scripts', 'prisma.cmd')
        else:
            prisma_cmd = os.path.join(venv_dir, 'bin', 'prisma')
        
        # 检查prisma命令是否存在
        if os.path.exists(prisma_cmd):
            print(f"找到prisma命令: {prisma_cmd}")
            result = subprocess.run(
                [prisma_cmd, 'generate'],
                cwd=current_dir,
                capture_output=True,
                text=True,
                encoding='utf-8'
            )
            
            # 输出结果
            if result.stdout:
                print(f"\nVirtual env Prisma generate output:\n{result.stdout}")
            if result.stderr:
                print(f"\nVirtual env Prisma generate errors:\n{result.stderr}")
            
            print(f"\nVirtual env Prisma generate completed with exit code: {result.returncode}")
        else:
            print(f"未找到虚拟环境中的prisma命令: {prisma_cmd}")
    
finally:
    # 恢复原始的LC_CTYPE
    if original_lc_ctype is not None:
        os.environ['LC_CTYPE'] = original_lc_ctype
    else:
        os.environ.pop('LC_CTYPE', None)

# 以相同的退出代码退出
sys.exit(result.returncode if 'result' in locals() else 1)