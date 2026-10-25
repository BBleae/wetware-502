import sys
import unittest
from pathlib import Path
sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from shell_parser import parse_line, basename


class ParserTests(unittest.TestCase):
    def test_compound_pipeline_redirects(self):
        parsed = parse_line("cd /tmp && cat a.txt | grep x > /tmp/b 2>&1")
        self.assertEqual(parsed.ops, ["&&"])
        self.assertEqual(parsed.command_words(), ["cd", "cat"])
        self.assertEqual(parsed.segments[1].stages[1].argv, ["grep", "x"])
        self.assertEqual(parsed.segments[1].redirects, [("1", ">", "/tmp/b"), ("2", ">", "&1")])
        self.assertTrue(parsed.segments[1].is_pipeline)
        self.assertEqual(parsed.segments[1].raw, "cat a.txt | grep x > /tmp/b 2>&1")

    def test_quotes_and_escapes(self):
        parsed = parse_line("echo 'a;b' \"c&&d\" a\\ b; /bin/LS")
        self.assertEqual(parsed.ops, [";"])
        self.assertEqual(parsed.segments[0].stages[0].argv, ["echo", "a;b", "c&&d", "a b"])
        self.assertEqual(parsed.command_words(), ["echo", "ls"])

    def test_substitutions_are_opaque(self):
        parsed = parse_line('echo "$(printf \'a;b\' | cat)" $(echo $(date); pwd) `echo x || true` && ls')
        self.assertEqual(parsed.ops, ["&&"])
        self.assertEqual(parsed.segments[0].stages[0].argv, ["echo", "$(printf 'a;b' | cat)", "$(echo $(date); pwd)", "`echo x || true`"])

    def test_or_and_pipeline_chain(self):
        parsed = parse_line("false || cat a | grep x | head -n 1 && echo yes")
        self.assertEqual(parsed.ops, ["||", "&&"])
        self.assertEqual(len(parsed.segments[1].stages), 3)
        self.assertEqual(parsed.all_words(), ["false", "cat", "a", "grep", "x", "head", "-n", "1", "echo", "yes"])

    def test_fd_adjacency_input_append_and_empty_quoted_arg(self):
        parsed = parse_line("cat < in >> out 2>err; echo 2 > out ''")
        self.assertEqual(parsed.segments[0].redirects, [("0", "<", "in"), ("1", ">>", "out"), ("2", ">", "err")])
        self.assertEqual(parsed.segments[1].stages[0].argv, ["echo", "2", ""])

    def test_failure_preserves_real_command(self):
        for line in ("echo 'oops", "echo $(cat", "cat |", "cat <<EOF", "sleep 3 &"):
            parsed = parse_line(line)
            self.assertEqual(parsed.segments[0].raw, line)
            self.assertEqual(parsed.segments[0].stages[0].argv, [])
            self.assertEqual(parsed.ops, [])
        self.assertEqual(basename("/BIN/CAT"), "cat")


if __name__ == "__main__":
    unittest.main()
