#!/usr/bin/env python3
"""Create a local Obsidian entry without overwriting notes or importing Mac state."""
import argparse
import json
from pathlib import Path
import sys

sys.path.insert(0, str(Path(__file__).resolve().parent))
from workflour_paths import vault_path

ROOT = Path(__file__).resolve().parents[1]


def initialize(vault):
    vault = Path(vault).expanduser()
    if not vault.is_absolute() or vault.is_symlink():
        raise ValueError('Vault must be an absolute non-symlink directory')
    vault.mkdir(parents=True, exist_ok=True)
    notes = {
        '首页.md': '# Workflour 本机项目入口\n\n'
            '这是当前电脑的知识库。账号和旧电脑会话没有迁入；安装通过不等于业务验收通过。\n\n'
            '- [[项目经理]]\n- [[01-需求/目标与待定事项]]\n- [[记录约定]]\n\n'
            f'工具仓库：`{ROOT}`。七角色部署说明见 [{ROOT}/docs/ubuntu-deployment/00-从这里开始.md](<{ROOT}/docs/ubuntu-deployment/00-从这里开始.md>)。\n'
            '项目共享账本保存在各项目目录。07-自动记录由观察器生成，不手工修改。\n',
        '项目经理.md': '# Plan · 项目负责人\n\n'
            '接收大管家原始需求，调研、组织评审、安排单主编码、技术审核和体验检查。\n'
            '独立维护各项目账本；记录实际证据和失败；技术完成后停在待用户验收。\n'
            '有实质进展才更新项目笔记及首页；历史Mac记录只能作为参考。\n',
        '01-需求/目标与待定事项.md': '# 本机目标与待定事项\n\n'
            '目标：在本机部署大管家、Plan Team、Code Team七角色。\n'
            '待验证：本机账号、模型目录与档位、真实调用、读图、浏览器及完整业务流。\n'
            '本机业务需求由用户提出后单独记录，不把历史样例当作新需求。\n',
        '记录约定.md': '# 记录约定\n\n'
            '区分用户要求、建议、假设、计划、已执行、已验证和受阻。保留真实失败与修复过程。\n'
            '搭建记录放04-搭建，测试证据索引放05-验证；每个项目有独立笔记和原件链接。\n'
            '手写摘要不替代项目账本、原生派单回执和测试原件。日期采用Asia/Shanghai。\n'
            '有实质进展时更新首页，写完成内容、停点、问题和下一步。不记录密钥或Cookie。\n'
            '07-自动记录只由观察器维护；未注册的项目不会被扫描导出。\n',
    }
    created = []
    for name, content in notes.items():
        path = vault / name
        if path.is_symlink() or path.parent.is_symlink():
            raise ValueError('Refuse note symlink: ' + name)
        path.parent.mkdir(parents=True, exist_ok=True)
        try:
            with path.open('x', encoding='utf-8') as stream:
                stream.write(content)
            created.append(name)
        except FileExistsError:
            if not path.is_file():
                raise ValueError('Expected note file: ' + name)
    for name in ('04-搭建', '05-验证', '07-自动记录'):
        path = vault / name
        if path.is_symlink():
            raise ValueError('Refuse managed folder symlink: ' + name)
        path.mkdir(exist_ok=True)
    return {'vault': str(vault), 'created': created, 'existing_notes_preserved': True}


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--vault', type=Path, default=vault_path())
    args = parser.parse_args()
    try:
        print(json.dumps(initialize(args.vault), ensure_ascii=False, indent=2))
    except (ValueError, OSError) as error:
        raise SystemExit(str(error)) from None
