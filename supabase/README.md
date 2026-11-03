# 云端同步初始化

1. 在 Supabase 项目打开 **SQL Editor**，新建查询。
2. 粘贴并运行 `001_space_editor_sync.sql` 的全部内容。
3. 在 **Settings → API Keys** 取得 Project URL 与 publishable/anon key；它们用于前端连接，不是数据库密码。

数据库表本身不授予浏览器读取权限。应用只通过三个 RPC 函数存取数据：创建项目、按私密链接读取、按编辑链接写入。
