"""Shell 规划用解析器，契约 v1。只拆分，不执行或展开 shell 表达式。"""
import os
from dataclasses import dataclass


@dataclass
class Stage:
    argv: list[str]
    raw: str


@dataclass
class Segment:
    raw: str
    stages: list[Stage]
    redirects: list[tuple[str, str, str]]
    is_pipeline: bool


@dataclass
class Parsed:
    raw: str
    segments: list[Segment]
    ops: list[str]

    def all_words(self):
        return [basename(w) for s in self.segments for stage in s.stages for w in stage.argv]

    def command_words(self):
        return [basename(s.stages[0].argv[0]) if s.stages and s.stages[0].argv else "" for s in self.segments]


def basename(word):
    return os.path.basename(word.rstrip("/")).lower() if word else ""


def first_word(seg):
    return basename(seg.stages[0].argv[0]) if seg.stages and seg.stages[0].argv else ""


def _substitution_end(text, start):
    """跳过完整命令替换，内部操作符不能切开外层命令。"""
    i, depth, quote = start + 2, 1, ""
    while i < len(text):
        c = text[i]
        if c == "\\" and quote != "'":
            i += 2
            continue
        if quote:
            if c == quote:
                quote = ""
        elif c in "'\"`":
            quote = c
        elif c == "(":
            depth += 1
        elif c == ")":
            depth -= 1
            if not depth:
                return i + 1
        i += 1
    raise ValueError("命令替换未闭合")


def _tokens(text):
    result, i = [], 0
    while i < len(text):
        if text[i].isspace():
            i += 1
            continue
        start = i
        if text[i] in ";&|<>":
            op = text[i]
            i += 1
            if i < len(text) and text[start:i + 1] in ("&&", "||", ">>", "<<", ">&", "<&"):
                op = text[start:i + 1]
                i += 1
            if op in ("&", "<<"):
                raise ValueError("交给真实 shell 处理")
            result.append((op, op, start, i))
            continue
        cooked, quote = [], ""
        while i < len(text):
            c = text[i]
            if not quote and (c.isspace() or c in ";&|<>"):
                break
            if c == "\\" and quote != "'":
                if i + 1 >= len(text):
                    raise ValueError("转义未闭合")
                following = text[i + 1]
                if quote == '"' and following not in '$`"\\\n':
                    cooked.append("\\")
                if following != "\n":
                    cooked.append(following)
                i += 2
            elif c == "$" and quote != "'" and text[i:i + 2] == "$(":
                end = _substitution_end(text, i)
                cooked.append(text[i:end])
                i = end
            elif c == "`" and quote != "'":
                end = i + 1
                while end < len(text) and text[end] != "`":
                    end += 2 if text[end] == "\\" else 1
                if end >= len(text):
                    raise ValueError("反引号未闭合")
                cooked.append(text[i:end + 1])
                i = end + 1
            elif c in "'\"" and not quote:
                quote = c
                i += 1
            elif c == quote:
                quote = ""
                i += 1
            else:
                cooked.append(c)
                i += 1
        if quote:
            raise ValueError("引号未闭合")
        result.append(("word", "".join(cooked), start, i))
    return result


def parse_line(line):
    try:
        tokens = _tokens(line)
        segments, ops, stages, redirects, argv = [], [], [], [], []
        segment_start = stage_start = 0
        i = 0
        while i < len(tokens):
            kind, value, start, end = tokens[i]
            if kind == "word":
                # 仅紧邻重定向符的数字是 fd，echo 2 >a 的 2 仍是参数。
                if value.isdigit() and i + 1 < len(tokens) and tokens[i + 1][0] in (">", ">>", "<", ">&", "<&") and end == tokens[i + 1][2]:
                    i += 1
                    kind, _, start, end = tokens[i]
                    fd = value
                else:
                    argv.append(value)
                    i += 1
                    continue
            else:
                fd = "0" if kind.startswith("<") else "1"
            if kind in (">", ">>", "<", ">&", "<&"):
                i += 1
                if i >= len(tokens) or tokens[i][0] != "word":
                    raise ValueError("缺少重定向目标")
                target = tokens[i][1]
                # 契约仅使用 >、>>、<；fd 复制通过 &target 表达。
                redirects.append((fd, kind[0] if kind.endswith("&") else kind, "&" + target if kind.endswith("&") else target))
            elif kind in ("|", ";", "&&", "||"):
                if not argv:
                    raise ValueError("空命令")
                stages.append(Stage(argv, line[stage_start:start].strip()))
                argv = []
                stage_start = end
                if kind != "|":
                    segments.append(Segment(line[segment_start:start].strip(), stages, redirects, len(stages) > 1))
                    ops.append(kind)
                    stages, redirects = [], []
                    segment_start = end
            i += 1
        if argv or stages or redirects:
            if not argv:
                raise ValueError("空管道")
            stages.append(Stage(argv, line[stage_start:].strip()))
            segments.append(Segment(line[segment_start:].strip(), stages, redirects, len(stages) > 1))
        if len(ops) >= len(segments) and ops:
            if ops[-1] == ";":
                ops.pop()
            else:
                raise ValueError("命令未完成")
        return Parsed(line, segments, ops)
    except Exception:
        return Parsed(line, [Segment(line, [Stage([], line)], [], False)], [])
