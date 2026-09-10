# References

- 对于资料的收集，应该不是自己在这里搞事情，应该借助别人成熟的爬虫的方法；
- 找开源的爬虫：爬论文、爬网页；

## 哔站


## 目标
- 我要实现一个关于地氟病的专业只是库
- 所以我需要很多关于这方面的很多内容
- 包括病症的特点、表现、后果、并发症、治疗方案、等等一系列专业知识都需要包括到我的知识库中
- 之后会提供给LLM进行使用以减少幻觉，并作为诊断报告的生成

## 内容
- 要尽可能的收集有关于以下关于氟中毒的相关内容：
地氟病、氟中毒、氟斑牙、氟骨症
endemic fluorosis、fluorosis、dental fluorosis、skeletal fluorosis

## 资料要求
1. 专业的学术网站，包括但不限于： PubMed、Google scholar、知网、万方等等；
2. 出版社，包括国内外的出版社刊物、专业书籍等等；
3. 国内外的医院公开网站发布的相关资料教程，治疗方案等等；
4. 专业公司、组织的网站公开资料等等；
5. 包括一些挑战赛的公开数据资料；
6. 其他我没有想到，但是资料质量较好的资源，请帮我补充；
7. 以上的提到的具体的网站名字只是我目前能想到的资料网站，对应的其他的优质网站请帮我补充；

## 要求
1. 对于以上提到的内容，我需要到相应的网站上进行搜集资料，所以你需要帮我列出所有可能网站的搜索地址和搜索方式、搜索指令、搜索关键词等等；

## 分析报告

这份需求的核心是围绕“地方性氟中毒”建立一个可被 LLM 直接调用的专业医学知识库，因此知识建设的重点不在泛医学覆盖，而在单病种深度、术语统一和证据可追溯。对应“目标”板块，知识库必须服务于报告生成与幻觉抑制，所以后续入库内容应尽量保留原始证据，而不是只存结论。

对应“内容”板块，主题边界已经明确限定为地氟病、氟中毒、氟斑牙、氟骨症及其英文同义词。这说明后续检索词、分类标签和抽取规则都应围绕同义词体系展开，避免因为中英文名称不统一导致漏抓资料。更适合的组织方式是按疾病实体、临床表现、病因机制、并发症和治疗干预来做结构化整理。

对应“资料要求”板块，来源优先级应当分层：学术网站和数据库用于获取高质量论文与综述，出版社与专业书籍用于补足系统性知识，医院和专业机构网站用于获取临床路径和指南，专业公司或组织网站用于补充标准化资料，公开数据与挑战赛数据则可用于结构化训练和验证。这里最重要的不是来源数量，而是来源权威性、更新时效和可审核性。

对应“要求”板块，当前真正需要的是一套可执行的采集与检索方案，也就是每类站点的搜索入口、站内检索方式、关键词组合和过滤策略。下面按板块列出可直接使用的搜索地址和检索方法。

1. PubMed
- 入口：`https://pubmed.ncbi.nlm.nih.gov/`
- 高级检索：`https://pubmed.ncbi.nlm.nih.gov/advanced/`
- 适合方式：直接搜索、Advanced Search Builder、MeSH、字段限定、日期限定
- 常用语法：`"fluorosis"[tiab]`、`("dental fluorosis"[tiab] OR "skeletal fluorosis"[tiab])`、`fluorosis AND treatment`、`fluorosis[mh]`、`fluorosis AND 2020/01/01[dp]`
- 关键词模板：
  - 疾病词：`endemic fluorosis`, `fluorosis`, `dental fluorosis`, `skeletal fluorosis`
  - 中文补充：`地方性氟中毒`, `氟中毒`, `氟斑牙`, `氟骨症`
  - 主题词：`pathogenesis`, `clinical features`, `diagnosis`, `treatment`, `prevention`, `epidemiology`, `children`

2. Google Scholar
- 入口：`https://scholar.google.com/`
- 检索地址：`https://scholar.google.com/scholar?q=关键词`
- 适合方式：标题精确匹配、作者限定、年份筛选、按日期排序、引用链追踪
- 常用语法：`author:"fluorosis"`、`"dental fluorosis"`、`intitle:fluorosis`、`site:edu fluorosis`、`"skeletal fluorosis" treatment`
- 关键词模板：
  - `fluorosis` `dental fluorosis` `skeletal fluorosis` `endemic fluorosis`
  - `fluoride exposure` `drinking water` `fluoride level` `fluorosis prevalence`
  - `review` `systematic review` `case report` `guideline`

3. 中国知网 CNKI
- 入口：`https://www.cnki.net/`
- 常见检索入口：站内检索框、CNKI 高级检索、期刊站点的“高级检索”
- 期刊站点检索例：`https://*.cbpt.cnki.net/EditorH3N/WebPublication/advSearchArticle.aspx`
- 适合方式：题名、摘要、关键词、作者、单位、年份、分类号检索
- 常用检索思路：在题名/关键词中用“氟中毒 OR 氟斑牙 OR 氟骨症 OR 地方性氟中毒”
- 关键词模板：
  - `地方性氟中毒`
  - `氟中毒 AND 病因`
  - `氟斑牙 AND 诊断`
  - `氟骨症 AND 治疗`
  - `氟化物 AND 流行病学`
- 适合筛选：来源类别、核心期刊、年份、学科、基金、作者单位

4. 万方数据
- 入口：`https://www.wanfangdata.com.cn/`
- 适合方式：自然语句检索、题名/作者/作者单位/关键词/摘要检索、高级检索
- 常用检索思路：`地方性氟中毒`、`氟斑牙`、`skeletal fluorosis`、`fluoride exposure`、`drinking water fluorosis`
- 关键词模板：
  - 疾病：`地氟病` `氟中毒` `氟斑牙` `氟骨症`
  - 主题：`临床表现` `治疗方案` `流行病学` `病理机制` `预防`
- 适合筛选：期刊、学位、会议、科技报告、标准、成果

5. 出版社和专业书籍平台
- 入口：出版社官网、图书馆目录、Google Books、各类电子书平台
- 适合方式：书名检索、章节检索、索引词检索、作者检索
- 搜索关键词：
  - `fluorosis textbook`
  - `oral pathology fluorosis`
  - `environmental health fluorosis`
  - `地方性氟中毒 书籍`
  - `氟斑牙 口腔病理`
- 检索重点：病因学、病理学、口腔医学、骨科影像、公共卫生章节

6. 医院官网、学会官网、专业组织官网
- 入口：各医院官网、中华医学会/专科分会、WHO、CDC、NHS、NIH、MedlinePlus 等机构站点
- 适合方式：站内搜索、`site:` 限定、专题页搜索
- 常用搜索式：
  - `site:who.int fluorosis`
  - `site:cdc.gov fluorosis`
  - `site:nih.gov fluorosis`
  - `site:medlineplus.gov fluorosis`
  - `site:nhc.gov.cn 氟中毒`
  - `site:chinacdc.cn 氟斑牙`
- 关键词模板：
  - `clinical guideline`
  - `patient education`
  - `diagnosis`
  - `management`
  - `prevention`

7. 公共数据平台与挑战赛数据
- 入口：`https://www.kaggle.com/datasets`、`https://zenodo.org/`、`https://figshare.com/`、`https://datasetsearch.research.google.com/`
- 适合方式：关键词检索、标签检索、主题检索、文件类型筛选
- 搜索关键词：
  - `fluorosis dataset`
  - `dental fluorosis images`
  - `fluoride exposure dataset`
  - `public health dataset fluorosis`
- 检索重点：图像数据、病例数据、流行病学数据、区域饮水氟暴露数据

8. 推荐的统一关键词池
- 中文主词：`地方性氟中毒`、`氟中毒`、`氟斑牙`、`氟骨症`
- 英文主词：`endemic fluorosis`、`fluorosis`、`dental fluorosis`、`skeletal fluorosis`
- 临床词：`symptom`、`signs`、`diagnosis`、`imaging`、`treatment`、`management`
- 机制词：`pathogenesis`、`mechanism`、`fluoride exposure`、`water fluoride`
- 人群词：`children`、`adolescent`、`pregnancy`、`rural population`
- 研究词：`review`、`systematic review`、`case report`、`guideline`、`epidemiology`

综合来看，这个项目的知识库应按“主题收敛、来源分层、证据留痕、结构化抽取”四个原则推进；而检索层面则应按“站点入口 + 检索语法 + 关键词池 + 筛选条件”四件套执行。这样既能支撑后续 RAG 检索和知识图谱构建，也能让诊断报告生成更稳定、更可解释。
