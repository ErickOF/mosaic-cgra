"""Read native tile interfaces without importing simulation-owned defaults.

The evaluator accepts integer SystemVerilog expressions only. Geometry-valid
aliases select their valid branch; the exported RTL retains its real elaboration
guards, while the editor validates editable combinations before generation.
"""

import ast
from functools import lru_cache
from pathlib import Path
import re

ROOT = Path(__file__).resolve().parents[3]
RTL = ROOT / "src/rtl"


def integer(expression, lookup):
    expression = " ".join(expression.split())
    expression = re.sub(r"\b\d+'\(", "(", expression)
    while expression.startswith("(") and expression.endswith(")"):
        depth = 0
        for i, char in enumerate(expression):
            depth += (char == "(") - (char == ")")
            if depth == 0 and i != len(expression) - 1:
                break
        else:
            expression = expression[1:-1].strip()
            continue
        break
    depth = 0
    question = None
    nested = 0
    for i, char in enumerate(expression):
        depth += (char == "(") - (char == ")")
        if depth:
            continue
        if char == "?":
            if question is None:
                question = i
            else:
                nested += 1
        elif char == ":" and question is not None:
            if nested:
                nested -= 1
            else:
                branch = expression[question + 1:i] if integer(expression[:question], lookup) \
                    else expression[i + 1:]
                return integer(branch, lookup)
    # Resolve ternaries nested inside arithmetic or function arguments first.
    stack = []
    for i, char in enumerate(expression):
        if char == "(":
            stack.append(i)
        elif char == ")":
            start = stack.pop()
            if "?" in expression[start + 1:i]:
                value = integer(expression[start + 1:i], lookup)
                return integer(expression[:start] + str(value) + expression[i + 1:], lookup)
    expression = re.sub(r"(\d+)'([bhd])([0-9a-fA-F_]+)",
        lambda m: str(int(m[3].replace("_", ""), {"b": 2, "h": 16, "d": 10}[m[2]])),
        expression)
    expression = expression.replace("$clog2", "clog2").replace("===", "==")
    expression = expression.replace("!==", "!=").replace("&&", " and ").replace("||", " or ")

    def visit(node):
        match node:
            case ast.Constant(value=int(value)):
                return value
            case ast.Name(id=name):
                return lookup(name)
            case ast.Call(func=ast.Name(id="clog2"), args=[arg], keywords=[]):
                return max(0, (visit(arg) - 1).bit_length())
            case ast.BinOp(left=left, op=op, right=right):
                a, b = visit(left), visit(right)
                match op:
                    case ast.Add(): return a + b
                    case ast.Sub(): return a - b
                    case ast.Mult(): return a * b
                    case ast.Div() | ast.FloorDiv(): return a // b
                    case ast.Mod(): return a % b
                    case ast.LShift(): return a << b
                    case ast.RShift(): return a >> b
                    case ast.BitOr(): return a | b
                    case ast.BitAnd(): return a & b
            case ast.BoolOp(op=ast.And(), values=values):
                return int(all(visit(value) for value in values))
            case ast.BoolOp(op=ast.Or(), values=values):
                return int(any(visit(value) for value in values))
            case ast.Compare(left=left, ops=[op], comparators=[right]):
                a, b = visit(left), visit(right)
                match op:
                    case ast.Eq(): return int(a == b)
                    case ast.NotEq(): return int(a != b)
                    case ast.Gt(): return int(a > b)
                    case ast.GtE(): return int(a >= b)
                    case ast.Lt(): return int(a < b)
                    case ast.LtE(): return int(a <= b)
            case ast.UnaryOp(op=ast.USub(), operand=value):
                return -visit(value)
        raise ValueError(f"Unsupported native width expression: {expression}")

    return visit(ast.parse(expression, mode="eval").body)


@lru_cache(maxsize=128)
def declarations(module):
    source = (RTL / f"{module}.sv").read_text()
    if ") (" in source:
        header, interface = source.split(") (", 1)
    else:
        header, interface = re.split(r"\bmodule\s+\w+\s*\(", source, maxsplit=1)
    header = re.sub(r"//[^\n]*", "", header)
    expressions = {}
    for match in re.finditer(
            r"\b(?:localparam|parameter)\s+(?:(?:int|bit|logic(?:\s*\[[^]]+\])?)\s+)?"
            r"(\w+)\s*=\s*(.*?)(?=,\s*(?:localparam|parameter)\b|$)", header, re.S):
        expressions[match[1]] = match[2].strip().rstrip(",").strip()
    ports = re.findall(r"\b(input|output)\s+(?:wire|logic)\s*"
                       r"(?:\[([^\]]+)\]\s*)?(\w+)", interface.split(");", 1)[0])
    return expressions, ports


def defaults(kind):
    """Literal public defaults come from production RTL, not verification files."""
    module = f"mosaic_blocks/{kind.lower()}"
    expressions, _ = declarations(module)
    header = (RTL / f"{module}.sv").read_text().split(") (", 1)[0]
    names = set(re.findall(r"\bparameter\s+(\w+)\s*=", header))
    values = {name: int(value) for name, value in expressions.items()
              if name in names and value.isdecimal()}
    for name in names:
        if name.startswith("ENABLE_"):
            values[name] = integer(expressions[name], values.__getitem__)
    return values


def ports(module, parameters):
    expressions, interface = declarations(module)
    values = dict(parameters)

    def lookup(name):
        if name not in values:
            if name.endswith(("_VALID", "PARAMETERS_VALID")):
                values[name] = 1
            else:
                values[name] = integer(expressions[name], lookup)
        return values[name]

    result = {}
    for direction, extent, name in interface:
        if extent:
            extent = extent.replace("local_switch_pkg::ERROR_CODE_WIDTH", "3")
            high, low = extent.split(":")
            width = integer(high, lookup) - integer(low, lookup) + 1
        else:
            width = 1
        if width < 1:
            raise ValueError(f"Invalid native port width: {module}.{name}")
        result[name] = direction, width
    return result
