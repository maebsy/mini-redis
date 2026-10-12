"""과제 제약 조건 자동 검증.

* 패키지 코드에서 dict / set / collections 를 사용하지 않는다.
* 해시맵이 파이썬 내장 hash() 에 의존하지 않는다.
* 자료구조는 각각 독립된 모듈 파일로 분리되어 있다.
* 공개 클래스/함수에는 docstring 이 있다.
"""

import ast
import pathlib
import unittest

PACKAGE = pathlib.Path(__file__).resolve().parent.parent / "mini_redis"
BANNED_NAMES = {"dict", "set", "frozenset", "defaultdict", "OrderedDict", "Counter", "deque", "ChainMap"}


def iter_sources():
    for path in sorted(PACKAGE.rglob("*.py")):
        yield path, ast.parse(path.read_text(encoding="utf-8"), filename=str(path))


class BuiltinCollectionBanTest(unittest.TestCase):
    def test_no_dict_set_or_collections(self):
        violations = []
        for path, tree in iter_sources():
            rel = path.relative_to(PACKAGE.parent)
            for node in ast.walk(tree):
                if isinstance(node, (ast.Dict, ast.DictComp)):
                    violations.append("{}:{} dict literal/comprehension".format(rel, node.lineno))
                elif isinstance(node, (ast.Set, ast.SetComp)):
                    violations.append("{}:{} set literal/comprehension".format(rel, node.lineno))
                elif isinstance(node, ast.Name) and node.id in BANNED_NAMES:
                    violations.append("{}:{} uses '{}'".format(rel, node.lineno, node.id))
                elif isinstance(node, ast.Import):
                    for alias in node.names:
                        if alias.name.split(".")[0] == "collections":
                            violations.append("{}:{} import collections".format(rel, node.lineno))
                elif isinstance(node, ast.ImportFrom) and (node.module or "").split(".")[0] == "collections":
                    violations.append("{}:{} from collections import".format(rel, node.lineno))
        self.assertEqual(violations, [], "\n".join(violations))

    def test_hashmap_does_not_use_builtin_hash(self):
        tree = ast.parse((PACKAGE / "structures" / "hashmap.py").read_text(encoding="utf-8"))
        calls = [n for n in ast.walk(tree)
                 if isinstance(n, ast.Call) and isinstance(n.func, ast.Name) and n.func.id == "hash"]
        self.assertEqual(calls, [])


class StructureLayoutTest(unittest.TestCase):
    def test_each_structure_has_its_own_module(self):
        for name in ("linked_list.py", "hashmap.py", "min_heap.py"):
            self.assertTrue((PACKAGE / "structures" / name).is_file(), name)

    def test_public_classes_and_functions_have_docstrings(self):
        missing = []
        for path, tree in iter_sources():
            if ast.get_docstring(tree) is None:
                missing.append(str(path.relative_to(PACKAGE.parent)))
            for node in tree.body:
                if isinstance(node, (ast.ClassDef, ast.FunctionDef)) and not node.name.startswith("_"):
                    if ast.get_docstring(node) is None and node.name not in ("TreeNode", "BSTNode"):
                        missing.append("{}:{}".format(path.relative_to(PACKAGE.parent), node.name))
        self.assertEqual(missing, [], "\n".join(missing))


if __name__ == "__main__":
    unittest.main()
