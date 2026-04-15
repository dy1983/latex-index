# zhmakeindex_py

**中文 LaTeX 索引生成工具** — Python 实现

[简体中文](#简体中文) | [English](#english)

---

## 简体中文

### 概述

`zhmakeindex_py` 是一个轻量级 Python 程序，用于处理 LaTeX `.idx` 索引文件，生成排序正确的 `.ind` 索引文件。中文条目采用逐字比较的排序方式：每个字先按拼音比较，再按总笔画数比较；程序同时支持多音字（polyphone）覆盖，并内置基于 Unihan `kTotalStrokes` 的总笔画数据。对于同拼音同笔画的汉字，程序会优先读取笔顺模板，并在模板缺字时自动补全可比较的笔顺签名。

**主要功能：**
- ✅ 解析 LaTeX `.idx` 索引文件（支持嵌套花括号、转义字符、TeX 命令等）
- ✅ 中文逐字排序：每个字先按拼音，再按总笔画数比较
- ✅ 笔顺模板自动补全：遇到同拼音同笔画候选时，缺失字会自动写回 `data/stroke_order.yaml`
- ✅ 同拼音同笔画冲突提示（若自动补全后仍无法区分，则使用稳定伪随机回退并给出警告）
- ✅ 智能页码合并（相邻页码范围优化）
- ✅ 生成 LaTeX `.ind` 索引文件
- ✅ **自动索引检查**（验证页码顺序、条目排序、cross-reference 位置等）

### 安装

#### 环境要求
- Python 3.7+
- 依赖包：`pypinyin`, `PyYAML`, `unidecode`

#### 设置虚拟环境

```bash
cd /path/to/zhmakeindex_py
python -m venv .venv
source .venv/bin/activate  # 或在 Windows 上: .venv\Scripts\activate
pip install -r requirements.txt
```

也可以在已有的 conda 环境中直接安装依赖：

```bash
conda activate your-env
pip install -r requirements.txt
```

### 快速开始

#### 最简便用法（自动输出，自动检查）

```bash
python cli.py main.idx
```

结果：自动生成 `main.ind`，加载内置 `data/poly.yaml`，必要时创建或更新 `data/stroke_order.yaml`，并输出检查报告

#### 使用自定义多音字字典

```bash
python cli.py main.idx --polyphone custom_poly.yaml
```

#### 使用自定义笔顺字典（可选）

```bash
python cli.py main.idx --stroke-order data/stroke_order.yaml
```

结果：优先读取指定模板；若遇到同拼音同总笔画的汉字而模板缺字，程序会尝试自动补全并写回该文件

#### 指定输出文件

```bash
python cli.py main.idx -o output.ind
```

#### 跳过自动检查

```bash
python cli.py main.idx --no-check
```

#### 单独运行检查

```bash
python check_index.py output.ind
```

### 选项说明

| 选项 | 描述 |
|------|------|
| `<idx_file>` | 输入的 `.idx` 文件（必须） |
| `-o, --output` | 输出文件名（可选；默认：同目录下，同名但扩展名为 `.ind`） |
| `--polyphone` | YAML 格式的多音字覆盖字典（可选；默认使用内置的 `data/poly.yaml`） |
| `--stroke-order` | YAML/JSON 格式的笔顺模板（可选；默认使用 `data/stroke_order.yaml`，并在需要时自动追加新字） |
| `--no-check` | 生成后不运行自动检查（可选） |

### 多音字字典 (data/poly.yaml)

多音字字典是一个 YAML 文件，用于覆盖特定词语的拼音读音。内置字典 `data/poly.yaml` 包含物理学、数学等领域的常用术语。用户可以编辑或创建自己的字典。

**字典格式示例：**

```yaml
# 词语映射（每个字的拼音用空格分隔，包含声调数字）
弹性: tan2 xing4
弹簧: tan2 huang2
重力: zhong4 li4
重正: chong2 zheng4
系统: xi4 tong3

# 物理术语
非弹性散射: fei1 tan2 san3 she4
强相互作用: qiang2 xiang4 hu4 zuo4 yong4
磁性系统的热力学: ci2 xing4 xi4 tong3 de re4 li4 xue2
```

**多音字覆盖规则：**
1. 词语优先：若输入词语在字典中有条目，直接使用字典的拼音
2. 前缀匹配：支持"最长匹配"。例如，若字典有 `重正: chong2 zheng4`，那么 `重正化` 会被拼音化为 `chong2 zheng4 hua4`（后续字使用 `pypinyin` 默认值）
3. 字符回退：若词语不在字典中，则逐字符使用字典或  `pypinyin` 默认拼音

### 中文排序规则

1. 只对中文字符启用新规则；纯英文和其他非中文字符仍按原有的小写字典序排序。
2. 中文条目按字符位置逐字比较，而不是先把整词转换成一整串拼音再比较。
3. 每个汉字先比较拼音；若拼音相同，再比较总笔画数。总笔画数来自内置的 Unihan `kTotalStrokes` 数据，而不是部件分解结果。
4. 只有当前一字无法区分时，才继续比较下一字。因此同一个汉字开头的词条会被排在一起。
5. 程序会优先读取 `data/stroke_order.yaml`（或 `--stroke-order` 指定的模板）；如果某组同拼音同总笔画的候选字缺少笔顺信息，会在线获取单字笔顺数据、提取可比较的笔顺签名，并追加到模板文件。
6. 若自动补全成功，则在“拼音 + 总笔画数”相同后继续按笔顺签名比较；这里不要求模板事先覆盖全部中文字符。
7. 若某一位置出现“拼音相同且总笔画数也相同，但字形不同”的情况，而当前模板和自动补全仍无法取得可区分的笔顺签名，则程序会发出警告，并使用稳定伪随机回退保证输出可复现。

### 笔顺模板（可自动补全）

笔顺模板用于给每个汉字提供可比较的笔顺签名。当前版本支持 YAML 或 JSON 映射，键为单个汉字，值推荐写成带 `sequence` 字段的对象；`sequence` 是“按笔顺排列的逐笔签名”列表，每个列表项对应一笔。程序首次运行时会创建一个只包含一两个示例字的模板文件，后续遇到同拼音同总笔画的候选字时再按需补全，而不是一次性写入整表。

**示例：**

```yaml
一:
	sequence:
		- H
	source: seed
二:
	sequence:
		- H
		- H
	source: seed
```

支持的基本笔顺符号包括：`横/一/H`、`竖/丨/S`、`撇/丿/P`、`捺/㇏/N`、`点/丶/D`，以及可选扩展 `提/T`、`折/Z`、`钩/G`。自动补全时，程序会从 Hanzi Writer 的单字数据中提取更细的方向签名，并以同样的 `sequence` 列表形式写回模板。若网络不可用或外部数据不足，程序会保留当前模板内容并给出警告。

### 自动检查功能

生成 `.ind` 文件后，程序自动运行验证，检查以下内容：

| 检查项 | 详细说明 | 等级 |
|--------|---------|------|
| **页码顺序** | 验证每条索引项的页码是否从小到大排列（如 `1, 5--7, 10` 有效，但 `10, 5--7, 1` 无效） | 错误 |
| **条目排序** | 使用“逐字拼音 + 总笔画数 + 可选笔顺键”规则验证相邻索引项顺序是否正确 | 错误 |
| **页码合并优化** | 提示可能未能最优合并的页码（如果存在 1-2 页的间隔，例如 `11, 12--15` 可能应合并为 `11--15`） | 警告 |
| **排序歧义提醒** | 若某一字符位置存在“同拼音且同总笔画”的不同汉字，而模板和自动补全仍无法区分，提示程序使用稳定伪随机回退 | 警告 |

**检查结果说明：**
- **ERRORS**：严重问题，表示索引的正确性有问题（页码顺序混乱、条目排序错误）
- **WARNINGS**：提示信息，表示可能的优化机会或排序歧义（但不影响生成）

检查报告会在生成完成后自动打印。若本次运行自动补充了新的笔顺签名，CLI 也会在报告前提示哪些字已被写回模板文件。

### 程序架构

```
zhmakeindex_py/
├── cli.py                    # 主程序入口
├── idx_parser.py             # .idx 文件解析器
├── readings.py               # 拼音生成（支持多音字）
├── data/
│   ├── poly.yaml                  # 内置多音字字典
│   ├── stroke_order.yaml          # 按需增长的笔顺模板
│   └── unihan_total_strokes.json  # 内置 Unihan 总笔画表
├── sorter.py                 # 拼音排序
├── writer.py                 # .ind 文件生成与页码合并
├── check_index.py            # 索引检查与验证
├── requirements.txt          # 依赖包列表
└── README.md                 # 本文件
```

### 参考与致谢

本程序参考了 **刘海洋** 的 Go 实现版本：[zhmakeindex](https://github.com/leo-liu/zhmakeindex)

- 借鉴了其索引解析、拼音排序、页码合并等核心算法
- 代码主要采用 **AI 辅助编写方式** 完成

**特别感谢：**
- 感谢刘海洋的原创 Go 实现，提供了算法和设计思路
- 代码借助 Claude AI 编写和完善

### 示例

```bash
# 处理物理学教科书索引
python cli.py physics_index.idx --polyphone physics_poly.yaml

# 输出示例：
# Wrote physics_index.ind with 803 entries
# 
# ============================================================
# INDEX CHECK REPORT
# ============================================================
# Total entries: 529
# 
# ERRORS (13):
#   ✗ Entry 9 '...' should not come before Entry 8 '...'
#   ...
# 
# WARNINGS (5):
#   ⚠ Entry 107 '...': pages may not be optimally merged
#   ...
```

### 常见问题

**Q: 如何自定义多音字读音？**  
A: 编辑 `data/poly.yaml` 文件（或通过 `--polyphone` 指定自定义文件），按照 YAML 格式添加条目即可。

**Q: 支持哪些 LaTeX 索引格式？**  
A: 支持标准的 `\indexentry{term|encap}{page}` 格式和嵌套、转义等复杂情况。

**Q: 检查报告中有错误怎么办？**  
A: 先检查多音字覆盖是否完整，再检查输入 `.idx` 文件的索引项是否有误；如果只有排序歧义警告，则表示当前存在“同拼音同总笔画”的不同汉字，而当前没有完整笔顺数据，或提供的笔顺键仍不足以区分它们。

**Q: 程序会一次性生成整套笔顺模板吗？**  
A: 不会。默认模板只带少量示例字。程序只会在本次输入里真的遇到“同拼音同总笔画”的候选字时，尝试补充这些字的笔顺签名并写回模板。

**Q: 自动补全笔顺模板依赖什么？**  
A: 当前版本会按字请求 Hanzi Writer 公开数据，并从中提取逐笔方向签名。如果网络不可用，程序不会报错退出，而是继续使用稳定伪随机回退并给出警告。

---

## English

### Overview

`zhmakeindex_py` is a lightweight Python tool for processing LaTeX `.idx` index files and generating correctly sorted `.ind` index files. Chinese entries are compared character by character: each character is ordered by pinyin first and total stroke count second. The program also supports polyphone overrides, ships with bundled Unihan `kTotalStrokes` data, and maintains a small stroke-order template that grows only when ambiguous characters actually appear.

**Key Features:**
- ✅ Parse LaTeX `.idx` index files (nested braces, escape chars, TeX commands, etc.)
- ✅ Character-by-character Chinese sorting: pinyin first, total stroke count second
- ✅ On-demand stroke-order template updates for same-pinyin same-stroke candidates
- ✅ Ambiguity warnings for characters with the same pinyin and stroke count when stroke-order data is still insufficient
- ✅ Smart page merging (optimize adjacent page ranges)
- ✅ Generate LaTeX `.ind` index files
- ✅ **Automatic index validation** (page order, entry ordering, cross-reference placement, etc.)

### Installation

#### Requirements
- Python 3.7+
- Dependencies: `pypinyin`, `PyYAML`, `unidecode`

#### Setup

```bash
cd /path/to/zhmakeindex_py
python -m venv .venv
source .venv/bin/activate  # or on Windows: .venv\Scripts\activate
pip install -r requirements.txt
```

You can also install dependencies inside an existing conda environment:

```bash
conda activate your-env
pip install -r requirements.txt
```

### Quick Start

#### Default usage (auto output + auto check)

```bash
python cli.py main.idx
```

Output: generates `main.ind`, loads built-in `data/poly.yaml`, and displays check report

#### Use custom polyphone dictionary

```bash
python cli.py main.idx --polyphone custom_poly.yaml
```

#### Use a custom stroke-order dictionary (optional)

```bash
python cli.py main.idx --stroke-order data/stroke_order.yaml
```

Output: reads the specified template first and appends newly resolved ambiguous characters back into it when needed

#### Specify output file

```bash
python cli.py main.idx -o output.ind
```

#### Skip automatic check

```bash
python cli.py main.idx --no-check
```

#### Run check independently

```bash
python check_index.py output.ind
```

### Usage Options

| Option | Description |
|--------|-------------|
| `<idx_file>` | Input `.idx` file (required) |
| `-o, --output` | Output filename (optional; default: same dir + same name with `.ind` extension) |
| `--polyphone` | YAML polyphone override dict (optional; default uses built-in `data/poly.yaml`) |
| `--stroke-order` | YAML/JSON stroke-order template (optional; defaults to `data/stroke_order.yaml` and is updated on demand) |
| `--no-check` | Skip automatic validation after generation (optional) |

### Polyphone Dictionary (data/poly.yaml)

The polyphone dictionary is a YAML file that overrides pinyin readings for specific terms. The built-in dictionary `data/poly.yaml` contains common terms from physics, mathematics, and other fields. Users can edit or create custom dictionaries.

**Dictionary format example:**

```yaml
# Word mappings (pinyin for each character separated by space, with tone numbers)
弹性: tan2 xing4
弹簧: tan2 huang2
重力: zhong4 li4
重正: chong2 zheng4
系统: xi4 tong3

# Physics/Math terms
非弹性散射: fei1 tan2 san3 she4
强相互作用: qiang2 xiang4 hu4 zuo4 yong4
磁性系统的热力学: ci2 xing4 xi4 tong3 de re4 li4 xue2
```

**Polyphone Override Rules:**
1. **Word match first**: If a term exists in the dictionary, use its pinyin directly
2. **Prefix matching**: Supports longest-match. E.g., if dictionary has `重正: chong2 zheng4`, then `重正化` becomes `chong2 zheng4 hua4` (appending default PyPinyin for subsequent characters)
3. **Character fallback**: If term not in dictionary, use dictionary or PyPinyin default for each character

### Chinese Sorting Rules

1. The new rule applies only to Chinese characters; English and other non-Chinese text keeps the previous lowercase lexical ordering.
2. Chinese entries are compared character by character instead of comparing one full pinyin string for the entire term.
3. For each Chinese character, pinyin is compared first and total stroke count second. Total strokes come from bundled Unihan `kTotalStrokes` data instead of component decomposition.
4. The next character is considered only when the current character cannot decide the order, which keeps entries sharing the same leading character together.
5. The program reads `data/stroke_order.yaml` (or the file supplied via `--stroke-order`) first; when an ambiguous same-pinyin same-total-stroke group is missing entries, it fetches per-character stroke data online, derives comparable stroke signatures, and appends them to the template.
6. Once a character has a stroke signature, that signature becomes the third comparison layer after pinyin and total stroke count; full pre-coverage is not required.
7. If some characters still cannot obtain a usable signature, or the extracted signatures are still identical, the program emits a warning and falls back to a stable pseudo-random order.

### Stroke-Order Template (Auto-Growing)

The stroke-order template is a YAML or JSON mapping from a single Chinese character to a comparable stroke-signature sequence. The recommended format is an object with a `sequence` list, where each item represents one stroke. The file starts small and grows only when the current input actually needs more stroke-order data.

**Example:**

```yaml
一:
	sequence:
		- H
	source: seed
二:
	sequence:
		- H
		- H
	source: seed
```

Supported basic stroke symbols include `横/一/H`, `竖/丨/S`, `撇/丿/P`, `捺/㇏/N`, and `点/丶/D`, with optional extensions for `提/T`, `折/Z`, and `钩/G`. Auto-populated entries use the same `sequence` list, but each stroke item may contain a more detailed direction signature derived from Hanzi Writer data. If the network is unavailable, the program keeps the template unchanged and falls back with a warning.

### Automatic Validation

After `.ind` file generation, the program automatically runs validation checks:

| Check | Detailed Description | Level |
|-------|----------------------|-------|
| **Page order** | Verify pages in each entry are sorted small-to-large (e.g., `1, 5--7, 10` is valid; `10, 5--7, 1` is not) | Error |
| **Entry order** | Validate entry ordering with the character-by-character pinyin + total-stroke + optional stroke-order rule | Error |
| **Page merging optimization** | Suggest potential improvements for page ranges (e.g., if gaps of 1-2 pages exist, they may be worth merging) | Warning |
| **Sorting ambiguity** | Warn when different characters share the same pinyin and total stroke count and the template plus on-demand updates still cannot separate them | Warning |

**Report Levels:**
- **ERRORS**: Critical issues affecting index correctness (misaligned page order, wrong entry sorting)
- **WARNINGS**: Optimization suggestions or sorting ambiguities (do not block generation)

The validation report is printed automatically after generation. If new stroke signatures were added during the run, the CLI prints which characters were written back into the template before the report.

### Program Architecture

```
zhmakeindex_py/
├── cli.py                    # Main entry point
├── idx_parser.py             # .idx file parser
├── readings.py               # Pinyin generation (polyphone support)
├── data/
│   ├── poly.yaml                 # Built-in polyphone dictionary
│   ├── stroke_order.yaml         # On-demand stroke-order template
│   └── unihan_total_strokes.json # Bundled Unihan total-stroke table
├── sorter.py                 # Pinyin-based sorting
├── writer.py                 # .ind file generation + page merging
├── check_index.py            # Index validation
├── requirements.txt          # Dependency list
└── README.md                 # This file
```

### References & Acknowledgments

This program references the Go implementation by **Liu Haiyang**: [zhmakeindex](https://github.com/leo-liu/zhmakeindex)

- Adapted core algorithms for index parsing, pinyin sorting, and page merging
- Code written with **AI assistance** (Claude)

**Special Thanks:**
- Liu Haiyang's original Go implementation for algorithm design and inspiration
- Claude AI for code writing and refinement

### Example

```bash
# Process a physics textbook index
python cli.py physics_index.idx --polyphone physics_poly.yaml

# Sample output:
# Wrote physics_index.ind with 803 entries
# 
# ============================================================
# INDEX CHECK REPORT
# ============================================================
# Total entries: 529
# 
# ERRORS (13):
#   ✗ Entry 9 '...' should not come before Entry 8 '...'
#   ...
# 
# WARNINGS (5):
#   ⚠ Entry 107 '...': pages may not be optimally merged
#   ...
```

### FAQ

**Q: How do I customize polyphone readings?**  
A: Edit `data/poly.yaml` (or use `--polyphone` to specify a custom file) and add entries in YAML format.

**Q: What LaTeX index formats are supported?**  
A: Standard `\indexentry{term|encap}{page}` format with nested braces, escapes, etc.

**Q: What if the check report shows errors?**  
A: First check whether the polyphone overrides are complete, then verify the input `.idx` entries themselves. If you only see ambiguity warnings, the output is still usable, but some characters still share the same pinyin and total stroke count while the current stroke-order data is missing or still too coarse.

**Q: Does the program generate a full stroke-order template up front?**  
A: No. The default template starts with only a couple of seed entries. More characters are added only when the current input really hits a same-pinyin same-total-stroke ambiguity.

**Q: What powers the automatic stroke-order updates?**  
A: The current implementation fetches per-character Hanzi Writer data and extracts per-stroke direction signatures from it. If that data cannot be fetched, the program still completes the run and falls back with a warning.

---

## License

MIT License

## Author

程序由 Claude AI 协助编写，参考刘海洋的 zhmakeindex 项目。

---

**更新日期**: 2026 年 4 月 15 日  
**版本**: 1.2
