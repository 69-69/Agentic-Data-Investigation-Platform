import hashlib

import sqlglot
from sqlglot import exp
from sqlglot.optimizer.scope import Scope, traverse_scope

from agent_service.errors import ToolError

# Deliberately narrow AST language. New SQL features require security review/tests.
SAFE_NODES = {
    "Select",
    "From",
    "Table",
    "Identifier",
    "Column",
    "Star",
    "Alias",
    "Literal",
    "Where",
    "And",
    "Or",
    "Not",
    "EQ",
    "NEQ",
    "GT",
    "GTE",
    "LT",
    "LTE",
    "Is",
    "Null",
    "In",
    "Tuple",
    "Between",
    "Paren",
    "Add",
    "Sub",
    "Mul",
    "Div",
    "Neg",
    "Count",
    "Sum",
    "Avg",
    "Min",
    "Max",
    "Case",
    "If",
    "Boolean",
    "Group",
    "Order",
    "Ordered",
    "Distinct",
    "Limit",
    "Join",
    "TableAlias",
    "With",
    "CTE",
    "Subquery",
    "Union",
}


class SqlGuard:
    def __init__(self, tables: set[str], default_limit=100, maximum=500):
        self.tables = frozenset(tables)
        self.default_limit = default_limit
        self.maximum = maximum

    def parse(self, sql: str):
        if not isinstance(sql, str) or not sql.strip() or len(sql) > 16000:
            raise ToolError("SQL_REJECTED")
        try:
            if any(token.comments for token in sqlglot.tokenize(sql, read="postgres")):
                raise ValueError("comments")
            parsed = sqlglot.parse(sql, read="postgres")
            if len(parsed) != 1 or not isinstance(parsed[0], (exp.Select, exp.Union)):
                raise ValueError("statement")
            tree = parsed[0]
            for node in tree.walk():
                if type(node).__name__ not in SAFE_NODES:
                    raise ValueError("unsupported syntax")
                if isinstance(node, exp.With) and node.args.get("recursive"):
                    raise ValueError("recursive")
                if isinstance(node, exp.Limit):
                    value = node.expression
                    if not isinstance(value, exp.Literal) or value.is_string or not value.this.isdigit():
                        raise ValueError("limit")
                if isinstance(node, exp.Column) and len(node.parts) > 2:
                    raise ValueError("qualified column")
            scopes = traverse_scope(tree)
            if not scopes:
                raise ValueError("scope")
            for scope in scopes:
                for _, source in scope.selected_sources.values():
                    if isinstance(source, Scope):
                        continue  # A structurally validated CTE/subquery, not a real table.
                    if not isinstance(source, exp.Table) or source.catalog or source.db != "analytics":
                        raise ValueError("relation")
                    if f"{source.db}.{source.name}" not in self.tables:
                        raise ValueError("allowlist")
            # Also catches unused CTE base tables through traversal of each scope.
            return tree
        except ToolError:
            raise
        except Exception:
            raise ToolError("SQL_REJECTED") from None

    def prepare(self, sql: str, dialect="postgres") -> tuple[str, int]:
        tree = self.parse(sql)
        requested = tree.args.get("limit")
        cap = min(int(requested.expression.this), self.maximum) if requested else self.default_limit
        inner = tree.sql(dialect=dialect, comments=False)
        # Preserve model LIMIT semantics inside, with an external unbypassable fetch cap.
        return f"SELECT * FROM ({inner}) AS bounded_result LIMIT {cap + 1}", cap

    def bind(self, sql: str, dialect="postgres"):
        """Bind data literals after validation; identifiers and LIMIT remain AST-controlled."""
        bounded, cap = self.prepare(sql, dialect=dialect)
        tree = sqlglot.parse_one(bounded, read=dialect)
        parameters = {}
        names = {}
        for node in list(tree.walk()):
            if isinstance(node, exp.Literal) and not isinstance(node.parent, exp.Limit):
                # Numeric ORDER BY/GROUP BY ordinals are syntax, not data values.
                if not node.is_string:
                    continue
                name = names.setdefault(node.this, f"p{len(parameters)}")
                parameters[name] = node.this
                node.replace(exp.Placeholder(this=name))
        return tree.sql(dialect=dialect), parameters, cap, bounded

    def audit(self, sql: str) -> dict:
        result = {"sqlHash": hashlib.sha256(sql.encode()).hexdigest()}
        try:
            tree = self.parse(sql).copy()
            for node in tree.walk():
                if isinstance(node, exp.Literal):
                    node.set("this", "0" if not node.is_string else "[redacted]")
                elif isinstance(node, exp.Identifier):
                    node.set("this", "identifier")
            result["sqlShape"] = tree.sql(comments=False)
        except ToolError:
            result["sqlShape"] = "[rejected]"
        return result
