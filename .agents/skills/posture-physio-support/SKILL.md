---
name: posture-physio-support
description: Use when reviewing body or posture asymmetry, movement limitations, neck or shoulder symptoms, preparing a physiotherapy visit, or tracking an existing clinician-directed rehabilitation plan in physical_sys. 用于体态不对称、功能变化及物理治疗随访；不用于照片诊断或自行制定治疗处方。
---

# 体态与物理治疗辅助

这是 physical_sys 的项目级技能。支持症状整理、功能追踪和专业就诊准备，不诊断疾病或结构异常。

## 输入与证据

先使用本轮用户提供的信息，以及访问权限允许的项目记录。只收集会改变判断的信息：

- 不对称的部位、左右侧、首次发现时间、是否突然发生或持续变化。
- 疼痛、麻木、无力、活动受限；哪些活动受影响，什么加重或缓解，运动后及次日反应。
- 已有康复、骨科或牙科结论及原文来源；治疗师给出的动作、剂量、禁忌与复查安排。
- 用户目标是外观、疼痛、功能或专项表现，分别记录，不混为同一目标。

缺少关键信息时只问当前最必要的一项，其余标记未知。未经询问的症状不能写成“没有”。
区分用户自述、实际测量、专业结论与模型推断；保留日期、单位和来源。不要将外观差异自动解释为病理。

## 工作流程

1. 先识别需要就医的变化。突然出现脸部或肢体无力、言语异常时，停止体态分析并提示立即联系当地急救；新出现或加重的神经症状、外伤后明显功能丧失等优先专业评估。未完成筛查不能宣称已排除风险。
2. 分别描述静态外观、活动表现和功能影响。照片仅能支持可见差异，说明镜头、站姿、角度和光线的限制；不据照片诊断长短腿、骨盆旋转、脊柱疾病或“肌肉失衡”。
3. 选择已有、可重复的复查指标，例如同一活动的耐受时间、同一量表的疼痛评分、专业测得的活动度。不同测量方法不直接合并；数据不足时不预测康复时长。
4. 对已由专业人员制定的计划，整理执行情况及症状反应；不自行增加动作剂量、改变康复阶段或安排诱发疼痛的特殊测试。
5. 若同时涉及颌痛、张口、咀嚼、咬合或颌面变化，读取相邻 `orofacial-tmj-support/SKILL.md`。体态与颌面关系只作为待验证问题，不推断“纠正身体即可纠正颌骨”。
6. 将功能趋势在可用时交给可选 rehabilitation-analyzer；将训练限制候选交给 personal-performance-orchestrator。医生或治疗师的限制优先于训练进阶，候选不等于获准执行。

## 输出

输出简短的事实摘要、未确认问题、复查指标与就诊摘要。需要交接时使用以下字段，缺失值为 null：

| 字段 | 内容 |
|---|---|
| observed_at / source_ref | 观察日期与来源 |
| concern / side | 关注点与侧别 |
| evidence_kind | user_reported、measured、clinician_reported 或 inferred；仅用于交接，不擅改项目 schema |
| symptoms / functional_impact | 症状及活动影响 |
| clinician_constraints | 专业限制、来源与有效期；未知不填造 |
| followup_metrics | 可重复复查的指标、单位与方法 |
| training_constraint_candidates | 待确认限制及依据；无依据不编造 |
| unanswered_questions / care_next_step | 缺失信息与下一步评估 |

## 项目接入与授权

按需读取相邻项目 skill，而非调用同名全局副本。项目健康记录位于 `data/rehab/rehab_log.jsonl` 等已有路径；先遵循项目和运行时访问政策。
调用本技能不赋予健康数据读取、记录写入或外发权限。默认在会话内形成摘要；只有针对记录任务获得授权后才按既有格式追加，保留历史与纠正链，不创建第二套健康档案。
本技能写入授权仅用于安装技能，不代表获准读取真实健康记录或修改治疗计划。

## 来源与适配记录

编写日期：2026-10-11。以下为审查参考；本文件独立编写，不是上游临床技能的完整复制，也不声称临床验证。

- [physio-initial-assessment](https://github.com/mohitagw15856/pm-claude-skills/blob/91c96108b6013f4af481ddb3fc1e7f60e8c5df9e/skills/physio-initial-assessment/SKILL.md)：上游面向持证临床人员；参考功能、症状时序和复查结构，未引入诊断及自行执行检查的流程。
- [NHS：卒中症状](https://www.nhs.uk/conditions/stroke/symptoms/)：突发脸部或肢体无力、言语异常的急救分流参考；急救号码使用用户所在地号码。
- 具体医学问题需要检索时遵循 agent-reach，以官方指南和原始研究核验；GitHub skill 本身不是医学证据。

可选第三方 skill 未随公开版本打包；缺失时报告不可用，不自动安装或假定已执行。
