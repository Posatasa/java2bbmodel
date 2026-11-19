# java2bbmodel

把 Minecraft Java 版实体模型类（`ModelBase` / `ModelRenderer` 那一套 `.java`）转成 Blockbench 的 `.bbmodel`。只需要 Python 3，没有第三方依赖。

## 用法

不带参数时自动扫描：把本脚本放在模型目录里直接运行，会递归找出脚本所在目录下所有 `.java`，按原目录结构输出到同级的 `output/`。

```bash
python java2bbmodel.py
```

也可以指定路径：

```bash
python java2bbmodel.py modelFoo.java          # 输出 modelFoo.java 旁边的 modelFoo.bbmodel
python java2bbmodel.py Model_Java/ -o out/    # 整个目录
python java2bbmodel.py modelFoo.java -o foo.bbmodel
```

| 参数 | 说明 |
| --- | --- |
| `-o, --output` | 输出文件或目录；不传就写到输入文件旁边 |
| `--y-origin` | Y 翻转的基准高度，默认 `24`（脚底落在 y=0）；给 `0` 则模型整体挂在 y<0 |
| `-q, --quiet` | 不打印每个文件的转换结果 |

PyCharm：直接 Run 就行（无参数＝自动扫描脚本同级目录）；要指定路径就填在 Run Configuration 的 `Parameters` 里。

## 说明

- 坐标按 Blockbench `modded_entity` 的约定换算：`x→-x`、`y→24-y`、`z` 不变，旋转 `rx`/`ry` 取反、`rz` 不变；`addChild` 的层级写成 `outliner` 嵌套树。转出来再导回 `.java`，数字和原文件一致。
- 只读构造函数，`setRotationAngles` / `setLivingAnimations` 里的动画不会转换。
- 贴图不打包，在 Blockbench 里自己挂。

## 测试

```bash
python -m unittest discover -s tests
```
