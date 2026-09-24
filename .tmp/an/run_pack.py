import subprocess, sys, os
os.chdir(r'C:/code/GBA-Rom-Translator')
MODULES = "属性名,属性名-华丽大赛,性格名,特性名,宝可梦名,招式名,招式名-华丽大赛,训练家名,训练家个人名,地点名,秘密基地装饰名,道具名,树果名,道具说明,招式说明,招式说明-华丽大赛,特性说明,图鉴分类名,图鉴说明,UI界面,剧情,补漏剧情"
cmd = [
    r'C:/Python314/python.exe','-m','meowth','full',
    r'C:/code/GBA-Rom-Translator/roms/origin/POKEMON_RUBY_AXVJ00.gba',
    '-o', r'C:/code/GBA-Rom-Translator/roms/outputs',
    '--work-dir','work',
    '--source','ja','--target','zh-Hans',
    '--modules',MODULES,
    '--provider','qwen','--model','qwen3.5-omni-flash',
    '--seed-only',
]
env=dict(os.environ); env['PYTHONPATH']=r'C:/code/GBA-Rom-Translator/src'
print("RUN:", " ".join(cmd[:-1]), cmd[-1], flush=True)
p=subprocess.run(cmd, env=env, capture_output=True, text=True, encoding='utf-8', errors='replace')
print("### STDOUT ###"); print(p.stdout[-8000:])
print("### STDERR ###"); print(p.stderr[-4000:])
print("exit =", p.returncode)
