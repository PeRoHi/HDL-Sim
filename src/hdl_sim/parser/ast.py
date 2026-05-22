"""Abstract syntax tree nodes for the supported Verilog subset."""

from __future__ import annotations

from dataclasses import dataclass, field
from enum import Enum, auto


class DeclKind(Enum):
    REG = auto()
    WIRE = auto()


class EdgeKind(Enum):
    POSEDGE = auto()
    NEGEDGE = auto()


@dataclass(frozen=True, slots=True)
class SourceLocation:
    line: int | None = None
    column: int | None = None


@dataclass(frozen=True, slots=True)
class Range:
    msb: int
    lsb: int

    @property
    def width(self) -> int:
        return abs(self.msb - self.lsb) + 1


@dataclass(frozen=True, slots=True)
class Declaration:
    kind: DeclKind
    name: str
    range: Range | None = None
    loc: SourceLocation | None = None


class Expr:
    pass


@dataclass(frozen=True, slots=True)
class IntLiteral(Expr):
    value: int
    width: int | None = None


@dataclass(frozen=True, slots=True)
class IdentRef(Expr):
    name: str


@dataclass(frozen=True, slots=True)
class UnaryExpr(Expr):
    op: str
    operand: Expr


@dataclass(frozen=True, slots=True)
class BinaryExpr(Expr):
    op: str
    left: Expr
    right: Expr


@dataclass(frozen=True, slots=True)
class ConcatExpr(Expr):
    parts: tuple[Expr, ...]


class Stmt:
    pass


@dataclass(frozen=True, slots=True)
class Block(Stmt):
    statements: tuple[Stmt, ...]


@dataclass(frozen=True, slots=True)
class BlockingAssign(Stmt):
    target: str
    expr: Expr


@dataclass(frozen=True, slots=True)
class NonBlockingAssign(Stmt):
    target: str
    expr: Expr


@dataclass(frozen=True, slots=True)
class DelayControl(Stmt):
    delay: int
    body: Stmt


@dataclass(frozen=True, slots=True)
class Forever(Stmt):
    body: Stmt


@dataclass(frozen=True, slots=True)
class Repeat(Stmt):
    count: int
    body: Stmt


@dataclass(frozen=True, slots=True)
class IfStmt(Stmt):
    condition: Expr
    then_branch: Stmt
    else_branch: Stmt | None = None


@dataclass(frozen=True, slots=True)
class EventControl(Stmt):
    events: tuple[Expr, ...]
    body: Stmt


@dataclass(frozen=True, slots=True)
class AssignStmt:
    target: str
    expr: Expr


@dataclass(frozen=True, slots=True)
class InitialBlock:
    body: Stmt


@dataclass(frozen=True, slots=True)
class AlwaysBlock:
    sensitivity: tuple[tuple[EdgeKind | None, str], ...] | None
    body: Stmt


@dataclass(frozen=True, slots=True)
class ContinuousAssign:
    target: str
    expr: Expr


@dataclass(frozen=True, slots=True)
class Module:
    name: str
    declarations: tuple[Declaration, ...]
    continuous_assigns: tuple[ContinuousAssign, ...] = ()
    initial_blocks: tuple[InitialBlock, ...] = ()
    always_blocks: tuple[AlwaysBlock, ...] = ()
    loc: SourceLocation | None = None


@dataclass(frozen=True, slots=True)
class Design:
    modules: tuple[Module, ...] = field(default_factory=tuple)

    @property
    def top(self) -> Module:
        if len(self.modules) != 1:
            msg = "exactly one module is supported in this MVP"
            raise ValueError(msg)
        return self.modules[0]
