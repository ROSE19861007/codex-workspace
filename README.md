# codex-workspace

通用工作区，专门交给 OpenAI **Codex** 处理各类代码与自动化任务。

## 这是什么

- 一个面向 AI 编程智能体（Codex）的仓库。
- 你把任务描述、需求、素材放进来；Codex 先读根目录的 `codex.md` 了解约定，再动手。
- 公开库：Codex 可直接连；私有库需先在 GitHub 给 Codex App 授权该仓库。

## 目录结构

```
codex-workspace/
├─ codex.md        # 给 Codex 的说明书（最重要，它一进来先读这个）
├─ AGENTS.md       # 兼容其它智能体的同名约定文件
├─ README.md       # 本文件，给人看的概览
├─ .gitignore      # 忽略依赖 / 密钥 / 系统文件
├─ tasks/          # 每个任务一个子目录：tasks/<任务名>/
│  ├─ README.md    # 怎么新建一个任务
│  └─ _template/   # 任务模板（复制改名即可用）
├─ src/            # 可复用的通用脚本 / 工具
└─ docs/           # 参考资料、说明文档
```

## 怎么用

1. 在 `tasks/` 下新建一个目录（复制 `_template`），写清楚你要 Codex 做什么。
2. 让 Codex 连这个仓库（公开库直接连；私有库需给 Codex App 授权）。
3. Codex 读 `codex.md` 后按约定执行，把结果提交进来。

## 约定速览

- 默认分支：`main`
- 一个逻辑改动一次提交，提交信息说清"改了什么、为什么"
- 密钥 / token / 密码**绝不**写进代码或提交
- 不确定时，在提交说明里写明"待确认点"，不要悄悄猜

详细约定见 [`codex.md`](./codex.md)。
