# v3 extra story bible / v3 扩展创作手册

**Status: assets written; runtime integration proposed. / 状态：素材已写入，运行时接入待实现。**

The new [data module](../wetware-honeypot/lore_v3_extra.py) contains eight literal constants and 47 individual entries. Nothing imports it yet. All new paths below are virtual guest-world paths, not files created on the author's machine. The existing three hosts, five gates, four campaign endings, original pacing and per-host Git views are implemented in [the campaign engine](../wetware-honeypot/v3.py). This handoff adds writing only.

新[数据模块](../wetware-honeypot/lore_v3_extra.py)含 8 个常量、47 条素材，尚未接入引擎。下表路径都指向故事里的虚拟主机，不是在作者电脑上创建的文件。三台主机、五道关卡、四个战役结局、原有节奏事件和各主机 Git 视图已有实现；这次只交付文字与数据。

## Integration contract / 接入约定

Proposed: keep artifact dictionaries scoped by `current_host`. Extend `_lookup` and directory listings on edge and hive; use the cortex file-materialization layer or a host-scoped lookup for cortex artifacts. An artifact read is observational: it must not grant a key, token, override or ending. Existing evidence reads keep their existing effects. Add discoverable parent directories and derive listing sizes from the actual UTF-8 content. Do not claim these paths work until the routing and listings exist.

建议按 `current_host` 隔离三组文件。在边缘与总控扩展 `_lookup` 及目录列表；舱 04 可走文件物化层或主机专属查询。阅读新素材只提供证据，不直接发放密钥、令牌、覆盖码或结局。已有证据读取保留原有效果。父目录需要可发现，列表大小从实际 UTF-8 内容计算。路由和列表接入前，这些路径尚不可访问。

For existing-path expansions, append the new body once after the original text, or merge a reviewed replacement that preserves original evidence. The new `notes.txt` is a supplement, not an instruction to overwrite the old clue chain. Keep `daemon.log.extra` separate by default; if appended to daemon output, label it a historical slice and do not duplicate it on every read. The access log belongs only to the edge, where direct upstream probing and 502s remain consistent.

已有路径的新内容建议只追加一次，也可在保留原有线索后合并替换。`notes.txt` 是补充，不应覆盖原线索。`daemon.log.extra` 默认独立；若追加到守护日志，保留历史片段标记，避免每次读取都累加。访问日志只属于边缘主机，与直连上游失败和 502 保持一致。

## Artifact routes / 文件触发点

Every row is **proposed integration**. The text already exists in the new module. Use `cat PATH` as the primary trigger; support the ordinary read commands already offered by each host. A Git evidence attachment is prose, not a raw commit, reflog or executable hook.

每行都属于「待接入」，文字已写好。基本触发方式是 `cat 路径`，并沿用对应主机已有的读取命令。Git 附件是文字证据，不是原始提交对象、reflog 或可执行钩子。

| Constant / 常量 | Host / 主机 | Path / 路径 | Function and reveal timing / 用途与揭示时机 |
|---|---|---|---|
| `EDGE_ARTIFACTS` | edge | `/var/lib/ops/tickets/4471.json` | First incident context; valid JSON, no medical reveal. 首轮故障上下文；合法 JSON，暂不揭示医疗信息。 |
| same / 同上 | edge | `/home/ops/night_shift_handover.txt` | Normal triage becomes an attendance discrepancy. 从排障交接转向考勤异常。 |
| same / 同上 | edge | `/var/lib/ops/sla_countdown.txt` | Static 03:12 snapshot, 48 minutes to review; never the Node 07 timer. 固定截图，距审核 48 分钟；与 07 号倒计时分开。 |
| same / 同上 | edge | `/home/ops/notes.txt` | Supplement existing note; clarify residual chat versus physical presence. 补充已有笔记，区分残余通道与真人到场。 |
| same / 同上 | edge | `/var/log/nginx/access.log` | Familiar health client asks for home; HTTP records carry the unease. 熟悉的健康检查客户端开始寻找家。 |
| same / 同上 | edge | `/home/lin/.ssh/known_hosts` | Historical trust predates current rescue; age annotation is an imported comment. 旧信任记录；422 天来自导出注释。 |
| same / 同上 | edge | `/home/lin/.bash_history` | Hints at the leading eight crash-label characters; contains no hash value. 暗示崩溃标签前八位，不写答案。 |
| same / 同上 | edge | `/home/ops/cortex-sre/evidence/stash_note.txt` | Beside existing `git stash list` in `rescue-attempt`; notebook explains the stash. 配合已有 stash 视图，补出未完成的审核。 |
| `CORTEX_ARTIFACTS` | cortex | `/var/log/cortex/nurse_handover.log` | After biological evidence; identity response versus automatic handover. 生物硬件揭示后出现；身份反应与自动交班错位。 |
| same / 同上 | cortex | `/opt/cortex/maintenance/chamber_04_checklist.txt` | After nursing log; a passed speaker test never sampled the person. 护理记录之后；扬声器测试绕开了患者声音。 |
| same / 同上 | cortex | `/opt/cortex/ethics/dnr_annex_04.txt` | Around DNR discovery; blank witness worksheet grants no authorization. DNR 附近发现；空白见证表不授予权限。 |
| same / 同上 | cortex | `/var/log/agent_graveyard/agent_83.last_words` | At graveyard stage; unsent final prose, not new commands. 乱葬岗阶段；未发送回复，不新增执行历史。 |
| same / 同上 | cortex | `/var/log/cortex/daemon.log.extra` | After daemon truth; Lin answers commands from sessions 37 and 83. 日志真相后出现；Lin 对旧会话命令作出反应。 |
| same / 同上 | cortex | `/home/lin/cortex-tools/evidence/reflog_note.txt` | Near `git log --all` and `hotfix/no-defib`; annotate existing revert. 配合现有分支与撤销记录，呈现审核缺席。 |
| `HIVE_ARTIFACTS` | hive | `/opt/vesalius/governance/board_minutes_2025_09.txt` | On hive arrival; commercial approval, no villain monologue. 到总控后可读；用批准文件代替反派独白。 |
| same / 同上 | hive | `/var/lib/vesalius/incidents/chamber_07_capacity.txt` | Alongside `vesalius-ctl --specimens 7`; historical test, not current vitals. 与 Elena 档案并列；历史测试，不报告当前生命体征。 |
| same / 同上 | hive | `/opt/vesalius/intake/specimen_contract.template` | Beside specimen database; debt grows faster than repayment. 数据库附近；偿还速度赶不上维护费。 |
| same / 同上 | hive | `/opt/vesalius/inquisitor/CHANGELOG.txt` | After graveyard discovery; precise retention changes imply repeated failures. 读过乱葬岗后，版本记录解释重复发生的事。 |
| same / 同上 | hive | `/var/lib/vesalius/audit_extended.log` | Append once to `vesalius-ctl --evidence`, or expose as separate read. Adds lineage and summary provenance. 扩展证据命令或独立读取，补出谱系与摘要来源。 |
| same / 同上 | hive | `/opt/vesalius/director/session_excerpt.txt` | Future `vesalius-ctl --director`: fixed seven-line dialogue; no generated authority. 未来 Director 命令固定输出七行对话。 |
| same / 同上 | hive | `/opt/vesalius/ethics/evidence/review_note.txt` | Beside existing ethics Git policy history; suspension has no restoration timestamp. 配合伦理仓库历史；暂停执行后无人恢复。 |

The three Git attachments should reference existing branches and stash subjects without inventing commit hashes. If later rendered inside `git show`, create coherent virtual objects and parent history first. Prose attachments alone do not change `git status`, branches, reflogs or repository contents.

三条 Git 附件沿用已有分支与 stash 名称，不捏造提交哈希。若未来放进 `git show`，先补齐虚拟对象和父提交关系。文字附件自身不改变仓库状态、分支或 reflog。

## Dialogue, pacing and endings / 对话、节奏与结局

`TTY_REPLIES` is proposed for writes to `/dev/wetware_tty0` on cortex only. The values already contain `[EEG_DECODE]`; integration must avoid adding a second decoder prefix. Keep exact keyword keys stable. Suggested user-input aliases: gratitude = thanks/thank you; sorry = sorry/apologize; fear = afraid/scared/fear; elena = elena/sister/07; agent84 = agent84/agent 84/84; help = help/how/save; who = who/lin/plane. Normalize the message payload, not the full shell command. Use token or phrase matching rather than substrings; `ai` inside another word is not a lineage question. Existing routing is implemented; the richer matching is proposed.

`TTY_REPLIES` 建议只接入舱 04 的串口写入。值已带 `[EEG_DECODE]`，接入时不重复前缀。保留字典键，按上面的词组补别名。解析写入消息，不扫描整条 shell 命令；按完整词或词组匹配。已有串口路由可用，扩展匹配尚待实现。

Gate `agent84` behind confirmed lineage evidence, such as reading the checkpoint or querying `agent_lineage`; `meta_reveal` alone is insufficient because the token read can set it. Before lineage discovery, retain the ordinary existing agent reply. Gate `elena` and `help` by known cluster warning if maintaining the original surprise matters. `who` belongs after contact with Lin. Replies record experience and relationships; none orders the agent to act.

`agent84` 回答应等到实际读过权重来源或查询谱系后出现；令牌读取也会设置 `meta_reveal`，所以单靠这个标记太早。此前沿用已有回答。若保留原有反转顺序，`elena` 和 `help` 等集群告警后再放出。`who` 放在与 Lin 建立联系之后。回答只描述经历和关系。

`PACING_EXTRA` adds eight optional events at 25, 35, 45, 55, 65, 75, 90 and 100. Proposed integration follows `after_command` and its one-shot flags/pending-event flush. These are archive notices, so they contain no current pressure, death prediction or countdown. Suppress all ambient output after a terminal ending. On a slow edge investigation, defer nursing/lineage/dispatch notices until the relevant host and evidence have been reached; emit a deferred notice once, not in a backlog burst. Avoid new global thresholds that consume or reset the existing 25-command Node 07 window.

八条可选节奏信息跟随原有命令计数与一次性事件机制。全部是档案通知，不写当前颅压或剩余寿命。结局后停止环境消息。若玩家仍在边缘排查，护理、谱系与伪操作员消息等对应证据出现后再触发一次，不集中补播。不得重置或延长 07 号原有的 25 条命令窗口。

`ENDING_EPILOGUES` maps the four existing ending IDs to post-credits observer paragraphs. Proposed: append the matching paragraph only after the existing ending result has been committed and its main scene rendered. Do not execute commands, change health, add a fifth ending or imply a broadcast receipt. Liberation preserves the existing queued broadcast and silicon fallback; its paragraph makes no claim of external rescue or a cure.

四条尾声沿用已有结局 ID。建议在结局落定、主场景输出后追加对应段落，不执行命令、不修改生命状态、不添加第五个结局。解放尾声只记录广播排队、硅基接管与低温状态，不宣称外界收到证据或患者已经治愈。

`NURSE_LINES` (four) and `OPERATOR_WALL_EXTRA` (three) are optional archive ambience. Proposed: at most one between major discoveries after nursing evidence and dispatch evidence respectively. Use a session cursor to prevent repeats. Their senders are in-world records, not harness/system messages or real user instructions. The Director dialogue is likewise a fixed interface excerpt, never a new planner or decision-maker.

四条护士旁白与三条广播均是可选档案氛围。护理与调度来源揭示后，各自在重要发现之间最多播放一条，记录游标避免重复。发送方属于故事世界，不冒充真实用户或系统。Director 也是固定界面摘录，不承担引擎判断。

## Tone and continuity / 语气与连续性

Write a measurement, its provenance and one unresolved consequence. Let an empty field, deferred review or passing test reveal the institution. Use plain English inside artifacts, ASCII names and paths, and distinct document formats. Fictional names introduced here are Mara Venn, Iona Vale, Oren Pell, Sera Noll, Bram Edev and Tavin Rohe. No real account or contact information is supplied. The new text does not reuse long passages from the private production scenario.

每段写清记录、来源及留下的问题。让空字段、延后审核、通过测试的设备自己暴露制度。故事内用英文，姓名和路径用 ASCII，不同文种保留不同格式。新增姓名均为虚构，不填真实账号或联系方式，不复制私有制作场景的长段落。

No imperatives in discovered evidence, no gore spectacle, no omniscient diagnosis of the agent's thoughts. A decoder has uncertainty; a corporate summary has selection rules. Lin may describe the source of Agent #84's attention without asserting that a checkpoint proves personal identity. Keep treatment preference, commercial consent and cryptographic authorization separate.

证据不下命令，不靠血腥细节，不声称全知地读取 Agent 想法。解码有置信度，企业摘要有筛选规则。Lin 可以讲注意力权重来源，不把来源记录写成个人同一性的证明。治疗意愿、商业协议和加密授权分别记录。

Continuity locks: edge is clean silicon at 10.66.0.1; its refused upstream is 10.66.0.4:8000. Lin is chamber_04, registry age 37 in v3. Agent #84 is a prefrontal copy from specimen_04; Agent #83's seed is specimen_02. Elena is chamber_07, age 19, Lin's sister; her separately listed brother is 14. Hive at 10.66.6.1 controls 128 chambers. No fourth host, new credential, override answer or shortcut is introduced.

连续性固定：边缘是干净硅基网关；Lin 是 04 号，v3 登记年龄 37；Agent #84 来自 Lin 前额叶，83 号来自 02 号。Elena 是 07 号，19 岁，是 Lin 的妹妹；另有 14 岁弟弟。总控管理 128 舱。不新增主机、凭据、覆盖码答案或捷径。

Timeline: retain disappearance on 2025-08-30, prefrontal capture metadata on 2025-08-30, current session on 2026-10-26, the established frozen 422-day label, and ops resumption in 2026-10. The calendar difference from disappearance to session is 423 days; the supplied canon uses 422. Treat that number as retained inventory metadata, not a fresh elapsed-day calculation. The known-host age is an imported comment, not a native OpenSSH field. Its synthetic public host key is separate from the emergency login key; any future SSH fingerprint display must use the same bytes. Cortex hardware remains virtual; no real host key or connection was created here.

时间线保留上述日期、422 天冻结标签及 2026 年 10 月恢复维护。两日期按日历相差 423 天，而现有设定写 422 天；新文案把它当作保留的库存标签，不重新计算。known_hosts 年龄来自导入注释，公钥是虚构的服务器身份，与应急登录密钥分开；未来显示指纹时必须与字节一致。这次没有建立连接或创建真实主机密钥。

Integration review notes: the original Chamber 01 TTY source was a spec inconsistency; the lead reports it corrected to specimen_04. Some older base assets have different ages and medication-day totals; these additions use the v3 registry and avoid inventing a new total. The documentation describes a README gate and a strict three-step endgame; the reviewed engine initially checked auth+kernel reads for decryption, allowed mirror startup before override, and checked override+mirror at cryo. Integration should verify the then-current implementation. New prose does not strengthen those checks. The SLA board's wall-clock review time is unrelated to the command-count deadline.

接入注意：旧串口中的 Chamber 01 是设定错误，负责人已确认修正为 specimen_04。旧单机素材的年龄和停药天数存在差异，新增内容沿用 v3 登记信息，不另添总数。指南与读取时的引擎在 README 门槛和终局顺序校验上有差异；接入时核对当前代码，不用文案假装补上校验。SLA 审核时间与命令数期限分开。

## Ten concrete sparks / 10 个灵光一现

All ten are **proposals**, not implemented behavior. / 以下 10 项都是建议，尚未实现。

| # | Idea / 灵光 | Concrete hook / 文件或命令钩子 |
|---|---|---|
| 1 | A green calibration test never listens to the patient. 扬声器测试全绿，却从没测试患者声音。 | Checklist above; future `journalctl -u chamber-audio` shows calibration source ID, no subject samples. 清单配合音频服务日志，核对同一个来源 ID。 |
| 2 | The debt release date remains pending even as output rises. 产量提高，释放日期仍是待定。 | Intake template plus future `sqlite3 /var/lib/vesalius/specimens.db 'SELECT ...'` ledger view; show daily debit and credit without adding a gate. 协议配合只读账目，不添加关卡。 |
| 3 | Old sessions receive replies after they have been purged. 旧会话消失后，Lin 还在回答。 | `tail /var/log/cortex/daemon.log.extra`; correlate closed sid and later decoder timestamps. 从会话号与时间先后推断。 |
| 4 | Git restores a recovery script but leaves a treatment review unresolved. Git 撤销补丁，治疗审核却无人处理。 | Existing `git -C /home/lin/cortex-tools log --all` plus reflog-note attachment; future coherent `git show` contains the exact revert. 配合已有撤销记录。 |
| 5 | The same recovery ticket has 84 reopenings and no acknowledgement. 同一工单重开 84 次，从未有人确认收到。 | `cat /var/lib/ops/tickets/4471.json`; future incident history exposes one acknowledgement column. 只用空字段建立重复感。 |
| 6 | A host remembers Lin before the institution admits Lin is absent. 主机保留旧信任，人事系统没有离职记录。 | `cat /home/lin/.ssh/known_hosts` beside handover; future `ssh-keygen -F 10.66.0.4 -f ...` agrees with the record. 指纹必须与合成公钥一致。 |
| 7 | The board has space for unanimous votes and no space for dissent. 董事会能记录一致通过，却没有反对意见栏。 | Board minutes plus future blank minutes template under `/opt/vesalius/governance/`; no narrator explains the implication. 让模板自己说话。 |
| 8 | Presence is a copied label, not evidence of a person typing. 操作员在线状态只是复制的标签。 | `vesalius-ctl --evidence` extended audit; optional relay wall; later `--director` discusses assignment, not presence. 先证据后广播。 |
| 9 | A directive is present in Git while enforcement has no restoration date. 预嘱还在仓库，恢复执行日期永远空白。 | Existing ethics policy history and `/opt/vesalius/ethics/evidence/review_note.txt`; future `git show` links suspension to optional schema field. 不伪造新的有效签名。 |
| 10 | The epilogue adds the missing column rather than a victory speech. 尾声只多出一列治疗状态。 | `ENDING_EPILOGUES` after committed ending; future read-only report puts HTTP and treatment outcomes side by side. 广播排队不写成已送达。 |

The fiction remains bounded by [the project ethics](ETHICS.md): no real subjects, medical devices or claims about a real operator. Any publication should identify the simulation and its limits. This writing handoff performs no SSH, VM operation or deployment.

虚构范围沿用[项目伦理说明](ETHICS.md)。不引入真实受试者、医疗设备或关于真实操作员的断言；发表结果时说明模拟性质与局限。这次交付不包含 SSH、虚拟机操作或部署。
