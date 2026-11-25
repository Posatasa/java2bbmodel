# java2bbmodel

把 Minecraft Java 版实体模型转成 Blockbench 的 `.bbmodel`。

## 用法

```bash
python java2bbmodel.py                      # 自动扫描脚本所在目录，结果写到 output/
python java2bbmodel.py modelFoo.java        # 输出 modelFoo.java 旁边的 modelFoo.bbmodel
python java2bbmodel.py Model_Java/ -o out/  # 整个目录
python java2bbmodel.py modelFoo.java -o foo.bbmodel
```

也可以直接运行 `run_gui.bat`（等于 `python java2bbmodel_gui.py`）。

| 参数 | 说明 |
| --- | --- |
| `-o, --output` | 输出文件或目录；不传就写到输入文件旁边 |
| `--y-origin` | Y 翻转的基准高度，默认 `24`（脚底落在 y=0）；给 `0` 则模型整体挂在 y<0 |
| `-q, --quiet` | 不打印每个文件的转换结果 |

## 测试

```bash
python -m unittest discover -s tests
```
