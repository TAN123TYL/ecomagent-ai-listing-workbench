# CSV 批量 Listing 工作流

该功能基于 EcomAgent 的 Listing Generator 二次开发，用于把 Excel 可读的 CSV
商品表批量转换为待审核的 Amazon Listing。它重点解决三件事：

1. 统一商品输入格式，减少逐条复制字段。
2. 使用有并发上限的批处理调用 LLM，单行失败不会中断整批任务。
3. 在导出前检查标题、卖点、描述、搜索词和 A+ 主题，并标记需要人工复核的行。

## 输入格式

支持的列名不区分大小写，首列推荐使用 `keyword`。

| 标准列 | 可选别名 | 说明 |
|---|---|---|
| keyword | primary_keyword / product_name / title | 主要搜索词或商品名 |
| asin | asin | 参考 ASIN，可为空 |
| brand | brand | 品牌，可为空 |
| features | feature / selling_points | 多个卖点使用 `\|` 或换行分隔 |
| marketplace | market | 默认 `amazon.com` |
| language | lang | `en/de/fr/es/it/jp` |

其他列会作为商品上下文传给生成模块。文件支持 UTF-8 BOM，因此可以直接从
Excel 另存为 CSV 后使用。

## 运行

先在仓库根目录配置 `.env`，然后执行：

```bash
cd backend
python scripts/batch_listing.py \
  --input ../examples/batch_products.csv \
  --output ../outputs/review.csv \
  --concurrency 3
```

输出文件用 Excel 打开后，重点检查以下字段：

- `status`：`success`、`needs_review` 或 `failed`
- `validation_issues`：规则校验未通过的原因
- `title`、`bullet_1` 至 `bullet_5`、`description`、`search_terms`

## 人工审核清单

1. 核对品牌、材质、尺寸、认证和功能是否与真实商品一致。
2. 删除无法由商品资料证明的绝对化描述和效果承诺。
3. 检查标题是否自然包含主要关键词，避免关键词堆砌。
4. 检查卖点是否完整、可读，并避免重复表达。
5. 确认输出不包含客户隐私、未授权图片说明或敏感业务数据。

## 规则边界

自动校验只负责可计算的格式规则，不能替代事实核验和平台合规审核。
所有 `needs_review` 行都必须由人工确认后才能用于业务。
