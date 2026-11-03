# 使用说明

将 `.md` 文档放到 `/home/apex/md-service/public/docs/`，图片与文档保持原有相对目录结构。刷新首页即可发现新增文档，无需重启。

[返回功能示例](sample.md)

## 服务管理

```sh
systemctl --user status md-docs
systemctl --user restart md-docs
journalctl --user -u md-docs -n 50
```
