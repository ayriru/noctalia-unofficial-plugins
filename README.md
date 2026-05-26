# noctalia-unofficial-plugins
Noctalia's unofficial plugins

## packagekit

这是一个示例插件，位于 `packagekit/`。包信息在 `packagekit/manifest.json` 中定义。

打包插件（需在 Linux 环境中安装 `zip`）：

```bash
npm run pack
```

生成的文件为 `packagekit-package.zip`，包含 `packagekit/` 目录下的所有文件。
