# java2bbmodel

把 Minecraft Java 版实体模型类（`ModelBase` / `ModelRenderer` 那一套 `.java`）转成 Blockbench 的 `.bbmodel`。

## 用法

```bash
python java2bbmodel.py                      # 自动扫描脚本所在目录，结果写到 output/
python java2bbmodel.py modelFoo.java        # 输出 modelFoo.java 旁边的 modelFoo.bbmodel
python java2bbmodel.py Model_Java/ -o out/  # 整个目录
python java2bbmodel.py modelFoo.java -o foo.bbmodel
```

| 参数 | 说明 |
| --- | --- |
| `-o, --output` | 输出文件或目录；不传就写到输入文件旁边 |
| `--y-origin` | Y 翻转的基准高度，默认 `24`（脚底落在 y=0）；给 `0` 则模型整体挂在 y<0 |
| `-q, --quiet` | 不打印每个文件的转换结果 |

贴图不打包，在 Blockbench 里自己挂。

## 图形界面

不想敲命令就双击 `run_gui.bat`（等价于 `python java2bbmodel_gui.py`）：选文件或文件夹、确认输出目录、点“开始转换”，转完可以直接打开输出目录。

用的 Tkinter，Python 自带，**不需要编译**，也不用装 PyInstaller 之类的东西。

## 测试

```bash
python -m unittest discover -s tests
```
