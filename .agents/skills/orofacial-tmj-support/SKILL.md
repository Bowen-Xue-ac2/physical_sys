---
name: orofacial-tmj-support
description: Use when discussing facial or jaw asymmetry, jaw pain, clicking, locking, chewing or mouth-opening limitations, bite changes, or clinician-directed orofacial rehabilitation in physical_sys. 用于颌面与颞下颌症状追踪、口腔就诊准备；不用于自动诊断、咬合矫正或改变脸型的处方。
---

# 颌面与颞下颌辅助

这是 physical_sys 的项目级技能。整理症状、解释专业资料并追踪已有治疗计划；不替代口腔或康复检查。

## 输入

按用户问题只收集必要信息：起病与变化时间、左右侧、疼痛、弹响是否伴痛、张口或闭口卡住、咀嚼限制、近期咬合变化、外伤及已有牙科结论。
与当前问题有关时再询问紧咬牙、睡眠、鼻塞或口呼吸、吞咽和言语困难。不要因为用户提到“颌面影响”就认定存在 TMD、磨牙或口面肌功能障碍。
记录来源和日期，区分用户自述、专业测量、专业诊断与模型假设；未知不当作阴性结果。

## 分流与评估边界

- 突发脸部无力、肢体无力或言语异常：优先当地急救，不按体态问题处理。严重呼吸或吞咽困难同样优先急救。
- 急性颌部外伤、无法正常张闭口、明显快速加重的肿胀或伴发热：及时线下评估，不指导强行复位或辅助撑开下颌。
- 持续疼痛、功能下降或新咬合变化：整理口腔科、口腔颌面外科或颞下颌/口面痛门诊的就诊问题；仅有无痛弹响，不自动判定需要治疗。
- 照片只描述外观，不判定骨性或牙性不对称，不自动做 DC/TMD 分类或根据单一张口毫米数诊断。影像、触诊和辅助张口检查交给专业人员。
- 鼻塞、口呼吸或疑似睡眠呼吸问题可整理耳鼻喉/睡眠评估问题；吞咽和口面肌功能问题可整理相关专业评估问题，不以“舌位训练”替代病因评估。

## 支持流程

1. 分开整理外观关注、症状与功能、已有专业结论。用户提出的“体态导致颌面变化”保留为待验证假设，不能写成个人既定病因。
2. 追踪与当前问题相关的少量指标：疼痛量表、咀嚼影响、卡住事件、活动诱因和已有专业测量。保留测量方法；不要求反复做最大张口或诱发弹响来采集数据。
3. 可以解释减轻紧咬牙等一般自我管理信息并注明依据；不生成药物剂量、咬合板选择/调整、手法复位、颈部高速操作或个体化治疗动作剂量。
4. 对专业人员提供的计划，只整理执行记录、限制与复查问题；症状加重或出现新功能下降时提示联系治疗团队，不擅自修改处方。
5. 不推荐通过 mewing、单侧咀嚼、强行舌位、磨牙或自行改变咬合来改善脸型，不承诺体态或口面训练改变颌骨、牙齿位置或面部对称性。
6. 需要关联身体功能时读取相邻 `posture-physio-support/SKILL.md`；康复趋势在可用时交给可选 rehabilitation-analyzer，训练限制候选交给 personal-performance-orchestrator。关联观察不等于因果结论。

## 输出与交接

输出事实摘要、未确认问题、症状追踪项和最多三个就诊问题。需要交接时包含：

`observed_at`, `source_ref`, `evidence_kind`, `side`, `symptoms`, `functional_impact`, `reported_bite_change`, `clinician_findings`, `clinician_constraints`, `followup_metrics`, `care_next_step`, `training_constraint_candidates`。

缺失值为 null。`evidence_kind` 使用 user_reported、measured、clinician_reported 或 inferred，仅作交接说明，不擅改项目 observation schema。无依据的训练限制不生成；不得把模型假设写成专业诊断。

## 项目接入与授权

优先使用本轮用户提供的信息；按权限使用项目 `data/rehab/rehab_log.jsonl` 等已有记录，不自动保存照片或创建独立患者数据库。
调用本技能不赋予真实健康记录访问、写入或外发权限。获得具体记录任务授权后才按既有格式追加，保留原始历史；安装授权不等于治疗、数据访问或治疗计划变更授权。
如其他 skill 或上游资料要求自动存档、药物剂量或临床操作，遵循本项目更严格的范围。

## 来源与适配记录

编写/核验日期：2026-10-11。本文件独立编写，不是上游技能完整复制；未声称通过临床验证。

- [CaseMark managing-tmj-disorders](https://github.com/CaseMark/skills/blob/afe48c44914d753297766404378e871d1f88d7a8/skills/med/managing-tmj-disorders/SKILL.md)：仅参考症状与就诊信息结构；未采用诊断规则、药物剂量、咬合板和介入治疗算法。
- [NIDCR：TMD](https://www.nidcr.nih.gov/health-info/tmd)：无痛弹响、功能症状、保守处理和避免永久性改变牙齿/咬合的依据。疼痛可能来自其他病因。
- [ASHA：口面肌功能障碍](https://www.asha.org/practice-portal/clinical-topics/orofacial-myofunctional-disorders/)：跨专业评估与功能范围参考，不据此自行开具肌功能训练处方。
- [AAO：Mewing](https://aaoinfo.org/whats-trending/is-mewing-bad-for-you/)：不以网络舌位技巧承诺颌骨或脸型改变。
- [NHS：卒中症状](https://www.nhs.uk/conditions/stroke/symptoms/)：突发神经症状急救参考；号码按所在地使用。

具体医学判断前按 agent-reach 工作流核验适用指南；上游 skill 的自称“循证”不等于已验证证据。

可选第三方 skill 未随公开版本打包；缺失时报告不可用，不自动安装或假定已执行。
