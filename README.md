# zhmakeindex_py

**中文 LaTeX 索引生成工具** — Python 实现

[简体中文](#简体中文) | [English](#english)

---

## 简体中文

### 概述

`zhmakeindex_py` 是一个轻量级 Python 程序，用于处理 LaTeX `.idx` 索引文件，生成排序正确的 `.ind` 索引文件。中文条目采用逐字比较的排序方式：每个字先按拼音比较，再按笔画数比较；程序同时支持多音字（polyphone）覆盖，允许用户为特定汉字或词语指定正确的拼音读音。

**主要功能：**
- ✅ 解析 LaTeX `.idx` 索引文件（支持嵌套花括号、转义字符、TeX 命令等）
- ✅ 中文逐字排序：每个字先按拼音，再按笔画数比较
- ✅ 同拼音同笔画冲突提示（当前使用稳定伪随机回退，并给出警告）
- ✅ 智能页码合并（相邻页码范围优化）
- ✅ 生成 LaTeX `.ind` 索引文件
- ✅ **自动索引检查**（验证页码顺序、条目排序、cross-reference 位置等）

### 安装

#### 环境要求
- Python 3.7+
- 依赖包：`pypinyin`, `PyYAML`, `hanzipy`, `unidecode`

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

结果：自动生成 `main.ind`，加载内置 `poly.yaml`，并输出检查报告

#### 使用自定义多音字字典

```bash
python cli.py main.idx --polyphone custom_poly.yaml
```

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
| `--polyphone` | YAML 格式的多音字覆盖字典（可选；默认使用内置的 `poly.yaml`） |
| `--no-check` | 生成后不运行自动检查（可选） |

### 多音字字典 (poly.yaml)

多音字字典是一个 YAML 文件，用于覆盖特定词语的拼音读音。内置字典 `poly.yaml` 包含物理学、数学等领域的常用术语。用户可以编辑或创建自己的字典。

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
3. 每个汉字先比较拼音；若拼音相同，再比较笔画数。
4. 只有当前一字无法区分时，才继续比较下一字。因此同一个汉字开头的词条会被排在一起。
5. 若某一位置出现“拼音相同且笔画数也相同，但字形不同”的情况，当前版本会发出警告，并使用稳定伪随机回退保证输出可复现；后续可扩展为笔画顺序比较。

### 自动检查功能

生成 `.ind` 文件后，程序自动运行验证，检查以下内容：

| 检查项 | 详细说明 | 等级 |
|--------|---------|------|
| **页码顺序** | 验证每条索引项的页码是否从小到大排列（如 `1, 5--7, 10` 有效，但 `10, 5--7, 1` 无效） | 错误 |
| **条目排序** | 使用“逐字拼音 + 笔画数”规则验证相邻索引项顺序是否正确 | 错误 |
| **页码合并优化** | 提示可能未能最优合并的页码（如果存在 1-2 页的间隔，例如 `11, 12--15` 可能应合并为 `11--15`） | 警告 |
| **排序歧义提醒** | 若某一字符位置存在“同拼音且同笔画”的不同汉字，提示当前使用稳定伪随机回退 | 警告 |

**检查结果说明：**
- **ERRORS**：严重问题，表示索引的正确性有问题（页码顺序混乱、条目排序错误）
- **WARNINGS**：提示信息，表示可能的优化机会或排序歧义（但不影响生成）

检查报告会在生成完成后自动打印，用户可以审视是否需要调整多音字字典或修正输入索引。

### 程序架构

```
zhmakeindex_py/
├── cli.py                    # 主程序入口
├── idx_parser.py             # .idx 文件解析器
├── readings.py               # 拼音生成（支持多音字）
├── sorter.py                 # 拼音排序
├── writer.py                 # .ind 文件生成与页码合并
├── check_index.py            # 索引检查与验证
├── poly.yaml                 # 内置多音字字典
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
A: 编辑 `poly.yaml` 文件（或通过 `--polyphone` 指定自定义文件），按照 YAML 格式添加条目即可。

**Q: 支持哪些 LaTeX 索引格式？**  
A: 支持标准的 `\indexentry{term|encap}{page}` 格式和嵌套、转义等复杂情况。

**Q: 检查报告中有错误怎么办？**  
A: 先检查多音字覆盖是否完整，再检查输入 `.idx` 文件的索引项是否有误；如果只有排序歧义警告，则表示当前存在“同拼音同笔画”的不同汉字，输出仍可用，但排序依据暂时还不够细。

---

## English

### Overview

`zhmakeindex_py` is a lightweight Python tool for processing LaTeX `.idx` index files and generating correctly sorted `.ind` index files. Chinese entries are compared character by character: each character is ordered by pinyin first and stroke count second. The program also supports polyphone overrides, allowing users to specify preferred pronunciations for specific characters or words.

**Key Features:**
- ✅ Parse LaTeX `.idx` index files (nested braces, escape chars, TeX commands, etc.)
- ✅ Character-by-character Chinese sorting: pinyin first, stroke count second
- ✅ Ambiguity warnings for characters with the same pinyin and stroke count
- ✅ Smart page merging (optimize adjacent page ranges)
- ✅ Generate LaTeX `.ind` index files
- ✅ **Automatic index validation** (page order, entry ordering, cross-reference placement, etc.)

### Installation

#### Requirements
- Python 3.7+
- Dependencies: `pypinyin`, `PyYAML`, `hanzipy`, `unidecode`

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

Output: generates `main.ind`, loads built-in `poly.yaml`, and displays check report

#### Use custom polyphone dictionary

```bash
python cli.py main.idx --polyphone custom_poly.yaml
```

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
| `--polyphone` | YAML polyphone override dict (optional; default uses built-in `poly.yaml`) |
| `--no-check` | Skip automatic validation after generation (optional) |

### Polyphone Dictionary (poly.yaml)

The polyphone dictionary is a YAML file that overrides pinyin readings for specific terms. The built-in dictionary `poly.yaml` contains common terms from physics, mathematics, and other fields. Users can edit or create custom dictionaries.

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
3. For each Chinese character, pinyin is compared first and stroke count second.
4. The next character is considered only when the current character cannot decide the order, which keeps entries sharing the same leading character together.
5. If two different characters still have the same pinyin and the same stroke count at a given position, the current version emits a warning and falls back to a stable pseudo-random order; this can later be refined with stroke-order comparison.

### Automatic Validation

After `.ind` file generation, the program automatically runs validation checks:

| Check | Detailed Description | Level |
|-------|----------------------|-------|
| **Page order** | Verify pages in each entry are sorted small-to-large (e.g., `1, 5--7, 10` is valid; `10, 5--7, 1` is not) | Error |
| **Entry order** | Validate entry ordering with the character-by-character pinyin-plus-stroke rule | Error |
| **Page merging optimization** | Suggest potential improvements for page ranges (e.g., if gaps of 1-2 pages exist, they may be worth merging) | Warning |
| **Sorting ambiguity** | Warn when different characters share the same pinyin and stroke count, so a stable pseudo-random fallback is used | Warning |

**Report Levels:**
- **ERRORS**: Critical issues affecting index correctness (misaligned page order, wrong entry sorting)
- **WARNINGS**: Optimization suggestions or sorting ambiguities (do not block generation)

The validation report is printed automatically after generation, allowing users to review whether adjustments to the polyphone dictionary or input index are needed.

### Program Architecture

```
zhmakeindex_py/
├── cli.py                    # Main entry point
├── idx_parser.py             # .idx file parser
├── readings.py               # Pinyin generation (polyphone support)
├── sorter.py                 # Pinyin-based sorting
├── writer.py                 # .ind file generation + page merging
├── check_index.py            # Index validation
├── poly.yaml                 # Built-in polyphone dictionary
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
A: Edit `poly.yaml` (or use `--polyphone` to specify a custom file) and add entries in YAML format.

**Q: What LaTeX index formats are supported?**  
A: Standard `\indexentry{term|encap}{page}` format with nested braces, escapes, etc.

**Q: What if the check report shows errors?**  
A: First check whether the polyphone overrides are complete, then verify the input `.idx` entries themselves. If you only see ambiguity warnings, the output is still usable, but a finer-grained Chinese ordering rule has not been implemented yet.

---

## License

MIT License

## Author

程序由 Claude AI 协助编写，参考刘海洋的 zhmakeindex 项目。

---

**更新日期**: 2026 年 4 月 14 日  
**版本**: 1.1
